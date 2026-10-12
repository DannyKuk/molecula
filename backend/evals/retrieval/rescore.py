"""Score a saved comparison run again against the current answer key, embedding nothing.

    OFFLINE=1 uv run python -m evals.retrieval.rescore ../data/build/eval/embeddings-<stamp>.json

The run keeps every question's top chunks per model; their texts come from the store, so the
store must hold the same chunks as when the run was made. Prints the same report as the run.
"""

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

from evals.retrieval.compare_embeddings import (
    QuestionResult,
    Result,
    Retrieved,
    first_hit_rank,
    label_chunks,
    report,
    scored,
)
from evals.retrieval.dataset import Question, load_questions

from molecula.config import get_settings
from molecula.store.index import Chunk


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=Path, help="a results file the comparison saved")
    args = parser.parse_args()

    run = json.loads(args.run.read_text(encoding="utf-8"))
    chunks = {chunk.id: chunk for chunk in label_chunks(get_settings())}
    questions = load_questions()
    saved_ids = [question["id"] for question in run["questions"]]
    if saved_ids != [question.id for question in questions]:
        print("The run was made with other questions; scoring needs the same set.", file=sys.stderr)
        return 1
    missing = {
        retrieved["chunk"]
        for row in run["results"]
        for question in row["questions"]
        for retrieved in question["top_in_drug"] + question["top_whole_index"]
        if retrieved["chunk"] not in chunks
    }
    if missing:
        print(f"{len(missing)} chunks of the run are not in the store.", file=sys.stderr)
        return 1

    results = [rescored(row, questions, chunks) for row in run["results"]]
    print(report(results, questions))
    return 0


def rescored(row: dict[str, Any], questions: list[Question], chunks: dict[str, Chunk]) -> Result:
    per_question = [
        question_result(question, saved, chunks)
        for question, saved in zip(questions, row["questions"], strict=True)
    ]
    kept = {f.name: row[f.name] for f in fields(Result)} | scored(questions, per_question)
    return Result(**kept)


def question_result(
    question: Question, saved: dict[str, Any], chunks: dict[str, Chunk]
) -> QuestionResult:
    in_drug = [Retrieved(**retrieved) for retrieved in saved["top_in_drug"]]
    whole_index = [Retrieved(**retrieved) for retrieved in saved["top_whole_index"]]
    return QuestionResult(
        id=question.id,
        query_ms=saved["query_ms"],
        rank_in_drug=first_hit_rank(question, [chunks[r.chunk] for r in in_drug]),
        rank_whole_index=first_hit_rank(question, [chunks[r.chunk] for r in whole_index]),
        top_in_drug=in_drug,
        top_whole_index=whole_index,
    )


if __name__ == "__main__":
    sys.exit(main())
