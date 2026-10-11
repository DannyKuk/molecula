from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Response

from molecula.api import examples
from molecula.api.dependencies import CompoundServiceDep, TargetServiceDep
from molecula.schemas.compounds import Cid, Compound, DrugName, Resolution, SupportedDrug
from molecula.schemas.errors import ErrorDetail
from molecula.schemas.targets import DrugTargets

SDF_MEDIA_TYPE = "chemical/x-mdl-sdfile"

router = APIRouter(prefix="/drugs", tags=["drugs"])

CidParam = Annotated[Cid, Path(description="PubChem CID of a supported drug.", examples=[5291])]


class SdfResponse(Response):
    media_type = SDF_MEDIA_TYPE


def json_example(example: Any) -> dict[str, Any]:
    return {"content": {"application/json": {"example": example}}}


def not_supported(cid: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"CID {cid} is not a supported drug.")


NOT_SUPPORTED_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorDetail,
        "description": "The drug isn't supported.",
        **json_example({"detail": "CID 1 is not a supported drug."}),
    }
}


@router.get(
    "",
    responses={
        200: json_example([drug.model_dump() for drug in examples.SUPPORTED_DRUGS]),
    },
)
def list_drugs(service: CompoundServiceDep) -> list[SupportedDrug]:
    """Every supported drug by name, with the scope aliases (brands, other generics)."""
    return service.list_drugs()


@router.get(
    "/resolve",
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "found": {"value": examples.FOUND.model_dump()},
                        "not_supported": {"value": examples.NOT_SUPPORTED.model_dump()},
                    }
                }
            }
        }
    },
)
def resolve_drug(
    name: Annotated[
        DrugName,
        Query(description="A generic name, brand, alias or salt name.", examples=["Gleevec"]),
    ],
    service: CompoundServiceDep,
) -> Resolution:
    """The supported drug a name refers to. A name outside the store is `not_supported`."""
    return service.resolve(name)


@router.get(
    "/{cid}",
    responses={200: json_example(examples.IMATINIB.model_dump()), **NOT_SUPPORTED_RESPONSE},
)
def get_drug(cid: CidParam, service: CompoundServiceDep) -> Compound:
    """A supported drug with the properties PubChem reports."""
    compound = service.get_compound(cid)
    if compound is None:
        raise not_supported(cid)
    return compound


@router.get(
    "/{cid}/structure",
    response_class=SdfResponse,
    responses={
        200: {
            "description": "The 3D conformer as SDF.",
            "content": {SDF_MEDIA_TYPE: {"example": examples.SDF}},
        },
        404: {
            "model": ErrorDetail,
            "description": "The drug isn't supported or has no 3D structure.",
            **json_example({"detail": "semaglutide has no 3D structure."}),
        },
    },
)
def get_drug_structure(cid: CidParam, service: CompoundServiceDep) -> SdfResponse:
    """The drug's 3D conformer as an SDF file, from PubChem or computed with RDKit."""
    compound = service.get_compound(cid)
    if compound is None:
        raise not_supported(cid)
    structure = service.get_structure(cid)
    if structure is None:
        raise HTTPException(status_code=404, detail=f"{compound.name} has no 3D structure.")
    return SdfResponse(content=structure.sdf)


@router.get(
    "/{cid}/targets",
    responses={200: json_example(examples.IMATINIB_TARGETS.model_dump()), **NOT_SUPPORTED_RESPONSE},
)
def get_drug_targets(cid: CidParam, service: TargetServiceDep) -> DrugTargets:
    """The targets the drug acts on, with ChEMBL's mechanism for each. A supported drug that
    ChEMBL lists no mechanism for has an empty list."""
    targets = service.get_targets(cid)
    if targets is None:
        raise not_supported(cid)
    return targets
