from typing import Any

from langchain_core.tools import StructuredTool

from molecula.schemas.tools import DrugArgs, DrugNotSupported, DrugProperties
from molecula.services.compounds import CompoundService
from molecula.tools.base import build_tool, not_supported


def drug_properties(compounds: CompoundService, drug: str) -> DrugProperties | DrugNotSupported:
    """The properties of the supported drug a name refers to, or why there are none."""
    resolution = compounds.resolve(drug)
    match = resolution.match
    if match is None:
        return not_supported(resolution)
    return DrugProperties(query=resolution.query, compound=match.compound)


def get_properties_tool(compounds: CompoundService) -> StructuredTool:
    def get_properties(drug: str) -> DrugProperties | DrugNotSupported:
        """Look up a supported drug's chemical properties as PubChem reports them.

        `drug` can be a generic name, a brand, a non-US or German name or a salt name; it is
        resolved to the stored drug first. Pass it as the user wrote it, typos included:
        never correct a spelling yourself.

        Returns `status: "found"` with the `compound`: PubChem CID, generic name, molecular
        formula, molecular weight (g/mol), XLogP, topological polar surface area (Å²),
        hydrogen bond donors and acceptors, rotatable bonds, heavy atoms, SMILES, InChIKey,
        whether a 3D structure exists, and `source_url`, its PubChem page; and `ref`, the number
        to cite these properties with in square brackets, like `[2]`. XLogP or TPSA can be null
        when PubChem has no value. Returns `status: "not_supported"` with `suggestions` when
        Molecula doesn't know the name (it may be misspelt): say the name wasn't found and offer
        the suggestions by their `alias`, never pick one yourself.
        """
        return drug_properties(compounds, drug)

    return build_tool(get_properties, DrugArgs, getting_properties)


def getting_properties(args: dict[str, Any]) -> str:
    return f"Getting the properties of {args.get('drug', 'the drug')}"
