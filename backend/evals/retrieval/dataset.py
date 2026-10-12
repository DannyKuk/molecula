from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from molecula.store.index import Chunk
from molecula.store.labels import SectionGroup

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "retrieval_questions.yaml"


class Question(BaseModel):
    """A question about one drug and the passages of its label that answer it.

    A retrieved chunk is a hit when it belongs to the drug and contains `evidence` or one of
    `pooled_evidence`, so the answer key doesn't depend on how the labels are chunked or which
    section repeats the answer. `pooled_evidence` holds passages that say the same in other words,
    found by judging the chunks the compared models ranked above the evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    cid: int
    drug: str
    section_group: SectionGroup
    evidence: str
    pooled_evidence: list[str] = []
    origin: Literal["hand", "sampled"]

    @field_validator("evidence")
    @classmethod
    def normalize_whitespace(cls, evidence: str) -> str:
        # The chunker collapses whitespace the same way.
        return " ".join(evidence.split())

    @field_validator("pooled_evidence")
    @classmethod
    def normalize_each(cls, passages: list[str]) -> list[str]:
        return [" ".join(passage.split()) for passage in passages]

    @property
    def passages(self) -> list[str]:
        return [self.evidence, *self.pooled_evidence]


def load_questions(path: Path = DATASET) -> list[Question]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = [Question.model_validate(entry) for entry in entries]
    duplicates = {q.id for q in questions if sum(other.id == q.id for other in questions) > 1}
    if duplicates:
        raise ValueError(f"Duplicate question ids in {path}: {sorted(duplicates)}")
    return questions


def is_hit(question: Question, chunk: Chunk) -> bool:
    return chunk.cid == question.cid and any(p in chunk.text for p in question.passages)


def unanswerable(questions: list[Question], chunks: list[Chunk]) -> list[Question]:
    """Questions with a passage that no single chunk of their drug contains: a typo in the key."""
    own = {q.id: [chunk.text for chunk in chunks if chunk.cid == q.cid] for q in questions}
    return [
        q for q in questions if any(not any(p in text for text in own[q.id]) for p in q.passages)
    ]
