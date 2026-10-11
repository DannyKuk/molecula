from typing import Any
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from molecula.sources.errors import SourceFormatError, SourceNotFound
from molecula.sources.http import SourceClient

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPERTY_FIELDS = (
    "SMILES",
    "InChIKey",
    "MolecularFormula",
    "MolecularWeight",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
    "RotatableBondCount",
    "HeavyAtomCount",
)


class CompoundProperties(BaseModel):
    model_config = ConfigDict(frozen=True)

    cid: int = Field(alias="CID")
    smiles: str = Field(alias="SMILES")
    inchikey: str = Field(alias="InChIKey")
    formula: str = Field(alias="MolecularFormula")
    molecular_weight: float = Field(alias="MolecularWeight")
    xlogp: float | None = Field(None, alias="XLogP")
    tpsa: float | None = Field(None, alias="TPSA")
    hbd: int = Field(alias="HBondDonorCount")
    hba: int = Field(alias="HBondAcceptorCount")
    rotatable_bonds: int = Field(alias="RotatableBondCount")
    heavy_atoms: int = Field(alias="HeavyAtomCount")

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_smiles(cls, data: Any) -> Any:
        # PubChem renamed the IsomericSMILES property to SMILES; older responses carry the old key.
        if isinstance(data, dict) and "SMILES" not in data and "IsomericSMILES" in data:
            return {**data, "SMILES": data["IsomericSMILES"]}
        return data


class IdentifierList(BaseModel):
    cids: list[int] = Field(alias="CID", min_length=1)


class CidsResponse(BaseModel):
    identifiers: IdentifierList = Field(alias="IdentifierList")


class PropertyTable(BaseModel):
    rows: list[CompoundProperties] = Field(alias="Properties", min_length=1)


class PropertiesResponse(BaseModel):
    table: PropertyTable = Field(alias="PropertyTable")


class SynonymInformation(BaseModel):
    synonyms: list[str] = Field([], alias="Synonym")


class InformationList(BaseModel):
    entries: list[SynonymInformation] = Field(alias="Information", min_length=1)


class SynonymsResponse(BaseModel):
    information: InformationList = Field(alias="InformationList")


class PubChemClient:
    """PubChem PUG REST: names to CIDs, parent compounds, properties, 3D conformers, synonyms."""

    def __init__(self, http: SourceClient) -> None:
        self._http = http

    def cids_for_name(self, name: str, *, refresh: bool = False) -> list[int]:
        """CIDs PubChem matches to a name, brand or synonym. Raises SourceNotFound if none."""
        url = f"{PUG}/compound/name/{quote(name, safe='')}/cids/JSON"
        return parse(self._http.get(url, refresh=refresh), CidsResponse).identifiers.cids

    def parent_cids(self, cid: int, *, refresh: bool = False) -> list[int]:
        """The parent compound(s) of a salt or mixture; a parent compound returns itself."""
        response = self._http.get(
            f"{PUG}/compound/cid/{cid}/cids/JSON", params={"cids_type": "parent"}, refresh=refresh
        )
        return parse(response, CidsResponse).identifiers.cids

    def properties(self, cid: int, *, refresh: bool = False) -> CompoundProperties:
        response = self._http.get(
            f"{PUG}/compound/cid/{cid}/property/{','.join(PROPERTY_FIELDS)}/JSON", refresh=refresh
        )
        return parse(response, PropertiesResponse).table.rows[0]

    def conformer_sdf(self, cid: int, *, refresh: bool = False) -> str | None:
        """PubChem's 3D conformer as SDF, or None when it has none (peptides, proteins, metals)."""
        try:
            response = self._http.get(
                f"{PUG}/compound/cid/{cid}/SDF", params={"record_type": "3d"}, refresh=refresh
            )
        except SourceNotFound:
            return None
        return response.text

    def synonyms(self, cid: int, *, refresh: bool = False) -> list[str]:
        """All synonyms, most relevant first as PubChem ranks them."""
        response = self._http.get(f"{PUG}/compound/cid/{cid}/synonyms/JSON", refresh=refresh)
        return parse(response, SynonymsResponse).information.entries[0].synonyms


def parse[M: BaseModel](response: httpx2.Response, model: type[M]) -> M:
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        raise SourceFormatError(f"{response.request.url}: unexpected response shape") from error
