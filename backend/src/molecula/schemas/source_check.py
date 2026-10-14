from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from molecula.schemas.chat import ToolResultEvent, Usage

type ClaimLabel = Literal["not_a_claim", "supported", "unsupported"]


class Claim(BaseModel):
    """A part of an answer judged as one: a sentence, or a list or table under one citation.
    `refs` are the numbers it cites, as `[n]` or `【n】`."""

    model_config = ConfigDict(frozen=True)

    text: str
    refs: tuple[int, ...] = ()


class CheckedClaim(Claim):
    """A claim and the check's verdict on it: `supported` when the results it cites hold it,
    `not_a_claim` when it states nothing about a drug.

    `decided_by` says where the verdict comes from: the model, with its `reason`;
    `unknown_refs` for a claim whose refs no tool returned; `no_verdict` when the model gave
    none for it. Both of those are `unsupported` without a reason.
    """

    label: ClaimLabel
    decided_by: Literal["model", "unknown_refs", "no_verdict"]
    reason: str = ""


class CheckedAnswer(BaseModel):
    """Every claim of an answer with its verdict, in the answer's order."""

    model_config = ConfigDict(frozen=True)

    claims: list[CheckedClaim]
    usage: Usage = Field(default_factory=Usage)

    @property
    def passed(self) -> bool:
        return all(claim.label != "unsupported" for claim in self.claims)


class SourceCheck(Protocol):
    async def check(self, answer: str, results: Sequence[ToolResultEvent]) -> CheckedAnswer:
        """Splits the answer into claims and judges each against the tool results it cites."""
        ...


class ClaimJudgement(BaseModel):
    # No docstrings here: pydantic would send them to the model as the schema's description,
    # and the instructions for these fields live in prompts/guard/source_check.md.
    model_config = ConfigDict(frozen=True)

    id: int
    reason: str
    verdict: ClaimLabel


class ClaimJudgements(BaseModel):
    model_config = ConfigDict(frozen=True)

    judgements: list[ClaimJudgement]
