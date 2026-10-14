from typing import Literal

from pydantic import BaseModel, ConfigDict

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
