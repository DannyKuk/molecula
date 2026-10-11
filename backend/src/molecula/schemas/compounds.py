from typing import Literal

from pydantic import BaseModel, ConfigDict

type ConformerSource = Literal["pubchem", "rdkit"]


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
