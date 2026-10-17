from typing import Any

from evals.chat_model.comparisons import Asked, ComparisonQuestion, load_questions, report


def tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_call", "id": name, "name": name, "args": args}


def asked(*events: dict[str, Any], seconds: float = 1.0) -> Asked:
    return Asked("ibuprofen-aspirin", list(events), seconds)


QUESTION = ComparisonQuestion(
    id="ibuprofen-aspirin",
    question="Compare ibuprofen and aspirin",
    drugs=["ibuprofen", "aspirin"],
    kind="comparison",
)


def test_a_label_search_or_target_lookup_is_evidence_for_the_drug_it_names() -> None:
    answer = asked(
        tool_call(
            "search_labels", {"question": "What is Ibuprofen used for?", "drug": "Ibuprofen"}
        ),
        tool_call("get_targets", {"drug": "aspirin"}),
    )

    assert answer.has_evidence_for("ibuprofen")
    assert answer.has_evidence_for("aspirin")


def test_a_3d_view_or_the_properties_are_no_evidence_for_how_a_drug_works() -> None:
    answer = asked(
        tool_call("get_complex", {"drug": "ibuprofen"}),
        tool_call("compare_drugs", {"drugs": ["ibuprofen", "aspirin"]}),
    )

    assert not answer.has_evidence_for("ibuprofen")
    assert not answer.has_evidence_for("aspirin")


def test_the_report_counts_answers_with_evidence_for_every_drug() -> None:
    both = asked(
        tool_call("search_labels", {"question": "How do ibuprofen and aspirin differ?"}),
        seconds=2.0,
    )
    one = asked(tool_call("search_labels", {"drug": "ibuprofen"}), seconds=4.0)
    failed = asked({"type": "error", "message": "no answer"}, seconds=6.0)

    line = report([QUESTION], {QUESTION.id: [both, one, failed]}).splitlines()[-1]

    assert line.startswith("| ibuprofen-aspirin | comparison | 1 of 3 | 1 | 4.0 |")


def test_the_dataset_loads_and_every_question_names_its_drugs() -> None:
    questions = load_questions()

    assert len({q.id for q in questions}) == len(questions)
    assert all(q.drugs for q in questions)
