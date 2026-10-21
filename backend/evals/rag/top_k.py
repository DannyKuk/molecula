"""Compare how often the label search returns the answer at several `top_k` (#43).

    OFFLINE=1 uv run python -m evals.rag.top_k ../data/build/eval/citations/<cache>.jsonl

Replays every label search the agent made in a citation-eval cache: the search text and the
checked filter from each retrieval trace go through `LabelRetriever` again at each `top_k`, the
other retrieval settings as configured, with no model call. A question is answered when a kept
chunk of one of its searches belongs to its drug and holds its evidence, as in the citation and
embedding evals. The replay at the configured `top_k` must return the chunks the trace recorded,
which shows the store and index are the ones the answers were made with.

The answer key was pooled from the top 5 chunks of the compared embedding models, so a chunk at
rank 6 to 10 that states the answer in other words isn't counted: recall at a larger `top_k` is a
lower bound.
"""

import argparse
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from evals.chat_model.citations import read_cache
from evals.retrieval.dataset import Question, load_questions

from molecula.config import get_settings
from molecula.main import open_label_index
from molecula.rag.embeddings import get_embeddings
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import LabelFilter, Retrieval, RetrievedChunk
from molecula.store.keywords import KeywordIndex

TOP_KS = (5, 10)


class Retriever(Protocol):
    def retrieve(self, question: str, label_filter: LabelFilter | None = None) -> Retrieval: ...


@dataclass(frozen=True)
class Search:
    question_id: str
    text: str
    filter: LabelFilter | None
    kept: list[str]


@dataclass(frozen=True)
class Replayed:
    top_k: int
    answered: int
    questions: int
    chunks_per_search: float
    characters_per_search: float


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cache", type=Path, help="a .jsonl file in data/build/eval/citations/")
    parser.add_argument("--top-k", type=int, nargs="+", default=list(TOP_KS))
    args = parser.parse_args()

    settings = get_settings()
    questions = load_questions()
    answers = read_cache(args.cache)
    searches = [
        search
        for q in questions
        if q.id in answers
        for search in traced(q.id, answers[q.id].events)
    ]
    index = open_label_index(settings)
    if index is None:
        raise SystemExit("Build the label index first.")
    embeddings = get_embeddings(settings)

    def retriever(top_k: int) -> LabelRetriever:
        return LabelRetriever(
            index,
            embeddings,
            top_k=top_k,
            min_score=settings.retrieval_min_score,
            section_group_boost=settings.section_group_boost,
            mode=settings.retrieval_mode,
            keywords=KeywordIndex(settings.keyword_index_path),
        )

    # The cached answers were made with the embeddings alone; another mode returns other chunks.
    if settings.retrieval_mode == "dense":
        check_replay(searches, retriever(settings.retrieval_top_k), settings.retrieval_top_k)
    asked = [q for q in questions if q.id in answers]
    results = [replay(asked, searches, retriever(top_k), top_k) for top_k in args.top_k]
    print(report(results, len(searches)))
    return 0


def traced(question_id: str, events: list[dict[str, Any]]) -> list[Search]:
    return [
        Search(
            question_id=question_id,
            text=event["question"],
            filter=LabelFilter.model_validate(event["filter"]) if event["filter"] else None,
            kept=[chunk["id"] for chunk in event["candidates"] if chunk["kept"]],
        )
        for event in events
        if event["type"] == "retrieval_trace"
    ]


def check_replay(searches: list[Search], retriever: Retriever, top_k: int) -> None:
    differ = [s for s in searches if ids(retriever.retrieve(s.text, s.filter).chunks) != s.kept]
    if differ:
        raise SystemExit(
            f"{len(differ)} of {len(searches)} searches return other chunks at top_k {top_k} "
            f"than the cache recorded (first: {differ[0].question_id}):"
            " the store, the index or the retrieval settings changed since the answers were made."
        )


def replay(
    questions: list[Question], searches: list[Search], retriever: Retriever, top_k: int
) -> Replayed:
    found = [(s, retriever.retrieve(s.text, s.filter).chunks) for s in searches]
    by_question = {question.id: question for question in questions}
    answered = {
        search.question_id
        for search, chunks in found
        if any(holds_answer(by_question[search.question_id], chunk) for chunk in chunks)
    }
    return Replayed(
        top_k=top_k,
        answered=len(answered),
        questions=len(questions),
        chunks_per_search=statistics.fmean(len(chunks) for _, chunks in found),
        characters_per_search=statistics.fmean(
            sum(len(chunk.text) for chunk in chunks) for _, chunks in found
        ),
    )


def holds_answer(question: Question, chunk: RetrievedChunk) -> bool:
    return chunk.cid == question.cid and any(p in chunk.text for p in question.passages)


def ids(chunks: list[RetrievedChunk]) -> list[str]:
    return [chunk.id for chunk in chunks]


def report(results: list[Replayed], searches: int) -> str:
    lines = [
        f"{searches} label searches replayed",
        "",
        "| top_k | Answer returned | Chunks per search | Characters per search |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.top_k} | {r.answered}/{r.questions} ({r.answered / r.questions:.2f}) "
            f"| {r.chunks_per_search:.1f} | {r.characters_per_search:,.0f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
