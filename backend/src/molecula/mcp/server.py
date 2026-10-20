import logging
from collections.abc import Sequence

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import to_fastmcp
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

DEFAULT_PORT = 8001

# FastMCP turns its DNS rebinding protection off for any host but localhost, and Docker binds
# 0.0.0.0. The endpoint has no auth (#42), so it answers only requests addressed to localhost.
LOCALHOST_ONLY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
)


def build_server(
    tools: Sequence[BaseTool], *, host: str = "127.0.0.1", port: int = DEFAULT_PORT
) -> FastMCP:
    """The agent's tools as an MCP server: each tool's docstring is its description and its
    argument model its input schema. A result comes back as the JSON the agent reads; a drug
    Molecula doesn't know is a result like any other, and arguments that fail the schema or a
    tool that fails come back as an error result, not a protocol error.

    `host` and `port` are where `run("streamable-http")` listens.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    server = FastMCP(
        "molecula",
        tools=[to_fastmcp(tool) for tool in tools],
        host=host,
        port=port,
        transport_security=LOCALHOST_ONLY,
    )
    # FastMCP's constructor gives the root logger a handler of its own, which printed each of
    # the backend's log lines a second time.
    root.handlers[:] = handlers
    root.setLevel(level)
    return server
