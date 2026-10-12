from typing import TYPE_CHECKING, Any

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from molecula.config import OPENROUTER_ATTRIBUTION_HEADERS, OPENROUTER_BASE_URL, Settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    from transformers import PreTrainedTokenizerBase

LOCAL = "local"
# Every model gets the same chunks, so a comparison of models compares only the models.
CHUNK_TOKENIZER = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 32


class EmbeddingConfigError(Exception):
    """The settings don't say which embedding model to use, or it can't be reached."""


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
    if settings.embedding_model == LOCAL:
        return settings.local_embedding_model
    return settings.embedding_model


def get_embeddings(settings: Settings) -> Embeddings:
    """The local sentence-transformers model by default, or a cloud model through OpenRouter
    when EMBEDDING_MODEL names one (e.g. openai/text-embedding-3-small).

    Raises EmbeddingConfigError when the cloud model has no key or OFFLINE=1 forbids it.
    """
    if settings.embedding_model == LOCAL:
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
    )


def load_local_model(settings: Settings) -> SentenceTransformer:
    """The local model from `models_dir`, downloaded there first unless OFFLINE=1. Runs on the
    GPU in half precision when PyTorch sees one."""
    # Imported here: torch and sentence-transformers take seconds to load, and only the index
    # step and retrieval need them.
    import torch
    from sentence_transformers import SentenceTransformer

    on_gpu = torch.cuda.is_available()
    model_kwargs: dict[str, Any] = {"dtype": torch.float16} if on_gpu else {}
    try:
        return SentenceTransformer(
            settings.local_embedding_model,
            device="cuda" if on_gpu else "cpu",
            cache_folder=str(settings.models_dir),
            local_files_only=settings.offline,
            model_kwargs=model_kwargs,
        )
    except OSError as error:
        raise EmbeddingConfigError(
            missing_model(settings, settings.local_embedding_model)
        ) from error


def load_chunk_tokenizer(settings: Settings) -> PreTrainedTokenizerBase:
    from transformers import AutoTokenizer

    try:
        return AutoTokenizer.from_pretrained(
            CHUNK_TOKENIZER,
            cache_dir=str(settings.models_dir),
            local_files_only=settings.offline,
        )
    except OSError as error:
        raise EmbeddingConfigError(missing_model(settings, CHUNK_TOKENIZER)) from error


def missing_model(settings: Settings, name: str) -> str:
    if settings.offline:
        return (
            f"{name} isn't in {settings.models_dir} and OFFLINE=1 forbids the download. "
            "Run `python -m molecula.ingest index` once without OFFLINE=1."
        )
    return f"{name} could not be loaded from Hugging Face into {settings.models_dir}."
