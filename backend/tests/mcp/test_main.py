import asyncio
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from langchain_core.embeddings import FakeEmbeddings
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from fake_llm import ScriptedChatModel
from molecula import main
from molecula.config import Settings
from molecula.mcp import __main__ as mcp_main
from molecula.mcp.__main__ import open_server
from molecula.rag.embeddings import embedding_model_id
from molecula.store.db import connect
from molecula.store.index import LabelIndex

TOOL_NAMES = [
    "resolve_drug",
    "get_properties",
    "get_targets",
    "get_complex",
    "search_labels",
    "compare_drugs",
]


@pytest.fixture
def store() -> Iterator[sqlite3.Connection]:
    conn = connect(Path(":memory:"))
    yield conn
    conn.close()


def test_the_server_serves_every_agent_tool_over_the_built_store(
    settings: Settings, store: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    LabelIndex(settings.index_dir).rebuild([], [], embedding_model_id(settings))
    monkeypatch.setattr(mcp_main, "get_embeddings", lambda settings: FakeEmbeddings(size=3))
    monkeypatch.setattr(main, "get_chat_model", lambda settings: ScriptedChatModel(script=[]))
    server = open_server(settings, store, host="127.0.0.1", port=8001)

    async def listed() -> list[str]:
        async with create_connected_server_and_client_session(server) as session:
            return [tool.name for tool in (await session.list_tools()).tools]

    assert asyncio.run(listed()) == TOOL_NAMES


def test_main_runs_the_server_over_the_chosen_transport(
    settings: Settings, store: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    LabelIndex(settings.index_dir).rebuild([], [], embedding_model_id(settings))
    monkeypatch.setattr(mcp_main, "get_embeddings", lambda settings: FakeEmbeddings(size=3))
    monkeypatch.setattr(main, "get_chat_model", lambda settings: ScriptedChatModel(script=[]))
    monkeypatch.setattr(mcp_main, "get_settings", lambda: settings)
    monkeypatch.setattr(mcp_main, "open_store", lambda settings: store)
    transports: list[str] = []
    monkeypatch.setattr(FastMCP, "run", lambda self, transport: transports.append(transport))

    mcp_main.main(["--transport", "streamable-http"])

    assert transports == ["streamable-http"]


def test_without_the_label_index_the_server_says_how_to_get_it(
    settings: Settings, store: sqlite3.Connection
) -> None:
    with pytest.raises(SystemExit, match=r"molecula\.ingest fetch"):
        open_server(settings, store, host="127.0.0.1", port=8001)

    assert not settings.index_dir.exists()
