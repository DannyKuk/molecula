from typing import Any

from langchain_core.tools import StructuredTool

from molecula.schemas.tools import CompareDrugsArgs, DrugComparison
from molecula.services.compounds import CompoundService
from molecula.tools.base import build_tool
from molecula.tools.get_properties import drug_properties


def compare_drugs_tool(compounds: CompoundService) -> StructuredTool:
    def compare_drugs(drugs: list[str]) -> DrugComparison:
        """Put the chemical properties of 2 to 4 drugs side by side, as PubChem reports them.

        Each entry of `drugs` can be a generic name, a brand, a non-US or German name or a
        salt name; each is resolved to the stored drug first.

        Returns `drugs` in the order asked. A supported drug has `status: "found"` and its
        `compound`: CID, generic name, molecular formula, molecular weight (g/mol), XLogP,
        topological polar surface area (Å²), hydrogen bond donors and acceptors, rotatable
        bonds, heavy atoms, and `source_url`, the PubChem page to cite. A drug that isn't in
        Molecula's data has `status: "not_supported"` with `suggestions`: say it isn't
        supported, compare the others, and never substitute a suggestion yourself.
        """
        return DrugComparison(drugs=[drug_properties(compounds, drug) for drug in drugs])

    return build_tool(compare_drugs, CompareDrugsArgs, comparing)


def comparing(args: dict[str, Any]) -> str:
    return f"Comparing {', '.join(args.get('drugs', []))}"
