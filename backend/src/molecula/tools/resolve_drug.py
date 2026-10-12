from langchain_core.tools import StructuredTool

from molecula.schemas.tools import DrugNotSupported, ResolvedDrug, ResolveDrugArgs
from molecula.services.compounds import CompoundService
from molecula.tools.base import build_tool, not_supported


def resolve_drug_tool(compounds: CompoundService) -> StructuredTool:
    def resolve_drug(name: str) -> ResolvedDrug | DrugNotSupported:
        """Find out which supported drug a name refers to.

        `name` can be a generic name, a brand (Gleevec, Tylenol), a non-US or German name
        (paracetamol, Ibuflam) or a salt name from a prescription (imatinib mesylate). Case
        doesn't matter.

        Returns `status: "found"` with the drug's PubChem CID, its generic `name`, the stored
        name or alias the input matched (`matched_alias`, `match_kind`) and its PubChem page as
        `source_url`. Returns `status: "not_supported"` when the drug isn't in Molecula's data:
        then say it isn't supported. `suggestions` holds up to three supported names close to
        the input; offer them to the user to pick, never answer as if one of them was meant.
        """
        resolution = compounds.resolve(name)
        if (
            resolution.compound is None
            or resolution.matched_alias is None
            or resolution.match_kind is None
        ):
            return not_supported(resolution)
        return ResolvedDrug(
            query=resolution.query,
            cid=resolution.compound.cid,
            name=resolution.compound.name,
            matched_alias=resolution.matched_alias,
            match_kind=resolution.match_kind,
            source=resolution.compound.source,
            source_url=resolution.compound.source_url,
        )

    return build_tool(resolve_drug, ResolveDrugArgs)
