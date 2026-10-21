import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.tools import ToolResult
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.targets import TargetService
from molecula.tools.base import PROGRESS, progress_of, result_type_of
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

    The model reads the same JSON as from a local tool, and each result is rebuilt from the
    structured content as the local tool's typed result, so the chat's sources, retrieval
    trace and label filter usage work as with local tools (#316).
    """
    by_name = {tool.name: tool for tool in local}
    async with create_connected_server_and_client_session(server) as session:
        tools = await load_mcp_tools(session)
        yield [typed(tool, by_name.get(tool.name)) for tool in tools]


class McpSessions:
    """In-memory MCP sessions that stay open until `aclose`. Each is opened, held and closed by
    a task of its own, because an anyio context must be left by the task that entered it and a
    session opened while answering a request outlives that request."""

    def __init__(self) -> None:
        self._closing = asyncio.Event()
        self._held: list[asyncio.Task[None]] = []

    async def open(self, server: FastMCP, local: Sequence[BaseTool]) -> list[BaseTool]:
        """The tools of `server` over a new session, as `tools_over_mcp` gives them."""
        opened: asyncio.Future[list[BaseTool]] = asyncio.get_running_loop().create_future()

        async def hold() -> None:
            try:
                async with tools_over_mcp(server, local) as tools:
                    opened.set_result(tools)
                    await self._closing.wait()
            except Exception as error:
                if opened.done():
                    raise
                opened.set_exception(error)

        self._held.append(asyncio.create_task(hold()))
        return await opened

    async def aclose(self) -> None:
        self._closing.set()
        await asyncio.gather(*self._held)


def typed(tool: BaseTool, local: BaseTool | None) -> BaseTool:
    """`tool` with the progress text of `local`, returning its result as `local`'s typed result."""
    assert isinstance(tool, StructuredTool) and tool.coroutine is not None
    coroutine = tool.coroutine
    result_type = result_type_of(local) if local is not None else None

    async def call(**arguments: Any) -> tuple[Any, ToolResult | None]:
        content, artifact = await coroutine(**arguments)
        if result_type is None or artifact is None:
            return content, None
        return content, result_type.validate_python(artifact["structured_content"])

    progress = progress_of(local) if local is not None else None
    return tool.model_copy(
        update={
            "coroutine": call,
            "metadata": {**(tool.metadata or {}), PROGRESS: progress},
        }
    )
