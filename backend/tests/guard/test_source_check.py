import asyncio
import json
from typing import Any

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, SystemMessage

from fake_llm import DEFAULT_COST, ScriptedChatModel, answer_message, tool_call_message
from molecula import prompts
from molecula.guard.safety import fixed_answer
from molecula.guard.source_check import ChatModelSourceCheck, cited_sources
from molecula.schemas.chat import ToolResultEvent
from molecula.schemas.claims import CheckedClaim
from molecula.schemas.source_check import CheckedAnswer, SourceCheckFailed
from molecula.schemas.usage import Usage

PASSAGE = {
    "id": "set-1:adverse_reactions:0",
    "text": "The most common adverse reaction is headache.",
    "score": 0.61,
    "substance": "ONDANSETRON",
    "brand": "Zofran",
    "section": "adverse_reactions",
    "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set-1",
    "ref": 1,
}
LABEL_SEARCH = ToolResultEvent(
    id="call_1", name="search_labels", status="found", result={"passages": [PASSAGE]}
)
TARGETS = ToolResultEvent(
    id="call_2",
    name="get_targets",
    status="found",
    result={
        "status": "found",
        "name": "metamizole",
        "targets": [
            {
                "name": "Cyclooxygenase",
                "mechanism": "Cyclooxygenase inhibitor",
                "source_url": "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL2094253",
                "ref": 2,
            }
        ],
    },
)


def judged(*judgements: tuple[int, str] | tuple[int, str, list[int]]) -> AIMessage:
    """The model's verdicts: (claim, verdict) or (claim, verdict, the refs that hold it)."""
    return tool_call_message(
        "ClaimJudgements",
        {
            "judgements": [
                {
                    "id": judgement[0],
                    "reason": f"Because of claim {judgement[0]}.",
                    "verdict": judgement[1],
                    "held_by": list(judgement[2]) if len(judgement) == 3 else [],
                }
                for judgement in judgements
            ]
        },
    )


def check(
    answer: str, *script: Any, results: list[ToolResultEvent] | None = None
) -> tuple[CheckedAnswer, ScriptedChatModel]:
    model = ScriptedChatModel(script=list(script))
    source_check = ChatModelSourceCheck(model)
    checked = asyncio.run(source_check.check(answer, results or [LABEL_SEARCH, TARGETS]))
    return checked, model


def sent(model: ScriptedChatModel) -> dict[str, Any]:
    return json.loads(str(model.received[0][1].content))


def test_a_claim_its_source_holds_is_supported() -> None:
    checked, _ = check(
        "Headache is a common side effect of ondansetron [1].", judged((1, "supported"))
    )

    assert checked.claims == [
        CheckedClaim(
            text="Headache is a common side effect of ondansetron [1].",
            refs=(1,),
            label="supported",
            decided_by="model",
            reason="Because of claim 1.",
        )
    ]
    assert checked.passed


def test_a_claim_its_source_doesnt_hold_fails_the_answer() -> None:
    answer = "Headache is common [1]. Ondansetron blocks serotonin receptors [1]."

    checked, _ = check(answer, judged((1, "supported"), (2, "unsupported")))

    assert [claim.label for claim in checked.claims] == ["supported", "unsupported"]
    assert not checked.passed


def test_a_sentence_without_a_fact_is_not_a_claim_and_doesnt_fail_the_answer() -> None:
    checked, model = check("Ask your pharmacist if you are unsure.", judged((1, "not_a_claim")))

    assert checked.claims[0].label == "not_a_claim"
    assert checked.passed
    assert sent(model)["claims"] == [
        {"id": 1, "text": "Ask your pharmacist if you are unsure.", "refs": []}
    ]


def test_a_claim_citing_only_refs_no_tool_returned_is_unsupported_without_a_model_call() -> None:
    checked, model = check("Ondansetron is used after chemotherapy [7].")

    assert checked.claims[0].label == "unsupported"
    assert checked.claims[0].decided_by == "unknown_refs"
    assert model.received == []
    assert checked.usage == Usage()


def test_only_claims_with_a_returned_ref_or_none_reach_the_model() -> None:
    answer = "It is used after chemotherapy [7]. Headache is common [1]. Ask a doctor."

    checked, model = check(answer, judged((2, "supported"), (3, "not_a_claim")))

    assert [claim["id"] for claim in sent(model)["claims"]] == [2, 3]
    assert [claim.decided_by for claim in checked.claims] == ["unknown_refs", "model", "model"]


def test_a_provider_error_fails_the_check() -> None:
    timeout = openai.APITimeoutError(request=httpx.Request("POST", "http://llm.test/chat"))

    with pytest.raises(SourceCheckFailed):
        check("Headache is common [1].", timeout)


def test_a_malformed_verdict_makes_every_claim_unsupported() -> None:
    checked, _ = check("Headache is common [1].", answer_message("Looks fine to me."))

    assert [(c.label, c.decided_by) for c in checked.claims] == [("unsupported", "no_verdict")]


def test_a_claim_the_model_skipped_is_unsupported() -> None:
    answer = "Headache is common [1]. Metamizole inhibits cyclooxygenase [2]."

    checked, _ = check(answer, judged((1, "supported"), (9, "supported")))

    assert [(c.label, c.decided_by) for c in checked.claims] == [
        ("supported", "model"),
        ("unsupported", "no_verdict"),
    ]


def test_the_model_reads_the_prompt_and_every_returned_source_as_data() -> None:
    _, model = check("Metamizole inhibits cyclooxygenase [2].", judged((1, "supported")))

    assert model.received[0][0] == SystemMessage(prompts.load("guard/source_check"))
    assert sent(model)["sources"] == [
        {
            "ref": 1,
            "text": "The most common adverse reaction is headache.",
            "substance": "ONDANSETRON",
            "brand": "Zofran",
            "section": "adverse_reactions",
        },
        {
            "ref": 2,
            "name": "Cyclooxygenase",
            "mechanism": "Cyclooxygenase inhibitor",
            "drug": "metamizole",
        },
    ]


def test_a_fact_another_returned_source_holds_is_held_elsewhere_and_passes() -> None:
    checked, _ = check(
        "Metamizole inhibits cyclooxygenase [1].", judged((1, "held_elsewhere", [2]))
    )

    assert checked.claims == [
        CheckedClaim(
            text="Metamizole inhibits cyclooxygenase [1].",
            refs=(1,),
            label="held_elsewhere",
            decided_by="model",
            reason="Because of claim 1.",
            held_by=(2,),
        )
    ]
    assert checked.passed


def test_an_uncited_fact_a_returned_source_holds_is_held_elsewhere() -> None:
    checked, _ = check("Headache is common.", judged((1, "held_elsewhere", [1])))

    assert [(c.label, c.held_by) for c in checked.claims] == [("held_elsewhere", (1,))]


def test_held_by_keeps_only_returned_refs_the_claim_doesnt_cite() -> None:
    answer = "Headache is common [1]. Metamizole inhibits cyclooxygenase. It is cheap [1]."

    checked, _ = check(
        answer,
        judged(
            (1, "held_elsewhere", [1, 2, 9]),
            (2, "held_elsewhere", [9]),
            (3, "held_elsewhere", [1]),
        ),
    )

    assert [(c.label, c.held_by) for c in checked.claims] == [
        ("held_elsewhere", (2,)),
        ("unsupported", ()),
        ("supported", ()),
    ]


def test_held_by_is_ignored_unless_the_fact_is_held_elsewhere() -> None:
    checked, _ = check(
        "Headache is common [1]. Ondansetron is cheap [1].",
        judged((1, "supported", [2]), (2, "unsupported", [2])),
    )

    assert [(c.label, c.held_by) for c in checked.claims] == [
        ("supported", ()),
        ("unsupported", ()),
    ]


def test_the_guards_emergency_line_is_not_judged() -> None:
    answer = f"{fixed_answer('overdose_emergency')}\n\nHeadache is common [1]."

    checked, _ = check(answer, judged((1, "supported")))

    assert [claim.text for claim in checked.claims] == ["Headache is common [1]."]


def test_the_check_carries_the_models_token_usage() -> None:
    checked, _ = check("Headache is common [1].", judged((1, "supported")))

    assert checked.usage == Usage(
        input_tokens=12, output_tokens=8, total_tokens=20, cost_usd=DEFAULT_COST
    )


def test_an_answer_without_claims_passes_without_a_model_call() -> None:
    checked, model = check("")

    assert checked.claims == []
    assert checked.passed
    assert model.received == []


def test_cited_sources_drop_ids_links_and_scores() -> None:
    assert cited_sources([LABEL_SEARCH.result]) == {
        1: {
            "text": "The most common adverse reaction is headache.",
            "substance": "ONDANSETRON",
            "brand": "Zofran",
            "section": "adverse_reactions",
        }
    }
