from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings, FakeEmbeddings
from langchain_core.language_models import BaseChatModel

from fake_llm import ScriptedChatModel
from molecula import main
from molecula.agent.llm import LLMConfigError
from molecula.config import Settings
from molecula.main import app
from molecula.rag.embeddings import embedding_model_id
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.store.compounds import CompoundRecord, CompoundStore, Synonym
from molecula.store.db import connect
from molecula.store.index import Chunk, IndexModelMismatch, LabelIndex
from molecula.store.structures import ConformerFiles

IMATINIB = CompoundRecord(
    cid=5291,
    name="imatinib",
    inchikey="KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    smiles="CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
    formula="C29H31N7O",
    mw=493.6,
    xlogp=3.5,
    tpsa=86.3,
    hbd=2,
    hba=7,
    rotb=7,
    heavy_atoms=37,
    conformer_source="pubchem",
    source="pubchem",
)
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


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(_env_file=None, data_dir=tmp_path)
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
    assert labels == {"cid": 5291, "labels": [], "disclaimer": None}


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

    monkeypatch.setattr(main, "get_embeddings", embeddings)
    monkeypatch.setattr(main, "get_chat_model", chat_model)
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

    assert loaded_models == ["chat", "embeddings"]


def test_without_a_chat_model_the_label_search_is_off_and_the_routes_still_work(
    settings: Settings, loaded_models: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def unconfigured(settings: Settings) -> BaseChatModel:
        raise LLMConfigError("No chat model is configured.")

    monkeypatch.setattr(main, "get_chat_model", unconfigured)
    build_index(settings, embedding_model_id(settings))

    with TestClient(app) as client:
        assert client.get("/drugs").status_code == 200
        assert app.state.label_retriever is None
        assert app.state.filter_extractor is None

    assert loaded_models == []


def test_startup_refuses_an_index_built_with_another_embedding_model(
    settings: Settings, loaded_models: list[str]
) -> None:
    build_index(settings, "BAAI/bge-small-en-v1.5")

    with pytest.raises(IndexModelMismatch, match=r"bge-small-en-v1.5"), TestClient(app):
        pass

    assert loaded_models == []
