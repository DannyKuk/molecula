import asyncio
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

from fake_llm import ScriptedChatModel
from molecula import wiring
from molecula.agent.label_filter import DecisionFirstFilterExtractor
from molecula.config import Settings
from molecula.guard.safety import ChatModelInputCheck, DecisionModelInputCheck
from molecula.rag.embeddings import embedding_model_id
from molecula.rag.filters import FilterExtractor
from molecula.schemas.retrieval import Chunk
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.labels import LabelStore
from molecula.store.structures import ConformerFiles

CHUNK = Chunk(
    id="gleevec:adverse_reactions:0",
    text="Nausea and fluid retention.",
    cid=5291,
    substance="IMATINIB MESYLATE",
    brand="Gleevec",
    product_type="rx",
    section="adverse_reactions",
    section_group="adverse_reactions",
    sensitive=False,
    set_id="gleevec",
    effective_time="20260713",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
)


class UnitEmbeddings(Embeddings):
    """Embeds every text as the same vector, so the search finds the one stored chunk."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def build_index(settings: Settings) -> None:
    LabelIndex(settings.index_dir).rebuild([CHUNK], [[1.0, 0.0, 0.0]], embedding_model_id(settings))


def test_offline_the_chat_model_sorts_messages(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(offline=True, openrouter_api_key=SecretStr("sk-or-test"))

    input_check = wiring.open_input_check(settings, ScriptedChatModel(script=[]))

    assert isinstance(input_check, ChatModelInputCheck)


def test_online_jev_sorts_messages(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(offline=False, openrouter_api_key=SecretStr("sk-or-test"))

    decision_model = wiring.online_decision_model(settings)
    input_check = wiring.open_input_check(settings, ScriptedChatModel(script=[]))

    assert isinstance(input_check, DecisionModelInputCheck)
    assert decision_model is not None
    assert decision_model.model == "jev-1.13"


@pytest.mark.parametrize(
    ("offline", "key", "extractor"),
    [
        (False, SecretStr("sk-or-test"), DecisionFirstFilterExtractor),
        (True, SecretStr("sk-or-test"), FilterExtractor),
        (False, None, FilterExtractor),
    ],
)
def test_online_jev_extracts_the_label_filter_and_offline_the_chat_model(
    make_settings: Callable[..., Settings],
    conn: sqlite3.Connection,
    tmp_path: Path,
    offline: bool,
    key: SecretStr | None,
    extractor: type[FilterExtractor],
) -> None:
    settings = make_settings(offline=offline, openrouter_api_key=key)
    store = CompoundStore(conn)
    compounds = CompoundService(store, ConformerFiles(tmp_path), suggestion_cutoff=0.8)
    labels = LabelService(LabelStore(conn), store)

    found = wiring.open_filter_extractor(settings, ScriptedChatModel(script=[]), compounds, labels)

    assert type(found) is extractor


def test_online_without_an_openrouter_key_the_chat_model_sorts_messages(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(offline=False, openrouter_api_key=None)

    input_check = wiring.open_input_check(settings, ScriptedChatModel(script=[]))

    assert isinstance(input_check, ChatModelInputCheck)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (None, "The answers come from openai/gpt-oss-20b at http://host.docker.internal:1234/v1"),
        ("sk-or-test", "The answers come from openai/gpt-6-luna at OpenRouter"),
    ],
)
def test_the_log_says_which_model_writes_the_answers_and_where(
    make_settings: Callable[..., Settings],
    caplog: pytest.LogCaptureFixture,
    key: str | None,
    expected: str,
) -> None:
    settings = make_settings(
        offline=False,
        openrouter_api_key=key,
        llm_model="openai/gpt-6-luna",
        local_llm_base_url="http://host.docker.internal:1234/v1",
        local_llm_model="openai/gpt-oss-20b",
    )
    caplog.set_level(logging.INFO)

    wiring.open_chat_model(settings)

    assert expected in caplog.text


def test_hybrid_mode_fuses_the_keyword_search_when_its_index_is_built(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings(retrieval_mode="hybrid")
    build_index(settings)
    KeywordIndex(settings.keyword_index_path).rebuild([CHUNK])

    retriever = wiring.open_label_retriever(
        settings, LabelIndex(settings.index_dir), UnitEmbeddings()
    )

    [found] = retriever.retrieve(CHUNK.text).chunks
    assert found.bm25_rank == 1 and found.fused_score is not None


def test_hybrid_mode_without_the_keyword_index_searches_by_embeddings_and_says_how_to_build_it(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = make_settings(retrieval_mode="hybrid")
    build_index(settings)

    retriever = wiring.open_label_retriever(
        settings, LabelIndex(settings.index_dir), UnitEmbeddings()
    )

    [found] = retriever.retrieve(CHUNK.text).chunks
    assert found.dense_rank == 1 and found.fused_score is None
    assert "python -m molecula.ingest fetch" in caplog.text
    assert not settings.keyword_index_path.exists()


@pytest.mark.parametrize(
    ("overrides", "store_built"),
    [({"offline": True}, True), ({"label_update_schedule": False}, True), ({}, False)],
)
def test_no_nightly_run_offline_with_the_schedule_off_or_without_a_store(
    make_settings: Callable[..., Settings], overrides: dict[str, object], store_built: bool
) -> None:
    settings = make_settings(**({"offline": False} | overrides))
    LabelIndex(settings.index_dir).rebuild([], [], "fake")
    conn = connect(settings.db_path if store_built else Path(":memory:"))

    async def scheduled() -> asyncio.Task[None] | None:
        updater = wiring.open_label_updater(settings, conn, LabelIndex(settings.index_dir), None)
        return wiring.schedule_label_updates(settings, updater)

    assert asyncio.run(scheduled()) is None
    conn.close()


def test_the_nightly_run_is_scheduled_over_a_built_store(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(offline=False)
    LabelIndex(settings.index_dir).rebuild([], [], "fake")
    conn = connect(settings.db_path)

    async def scheduled() -> bool:
        updater = wiring.open_label_updater(settings, conn, LabelIndex(settings.index_dir), None)
        task = wiring.schedule_label_updates(settings, updater)
        assert task is not None
        task.cancel()
        return updater.can_run

    assert asyncio.run(scheduled())
    conn.close()
