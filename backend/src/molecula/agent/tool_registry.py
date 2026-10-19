from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.targets import TargetService
from molecula.tools.base import PROGRESS, progress_of
from molecula.tools.compare_drugs import compare_drugs_tool
from molecula.tools.get_complex import get_complex_tool
from molecula.tools.get_properties import get_properties_tool
from molecula.tools.get_targets import get_targets_tool
from molecula.tools.resolve_drug import resolve_drug_tool
from molecula.tools.search_labels import search_labels_tool


def build_tools(
    compounds: CompoundService,
    targets: TargetService,
    complexes: ComplexService,
    extractor: FilterExtractor,
    retriever: LabelRetriever,
) -> list[BaseTool]:
    """The agent's tools over the services built at startup."""
    return [
        resolve_drug_tool(compounds),
        get_properties_tool(compounds),
        get_targets_tool(compounds, targets),
        get_complex_tool(compounds, complexes),
        search_labels_tool(extractor, retriever),
        compare_drugs_tool(compounds),
    ]


@asynccontextmanager
async def tools_over_mcp(
    server: FastMCP, local: Sequence[BaseTool]
) -> AsyncIterator[list[BaseTool]]:
    """The tools `server` lists, each called through one in-memory MCP session that stays open
    until the context ends, with the progress text of the `local` tool of the same name.

    The model reads the same JSON as from a local tool, but the result carries no typed
    artifact, so the chat's sources, retrieval trace and shared reference numbers stay empty.
    """
    progress = {tool.name: progress_of(tool) for tool in local}
    async with create_connected_server_and_client_session(server) as session:
        tools = await load_mcp_tools(session)
        yield [
            tool.model_copy(
                update={"metadata": {**(tool.metadata or {}), PROGRESS: progress.get(tool.name)}}
            )
            for tool in tools
        ]
