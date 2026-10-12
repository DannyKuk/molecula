from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from molecula.store.index import Chunk
from molecula.store.labels import SectionGroup

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "retrieval_questions.yaml"


class Question(BaseModel):
    """A question about one drug and a passage of its label that answers it.

    A retrieved chunk is a hit when it belongs to the drug and contains `evidence`, so the answer
    key doesn't depend on how the labels are chunked or which section repeats the answer.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    cid: int
    drug: str
    section_group: SectionGroup
    evidence: str
    origin: Literal["hand", "sampled"]

    @field_validator("evidence")
    @classmethod
    def normalize_whitespace(cls, evidence: str) -> str:
        # The chunker collapses whitespace the same way.
        return " ".join(evidence.split())


def load_questions(path: Path = DATASET) -> list[Question]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = [Question.model_validate(entry) for entry in entries]
    duplicates = {q.id for q in questions if sum(other.id == q.id for other in questions) > 1}
    if duplicates:
        raise ValueError(f"Duplicate question ids in {path}: {sorted(duplicates)}")
    return questions


def is_hit(question: Question, chunk: Chunk) -> bool:
    return chunk.cid == question.cid and question.evidence in chunk.text


def unanswerable(questions: list[Question], chunks: list[Chunk]) -> list[Question]:
    """Questions whose evidence no single chunk of their drug contains: no model can find them."""
    return [q for q in questions if not any(is_hit(q, chunk) for chunk in chunks)]
