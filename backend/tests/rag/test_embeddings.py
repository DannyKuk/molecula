from pathlib import Path
from typing import Any

import numpy as np
import pytest
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from molecula.agent.llm import OPENROUTER_BASE_URL
from molecula.config import Settings
from molecula.rag.embeddings import (
    EmbeddingConfigError,
    LocalEmbeddings,
    embedding_model_id,
    get_embeddings,
)


class FakeSentenceTransformer:
    """Records how it was built and what it encoded; every text becomes [length, 1]."""

    def __init__(self, name: str, **options: Any) -> None:
        self.name = name
        self.options = options
        self.calls: list[tuple[str, list[str], dict[str, Any]]] = []

    def encode_document(self, texts: list[str], **options: Any) -> np.ndarray:
        self.calls.append(("document", texts, options))
        return np.array([[float(len(text)), 1.0] for text in texts])

    def encode_query(self, text: str, **options: Any) -> np.ndarray:
        self.calls.append(("query", [text], options))
        return np.array([float(len(text)), 1.0])


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ["OFFLINE", "OPENROUTER_API_KEY", "EMBEDDING_MODEL", "LOCAL_EMBEDDING_MODEL"]:
        monkeypatch.delenv(key, raising=False)


def settings(tmp_path: Path, **values: Any) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, **values)


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> list[FakeSentenceTransformer]:
    built: list[FakeSentenceTransformer] = []

    def build(name: str, **options: Any) -> FakeSentenceTransformer:
        built.append(FakeSentenceTransformer(name, **options))
        return built[-1]

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", build)
    monkeypatch.setattr("torch.cuda.is_available", lambda: False)
    return built


def test_local_model_is_the_default_and_loads_from_the_models_dir(
    tmp_path: Path, fake_model: list[FakeSentenceTransformer]
) -> None:
    current = settings(tmp_path)

    model = get_embeddings(current)

    assert isinstance(model, LocalEmbeddings)
    (loaded,) = fake_model
    assert loaded.name == "BAAI/bge-small-en-v1.5"
    assert loaded.options["cache_folder"] == str(current.models_dir)
    assert (loaded.options["device"], loaded.options["local_files_only"]) == ("cpu", False)


def test_offline_never_downloads_the_model(
    tmp_path: Path, fake_model: list[FakeSentenceTransformer]
) -> None:
    get_embeddings(settings(tmp_path, offline=True))

    assert fake_model[0].options["local_files_only"] is True


def test_gpu_runs_the_model_in_half_precision(
    tmp_path: Path, fake_model: list[FakeSentenceTransformer], monkeypatch: pytest.MonkeyPatch
) -> None:
    import torch

    monkeypatch.setattr("torch.cuda.is_available", lambda: True)

    get_embeddings(settings(tmp_path))

    assert fake_model[0].options["device"] == "cuda"
    assert fake_model[0].options["model_kwargs"] == {"dtype": torch.float16}


def test_missing_model_offline_says_how_to_get_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(name: str, **options: Any) -> None:
        raise OSError("not in the cache")

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", missing)

    with pytest.raises(EmbeddingConfigError, match="once without OFFLINE=1"):
        get_embeddings(settings(tmp_path, offline=True))


def test_local_embeddings_use_the_model_prompts_and_unit_vectors() -> None:
    model = FakeSentenceTransformer("m")
    local = LocalEmbeddings(model)  # type: ignore[arg-type]

    assert local.embed_documents(["abc", "de"]) == [[3.0, 1.0], [2.0, 1.0]]
    assert local.embed_query("abcd") == [4.0, 1.0]
    assert [(kind, options["normalize_embeddings"]) for kind, _, options in model.calls] == [
        ("document", True),
        ("query", True),
    ]


def test_cloud_model_goes_through_openrouter(tmp_path: Path) -> None:
    model = get_embeddings(
        settings(
            tmp_path,
            embedding_model="openai/text-embedding-3-small",
            openrouter_api_key=SecretStr("sk-test"),
        )
    )

    assert isinstance(model, OpenAIEmbeddings)
    assert (model.model, model.openai_api_base) == (
        "openai/text-embedding-3-small",
        OPENROUTER_BASE_URL,
    )
    assert model.check_embedding_ctx_length is False


def test_cloud_model_without_a_key_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingConfigError, match="needs OPENROUTER_API_KEY"):
        get_embeddings(settings(tmp_path, embedding_model="openai/text-embedding-3-small"))


def test_cloud_model_is_refused_offline(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingConfigError, match="OFFLINE=1 allows no external calls"):
        get_embeddings(
            settings(
                tmp_path,
                embedding_model="openai/text-embedding-3-small",
                openrouter_api_key=SecretStr("sk-test"),
                offline=True,
            )
        )


@pytest.mark.parametrize(
    ("values", "model"),
    [
        ({}, "BAAI/bge-small-en-v1.5"),
        (
            {"local_embedding_model": "nomic-ai/nomic-embed-text-v1.5"},
            "nomic-ai/nomic-embed-text-v1.5",
        ),
        ({"embedding_model": "openai/text-embedding-3-small"}, "openai/text-embedding-3-small"),
    ],
)
def test_index_records_the_model_in_use(tmp_path: Path, values: dict[str, str], model: str) -> None:
    assert embedding_model_id(settings(tmp_path, **values)) == model
