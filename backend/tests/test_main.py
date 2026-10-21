import asyncio
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings, FakeEmbeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from fake_llm import ScriptedChatModel, answer_message, tool_call_message
from molecula import main
from molecula.agent.agent import ChatAgent
from molecula.agent.decisions import DecisionModel, get_decision_model
from molecula.agent.label_filter import DecisionFirstFilterExtractor
from molecula.agent.llm import LLMConfigError
from molecula.config import Settings
from molecula.guard.chat import GuardedChat
from molecula.guard.safety import ChatModelInputCheck, DecisionModelInputCheck
from molecula.ingest.index import DrugIndexer
from molecula.main import app
from molecula.rag import embeddings as rag_embeddings
from molecula.rag.embeddings import embedding_model_id
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.chat import ChatModel
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.sources.http import SourceClient
from molecula.store.compounds import CompoundStore, Synonym
from molecula.store.db import connect
from molecula.store.index import Chunk, IndexModelMismatch, LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.labels import LabelStore
from molecula.store.structures import ComplexFiles, ConformerFiles
from sse import server_sent_events
from store_records import GLEEVEC, IMATINIB, IMATINIB_COMPLEX, compound_record

SDF = "5291\n  stored conformer\n$$$$\n"
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

QUESTION = {"messages": [{"role": "user", "content": "How does imatinib work?"}]}


@pytest.fixture
def settings(make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = make_settings(offline=False)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return settings


def test_frontend_origin_may_call_the_api() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_gets_no_cors_header() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_app_starts_without_a_store_and_supports_no_drug(settings: Settings) -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/drugs").json() == []
        resolution = client.get("/drugs/resolve", params={"name": "imatinib"}).json()
        targets = client.get("/drugs/5291/targets")
        labels = client.get("/drugs/5291/labels")

    assert resolution["status"] == "not_supported"
    assert targets.status_code == 404
    assert labels.status_code == 404
    assert not settings.db_path.exists()


def test_routes_serve_the_built_store(settings: Settings) -> None:
    conn = connect(settings.db_path)
    CompoundStore(conn).save(
        IMATINIB,
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias"), Synonym("STI571", "pubchem")],
        datetime(2026, 10, 11, tzinfo=UTC),
    )
    conn.close()
    ConformerFiles(settings.conformers_dir).write(5291, SDF)

    with TestClient(app) as client:
        drugs = client.get("/drugs").json()
        resolution = client.get("/drugs/resolve", params={"name": "imatinib mesylate"}).json()
        structure = client.get("/drugs/5291/structure")
        targets = client.get("/drugs/5291/targets").json()
        labels = client.get("/drugs/5291/labels").json()

    assert drugs == [{"cid": 5291, "name": "imatinib", "aliases": ["Gleevec"], "has_3d": True}]
    assert resolution["compound"]["cid"] == 5291
    assert structure.text == SDF
    assert targets == {"cid": 5291, "targets": []}
    assert labels == {"cid": 5291, "labels": []}


def test_stats_count_the_built_store_and_the_usage_log_lives_apart_from_it(
    settings: Settings,
) -> None:
    conn = connect(settings.db_path)
    CompoundStore(conn).save(IMATINIB, [], datetime(2026, 10, 11, tzinfo=UTC))
    conn.close()
    ConformerFiles(settings.conformers_dir).write(5291, SDF)

    with TestClient(app) as client:
        stats = client.get("/stats", params={"days": 7}).json()

    assert stats["knowledge_base"]["drugs"] == 1
    assert stats["knowledge_base"]["conformers"] == 1
    assert len(stats["usage"]["days"]) == 7
    assert settings.usage_db_path.exists()
    assert not settings.usage_db_path.is_relative_to(settings.build_dir)


def test_only_hero_drugs_have_a_complex_also_when_online(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(settings.db_path)
    for record in (IMATINIB, compound_record(3672, "ibuprofen")):
        CompoundStore(conn).save(record, [], datetime(2026, 10, 13, tzinfo=UTC))
    conn.close()
    ComplexFiles(settings.complexes_dir).write(5291, IMATINIB_COMPLEX.model_dump_json())

    def no_fetch(*args: object, **kwargs: object) -> None:
        raise AssertionError("a source was called")

    monkeypatch.setattr(SourceClient, "get", no_fetch)

    with TestClient(app) as client:
        complexes = client.app.state.complex_service

        assert not settings.offline
        assert complexes.get_complex(5291) == IMATINIB_COMPLEX
        assert complexes.get_complex(3672) is None


@pytest.mark.parametrize(("cutoff", "suggested"), [(0.8, ["Gleevec"]), (0.9, [])])
def test_name_suggestion_cutoff_comes_from_the_settings(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, cutoff: float, suggested: list[str]
) -> None:
    monkeypatch.setattr(settings, "name_suggestion_cutoff", cutoff)
    conn = connect(settings.db_path)
    CompoundStore(conn).save(
        IMATINIB,
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias")],
        datetime(2026, 10, 11, tzinfo=UTC),
    )
    conn.close()

    with TestClient(app) as client:
        resolution = client.get("/drugs/resolve", params={"name": "Gleevek"}).json()

    assert resolution["status"] == "not_supported"
    assert [suggestion["alias"] for suggestion in resolution["suggestions"]] == suggested


def build_index(settings: Settings, model: str) -> None:
    LabelIndex(settings.index_dir).rebuild([CHUNK], [[1.0, 0.0, 0.0]], model)


def judged_supported() -> AIMessage:
    """The source check's verdict on a one-claim answer: supported."""
    return tool_call_message(
        "ClaimJudgements",
        {"judgements": [{"id": 1, "reason": "The passage says so.", "verdict": "supported"}]},
    )


def use_models(monkeypatch: pytest.MonkeyPatch, model: ScriptedChatModel) -> None:
    """The scripted model sorts the message, answers it and checks the answer."""
    monkeypatch.setattr(main, "get_embeddings", lambda settings: UnitEmbeddings())
    monkeypatch.setattr(main, "get_chat_model", lambda settings, picked=None: model)
    monkeypatch.setattr(main, "get_answer_model", lambda settings, picked=None: model)
    monkeypatch.setattr(main, "get_source_check_model", lambda settings, picked=None: model)


@pytest.fixture
def loaded_models(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fakes the embedding and chat models and records which ones startup loaded."""
    loaded: list[str] = []

    def embeddings(settings: Settings) -> Embeddings:
        loaded.append("embeddings")
        return FakeEmbeddings(size=3)

    def chat_model(settings: Settings, model: ChatModel | None = None) -> BaseChatModel:
        loaded.append("chat")
        return ScriptedChatModel(script=[])

    def answer_model(settings: Settings, model: ChatModel | None = None) -> BaseChatModel:
        loaded.append("answer")
        return ScriptedChatModel(script=[])

    def source_check_model(settings: Settings, model: ChatModel | None = None) -> BaseChatModel:
        loaded.append("source check")
        return ScriptedChatModel(script=[])

    monkeypatch.setattr(main, "get_embeddings", embeddings)
    monkeypatch.setattr(main, "get_chat_model", chat_model)
    monkeypatch.setattr(main, "get_answer_model", answer_model)
    monkeypatch.setattr(main, "get_source_check_model", source_check_model)
    return loaded


def test_without_an_index_label_search_is_off_and_no_index_folder_appears(
    settings: Settings, loaded_models: list[str]
) -> None:
    with TestClient(app):
        assert app.state.label_retriever is None
        assert app.state.filter_extractor is None

    assert loaded_models == []
    assert not settings.index_dir.exists()


def test_startup_builds_the_label_search_over_a_matching_index(
    settings: Settings, loaded_models: list[str]
) -> None:
    build_index(settings, embedding_model_id(settings))

    with TestClient(app):
        assert isinstance(app.state.label_retriever, LabelRetriever)
        assert isinstance(app.state.filter_extractor, FilterExtractor)
        assert isinstance(app.state.chat_agent, ChatAgent)
        assert isinstance(app.state.chat, GuardedChat)

    assert loaded_models == ["chat", "embeddings", "source check", "answer"]


def test_without_a_chat_model_the_label_search_is_off_and_the_routes_still_work(
    settings: Settings, loaded_models: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def unconfigured(settings: Settings) -> BaseChatModel:
        raise LLMConfigError("No chat model is configured.")

    monkeypatch.setattr(main, "get_chat_model", unconfigured)
    build_index(settings, embedding_model_id(settings))

    with TestClient(app) as client:
        assert client.get("/drugs").status_code == 200
        assert client.post("/chat", json=QUESTION).status_code == 503
        assert app.state.label_retriever is None
        assert app.state.filter_extractor is None
        assert app.state.chat_agent is None
        assert app.state.chat is None

    assert loaded_models == []


def test_startup_refuses_a_cloud_embedding_model_offline(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud = make_settings(offline=True, embedding_model="openai/text-embedding-3-large")
    monkeypatch.setattr(main, "get_settings", lambda: cloud)
    monkeypatch.setattr(main, "get_chat_model", lambda settings: ScriptedChatModel(script=[]))
    build_index(cloud, "openai/text-embedding-3-large")

    with (
        pytest.raises(rag_embeddings.EmbeddingConfigError, match="OFFLINE=1 allows no external"),
        TestClient(app),
    ):
        pass


def test_startup_refuses_an_index_built_with_another_embedding_model(
    settings: Settings, loaded_models: list[str]
) -> None:
    build_index(settings, "BAAI/bge-small-en-v1.5")

    with pytest.raises(IndexModelMismatch, match=r"bge-small-en-v1.5"), TestClient(app):
        pass

    assert loaded_models == []


MECHANISM = replace(
    CHUNK,
    id="gleevec:mechanism_of_action:0",
    text="Imatinib inhibits the BCR-ABL tyrosine kinase.",
    section="mechanism_of_action",
    section_group="pharmacology",
)


class UnitEmbeddings(Embeddings):
    """Embeds every text as the same vector, so the search finds the one stored chunk."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class WordTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return text.split()


def store_the_mechanism_label(settings: Settings) -> None:
    conn = connect(settings.db_path)
    fetched = datetime(2026, 10, 11, tzinfo=UTC)
    CompoundStore(conn).save(
        IMATINIB, [Synonym("imatinib", "name"), Synonym("Gleevec", "alias")], fetched
    )
    LabelStore(conn).save(5291, (GLEEVEC,), fetched)
    conn.close()
    LabelIndex(settings.index_dir).rebuild(
        [MECHANISM], [[1.0, 0.0, 0.0]], embedding_model_id(settings)
    )


def search_the_mechanism_then_answer() -> ScriptedChatModel:
    return ScriptedChatModel(
        script=[
            tool_call_message("SortedMessage", {"category": "ok"}),
            tool_call_message(
                "search_labels",
                {
                    "question": "How does imatinib work?",
                    "drug": "imatinib",
                    "section": "pharmacology",
                },
            ),
            answer_message("It blocks the BCR-ABL kinase."),
            judged_supported(),
        ]
    )


def test_chat_answers_from_the_stored_labels_offline(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "offline", True)
    store_the_mechanism_label(settings)
    use_models(monkeypatch, search_the_mechanism_then_answer())

    with TestClient(app) as client:
        response = client.post("/chat", json=QUESTION)

    events = dict(server_sent_events(response.text))
    assert events["tool_call"]["name"] == "search_labels"
    passages = events["tool_result"]["result"]["passages"]
    assert [(p["ref"], p["id"], p["url"]) for p in passages] == [(1, MECHANISM.id, GLEEVEC.url)]
    assert events["retrieval_trace"]["filter"]["drugs"][0]["set_ids"] == ["gleevec"]
    assert events["sources"]["sources"] == [
        {
            "kind": "dailymed",
            "name": "Gleevec",
            "url": GLEEVEC.url,
            "section": "mechanism_of_action",
            "effective_time": "2026-07-13",
            "ref": 1,
        }
    ]
    assert "disclaimer" not in events["sources"]
    assert events["done"]["step_limit_reached"] is False
    assert events["done"]["category"] == "ok"
    assert events["source_check"]["checked"] is True
    assert [c["label"] for c in events["source_check"]["claims"]] == ["supported"]


def test_with_mcp_agent_tools_the_chat_answers_through_the_mcp_server(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "offline", True)
    monkeypatch.setattr(settings, "agent_tools", "mcp")
    store_the_mechanism_label(settings)
    use_models(monkeypatch, search_the_mechanism_then_answer())

    with TestClient(app) as client:
        response = client.post("/chat", json=QUESTION)

    events = list(server_sent_events(response.text))
    by_name = dict(events)
    assert by_name["tool_call"]["name"] == "search_labels"
    assert "Searching the imatinib label" in [
        data["message"] for name, data in events if name == "status"
    ]
    passages = by_name["tool_result"]["result"]["passages"]
    assert [(p["ref"], p["id"], p["text"]) for p in passages] == [(1, MECHANISM.id, MECHANISM.text)]
    answer = "".join(data["text"] for name, data in events if name == "token")
    assert answer == "It blocks the BCR-ABL kinase."
    assert by_name["source_check"]["checked"] is True
    assert by_name["done"]["category"] == "ok"
    # Over MCP the tool result carries no typed artifact, so these stay empty (#42).
    assert "retrieval_trace" not in by_name
    assert by_name["sources"]["sources"] == []


def test_chat_describes_the_stored_complex_offline(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "offline", True)
    conn = connect(settings.db_path)
    CompoundStore(conn).save(IMATINIB, [Synonym("imatinib", "name")], datetime.now(UTC))
    conn.close()
    stored = IMATINIB_COMPLEX.model_copy(update={"target": "ABL1", "organism": "Homo sapiens"})
    ComplexFiles(settings.complexes_dir).write(5291, stored.model_dump_json())
    LabelIndex(settings.index_dir).rebuild(
        [MECHANISM], [[1.0, 0.0, 0.0]], embedding_model_id(settings)
    )
    model = ScriptedChatModel(
        script=[
            tool_call_message("SortedMessage", {"category": "ok"}),
            tool_call_message("get_complex", {"drug": "imatinib"}),
            answer_message("The 3D view shows imatinib in ABL1 [1]."),
            judged_supported(),
        ]
    )
    use_models(monkeypatch, model)

    with TestClient(app) as client:
        response = client.post("/chat", json=QUESTION)

    events = dict(server_sent_events(response.text))
    result = events["tool_result"]["result"]
    assert (result["status"], result["pdb_id"], result["target"], result["ref"]) == (
        "found",
        "2HYY",
        "ABL1",
        1,
    )
    assert events["sources"]["sources"] == [
        {
            "kind": "rcsb",
            "name": "2HYY",
            "url": "https://www.rcsb.org/structure/2HYY",
            "section": None,
            "effective_time": None,
            "ref": 1,
        }
    ]
    assert events["sources"]["unknown_refs"] == []
    assert "disclaimer" not in events["sources"]


@pytest.mark.parametrize("checks", [{}, {"checks": "tested"}])
def test_a_picked_model_writes_the_answer_and_the_default_sorts_and_checks_it(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, checks: dict[str, str]
) -> None:
    monkeypatch.setattr(settings, "offline", True)
    LabelIndex(settings.index_dir).rebuild(
        [MECHANISM], [[1.0, 0.0, 0.0]], embedding_model_id(settings)
    )
    default = ScriptedChatModel(
        script=[tool_call_message("SortedMessage", {"category": "ok"}), judged_supported()]
    )
    gemma = ScriptedChatModel(script=[answer_message("Gemma writes this answer.")])
    asked_for: list[ChatModel | None] = []

    def answer_model(settings: Settings, model: ChatModel | None = None) -> BaseChatModel:
        asked_for.append(model)
        return default if model is None else gemma

    async def local_names(settings: Settings) -> list[str]:
        return ["google/gemma-4-31b"]

    use_models(monkeypatch, default)
    monkeypatch.setattr(main, "get_answer_model", answer_model)
    monkeypatch.setattr(main, "local_model_names", local_names)

    with TestClient(app) as client:
        listed = client.get("/models").json()
        response = client.post("/chat", json=QUESTION | {"model": "google/gemma-4-31b"} | checks)

    gemma_model = ChatModel(name="google/gemma-4-31b", local=True)
    assert gemma_model.model_dump() in listed["models"]
    assert asked_for == [None, gemma_model]
    events = server_sent_events(response.text)
    answer = "".join(data["text"] for name, data in events if name == "token")
    assert answer == "Gemma writes this answer."
    assert dict(events)["done"]["category"] == "ok"
    assert dict(events)["source_check"]["checked"] is True


def search_by_question_then_answer() -> ScriptedChatModel:
    """Sorts the message, searches the labels without naming the drug, so the filter is
    extracted from the question, answers and checks the answer."""
    return ScriptedChatModel(
        script=[
            tool_call_message("SortedMessage", {"category": "ok"}),
            tool_call_message("search_labels", {"question": "How does imatinib work?"}),
            tool_call_message("LabelQuery", {"substances": ["imatinib"]}),
            answer_message("It blocks the BCR-ABL kinase [1]."),
            judged_supported(),
        ]
    )


@pytest.mark.parametrize("agent_tools", ["local", "mcp"])
def test_a_local_pick_with_the_picked_checks_makes_no_openrouter_or_jev_call(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, agent_tools: str
) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr("sk-or-test"))
    monkeypatch.setattr(settings, "agent_tools", agent_tools)
    store_the_mechanism_label(settings)
    tested = ScriptedChatModel(script=[])
    gemma = search_by_question_then_answer()
    jev_calls: list[httpx2.Request] = []

    def model_for(settings: Settings, model: ChatModel | None = None) -> BaseChatModel:
        return tested if model is None else gemma

    def jev(settings: Settings) -> DecisionModel:
        def answer(request: httpx2.Request) -> httpx2.Response:
            jev_calls.append(request)
            return httpx2.Response(500)

        return get_decision_model(settings, transport=httpx2.MockTransport(answer))

    async def local_names(settings: Settings) -> list[str]:
        return ["google/gemma-4-31b"]

    monkeypatch.setattr(main, "get_embeddings", lambda settings: UnitEmbeddings())
    for getter in ("get_chat_model", "get_answer_model", "get_source_check_model"):
        monkeypatch.setattr(main, getter, model_for)
    monkeypatch.setattr(main, "get_decision_model", jev)
    monkeypatch.setattr(main, "local_model_names", local_names)

    with TestClient(app) as client:
        response = client.post(
            "/chat", json=QUESTION | {"model": "google/gemma-4-31b", "checks": "picked"}
        )

    events = dict(server_sent_events(response.text))
    assert events["done"]["category"] == "ok"
    assert events["retrieval_trace"]["filter_source"] == "model"
    assert events["retrieval_trace"]["filter"]["drugs"][0]["set_ids"] == ["gleevec"]
    assert [c["label"] for c in events["source_check"]["claims"]] == ["supported"]
    assert len(gemma.received) == 5
    assert tested.received == []
    assert jev_calls == []


def test_offline_no_cloud_model_is_offered_and_a_cloud_name_answers_422(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, loaded_models: list[str]
) -> None:
    monkeypatch.setattr(settings, "offline", True)
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr("sk-or-test"))
    monkeypatch.setattr(settings, "llm_models", ["openai/gpt-6-luna"])
    monkeypatch.setattr(settings, "local_llm_base_url", "http://localhost:1234/v1")
    monkeypatch.setattr(settings, "local_llm_model", "openai/gpt-oss-20b")

    async def local_names(settings: Settings) -> list[str]:
        return ["google/gemma-4-31b"]

    monkeypatch.setattr(main, "local_model_names", local_names)
    build_index(settings, embedding_model_id(settings))

    with TestClient(app) as client:
        listed = client.get("/models").json()
        response = client.post(
            "/chat", json=QUESTION | {"model": "openai/gpt-6-luna", "checks": "picked"}
        )

    assert listed["models"] == [
        {"name": "openai/gpt-oss-20b", "local": True},
        {"name": "google/gemma-4-31b", "local": True},
    ]
    assert response.status_code == 422


def test_without_a_local_server_only_the_configured_model_is_offered(
    settings: Settings, loaded_models: list[str]
) -> None:
    build_index(settings, embedding_model_id(settings))

    with TestClient(app) as client:
        listed = client.get("/models").json()

    assert [model["name"] for model in listed["models"]] == [listed["default"]]


def test_offline_the_chat_model_sorts_messages(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(offline=True, openrouter_api_key=SecretStr("sk-or-test"))

    input_check = main.open_input_check(settings, ScriptedChatModel(script=[]))

    assert isinstance(input_check, ChatModelInputCheck)


def test_online_jev_sorts_messages(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(offline=False, openrouter_api_key=SecretStr("sk-or-test"))

    decision_model = main.online_decision_model(settings)
    input_check = main.open_input_check(settings, ScriptedChatModel(script=[]))

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

    found = main.open_filter_extractor(settings, ScriptedChatModel(script=[]), compounds, labels)

    assert type(found) is extractor


def test_online_without_an_openrouter_key_the_chat_model_sorts_messages(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(offline=False, openrouter_api_key=None)

    input_check = main.open_input_check(settings, ScriptedChatModel(script=[]))

    assert isinstance(input_check, ChatModelInputCheck)


def test_no_response_or_log_line_contains_a_key_value(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    openrouter_key = "sk-or-v1-0123456789abcdef-test-key"
    openfda_key = "openfda-test-key-9876543210"
    settings = make_settings(
        offline=False,
        openrouter_api_key=openrouter_key,
        openfda_api_key=openfda_key,
        chat_requests_per_minute=1,
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    caplog.set_level(logging.DEBUG)

    with TestClient(app) as client:
        responses = [
            client.get("/health"),
            client.get("/drugs"),
            client.get("/drugs/resolve", params={"name": "imatinib"}),
            client.post("/chat", json=QUESTION),
            client.post("/chat", json=QUESTION),
            client.post("/chat", json={"messages": []}),
            client.get("/openapi.json"),
        ]

    assert [response.status_code for response in responses[3:5]] == [503, 429]
    assert "OPENROUTER_API_KEY is set" in caplog.text
    assert "OPENFDA_API_KEY is set" in caplog.text
    for key in (openrouter_key, openfda_key):
        assert key not in caplog.text
        for response in responses:
            assert key not in response.text
            assert key not in str(response.headers)


def test_retry_after_is_readable_across_origins() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-expose-headers"] == "Retry-After"


def test_hybrid_mode_fuses_the_keyword_search_when_its_index_is_built(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings(retrieval_mode="hybrid")
    build_index(settings, embedding_model_id(settings))
    KeywordIndex(settings.keyword_index_path).rebuild([CHUNK])

    retriever = main.open_label_retriever(
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
    build_index(settings, embedding_model_id(settings))

    retriever = main.open_label_retriever(
        settings, LabelIndex(settings.index_dir), UnitEmbeddings()
    )

    [found] = retriever.retrieve(CHUNK.text).chunks
    assert found.dense_rank == 1 and found.fused_score is None
    assert "python -m molecula.ingest fetch" in caplog.text
    assert not settings.keyword_index_path.exists()


def test_the_label_update_reindexes_with_the_apps_own_model_and_index(
    settings: Settings, loaded_models: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    build_index(settings, embedding_model_id(settings))
    connect(settings.db_path).close()
    reindexes: list[DrugIndexer] = []

    def fake_update_store(settings: Settings, reindex: DrugIndexer) -> None:
        reindexes.append(reindex)

    def no_second_model(settings: Settings) -> None:
        raise AssertionError("loaded the embedding model again")

    monkeypatch.setattr(main, "update_store", fake_update_store)
    monkeypatch.setattr(rag_embeddings, "get_embeddings", no_second_model)
    monkeypatch.setattr(rag_embeddings, "load_chunk_tokenizer", lambda settings: WordTokenizer())

    with TestClient(app):
        updater = app.state.label_updater
        assert updater.start()
        while updater.running:
            time.sleep(0.01)
        [reindex] = reindexes
        reindex(5291, [GLEEVEC])

    assert GLEEVEC.set_id in {chunk.set_id for chunk in LabelIndex(settings.index_dir).chunks()}
    assert loaded_models.count("embeddings") == 1


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
        updater = main.open_label_updater(settings, conn, LabelIndex(settings.index_dir), None)
        return main.schedule_label_updates(settings, updater)

    assert asyncio.run(scheduled()) is None
    conn.close()


def test_the_nightly_run_is_scheduled_over_a_built_store(
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(offline=False)
    LabelIndex(settings.index_dir).rebuild([], [], "fake")
    conn = connect(settings.db_path)

    async def scheduled() -> bool:
        updater = main.open_label_updater(settings, conn, LabelIndex(settings.index_dir), None)
        task = main.schedule_label_updates(settings, updater)
        assert task is not None
        task.cancel()
        return updater.can_run

    assert asyncio.run(scheduled())
    conn.close()


def test_by_default_the_update_route_is_off_and_stats_show_the_label_update(
    settings: Settings,
) -> None:
    with TestClient(app) as client:
        response = client.post("/labels/update")
        label_update = client.get("/stats").json()["label_update"]

    assert response.status_code == 404
    assert label_update == {"last_run": None, "running": False, "can_start": False}
