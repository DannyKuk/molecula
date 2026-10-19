import json
from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from molecula import prompts
from molecula.agent.llm import ChatModelError
from molecula.guard.claims import split_claims
from molecula.guard.safety import fixed_answer
from molecula.schemas.chat import ToolResultEvent
from molecula.schemas.claims import CheckedClaim, Claim
from molecula.schemas.source_check import (
    CheckedAnswer,
    ClaimJudgement,
    ClaimJudgements,
    SourceCheckFailed,
)
from molecula.schemas.usage import Usage, usage_of

# Fields of a cited result that say nothing a claim could state: ids, links, scores, flags.
UNSTATED_FIELDS = frozenset(
    {
        "id",
        "score",
        "url",
        "source_url",
        "set_id",
        "inchikey",
        "smiles",
        "accessions",
        "target_chembl_id",
        "in_section_groups",
        "conformer_source",
        "product_type",
        "sensitive",
        "effective_time",
    }
)


class ChatModelSourceCheck:
    """Judges an answer's claims by asking the chat model for `ClaimJudgements`, in one call
    per answer. A provider error is raised as SourceCheckFailed."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def check(self, answer: str, results: Sequence[ToolResultEvent]) -> CheckedAnswer:
        claims = split_claims(answer, leave_out=[fixed_answer("overdose_emergency")])
        sources = cited_sources([event.result for event in results])
        to_judge = {
            number: claim
            for number, claim in enumerate(claims, start=1)
            if not claim.refs or any(ref in sources for ref in claim.refs)
        }
        judgements, usage = await self._judge(to_judge, sources) if to_judge else ({}, Usage())
        checked = []
        for number, claim in enumerate(claims, start=1):
            if number not in to_judge:
                checked.append(_unsupported(claim, "unknown_refs"))
            elif number not in judgements:
                checked.append(_unsupported(claim, "no_verdict"))
            else:
                checked.append(_judged(claim, judgements[number], sources))
        return CheckedAnswer(claims=checked, usage=usage)

    async def _judge(
        self, claims: dict[int, Claim], sources: dict[int, dict[str, Any]]
    ) -> tuple[dict[int, ClaimJudgement], Usage]:
        data = {
            "sources": [{"ref": ref, **source} for ref, source in sorted(sources.items())],
            "claims": [
                {"id": number, "text": claim.text, "refs": list(claim.refs)}
                for number, claim in claims.items()
            ],
        }
        structured = self._model.with_structured_output(ClaimJudgements, include_raw=True)
        # The answer and the results go in their own message, never into the prompt: the
        # results hold label text, which is untrusted.
        try:
            result = await structured.ainvoke(
                [
                    SystemMessage(prompts.load("guard/source_check")),
                    HumanMessage(json.dumps(data, ensure_ascii=False)),
                ]
            )
        except ChatModelError as error:
            raise SourceCheckFailed(repr(error)) from error
        usage = usage_of(result["raw"])
        parsed = result["parsed"]
        if not isinstance(parsed, ClaimJudgements):
            return {}, usage
        judgements: dict[int, ClaimJudgement] = {}
        for judgement in parsed.judgements:
            if judgement.id in claims:
                judgements.setdefault(judgement.id, judgement)
        return judgements, usage


def _judged(claim: Claim, judgement: ClaimJudgement, sources: dict[int, Any]) -> CheckedClaim:
    """The model's verdict, with `held_by` cut to returned results the claim doesn't cite. A
    fact held only by the claim's own refs is supported; one held by no returned ref is not."""
    label = judgement.verdict
    held_by: tuple[int, ...] = ()
    if label == "held_elsewhere":
        named = [ref for ref in dict.fromkeys(judgement.held_by) if ref in sources]
        held_by = tuple(ref for ref in named if ref not in claim.refs)
        if not held_by:
            label = "supported" if named else "unsupported"
    return CheckedClaim(
        **claim.model_dump(),
        label=label,
        decided_by="model",
        reason=judgement.reason,
        held_by=held_by,
    )


def cited_sources(results: Sequence[Any]) -> dict[int, dict[str, Any]]:
    """Every result an answer can cite, by its `ref`, without the fields no claim states. A
    ChEMBL target is named with the drug it belongs to, which its parent result holds."""
    sources: dict[int, dict[str, Any]] = {}

    def visit(value: Any, drug: str | None) -> None:
        if isinstance(value, dict):
            name = value.get("name") if isinstance(value.get("name"), str) else None
            if isinstance(value.get("ref"), int):
                source = _stated(value)
                if drug is not None and "targets" not in value and "compound" not in value:
                    source.setdefault("drug", drug)
                sources.setdefault(value["ref"], source)
                return
            for child in value.values():
                visit(child, name or drug)
        elif isinstance(value, list):
            for child in value:
                visit(child, drug)

    for result in results:
        visit(result, None)
    return sources


def _stated(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _stated(child)
            for key, child in value.items()
            if key not in UNSTATED_FIELDS and key != "ref"
        }
    if isinstance(value, list):
        return [_stated(child) for child in value]
    return value


def _unsupported(claim: Claim, decided_by: Literal["unknown_refs", "no_verdict"]) -> CheckedClaim:
    return CheckedClaim(**claim.model_dump(), label="unsupported", decided_by=decided_by)
