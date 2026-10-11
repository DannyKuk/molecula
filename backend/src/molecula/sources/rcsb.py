from typing import Annotated, Any
from urllib.parse import quote

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from molecula.sources.http import SourceClient
from molecula.sources.parsing import parse

SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
CHEM_COMP = "https://data.rcsb.org/rest/v1/core/chemcomp"
GRAPHQL = "https://data.rcsb.org/graphql"
CONNECTIVITY_BLOCK = 14
ENTRY_BATCH = 200
ENTRY_DETAILS = """query ($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    struct { title }
    rcsb_entry_info { resolution_combined }
    polymer_entities {
      rcsb_polymer_entity_container_identifiers { auth_asym_ids }
      rcsb_entity_source_organism {
        scientific_name ncbi_taxonomy_id rcsb_gene_name { value } taxonomy_lineage { name }
      }
      uniprots { rcsb_uniprot_protein { gene { name { value type } } } }
    }
  }
}"""


def empty_if_none(value: Any) -> Any:
    return [] if value is None else value


# The data API answers null rather than [] for missing lists.
type OptionalList[T] = Annotated[list[T], BeforeValidator(empty_if_none)]


class SearchHit(BaseModel):
    identifier: str


class SearchResult(BaseModel):
    hits: list[SearchHit] = Field(alias="result_set")


class ChemCompDescriptor(BaseModel):
    inchikey: str | None = Field(None, alias="InChIKey")


class ChemComp(BaseModel):
    descriptor: ChemCompDescriptor | None = Field(None, alias="rcsb_chem_comp_descriptor")


class Source(BaseModel):
    """One source organism of an entity, with the depositor's gene names for its part.

    `lineage` holds the NCBI taxonomy names from the root down to the organism, synonyms included.
    """

    model_config = ConfigDict(frozen=True)

    organism: str | None = None
    taxonomy_id: int | None = None
    genes: list[str] = []
    lineage: list[str] = []

    def belongs_to(self, taxon: str) -> bool:
        """Whether `taxon` is one of the lineage names, ignoring case."""
        return taxon.casefold() in {name.casefold() for name in self.lineage}


class Entity(BaseModel):
    """A polymer entity: one protein (or nucleic acid) chain type in an entry.

    A fusion construct has one source per part: 6WV3 is GFP, human VKORC1 and GFP again.
    """

    model_config = ConfigDict(frozen=True)

    chains: list[str]
    sources: list[Source]
    genes: list[str]

    def source_for(self, upper_gene_names: set[str]) -> Source:
        """The first source whose depositor gene names include one of the genes.

        When no source names them (the match came from UniProt alone), the first source stands in.
        """
        carrying = (source for source in self.sources if has_gene(source.genes, upper_gene_names))
        return next(carrying, self.sources[0] if self.sources else Source())


class Entry(BaseModel):
    model_config = ConfigDict(frozen=True)

    pdb_id: str
    title: str | None
    resolution: float | None
    entities: list[Entity]


class ComplexCandidate(BaseModel):
    """An entry with the ligand bound: the chains and source organism that carry the target gene."""

    model_config = ConfigDict(frozen=True)

    pdb_id: str
    title: str | None
    resolution: float | None
    organism: str | None
    taxonomy_id: int | None
    chains: list[str]


class GeneName(BaseModel):
    value: str


class TaxonName(BaseModel):
    name: str


class SourceOrganism(BaseModel):
    scientific_name: str | None = None
    ncbi_taxonomy_id: int | None = None
    rcsb_gene_name: OptionalList[GeneName] = []
    taxonomy_lineage: OptionalList[TaxonName] = []

    def to_source(self) -> Source:
        return Source(
            organism=self.scientific_name,
            taxonomy_id=self.ncbi_taxonomy_id,
            genes=[gene.value for gene in self.rcsb_gene_name],
            lineage=[taxon.name for taxon in self.taxonomy_lineage],
        )


class UniProtName(BaseModel):
    value: str
    type: str


class UniProtGene(BaseModel):
    name: OptionalList[UniProtName] = []


class UniProtProtein(BaseModel):
    gene: OptionalList[UniProtGene] = []


class UniProt(BaseModel):
    protein: UniProtProtein | None = Field(None, alias="rcsb_uniprot_protein")


class EntityIdentifiers(BaseModel):
    auth_asym_ids: OptionalList[str] = []


class PolymerEntity(BaseModel):
    identifiers: EntityIdentifiers = Field(alias="rcsb_polymer_entity_container_identifiers")
    organisms: OptionalList[SourceOrganism] = Field([], alias="rcsb_entity_source_organism")
    uniprots: OptionalList[UniProt] = []

    def to_entity(self) -> Entity:
        return Entity(
            chains=self.identifiers.auth_asym_ids,
            sources=[organism.to_source() for organism in self.organisms],
            genes=self.gene_names(),
        )

    def gene_names(self) -> list[str]:
        """The depositor's gene names plus UniProt's primary ones, which fill the many gaps."""
        names = [gene.value for organism in self.organisms for gene in organism.rcsb_gene_name]
        names += [
            name.value
            for uniprot in self.uniprots
            if uniprot.protein
            for gene in uniprot.protein.gene
            for name in gene.name
            if name.type == "PRIMARY"
        ]
        return list(dict.fromkeys(names))


class Struct(BaseModel):
    title: str | None = None


class EntryInfo(BaseModel):
    resolution_combined: OptionalList[float] = []


class EntryDetails(BaseModel):
    rcsb_id: str
    struct: Struct | None = None
    info: EntryInfo | None = Field(None, alias="rcsb_entry_info")
    polymer_entities: OptionalList[PolymerEntity] = []

    def to_entry(self) -> Entry:
        resolutions = self.info.resolution_combined if self.info else []
        return Entry(
            pdb_id=self.rcsb_id,
            title=self.struct.title if self.struct else None,
            resolution=min(resolutions, default=None),
            entities=[entity.to_entity() for entity in self.polymer_entities],
        )


class EntriesData(BaseModel):
    entries: OptionalList[EntryDetails] = []


class EntriesResponse(BaseModel):
    data: EntriesData


class RcsbClient:
    """RCSB PDB: a compound's ligand codes and the entries that show a ligand bound to a target."""

    def __init__(self, http: SourceClient) -> None:
        self._http = http

    def ligand_codes(self, inchikey: str, *, refresh: bool = False) -> list[str]:
        """Ligand codes whose InChIKey matches exactly, stereo and protonation included."""
        query = terminal(
            "text_chem",
            attribute="rcsb_chem_comp_descriptor.InChIKey",
            operator="exact_match",
            value=inchikey,
        )
        return self._search(query, "mol_definition", refresh)

    def ligand_codes_by_connectivity(
        self, smiles: str, inchikey: str, *, refresh: bool = False
    ) -> list[str]:
        """Ligand codes for the same skeleton when the exact InChIKey has no match.

        A stereo-relaxed graph search on the SMILES finds the candidates; a candidate is kept when
        its InChIKey shares the connectivity block (the first 14 characters) with `inchikey`.
        """
        query = terminal(
            "chemical",
            type="descriptor",
            descriptor_type="SMILES",
            value=smiles,
            match_type="graph-relaxed-stereo",
        )
        block = connectivity_block(inchikey)
        return [
            code
            for code in self._search(query, "mol_definition", refresh)
            if (key := self.ligand_inchikey(code, refresh=refresh))
            and connectivity_block(key) == block
        ]

    def ligand_inchikey(self, code: str, *, refresh: bool = False) -> str | None:
        response = self._http.get(f"{CHEM_COMP}/{quote(code, safe='')}", refresh=refresh)
        descriptor = parse(response, ChemComp).descriptor
        return descriptor.inchikey if descriptor else None

    def entries_with_ligand(self, code: str, *, refresh: bool = False) -> list[str]:
        query = terminal(
            "text",
            attribute="rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
            operator="exact_match",
            value=code,
        )
        return self._search(query, "entry", refresh)

    def entries(self, pdb_ids: list[str], *, refresh: bool = False) -> list[Entry]:
        """Title, resolution and polymer entities of each entry, in one GraphQL request per batch.

        Unknown IDs are left out.
        """
        ids = sorted(set(pdb_ids))
        entries: list[Entry] = []
        for start in range(0, len(ids), ENTRY_BATCH):
            payload = {
                "query": ENTRY_DETAILS,
                "variables": {"ids": ids[start : start + ENTRY_BATCH]},
            }
            response = self._http.post_json(GRAPHQL, payload, refresh=refresh)
            entries += [
                details.to_entry() for details in parse(response, EntriesResponse).data.entries
            ]
        return entries

    def complexes(
        self,
        ligand_code: str,
        gene_names: list[str],
        *,
        taxon: str | None = None,
        refresh: bool = False,
    ) -> list[ComplexCandidate]:
        """Entries with the ligand and a polymer entity from one of the genes, in any organism.

        Gene names match case-insensitively (human ABL1, mouse Abl1). They are matched here rather
        than in the search because the only searchable gene field is the depositor's, which many
        entries leave empty (1IEP), while UniProt's gene names are only in the data API.

        With a `taxon`, the source that carries the gene must have it in its lineage: viral gene
        names such as `pol` are shared by HIV-1 and foamy virus.
        """
        wanted = {name.upper() for name in gene_names}
        entry_ids = self.entries_with_ligand(ligand_code, refresh=refresh)
        return [
            candidate(entry, target, target.source_for(wanted))
            for entry in self.entries(entry_ids, refresh=refresh)
            if (target := entity_with_gene(entry, wanted, taxon))
        ]

    def _search(self, query: dict[str, Any], return_type: str, refresh: bool) -> list[str]:
        payload = {
            "query": query,
            "return_type": return_type,
            "request_options": {"return_all_hits": True},
        }
        response = self._http.post_json(SEARCH, payload, refresh=refresh)
        # The search API answers "no hits" with 204 and an empty body.
        if response.status_code == 204:
            return []
        return [hit.identifier for hit in parse(response, SearchResult).hits]


def terminal(service: str, **parameters: str) -> dict[str, Any]:
    return {"type": "terminal", "service": service, "parameters": parameters}


def connectivity_block(inchikey: str) -> str:
    return inchikey[:CONNECTIVITY_BLOCK]


def has_gene(genes: list[str], upper_gene_names: set[str]) -> bool:
    return any(gene.upper() in upper_gene_names for gene in genes)


def entity_with_gene(
    entry: Entry, upper_gene_names: set[str], taxon: str | None = None
) -> Entity | None:
    return next(
        (
            entity
            for entity in entry.entities
            if has_gene(entity.genes, upper_gene_names)
            and (taxon is None or entity.source_for(upper_gene_names).belongs_to(taxon))
        ),
        None,
    )


def candidate(entry: Entry, target: Entity, source: Source) -> ComplexCandidate:
    return ComplexCandidate(
        pdb_id=entry.pdb_id,
        title=entry.title,
        resolution=entry.resolution,
        organism=source.organism,
        taxonomy_id=source.taxonomy_id,
        chains=target.chains,
    )
