import logging
from collections import Counter
from collections.abc import Sequence
from functools import cached_property
from pathlib import Path
from time import perf_counter
from typing import Protocol

from langchain_core.embeddings import Embeddings

from molecula.config import Settings
from molecula.rag.chunking import CountTokens, chunk_labels
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import Chunk, LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.labels import LabelRecord, LabelStore

logger = logging.getLogger(__name__)

EMBED_BATCH = 256


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...


def build_index(
    labels: Sequence[tuple[int, LabelRecord]],
    count_tokens: CountTokens,
    embeddings: Embeddings,
    index: LabelIndex,
    keywords: KeywordIndex,
    model: str,
) -> list[Chunk]:
    """Chunk every label, embed the chunks and replace the vector and keyword indexes with
    them."""
    chunks = chunk_labels(labels, count_tokens)
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        vectors.extend(embeddings.embed_documents([chunk.text for chunk in batch]))
        logger.info("embedded %d of %d chunks", len(vectors), len(chunks))
    index.rebuild(chunks, vectors, model)
    keywords.rebuild(chunks)
    return chunks


def reindex_drug(
    cid: int,
    labels: Sequence[LabelRecord],
    count_tokens: CountTokens,
    embeddings: Embeddings,
    index: LabelIndex,
    keywords: KeywordIndex,
) -> list[Chunk]:
    """Chunk and embed one compound's labels and replace its chunks in both indexes."""
    chunks = chunk_labels([(cid, label) for label in labels], count_tokens)
    vectors = embeddings.embed_documents([chunk.text for chunk in chunks]) if chunks else []
    index.replace_drug(cid, chunks, vectors)
    # A store fetched before #44 has no keyword index; `ingest fetch` builds it whole.
    if keywords.exists():
        keywords.replace_drug(cid, chunks)
    return chunks


class DrugIndexer:
    """Re-indexes one drug at a time with the settings' embedding model, which is loaded on the
    first call: most label updates change nothing and never need it. The backend passes the
    model and index it already holds, so a nightly run loads neither again."""

    def __init__(
        self,
        settings: Settings,
        *,
        embeddings: Embeddings | None = None,
        index: LabelIndex | None = None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._index = index

    def __call__(self, cid: int, labels: Sequence[LabelRecord]) -> None:
        tokenizer, embeddings, index = self._loaded
        reindex_drug(
            cid,
            labels,
            lambda text: len(tokenizer.tokenize(text)),
            embeddings,
            index,
            KeywordIndex(self._settings.keyword_index_path),
        )

    @cached_property
    def _loaded(self) -> tuple[Tokenizer, Embeddings, LabelIndex]:
        from molecula.rag.embeddings import (
            embedding_model_id,
            get_embeddings,
            load_chunk_tokenizer,
        )

        index = self._index
        if index is None:
            index = LabelIndex(self._settings.index_dir)
            index.check_model(embedding_model_id(self._settings))
        return (
            load_chunk_tokenizer(self._settings),
            self._embeddings or get_embeddings(self._settings),
            index,
        )


def stored_labels(db_path: Path) -> list[tuple[int, LabelRecord]]:
    conn = connect(db_path)
    try:
        labels = LabelStore(conn)
        return [
            (compound.cid, label)
            for compound in CompoundStore(conn).all()
            for label in labels.get(compound.cid)
        ]
    finally:
        conn.close()


def run(settings: Settings, *, index: LabelIndex | None = None) -> int:
    """`python -m molecula.ingest index`: chunk, embed and index every stored label section.
    An `index` already open is rebuilt in place: Windows can't delete a folder Chroma holds."""
    labels = stored_labels(settings.db_path)
    if not labels:
        logger.error("The store has no labels; run `python -m molecula.ingest labels` first")
        return 1
    # Imported here: torch and sentence-transformers take seconds to load, and the other ingest
    # steps don't need them.
    from molecula.rag.embeddings import (
        embedding_model_id,
        get_embeddings,
        load_chunk_tokenizer,
    )

    tokenizer = load_chunk_tokenizer(settings)
    model = embedding_model_id(settings)
    started = perf_counter()
    chunks = build_index(
        labels,
        lambda text: len(tokenizer.tokenize(text)),
        get_embeddings(settings),
        index or LabelIndex.empty(settings.index_dir),
        KeywordIndex(settings.keyword_index_path),
        model,
    )
    log_summary(chunks, len(labels), model, perf_counter() - started, settings.index_dir)
    return 0


def log_summary(
    chunks: list[Chunk], label_count: int, model: str, seconds: float, index_dir: Path
) -> None:
    size = sum(path.stat().st_size for path in index_dir.rglob("*") if path.is_file())
    logger.info(
        "%d chunks from %d labels embedded with %s in %.0f s; index %.1f MB in %s",
        len(chunks),
        label_count,
        model,
        seconds,
        size / 1e6,
        index_dir,
    )
    for group, count in sorted(Counter(chunk.section_group for chunk in chunks).items()):
        logger.info("  %s: %d chunks", group, count)
