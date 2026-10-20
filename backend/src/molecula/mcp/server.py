import logging
from collections.abc import Sequence
from typing import Any
from weakref import WeakKeyDictionary

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import to_fastmcp
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools import Tool
from mcp.server.session import ServerSession
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent

from molecula.schemas.tools import References, ToolResult

DEFAULT_PORT = 8001

# FastMCP turns its DNS rebinding protection off for any host but localhost, and Docker binds
# 0.0.0.0. The endpoint has no auth (#42), so it answers only requests addressed to localhost.
LOCALHOST_ONLY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
)


type SessionReferences = WeakKeyDictionary[ServerSession, References]


def build_server(
    tools: Sequence[BaseTool],
    *,
    number_sources: bool = False,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
) -> FastMCP:
    """The agent's tools as an MCP server: each tool's docstring is its description and its
    argument model its input schema. A result comes back as the JSON the agent reads; a drug
    Molecula doesn't know is a result like any other, and arguments that fail the schema or a
    tool that fails come back as an error result, not a protocol error.

    With `number_sources`, for clients outside the backend (#299), each result's `ref`s are
    numbered per MCP session the way the chat numbers them per answer, and its sources also
    come as `structuredContent`. The chat numbers its own, so it serves the tools without.

    `host` and `port` are where `run("streamable-http")` listens.
    """
    references: SessionReferences = WeakKeyDictionary()
    served = [
        numbering_sources(tool, references) if number_sources else to_fastmcp(tool)
        for tool in tools
    ]
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    server = FastMCP(
        "molecula",
        tools=served,
        host=host,
        port=port,
        transport_security=LOCALHOST_ONLY,
    )
    # FastMCP's constructor gives the root logger a handler of its own, which printed each of
    # the backend's log lines a second time.
    root.handlers[:] = handlers
    root.setLevel(level)
    return server


def numbering_sources(tool: BaseTool, references: SessionReferences) -> Tool:
    """`tool` served with its result renumbered by the calling session's `References` and its
    sources in `structuredContent`, next to the result the model reads."""

    async def call(ctx: Context, **arguments: Any) -> CallToolResult:
        message: ToolMessage = await tool.ainvoke(
            {"type": "tool_call", "id": ctx.request_id, "name": tool.name, "args": arguments}
        )
        if not isinstance(message.artifact, ToolResult):
            return CallToolResult(content=[TextContent(type="text", text=message.text)])
        session_references = references.setdefault(ctx.session, References())
        result = message.artifact.renumbered(session_references.ref_of)
        sources = [source.model_dump(mode="json") for source in result.sources()]
        return CallToolResult(
            content=[TextContent(type="text", text=result.model_dump_json())],
            structuredContent={**result.model_dump(mode="json"), "sources": sources},
        )

    return to_fastmcp(tool).model_copy(update={"fn": call, "context_kwarg": "ctx"})
