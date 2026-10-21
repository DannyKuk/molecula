import os
from collections.abc import Callable
from typing import Any

import httpx
import numpy as np
import pytest
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from fake_hub import install_fake_hub
from molecula.config import OPENROUTER_BASE_URL, Settings
from molecula.rag.embeddings import (
    MODEL_FILES,
    PINNED_MODEL,
    PINNED_REVISION,
    EmbeddingConfigError,
    LocalEmbeddings,
    ModelDownloadError,
    download_local_model,
    embedding_model_id,
    get_embeddings,
    has_local_model,
    snapshot_dir,
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
    for key in [
        "OFFLINE",
        "OPENROUTER_API_KEY",
        "EMBEDDING_MODEL",
        "LOCAL_EMBEDDING_MODEL",
        "LOCAL_EMBEDDING_MODEL_REVISION",
        "DISABLE_SAFETENSORS_CONVERSION",
    ]:
        # Set first, so monkeypatch restores the variable after a test where the loader sets it.
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)


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
    make_settings: Callable[..., Settings], fake_model: list[FakeSentenceTransformer]
) -> None:
    current = make_settings(offline=False)

    model = get_embeddings(current)

    assert isinstance(model, LocalEmbeddings)
    (loaded,) = fake_model
    assert loaded.name == "BAAI/bge-m3"
    assert loaded.options["cache_folder"] == str(current.models_dir)
    assert (loaded.options["device"], loaded.options["local_files_only"]) == ("cpu", False)


def test_local_model_loads_the_pinned_revision(
    make_settings: Callable[..., Settings], fake_model: list[FakeSentenceTransformer]
) -> None:
    # snapshot_download writes no refs/main, so a fetched model loads only by its revision.
    get_embeddings(make_settings(offline=True))

    assert fake_model[0].options["revision"] == PINNED_REVISION


def test_loading_never_fetches_a_second_converted_copy_of_the_weights(
    make_settings: Callable[..., Settings], fake_model: list[FakeSentenceTransformer]
) -> None:
    get_embeddings(make_settings(offline=False))

    assert os.environ["DISABLE_SAFETENSORS_CONVERSION"] == "true"


def test_offline_never_downloads_the_model(
    make_settings: Callable[..., Settings], fake_model: list[FakeSentenceTransformer]
) -> None:
    get_embeddings(make_settings(offline=True))

    assert fake_model[0].options["local_files_only"] is True


def test_gpu_runs_the_model_in_half_precision(
    make_settings: Callable[..., Settings],
    fake_model: list[FakeSentenceTransformer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import torch

    monkeypatch.setattr("torch.cuda.is_available", lambda: True)

    get_embeddings(make_settings(offline=False))

    assert fake_model[0].options["device"] == "cuda"
    assert fake_model[0].options["model_kwargs"] == {"dtype": torch.float16}


def test_missing_model_offline_says_how_to_get_it(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(name: str, **options: Any) -> None:
        raise OSError("not in the cache")

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", missing)

    with pytest.raises(EmbeddingConfigError, match="ingest fetch` once"):
        get_embeddings(make_settings(offline=True))


def test_default_settings_name_the_pinned_model(make_settings: Callable[..., Settings]) -> None:
    current = make_settings()

    assert (current.local_embedding_model, current.local_embedding_model_revision) == (
        PINNED_MODEL,
        PINNED_REVISION,
    )


def test_model_download_is_pinned_to_the_revision_and_the_files_the_app_reads(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = install_fake_hub(monkeypatch)
    current = make_settings()
    assert not has_local_model(current)

    download_local_model(current)

    (call,) = hub.calls
    assert call["repo_id"] == "BAAI/bge-m3"
    assert call["revision"] == "5617a9f61b028005a4858fdac845db406aefb181"
    assert call["cache_dir"] == current.models_dir
    assert call["allow_patterns"] == list(MODEL_FILES)
    assert "pytorch_model.bin" in call["allow_patterns"]
    assert not any("*" in pattern for pattern in call["allow_patterns"])
    assert has_local_model(current)


def test_weights_with_another_hash_are_rejected_and_deleted(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_hub(monkeypatch, weights=b"tampered weights")
    current = make_settings()

    with pytest.raises(ModelDownloadError, match="SHA-256"):
        download_local_model(current)

    assert not (snapshot_dir(current) / "pytorch_model.bin").exists()
    assert not has_local_model(current)


def test_partly_downloaded_model_is_not_there(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_hub(monkeypatch)
    current = make_settings()
    download_local_model(current)

    (snapshot_dir(current) / "tokenizer.json").unlink()

    assert not has_local_model(current)


def test_another_model_is_not_downloaded(
    make_settings: Callable[..., Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = install_fake_hub(monkeypatch)

    with pytest.raises(ModelDownloadError, match="downloads only BAAI/bge-m3"):
        download_local_model(make_settings(local_embedding_model="BAAI/bge-small-en-v1.5"))

    assert hub.calls == []


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("connection refused"), OSError("401 Client Error")],
)
def test_failed_model_download_is_a_download_error(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    def fail(repo_id: str, **options: Any) -> str:
        raise error

    monkeypatch.setattr("huggingface_hub.snapshot_download", fail)

    with pytest.raises(ModelDownloadError, match="could not be downloaded"):
        download_local_model(make_settings())


def test_local_embeddings_use_the_model_prompts_and_unit_vectors() -> None:
    model = FakeSentenceTransformer("m")
    local = LocalEmbeddings(model)  # type: ignore[arg-type]

    assert local.embed_documents(["abc", "de"]) == [[3.0, 1.0], [2.0, 1.0]]
    assert local.embed_query("abcd") == [4.0, 1.0]
    assert [(kind, options["normalize_embeddings"]) for kind, _, options in model.calls] == [
        ("document", True),
        ("query", True),
    ]


def test_cloud_model_goes_through_openrouter(make_settings: Callable[..., Settings]) -> None:
    model = get_embeddings(
        make_settings(
            embedding_model="openai/text-embedding-3-small",
            openrouter_api_key=SecretStr("sk-test"),
            offline=False,
        )
    )

    assert isinstance(model, OpenAIEmbeddings)
    assert (model.model, model.openai_api_base) == (
        "openai/text-embedding-3-small",
        OPENROUTER_BASE_URL,
    )
    assert model.check_embedding_ctx_length is False
    assert model.chunk_size <= 100


def test_cloud_model_without_a_key_is_a_config_error(
    make_settings: Callable[..., Settings],
) -> None:
    with pytest.raises(EmbeddingConfigError, match="needs OPENROUTER_API_KEY"):
        get_embeddings(
            make_settings(embedding_model="openai/text-embedding-3-small", offline=False)
        )


def test_cloud_model_is_refused_offline(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(EmbeddingConfigError, match="OFFLINE=1 allows no external calls"):
        get_embeddings(
            make_settings(
                embedding_model="openai/text-embedding-3-small",
                openrouter_api_key=SecretStr("sk-test"),
                offline=True,
            )
        )


@pytest.mark.parametrize(
    ("values", "model"),
    [
        ({}, "BAAI/bge-m3"),
        (
            {"local_embedding_model": "BAAI/bge-small-en-v1.5"},
            "BAAI/bge-small-en-v1.5",
        ),
        ({"embedding_model": "openai/text-embedding-3-small"}, "openai/text-embedding-3-small"),
    ],
)
def test_index_records_the_model_in_use(
    make_settings: Callable[..., Settings], values: dict[str, str], model: str
) -> None:
    assert embedding_model_id(make_settings(**values, offline=False)) == model
