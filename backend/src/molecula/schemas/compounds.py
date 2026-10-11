from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

type ConformerSource = Literal["pubchem", "rdkit"]

DRUG_NAME_PUNCTUATION = " -,()'+."
# SQLite's largest integer; a larger CID can't be looked up at all.
MAX_CID = 2**63 - 1


def check_drug_name(name: str) -> str:
    """Letters of any script (German "Acetylsalicylsäure"), digits, space and `-,()'+.`."""
    if not all(char.isalnum() or char in DRUG_NAME_PUNCTUATION for char in name):
        raise ValueError(
            "name may contain only letters, digits, spaces and the characters - , ( ) ' + ."
        )
    return name


DrugName = Annotated[
    str, StringConstraints(min_length=1, max_length=100), AfterValidator(check_drug_name)
]
Cid = Annotated[int, Field(gt=0, le=MAX_CID)]


class Compound(BaseModel):
    """A supported drug as its parent compound, with the properties PubChem reports."""

    model_config = ConfigDict(frozen=True)

    cid: int
    name: str
    inchikey: str
    smiles: str
    formula: str
    molecular_weight: float
    xlogp: float | None
    tpsa: float | None
    hbond_donors: int
    hbond_acceptors: int
    rotatable_bonds: int
    heavy_atoms: int
    has_3d: bool
    conformer_source: ConformerSource | None
    source: str
    source_url: str


class SupportedDrug(BaseModel):
    """A drug in the list of supported drugs: its scope name and aliases, no PubChem synonyms."""

    model_config = ConfigDict(frozen=True)

    cid: int
    name: str
    aliases: list[str]
    has_3d: bool


class Resolution(BaseModel):
    """Which supported drug a name refers to. `not_supported` means it isn't in the local data."""

    model_config = ConfigDict(frozen=True)

    query: str
    status: Literal["found", "not_supported"]
    compound: Compound | None = None
    matched_alias: str | None = None
    match_kind: Literal["name", "alias", "pubchem"] | None = None


class Structure(BaseModel):
    """A compound's 3D conformer as SDF."""

    model_config = ConfigDict(frozen=True)

    cid: int
    sdf: str
    conformer_source: ConformerSource
