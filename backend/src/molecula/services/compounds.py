from molecula.schemas.compounds import Compound, Resolution, Structure
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.structures import ConformerFiles

PUBCHEM_COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"

# Prescriptions and openFDA name the salt or hydrate ("imatinib mesylate"), the store holds the
# parent compound. Ester words like "acetate" are left out: medroxyprogesterone acetate is a
# different molecule from medroxyprogesterone.
SALT_WORDS = frozenset(
    {
        "anhydrous",
        "besilate",
        "besylate",
        "bisulfate",
        "bitartrate",
        "bromide",
        "calcium",
        "chloride",
        "citrate",
        "dihydrate",
        "dihydrochloride",
        "dimesylate",
        "disodium",
        "fumarate",
        "gluconate",
        "hbr",
        "hcl",
        "hemifumarate",
        "hemihydrate",
        "hyclate",
        "hydrate",
        "hydrobromide",
        "hydrochloride",
        "lactate",
        "magnesium",
        "malate",
        "maleate",
        "mesilate",
        "mesylate",
        "monohydrate",
        "nitrate",
        "pamoate",
        "phosphate",
        "potassium",
        "sesquihydrate",
        "sodium",
        "succinate",
        "sulfate",
        "sulphate",
        "tartrate",
        "tosylate",
        "trihydrate",
        "xinafoate",
    }
)


class CompoundService:
    """Drug names to compounds from the local store. Molecula supports exactly what is stored."""

    def __init__(self, store: CompoundStore, conformers: ConformerFiles) -> None:
        self._store = store
        self._conformers = conformers

    def resolve(self, name: str) -> Resolution:
        """The supported drug a name, brand, alias or salt name refers to, ignoring case."""
        query = " ".join(name.split())
        for candidate in name_candidates(query):
            if match := self._store.find(candidate):
                return Resolution(
                    query=query,
                    status="found",
                    compound=to_compound(match.compound),
                    matched_alias=match.synonym.alias,
                    match_kind=match.synonym.kind,
                )
        return Resolution(query=query, status="not_supported")

    def get_compound(self, cid: int) -> Compound | None:
        record = self._store.get(cid)
        return to_compound(record) if record else None

    def get_structure(self, cid: int) -> Structure | None:
        """The stored 3D conformer, or None for an unknown CID or a compound without 3D."""
        record = self._store.get(cid)
        if record is None or record.conformer_source is None:
            return None
        sdf = self._conformers.read(cid)
        if sdf is None:
            return None
        return Structure(cid=cid, sdf=sdf, conformer_source=record.conformer_source)

    def list_compounds(self) -> list[Compound]:
        """Every supported drug, by name."""
        return [to_compound(record) for record in self._store.all()]


def name_candidates(query: str) -> list[str]:
    """The name as given, then without its salt and hydrate words if any are left after that."""
    if not query:
        return []
    words = query.split()
    parent = [word for word in words if word.casefold() not in SALT_WORDS]
    if parent and len(parent) < len(words):
        return [query, " ".join(parent)]
    return [query]


def to_compound(record: CompoundRecord) -> Compound:
    return Compound(
        cid=record.cid,
        name=record.name,
        inchikey=record.inchikey,
        smiles=record.smiles,
        formula=record.formula,
        molecular_weight=record.mw,
        xlogp=record.xlogp,
        tpsa=record.tpsa,
        hbond_donors=record.hbd,
        hbond_acceptors=record.hba,
        rotatable_bonds=record.rotb,
        heavy_atoms=record.heavy_atoms,
        has_3d=record.has_3d,
        conformer_source=record.conformer_source,
        source=record.source,
        source_url=PUBCHEM_COMPOUND_URL.format(cid=record.cid),
    )
