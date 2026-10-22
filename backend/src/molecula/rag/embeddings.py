import hashlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from molecula.config import (
    LOCAL_EMBEDDINGS,
    OPENROUTER_ATTRIBUTION_HEADERS,
    OPENROUTER_BASE_URL,
    Settings,
)
from molecula.schemas.retrieval import EmbeddingSetup

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    from transformers import PreTrainedTokenizerBase

logger = logging.getLogger(__name__)

# Every model gets the same chunks, so a comparison of models compares only the models.
CHUNK_TOKENIZER = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 32
# Texts per request to a cloud model: Gemini on OpenRouter refuses more than 100 (#96).
CLOUD_BATCH_SIZE = 100

# The pinned model `ingest fetch` downloads; LOCAL_EMBEDDING_MODEL_REVISION's default in config.py
# is its commit. Exact names, because a pattern like *.json would also match onnx/tokenizer.json.
# README.md too, so an online start doesn't fetch it.
PINNED_MODEL = "BAAI/bge-m3"
PINNED_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
MODEL_FILES = (
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "1_Pooling/config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "pytorch_model.bin",
    "README.md",
)
WEIGHTS_FILE = "pytorch_model.bin"
# Hugging Face checks only the size of a download, so the weights are checked here.
WEIGHTS_SHA256 = "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38"


class EmbeddingConfigError(Exception):
    """The settings don't say which embedding model to use, or it can't be reached."""


class ModelDownloadError(Exception):
    """The pinned local model can't be downloaded, or its weights aren't the pinned ones."""


class LocalEmbeddings(Embeddings):
    """A sentence-transformers model run in-process, with the model's own query and document
    prompts and unit-length vectors, so cosine distance is a dot product."""

    def __init__(self, model: SentenceTransformer) -> None:
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode_document(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode_query(text, normalize_embeddings=True, convert_to_numpy=True)
        return vector.tolist()


def embedding_model_id(settings: Settings) -> str:
    """The model the index is built with, recorded with it: every query must use the same one."""
    if settings.embedding_model == LOCAL_EMBEDDINGS:
        return settings.local_embedding_model
    return settings.embedding_model


def embedding_setup(settings: Settings) -> EmbeddingSetup:
    """What the settings say the search runs on, whether or not the index is there to search."""
    return EmbeddingSetup(
        embedding_model=embedding_model_id(settings),
        local=settings.embedding_model == LOCAL_EMBEDDINGS,
        section_group_boost=settings.section_group_boost,
    )


def get_embeddings(settings: Settings) -> Embeddings:
    """The local sentence-transformers model by default, or a cloud model through OpenRouter
    when EMBEDDING_MODEL names one (e.g. openai/text-embedding-3-small).

    Raises EmbeddingConfigError when the cloud model has no key or OFFLINE=1 forbids it.
    """
    if settings.embedding_model == LOCAL_EMBEDDINGS:
        return LocalEmbeddings(load_local_model(settings))
    if settings.offline:
        raise EmbeddingConfigError(
            f"EMBEDDING_MODEL={settings.embedding_model} is a cloud model, but OFFLINE=1 allows "
            "no external calls. Set EMBEDDING_MODEL=local."
        )
    if settings.openrouter_api_key is None:
        raise EmbeddingConfigError(
            f"EMBEDDING_MODEL={settings.embedding_model} needs OPENROUTER_API_KEY. "
            "Set it, or set EMBEDDING_MODEL=local. See .env.example."
        )
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=OPENROUTER_BASE_URL,
        api_key=settings.openrouter_api_key,
        default_headers=dict(OPENROUTER_ATTRIBUTION_HEADERS),
        # The length check downloads tiktoken's encodings and counts with OpenAI's tokenizer;
        # chunks are already sized with CHUNK_TOKENIZER.
        check_embedding_ctx_length=False,
        chunk_size=CLOUD_BATCH_SIZE,
    )


def load_local_model(settings: Settings) -> SentenceTransformer:
    """The local model from `models_dir`, downloaded there first unless OFFLINE=1. Runs on the
    GPU in half precision when PyTorch sees one."""
    # Imported here: torch and sentence-transformers take seconds to load, and only the index
    # step and retrieval need them.
    import torch
    from sentence_transformers import SentenceTransformer

    # bge-m3 ships only pytorch_model.bin; without this, transformers also downloads a converted
    # model.safetensors from a pull request "for next time": a second 2.3 GB copy of the weights.
    os.environ.setdefault("DISABLE_SAFETENSORS_CONVERSION", "true")
    on_gpu = torch.cuda.is_available()
    model_kwargs: dict[str, Any] = {"dtype": torch.float16} if on_gpu else {}
    try:
        return SentenceTransformer(
            settings.local_embedding_model,
            device="cuda" if on_gpu else "cpu",
            cache_folder=str(settings.models_dir),
            revision=settings.local_embedding_model_revision,
            local_files_only=settings.offline,
            model_kwargs=model_kwargs,
        )
    except OSError as error:
        raise EmbeddingConfigError(
            missing_model(settings, settings.local_embedding_model, "fetch")
        ) from error


def snapshot_dir(settings: Settings) -> Path:
    """Where Hugging Face's cache keeps the files of the configured model and revision."""
    repo_folder = "models--" + settings.local_embedding_model.replace("/", "--")
    return settings.models_dir / repo_folder / "snapshots" / settings.local_embedding_model_revision


def has_local_model(settings: Settings) -> bool:
    """Whether every file the app reads of the pinned revision is in `models_dir`."""
    snapshot = snapshot_dir(settings)
    return all((snapshot / name).is_file() for name in MODEL_FILES)


def download_local_model(settings: Settings) -> None:
    """Download the pinned model's files into `models_dir` and check the weights' SHA-256.

    Raises ModelDownloadError for another model or revision than the pinned one, a failed
    download, or weights with another hash; bad weights are deleted, so the next run downloads
    them again.
    """
    from huggingface_hub import snapshot_download

    pinned = (settings.local_embedding_model, settings.local_embedding_model_revision)
    if pinned != (PINNED_MODEL, PINNED_REVISION):
        raise ModelDownloadError(
            f"fetch downloads only {PINNED_MODEL} at revision {PINNED_REVISION}, not "
            f"{pinned[0]} at {pinned[1]}. Build the index with that model instead: "
            "`python -m molecula.ingest index` downloads it."
        )
    try:
        snapshot = snapshot_download(
            PINNED_MODEL,
            revision=PINNED_REVISION,
            cache_dir=settings.models_dir,
            allow_patterns=list(MODEL_FILES),
        )
    # huggingface_hub raises its HTTP errors as OSError and connection errors as httpx2's.
    except (OSError, httpx2.HTTPError) as error:
        raise ModelDownloadError(
            f"{PINNED_MODEL} could not be downloaded from Hugging Face: {error}"
        ) from error
    check_weights(Path(snapshot) / WEIGHTS_FILE)


def check_weights(weights: Path) -> None:
    with weights.open("rb") as file:
        sha256 = hashlib.file_digest(file, "sha256").hexdigest()
    if sha256 != WEIGHTS_SHA256:
        # The snapshot entry may be a link into the cache's blobs; both go.
        blob = weights.resolve()
        weights.unlink()
        blob.unlink(missing_ok=True)
        raise ModelDownloadError(
            f"{weights} has SHA-256 {sha256}, not the pinned {WEIGHTS_SHA256}; it was deleted."
        )


def load_chunk_tokenizer(settings: Settings) -> PreTrainedTokenizerBase:
    from transformers import AutoTokenizer

    try:
        return AutoTokenizer.from_pretrained(
            CHUNK_TOKENIZER,
            cache_dir=str(settings.models_dir),
            local_files_only=settings.offline,
        )
    except OSError as error:
        raise EmbeddingConfigError(missing_model(settings, CHUNK_TOKENIZER, "index")) from error


def missing_model(settings: Settings, name: str, step: str) -> str:
    """Why the model didn't load, and the ingest step that downloads it."""
    if settings.offline:
        return (
            f"{name} isn't in {settings.models_dir} and OFFLINE=1 loads only local files. "
            f"Run `python -m molecula.ingest {step}` once; it downloads the model."
        )
    return f"{name} could not be loaded from Hugging Face into {settings.models_dir}."
