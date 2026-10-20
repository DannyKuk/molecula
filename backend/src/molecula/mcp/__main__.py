import argparse
import sqlite3

from mcp.server.fastmcp import FastMCP

from molecula.agent.tool_registry import build_tools
from molecula.config import Settings, get_settings
from molecula.main import (
    log_to_console,
    open_chat_model,
    open_filter_extractor,
    open_label_index,
    open_label_retriever,
    open_services,
    open_store,
)
from molecula.mcp.server import DEFAULT_PORT, build_server

NO_LABEL_SEARCH = (
    "The MCP server needs the label index and a chat model for search_labels: run "
    "`python -m molecula.ingest fetch` and set the chat model in .env (see .env.example)."
)


def open_server(settings: Settings, conn: sqlite3.Connection, *, host: str, port: int) -> FastMCP:
    """The MCP server over the store, built from the settings the way the backend builds its
    agent's tools. Exits when the label search can't be built."""
    services = open_services(settings, conn)
    index = open_label_index(settings)
    chat_model = open_chat_model(settings) if index is not None else None
    if index is None or chat_model is None:
        raise SystemExit(NO_LABEL_SEARCH)
    tools = build_tools(
        services.compounds,
        services.targets,
        services.complexes,
        open_filter_extractor(settings, chat_model, services.compounds, services.labels),
        open_label_retriever(settings, index),
    )
    return build_server(tools, host=host, port=port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m molecula.mcp", description="Serve Molecula's tools over MCP."
    )
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    log_to_console()
    settings = get_settings()
    conn = open_store(settings)
    try:
        open_server(settings, conn, host=args.host, port=args.port).run(args.transport)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
