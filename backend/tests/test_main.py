from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings, FakeEmbeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from fake_llm import ScriptedChatModel, answer_message, tool_call_message
from molecula import main
from molecula.agent.agent import ChatAgent
from molecula.agent.llm import LLMConfigError
from molecula.config import Settings
from molecula.guard.chat import GuardedChat
from molecula.main import app
from molecula.rag.embeddings import embedding_model_id
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.sources.http import SourceClient
from molecula.store.compounds import CompoundStore, Synonym
from molecula.store.db import connect
from molecula.store.index import Chunk, IndexModelMismatch, LabelIndex
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
    monkeypatch.setattr(main, "get_chat_model", lambda settings: model)
    monkeypatch.setattr(main, "get_source_check_model", lambda settings: model)


@pytest.fixture
def loaded_models(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fakes the embedding and chat models and records which ones startup loaded."""
    loaded: list[str] = []

    def embeddings(settings: Settings) -> Embeddings:
        loaded.append("embeddings")
        return FakeEmbeddings(size=3)

    def chat_model(settings: Settings) -> BaseChatModel:
        loaded.append("chat")
        return ScriptedChatModel(script=[])

    def source_check_model(settings: Settings) -> BaseChatModel:
        loaded.append("source check")
        return ScriptedChatModel(script=[])

    monkeypatch.setattr(main, "get_embeddings", embeddings)
    monkeypatch.setattr(main, "get_chat_model", chat_model)
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

    assert loaded_models == ["chat", "embeddings", "source check"]


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


def test_chat_answers_from_the_stored_labels_offline(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "offline", True)
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
    model = ScriptedChatModel(
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
    use_models(monkeypatch, model)

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
