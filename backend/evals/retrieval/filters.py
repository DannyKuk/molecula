"""Measure what the label filter (#13) does for retrieval, with the answer key's filters.

    OFFLINE=1 uv run python -m evals.retrieval.filters

Runs every retrieval question through `LabelRetriever` on the built index three times: over the
whole index, filtered to the question's drug, and filtered to the drug and the question's section
group. That is the ceiling of filter extraction: a chat model that extracts the right filter gets
these numbers. Also reports the scores of the answering chunks and of the best chunk that doesn't
answer, which the score threshold (`retrieval_min_score`) is chosen from. No chat model runs.
"""

import statistics
from collections import defaultdict

from evals.retrieval.dataset import Question, is_hit, load_questions

from molecula.config import get_settings
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import Chunk, DrugFilter, LabelFilter, LabelQuery, RetrievedChunk
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex

TOP_K = 10
SETUPS = ["whole index", "drug", "drug + section group"]


def main() -> int:
    settings = get_settings()
    index = LabelIndex(settings.index_dir)
    index.check_model(embedding_model_id(settings))
    retriever = LabelRetriever(
        index,
        get_embeddings(settings),
        top_k=TOP_K,
        min_score=-1.0,
        section_group_boost=settings.section_group_boost,
        mode=settings.retrieval_mode,
        keywords=KeywordIndex(settings.keyword_index_path),
    )
    set_ids = labels_by_drug(index.chunks())
    questions = load_questions()

    ranks: dict[str, list[int | None]] = defaultdict(list)
    hit_scores: list[float] = []
    miss_scores: list[float] = []
    for question in questions:
        for setup in SETUPS:
            found = retriever.retrieve(question.question, gold_filter(question, setup, set_ids))
            ranks[setup].append(first_hit_rank(question, found.chunks))
            if setup == "drug + section group":
                hit_scores += [c.score for c in found.chunks if is_hit(question, c)]
                misses = [c.score for c in found.chunks if not is_hit(question, c)]
                miss_scores += misses[:1]

    print(f"{len(questions)} questions, {embedding_model_id(settings)}, top {TOP_K}\n")
    print("| Search | recall@1 | recall@5 | MRR@10 |")
    print("|---|---|---|---|")
    for setup in SETUPS:
        print(
            f"| {setup} | {recall(ranks[setup], 1):.2f} | {recall(ranks[setup], 5):.2f} "
            f"| {mrr(ranks[setup]):.3f} |"
        )
    print("\nCosine similarity, drug + section group:")
    print(f"- chunks that answer: {spread(hit_scores)}")
    print(f"- best chunk that doesn't answer: {spread(miss_scores)}")
    return 0


def labels_by_drug(chunks: list[Chunk]) -> dict[int, list[str]]:
    by_drug: dict[int, list[str]] = defaultdict(list)
    for chunk in chunks:
        if chunk.set_id not in by_drug[chunk.cid]:
            by_drug[chunk.cid].append(chunk.set_id)
    return by_drug


def gold_filter(
    question: Question, setup: str, set_ids: dict[int, list[str]]
) -> LabelFilter | None:
    if setup == "whole index":
        return None
    drug = DrugFilter(
        name=question.drug, cid=question.cid, generic=question.drug, set_ids=set_ids[question.cid]
    )
    groups = [question.section_group] if setup == "drug + section group" else []
    return LabelFilter(extracted=LabelQuery(), drugs=[drug], section_groups=groups)


def first_hit_rank(question: Question, found: list[RetrievedChunk]) -> int | None:
    for rank, chunk in enumerate(found, start=1):
        if is_hit(question, chunk):
            return rank
    return None


def recall(ranks: list[int | None], k: int) -> float:
    return sum(rank is not None and rank <= k for rank in ranks) / len(ranks)


def mrr(ranks: list[int | None]) -> float:
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)


def spread(scores: list[float]) -> str:
    low, q1, median, q3, high = (
        min(scores),
        *statistics.quantiles(scores, n=4),
        max(scores),
    )
    return f"min {low:.3f}, quartiles {q1:.3f} / {median:.3f} / {q3:.3f}, max {high:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
