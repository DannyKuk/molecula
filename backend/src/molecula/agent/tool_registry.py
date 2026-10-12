from langchain_core.tools import BaseTool

from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.services.compounds import CompoundService
from molecula.services.targets import TargetService
from molecula.tools.compare_drugs import compare_drugs_tool
from molecula.tools.get_properties import get_properties_tool
from molecula.tools.get_targets import get_targets_tool
from molecula.tools.resolve_drug import resolve_drug_tool
from molecula.tools.search_labels import search_labels_tool


def build_tools(
    compounds: CompoundService,
    targets: TargetService,
    extractor: FilterExtractor,
    retriever: LabelRetriever,
) -> list[BaseTool]:
    """The agent's tools over the services built at startup."""
    return [
        resolve_drug_tool(compounds),
        get_properties_tool(compounds),
        get_targets_tool(compounds, targets),
        search_labels_tool(extractor, retriever, compounds),
        compare_drugs_tool(compounds),
    ]
