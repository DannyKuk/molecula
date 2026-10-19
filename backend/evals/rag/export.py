"""Pick the RAGAs questions and export the agent's answers to them for the judge (#43).

    uv run python -m evals.rag.export pick
    uv run python -m evals.rag.export answers ../data/build/eval/citations/<cache>.jsonl

`pick` writes `datasets/rag_questions.yaml`: from each section group of
`datasets/retrieval_questions.yaml`, the `PER_GROUP` questions whose id hashes lowest, so the
subset is spread over the label and doesn't follow the order the questions were written in.

`answers` reads a citation-eval cache (`evals/chat_model/citations.py`), which holds the agent's
answer to every retrieval question, and writes one sample per picked question to
data/build/eval/rag/<cache name>.samples.jsonl: the question, the answer and its contexts, every
label passage the answer's searches returned, headed by its number, label and section. The judge
(`evals/rag/judge.py`) reads that file in its own environment, so nothing here needs RAGAs.
"""

import argparse
import hashlib
from pathlib import Path
from typing import Any

import yaml
from evals.chat_model.citations import Answer, read_cache
from evals.retrieval.dataset import Question, load_questions
from pydantic import BaseModel, ConfigDict

from molecula.config import get_settings
from molecula.store.labels import SectionGroup

SUBSET = Path(__file__).resolve().parents[1] / "datasets" / "rag_questions.yaml"
PER_GROUP = 3
HEADER = (
    "# The retrieval questions the RAGAs eval judges answers to (#43), written by\n"
    "# `python -m evals.rag.export pick`: from each section group of retrieval_questions.yaml,\n"
    f"# the {PER_GROUP} whose id has the lowest SHA-256, in the order of that file.\n"
)


class Sample(BaseModel):
    """One answer as the judge reads it. `contexts` is empty when the agent searched nothing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    drug: str
    section_group: SectionGroup
    answer: str
    contexts: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pick", help=f"write {SUBSET.name}")
    answers = commands.add_parser("answers", help="export a citation-eval cache for the judge")
    answers.add_argument("cache", type=Path, help="a .jsonl file in data/build/eval/citations/")
    args = parser.parse_args()

    questions = load_questions()
    if args.command == "pick":
        ids = [question.id for question in pick(questions)]
        SUBSET.write_text(HEADER + yaml.safe_dump(ids, sort_keys=False), encoding="utf-8")
        print(f"{len(ids)} questions in {SUBSET}")
        return 0
    picked = subset(questions, yaml.safe_load(SUBSET.read_text("utf-8")))
    output = get_settings().build_dir / "eval" / "rag" / f"{args.cache.stem}.samples.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    found = samples(picked, read_cache(args.cache))
    output.write_text("".join(s.model_dump_json() + "\n" for s in found), encoding="utf-8")
    print(f"{len(found)} samples in {output}")
    return 0


def pick(questions: list[Question], per_group: int = PER_GROUP) -> list[Question]:
    def rank(question: Question) -> str:
        return hashlib.sha256(question.id.encode()).hexdigest()

    chosen: set[str] = set()
    for group in {question.section_group for question in questions}:
        in_group = sorted((q for q in questions if q.section_group == group), key=rank)
        chosen.update(question.id for question in in_group[:per_group])
    return [question for question in questions if question.id in chosen]


def subset(questions: list[Question], ids: list[str]) -> list[Question]:
    by_id = {question.id: question for question in questions}
    missing = [question_id for question_id in ids if question_id not in by_id]
    if missing:
        raise ValueError(f"{SUBSET.name} names questions that aren't in the dataset: {missing}")
    return [by_id[question_id] for question_id in ids]


def samples(questions: list[Question], answers: dict[str, Answer]) -> list[Sample]:
    missing = [question.id for question in questions if question.id not in answers]
    if missing:
        raise ValueError(f"The cache has no answer to: {missing}")
    return [sample(question, answers[question.id].events) for question in questions]


def sample(question: Question, events: list[dict[str, Any]]) -> Sample:
    passages = {
        passage["id"]: context(passage)
        for event in events
        if event["type"] == "tool_result" and event["name"] == "search_labels"
        if isinstance(event["result"], dict)
        for passage in event["result"].get("passages", [])
    }
    return Sample(
        id=question.id,
        question=question.question,
        drug=question.drug,
        section_group=question.section_group,
        answer="".join(e["text"] for e in events if e["type"] == "token").strip(),
        contexts=list(passages.values()),
    )


def context(passage: dict[str, Any]) -> str:
    """A passage with the number, label and section the agent read next to its text: without
    them the judge can't tell which product a passage is about or what `[1]` cites."""
    brand, substance = passage["brand"], passage["substance"]
    label = f"{brand} ({substance})" if brand else substance
    return f"[{passage['ref']}] {label}, {passage['section']}: {passage['text']}"


if __name__ == "__main__":
    raise SystemExit(main())
