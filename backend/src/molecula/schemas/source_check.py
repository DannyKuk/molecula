from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from molecula.schemas.chat import ToolResultEvent, Usage
from molecula.schemas.claims import CheckedClaim, ClaimLabel


class CheckedAnswer(BaseModel):
    """Every claim of an answer with its verdict, in the answer's order."""

    model_config = ConfigDict(frozen=True)

    claims: list[CheckedClaim]
    usage: Usage = Field(default_factory=Usage)

    @property
    def passed(self) -> bool:
        return all(claim.label != "unsupported" for claim in self.claims)


class SourceCheckFailed(Exception):
    """The check couldn't judge the answer."""


class SourceCheck(Protocol):
    async def check(self, answer: str, results: Sequence[ToolResultEvent]) -> CheckedAnswer:
        """Splits the answer into claims and judges each against the tool results it cites,
        then against the others. Raises SourceCheckFailed when it can't."""
        ...


class ClaimJudgement(BaseModel):
    # No docstrings here: pydantic would send them to the model as the schema's description,
    # and the instructions for these fields live in prompts/guard/source_check.md.
    model_config = ConfigDict(frozen=True)

    id: int
    reason: str
    verdict: ClaimLabel
    held_by: list[int] = []


class ClaimJudgements(BaseModel):
    model_config = ConfigDict(frozen=True)

    judgements: list[ClaimJudgement]
