import json
from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from molecula import prompts
from molecula.guard.claims import split_claims
from molecula.guard.safety import fixed_answer, usage_of
from molecula.schemas.chat import ToolResultEvent, Usage
from molecula.schemas.source_check import (
    CheckedAnswer,
    CheckedClaim,
    Claim,
    ClaimJudgement,
    ClaimJudgements,
)

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
    per answer. Provider errors are raised as they come, like the input check's."""

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
                judgement = judgements[number]
                checked.append(
                    CheckedClaim(
                        **claim.model_dump(),
                        label=judgement.verdict,
                        decided_by="model",
                        reason=judgement.reason,
                    )
                )
        return CheckedAnswer(claims=checked, usage=usage)

    async def _judge(
        self, claims: dict[int, Claim], sources: dict[int, dict[str, Any]]
    ) -> tuple[dict[int, ClaimJudgement], Usage]:
        cited = sorted({ref for claim in claims.values() for ref in claim.refs if ref in sources})
        data = {
            "sources": [{"ref": ref, **sources[ref]} for ref in cited],
            "claims": [
                {"id": number, "text": claim.text, "refs": list(claim.refs)}
                for number, claim in claims.items()
            ],
        }
        structured = self._model.with_structured_output(ClaimJudgements, include_raw=True)
        # The answer and the results go in their own message, never into the prompt: the
        # results hold label text, which is untrusted.
        result = await structured.ainvoke(
            [
                SystemMessage(prompts.load("guard/source_check")),
                HumanMessage(json.dumps(data, ensure_ascii=False)),
            ]
        )
        usage = usage_of(result["raw"])
        parsed = result["parsed"]
        if not isinstance(parsed, ClaimJudgements):
            return {}, usage
        judgements: dict[int, ClaimJudgement] = {}
        for judgement in parsed.judgements:
            if judgement.id in claims:
                judgements.setdefault(judgement.id, judgement)
        return judgements, usage


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
