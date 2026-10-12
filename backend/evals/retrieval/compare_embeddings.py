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
import os
import platform
import statistics
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Literal, Protocol

import numpy as np
from evals.retrieval.candidates import CANDIDATES, Candidate
from evals.retrieval.dataset import DATASET, Question, is_hit, load_questions, unanswerable

from molecula.config import Settings, get_settings
from molecula.ingest.index import stored_labels
from molecula.rag.chunking import CHUNK_TOKENS, OVERLAP_TOKENS, chunk_labels
from molecula.rag.embeddings import get_embeddings, load_chunk_tokenizer
from molecula.store.index import Chunk, LabelIndex

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

TOP_K = 10
# Chunks a run keeps the text of, for showing what each model found.
SHOWN_K = 5
WARMUP_QUERIES = 3
# Small enough that Qwen3-8B (16 GB in fp16) stays inside a 24 GB GPU with 500-token chunks;
# 16 spilled into shared memory and slowed it down. The same for every local model, so their
# embedding times compare.
EMBED_BATCH = 8
CLOUD_BATCH = 64

type Device = Literal["auto", "cpu"]


@dataclass(frozen=True)
class Scores:
    recall_at_1: float
    recall_at_5: float
    mrr_at_10: float


@dataclass(frozen=True)
class Retrieved:
    chunk: str
    score: float


@dataclass(frozen=True)
class QuestionResult:
    id: str
    query_ms: float
    rank_in_drug: int | None
    rank_whole_index: int | None
    top_in_drug: list[Retrieved]
    top_whole_index: list[Retrieved]


@dataclass(frozen=True)
class Result:
    label: str
    model: str
    dimensions: int
    build_device: str
    build_seconds: float
    build_vram_peak_gb: float | None
    query_device: str
    index_mb: float
    query_ms_p50: float
    query_ms_p95: float
    in_drug: Scores
    whole_index: Scores
    recall_at_5_by_group: dict[str, float]
    missed_in_drug: list[str]
    questions: list[QuestionResult]


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

    results = []
    for candidate in candidates:
        results.append(evaluate(candidate, chunks, questions, settings, args.device))
        free_gpu_memory()
    print(report(results, questions))
    save(results, questions, chunks, settings, args.device)
    return 0


def free_gpu_memory() -> None:
    """Release the last model before the next loads. On Windows a model that no longer fits in
    VRAM spills into shared system memory: Qwen3-8B after the smaller models ran ~25x slower."""
    import gc

    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


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
    build = document_vectors(candidate, embedder, chunks, settings)
    documents = build.vectors
    queries, latencies = query_vectors(candidate, embedder, questions)
    scores = queries @ documents.T
    cids = np.array([chunk.cid for chunk in chunks])

    per_question = [
        question_result(question, row, latency, chunks, cids == question.cid)
        for question, row, latency in zip(questions, scores, latencies, strict=True)
    ]
    return Result(
        label=candidate.label,
        model=candidate.model,
        dimensions=documents.shape[1],
        build_device=build.device,
        build_seconds=build.seconds,
        build_vram_peak_gb=build.vram_peak_gb,
        query_device=embedder.device,
        index_mb=index_size_mb(chunks, documents, candidate.model),
        query_ms_p50=statistics.median(latencies),
        query_ms_p95=statistics.quantiles(latencies, n=20)[-1],
        **scored(questions, per_question),
    )


def scored(questions: list[Question], per_question: list[QuestionResult]) -> dict[str, Any]:
    """The Result fields that follow from the ranks, so a saved run can be scored again."""
    in_drug = [result.rank_in_drug for result in per_question]
    anywhere = [result.rank_whole_index for result in per_question]
    by_group: dict[str, list[int | None]] = defaultdict(list)
    for question, rank in zip(questions, in_drug, strict=True):
        by_group[question.section_group].append(rank)
    return {
        "in_drug": summarize(in_drug),
        "whole_index": summarize(anywhere),
        "recall_at_5_by_group": {
            group: recall(ranks, 5) for group, ranks in sorted(by_group.items())
        },
        "missed_in_drug": [
            q.id for q, rank in zip(questions, in_drug, strict=True) if rank is None or rank > 5
        ],
        "questions": per_question,
    }


def question_result(
    question: Question, scores: np.ndarray, latency: float, chunks: list[Chunk], own: np.ndarray
) -> QuestionResult:
    in_drug = top_k(np.where(own, scores, -np.inf))
    whole_index = top_k(scores)
    return QuestionResult(
        id=question.id,
        query_ms=latency,
        rank_in_drug=first_hit_rank(question, [chunks[i] for i in in_drug]),
        rank_whole_index=first_hit_rank(question, [chunks[i] for i in whole_index]),
        top_in_drug=[Retrieved(chunks[i].id, float(scores[i])) for i in in_drug],
        top_whole_index=[Retrieved(chunks[i].id, float(scores[i])) for i in whole_index],
    )


def top_k(scores: np.ndarray) -> list[int]:
    """Positions of the TOP_K best chunks; chunks scored -inf (other drugs) are left out."""
    best = np.argsort(-scores)[:TOP_K]
    return [int(i) for i in best if np.isfinite(scores[i])]


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

    # As in the app's loader: no second, converted copy of weights published only as .bin.
    os.environ.setdefault("DISABLE_SAFETENSORS_CONVERSION", "true")
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


@dataclass(frozen=True)
class Build:
    vectors: np.ndarray
    seconds: float
    device: str
    vram_peak_gb: float | None


def document_vectors(
    candidate: Candidate, embedder: Embedder, chunks: list[Chunk], settings: Settings
) -> Build:
    """The chunks' vectors with how long embedding them took, where, and the GPU memory it
    peaked at, from the cache when the model, prefix and chunks are unchanged."""
    texts = [candidate.document_prefix + chunk.text for chunk in chunks]
    key = hashlib.sha256("\n".join([candidate.model, *texts]).encode()).hexdigest()[:16]
    cache = settings.build_dir / "eval" / "vectors" / f"{key}.npz"
    if cache.exists():
        cached = np.load(cache)
        logger.info("  document vectors from %s", cache)
        peak = float(cached["vram_peak_gb"])
        return Build(
            vectors=cached["vectors"],
            seconds=float(cached["seconds"]),
            device=str(cached["device"]),
            vram_peak_gb=None if np.isnan(peak) else peak,
        )

    reset_vram_peak()
    started = perf_counter()
    vectors = embedder.documents(texts).astype(np.float32)
    seconds = perf_counter() - started
    peak = vram_peak_gb() if embedder.device.startswith("cuda") else None
    logger.info(
        "  embedded %d chunks in %.0f s on %s, peak VRAM %s GB",
        len(texts),
        seconds,
        embedder.device,
        "-" if peak is None else f"{peak:.1f}",
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        cache,
        vectors=vectors,
        seconds=seconds,
        device=embedder.device,
        vram_peak_gb=np.nan if peak is None else peak,
    )
    return Build(vectors, seconds, embedder.device, peak)


def reset_vram_peak() -> None:
    import torch

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def vram_peak_gb() -> float:
    """The most GPU memory PyTorch held during the build, weights included. Close to the card's
    size means it may have spilled into shared memory, which slows it down."""
    import torch

    return torch.cuda.max_memory_reserved() / 1e9


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


def first_hit_rank(question: Question, ranked: list[Chunk]) -> int | None:
    """The 1-based rank of the first chunk that answers the question, or None."""
    for rank, chunk in enumerate(ranked, start=1):
        if is_hit(question, chunk):
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
            f"| {r.build_seconds:.0f} ({r.build_device}"
            f"{'' if r.build_vram_peak_gb is None else f', {r.build_vram_peak_gb:.1f} GB'}) "
            f"| {r.index_mb:.1f} "
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


def save(
    results: list[Result],
    questions: list[Question],
    chunks: list[Chunk],
    settings: Settings,
    device: Device,
) -> None:
    """Everything a results page needs without re-running: the run's setup, the questions, each
    model's ranks and top chunks per question, and the text of every chunk a model ranked in its
    top SHOWN_K."""
    shown = {
        retrieved.chunk
        for result in results
        for question in result.questions
        for retrieved in question.top_in_drug[:SHOWN_K] + question.top_whole_index[:SHOWN_K]
    }
    payload: dict[str, Any] = {
        "run": run_details(chunks, device),
        "questions": [question.model_dump() for question in questions],
        "results": [asdict(result) for result in results],
        "chunks": {
            chunk.id: {"cid": chunk.cid, "section": chunk.section, "text": chunk.text}
            for chunk in chunks
            if chunk.id in shown
        },
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = settings.build_dir / "eval" / f"embeddings-{stamp}.json"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    logger.info("results saved to %s", path)


def run_details(chunks: list[Chunk], device: Device) -> dict[str, Any]:
    import torch

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "chunks": len(chunks),
        "chunk_tokens": CHUNK_TOKENS,
        "overlap_tokens": OVERLAP_TOKENS,
        "top_k": TOP_K,
        "embed_batch": EMBED_BATCH,
        "device": device,
        "cpu": platform.processor(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "torch": torch.__version__,
        "python": platform.python_version(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
