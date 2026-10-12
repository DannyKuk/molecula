"""Compare embedding models on the retrieval questions.

    OFFLINE=1 uv run python -m evals.retrieval.compare_embeddings [--only bge-small qwen3-0.6b]
        [--device cpu]

Reports recall@1, recall@5 and MRR@10 per model, searched within the question's drug (as the
retriever in #13 filters) and over the whole index, plus document embedding time, index size and
the time to embed one query. The first run downloads the local candidates into
data/build/eval/models, so run it once without OFFLINE=1; cloud candidates always need the network
and OPENROUTER_API_KEY. Document vectors are cached in data/build/eval/vectors, so a run with
--device cpu after a GPU run only embeds the questions and measures CPU query time.
"""

import argparse
import hashlib
import json
import logging
import statistics
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Literal, Protocol

import numpy as np
from evals.retrieval.candidates import CANDIDATES, Candidate
from evals.retrieval.dataset import Question, is_hit, load_questions, unanswerable

from molecula.config import Settings, get_settings
from molecula.ingest.index import stored_labels
from molecula.rag.chunking import chunk_labels
from molecula.rag.embeddings import get_embeddings, load_chunk_tokenizer
from molecula.store.index import Chunk, LabelIndex

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

TOP_K = 10
WARMUP_QUERIES = 3
EMBED_BATCH = 16
CLOUD_BATCH = 64

type Device = Literal["auto", "cpu"]


@dataclass(frozen=True)
class Scores:
    recall_at_1: float
    recall_at_5: float
    mrr_at_10: float


@dataclass(frozen=True)
class Result:
    label: str
    model: str
    dimensions: int
    build_device: str
    build_seconds: float
    query_device: str
    index_mb: float
    query_ms_p50: float
    query_ms_p95: float
    in_drug: Scores
    whole_index: Scores
    recall_at_5_by_group: dict[str, float]
    missed_in_drug: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", metavar="LABEL", help="candidate labels to run")
    parser.add_argument(
        "--device", choices=["auto", "cpu"], default="auto", help="where local models run"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    settings = get_settings()
    candidates = [c for c in CANDIDATES if not args.only or c.label in args.only]
    chunks = label_chunks(settings)
    questions = load_questions()
    missing = unanswerable(questions, chunks)
    if missing:
        logger.error("No chunk holds the evidence of: %s", ", ".join(q.id for q in missing))
        return 1
    logger.info("%d questions over %d chunks", len(questions), len(chunks))

    results = [
        evaluate(candidate, chunks, questions, settings, args.device) for candidate in candidates
    ]
    print(report(results, questions))
    save(results, settings)
    return 0


def label_chunks(settings: Settings) -> list[Chunk]:
    tokenizer = load_chunk_tokenizer(settings)
    return chunk_labels(stored_labels(settings.db_path), lambda t: len(tokenizer.tokenize(t)))


def evaluate(
    candidate: Candidate,
    chunks: list[Chunk],
    questions: list[Question],
    settings: Settings,
    device: Device,
) -> Result:
    logger.info("%s: %s", candidate.label, candidate.model)
    embedder = load_embedder(candidate, settings, device)
    documents, build_seconds, build_device = document_vectors(candidate, embedder, chunks, settings)
    queries, latencies = query_vectors(candidate, embedder, questions)
    scores = queries @ documents.T
    cids = np.array([chunk.cid for chunk in chunks])

    in_drug = [
        first_hit_rank(q, s, chunks, cids == q.cid) for q, s in zip(questions, scores, strict=True)
    ]
    anywhere = [first_hit_rank(q, s, chunks, None) for q, s in zip(questions, scores, strict=True)]
    by_group: dict[str, list[int | None]] = defaultdict(list)
    for question, rank in zip(questions, in_drug, strict=True):
        by_group[question.section_group].append(rank)

    return Result(
        label=candidate.label,
        model=candidate.model,
        dimensions=documents.shape[1],
        build_device=build_device,
        build_seconds=build_seconds,
        query_device=embedder.device,
        index_mb=index_size_mb(chunks, documents, candidate.model),
        query_ms_p50=statistics.median(latencies),
        query_ms_p95=statistics.quantiles(latencies, n=20)[-1],
        in_drug=summarize(in_drug),
        whole_index=summarize(anywhere),
        recall_at_5_by_group={group: recall(ranks, 5) for group, ranks in sorted(by_group.items())},
        missed_in_drug=[
            q.id for q, rank in zip(questions, in_drug, strict=True) if rank is None or rank > 5
        ],
    )


class Embedder(Protocol):
    device: str

    def documents(self, texts: list[str]) -> np.ndarray: ...

    def query(self, text: str) -> np.ndarray: ...


class LocalEmbedder:
    def __init__(self, model: SentenceTransformer) -> None:
        self._model = model
        self.device = str(model.device)

    def documents(self, texts: list[str]) -> np.ndarray:
        return self._model.encode_document(
            texts,
            batch_size=EMBED_BATCH,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )

    def query(self, text: str) -> np.ndarray:
        return self._model.encode_query(text, normalize_embeddings=True, convert_to_numpy=True)


class CloudEmbedder:
    """A model behind OpenRouter, through the app's own `get_embeddings`. Vectors are scaled to
    unit length here, since not every provider returns them that way."""

    device = "openrouter"

    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings

    def documents(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), CLOUD_BATCH):
            vectors.extend(self._embeddings.embed_documents(texts[start : start + CLOUD_BATCH]))
            logger.info("  embedded %d of %d chunks", len(vectors), len(texts))
        return unit_length(np.array(vectors))

    def query(self, text: str) -> np.ndarray:
        return unit_length(np.array(self._embeddings.embed_query(text)))


def unit_length(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


def load_embedder(candidate: Candidate, settings: Settings, device: Device) -> Embedder:
    if candidate.cloud:
        return CloudEmbedder(
            get_embeddings(settings.model_copy(update={"embedding_model": candidate.model}))
        )
    import torch
    from sentence_transformers import SentenceTransformer

    on_gpu = device == "auto" and torch.cuda.is_available()
    return LocalEmbedder(
        SentenceTransformer(
            candidate.model,
            device="cuda" if on_gpu else "cpu",
            cache_folder=str(settings.build_dir / "eval" / "models"),
            local_files_only=settings.offline,
            model_kwargs={"dtype": torch.float16} if on_gpu else {},
        )
    )


def document_vectors(
    candidate: Candidate, embedder: Embedder, chunks: list[Chunk], settings: Settings
) -> tuple[np.ndarray, float, str]:
    """The chunks' vectors, how long embedding them took and where, from the cache when the
    model, prefix and chunks are unchanged."""
    texts = [candidate.document_prefix + chunk.text for chunk in chunks]
    key = hashlib.sha256("\n".join([candidate.model, *texts]).encode()).hexdigest()[:16]
    cache = settings.build_dir / "eval" / "vectors" / f"{key}.npz"
    if cache.exists():
        cached = np.load(cache)
        logger.info("  document vectors from %s", cache)
        return cached["vectors"], float(cached["seconds"]), str(cached["device"])

    started = perf_counter()
    vectors = embedder.documents(texts).astype(np.float32)
    seconds = perf_counter() - started
    logger.info("  embedded %d chunks in %.0f s on %s", len(texts), seconds, embedder.device)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, vectors=vectors, seconds=seconds, device=embedder.device)
    return vectors, seconds, embedder.device


def query_vectors(
    candidate: Candidate, embedder: Embedder, questions: list[Question]
) -> tuple[np.ndarray, list[float]]:
    """Each question embedded on its own, as the app embeds a user's question, with the time
    each one took in milliseconds."""
    for question in questions[:WARMUP_QUERIES]:
        embedder.query(candidate.query_prefix + question.question)
    vectors, latencies = [], []
    for question in questions:
        started = perf_counter()
        vectors.append(embedder.query(candidate.query_prefix + question.question))
        latencies.append((perf_counter() - started) * 1000)
    return np.stack(vectors).astype(np.float32), latencies


def first_hit_rank(
    question: Question, scores: np.ndarray, chunks: list[Chunk], allowed: np.ndarray | None
) -> int | None:
    """The 1-based rank of the first chunk that answers the question, within the top TOP_K."""
    if allowed is not None:
        scores = np.where(allowed, scores, -np.inf)
    for rank, position in enumerate(np.argsort(-scores)[:TOP_K], start=1):
        if is_hit(question, chunks[position]):
            return rank
    return None


def recall(ranks: list[int | None], k: int) -> float:
    return sum(rank is not None and rank <= k for rank in ranks) / len(ranks)


def summarize(ranks: list[int | None]) -> Scores:
    return Scores(
        recall_at_1=recall(ranks, 1),
        recall_at_5=recall(ranks, 5),
        mrr_at_10=sum(1 / rank for rank in ranks if rank is not None) / len(ranks),
    )


def index_size_mb(chunks: list[Chunk], vectors: np.ndarray, model: str) -> float:
    """The size of a ChromaDB index of these vectors, built as `ingest index` builds it."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        path = Path(folder) / "chroma"
        LabelIndex.empty(path).rebuild(chunks, vectors.tolist(), model)
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def report(results: list[Result], questions: list[Question]) -> str:
    lines = [
        f"{len(questions)} questions. In drug: searched within the question's drug. "
        "Query time: one question, after warm-up.",
        "",
        "| Model | Dims | R@1 in drug | R@5 in drug | MRR@10 in drug | R@5 whole index "
        "| MRR@10 whole index | Embed chunks (s) | Index (MB) | Query p50 / p95 (ms) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.label} | {r.dimensions} | {r.in_drug.recall_at_1:.2f} "
            f"| {r.in_drug.recall_at_5:.2f} | {r.in_drug.mrr_at_10:.3f} "
            f"| {r.whole_index.recall_at_5:.2f} | {r.whole_index.mrr_at_10:.3f} "
            f"| {r.build_seconds:.0f} ({r.build_device}) | {r.index_mb:.1f} "
            f"| {r.query_ms_p50:.0f} / {r.query_ms_p95:.0f} ({r.query_device}) |"
        )
    counts: dict[str, int] = defaultdict(int)
    for question in questions:
        counts[question.section_group] += 1
    lines += [
        "",
        "Recall@5 in drug by section group:",
        "",
        "| Section group | n | " + " | ".join(r.label for r in results) + " |",
        "|---|---|" + "---|" * len(results),
    ]
    for group, count in sorted(counts.items()):
        cells = " | ".join(f"{r.recall_at_5_by_group[group]:.2f}" for r in results)
        lines.append(f"| {group} | {count} | {cells} |")
    lines.append("")
    for r in results:
        lines.append(f"Missed in drug at 5 by {r.label}: {', '.join(r.missed_in_drug) or '-'}")
    return "\n".join(lines)


def save(results: list[Result], settings: Settings) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = settings.build_dir / "eval" / f"embeddings-{stamp}.json"
    rows: list[dict[str, Any]] = [asdict(result) for result in results]
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    logger.info("results saved to %s", path)


if __name__ == "__main__":
    raise SystemExit(main())
