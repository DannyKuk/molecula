from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from molecula.sources.http import SourceClient
from molecula.sources.parsing import parse

EBI = "https://www.ebi.ac.uk"
API = f"{EBI}/chembl/api/data"
MOLECULE_FIELDS = "molecule_chembl_id,pref_name,molecule_hierarchy"
CONNECTIVITY_BLOCK_LENGTH = 14


class MoleculeHierarchy(BaseModel):
    parent_chembl_id: str | None


class Molecule(BaseModel):
    model_config = ConfigDict(frozen=True)

    chembl_id: str = Field(alias="molecule_chembl_id")
    pref_name: str | None
    hierarchy: MoleculeHierarchy | None = Field(alias="molecule_hierarchy")

    @property
    def parent_chembl_id(self) -> str:
        """The parent (salt-free) molecule; a record without a hierarchy is its own parent."""
        if self.hierarchy and self.hierarchy.parent_chembl_id:
            return self.hierarchy.parent_chembl_id
        return self.chembl_id


class Mechanism(BaseModel):
    model_config = ConfigDict(frozen=True)

    molecule_chembl_id: str
    mechanism_of_action: str
    action_type: str | None
    target_chembl_id: str | None


class ComponentSynonym(BaseModel):
    model_config = ConfigDict(frozen=True)

    synonym: str = Field(alias="component_synonym")
    syn_type: str


class TargetComponent(BaseModel):
    model_config = ConfigDict(frozen=True)

    accession: str | None
    description: str | None = Field(alias="component_description")
    synonyms: list[ComponentSynonym] = Field([], alias="target_component_synonyms")

    @property
    def gene_symbol(self) -> str | None:
        return next((s.synonym for s in self.synonyms if s.syn_type == "GENE_SYMBOL"), None)


class Target(BaseModel):
    model_config = ConfigDict(frozen=True)

    chembl_id: str = Field(alias="target_chembl_id")
    pref_name: str
    target_type: str
    organism: str | None
    components: list[TargetComponent] = Field(alias="target_components")


class PageMeta(BaseModel):
    next: str | None


class Page[Item: BaseModel](BaseModel):
    items: list[Item] = Field(validation_alias=AliasChoices("molecules", "mechanisms"))
    page_meta: PageMeta


class ChemblClient:
    """ChEMBL REST API: InChIKey to molecule, a parent's mechanisms, and their targets."""

    def __init__(self, http: SourceClient) -> None:
        self._http = http

    def molecules_for_inchikey(self, inchikey: str, *, refresh: bool = False) -> list[Molecule]:
        """Molecules with exactly this standard InChIKey; empty if none."""
        return self._molecules(
            {"molecule_structures__standard_inchi_key": inchikey}, refresh=refresh
        )

    def molecules_for_connectivity(self, inchikey: str, *, refresh: bool = False) -> list[Molecule]:
        """Molecules sharing the InChIKey's connectivity block (the first 14 characters, which
        leave out stereo); empty if none."""
        block = inchikey[:CONNECTIVITY_BLOCK_LENGTH]
        return self._molecules(
            {"molecule_structures__standard_inchi_key__startswith": block}, refresh=refresh
        )

    def molecules_named(self, name: str, *, refresh: bool = False) -> list[Molecule]:
        """Molecules whose preferred name is `name`, ignoring case; empty if none.

        Finds drugs whose structure ChEMBL draws differently, such as another tautomer.
        """
        return self._molecules({"pref_name__iexact": name}, refresh=refresh)

    def mechanisms(self, parent_chembl_id: str, *, refresh: bool = False) -> list[Mechanism]:
        """Every mechanism of a parent molecule and its salts; empty if ChEMBL lists none.

        Mechanisms are recorded on the salt form (imatinib mesylate, not imatinib), so this
        filters on the parent ID rather than the molecule ID.
        """
        return self._all_pages(
            f"{API}/mechanism.json",
            {"parent_molecule_chembl_id": parent_chembl_id},
            Page[Mechanism],
            refresh=refresh,
        )

    def target(self, target_chembl_id: str, *, refresh: bool = False) -> Target:
        response = self._http.get(f"{API}/target/{target_chembl_id}.json", refresh=refresh)
        return parse(response, Target)

    def _molecules(self, filters: dict[str, str], *, refresh: bool) -> list[Molecule]:
        return self._all_pages(
            f"{API}/molecule.json",
            {**filters, "only": MOLECULE_FIELDS},
            Page[Molecule],
            refresh=refresh,
        )

    def _all_pages[Item: BaseModel](
        self, url: str, params: dict[str, str], page_model: type[Page[Item]], *, refresh: bool
    ) -> list[Item]:
        page = parse(self._http.get(url, params=params, refresh=refresh), page_model)
        items = list(page.items)
        while page.page_meta.next:
            # `next` is a path on the same host that already carries the filters and offset.
            response = self._http.get(f"{EBI}{page.page_meta.next}", refresh=refresh)
            page = parse(response, page_model)
            items.extend(page.items)
        return items
