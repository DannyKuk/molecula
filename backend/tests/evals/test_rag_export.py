from typing import Any

import pytest
from evals.chat_model.citations import Answer
from evals.rag.export import pick, sample, samples, subset
from evals.retrieval.dataset import Question


def question(id: str, section_group: str = "pharmacology") -> Question:
    return Question(
        id=id,
        question=f"Question {id}?",
        cid=5291,
        drug="imatinib",
        section_group=section_group,
        evidence="inhibits the BCR-ABL tyrosine kinase",
        origin="hand",
    )


def passage(id: str, ref: int, text: str, brand: str | None = "Gleevec") -> dict[str, Any]:
    return {
        "ref": ref,
        "id": id,
        "text": text,
        "cid": 5291,
        "substance": "IMATINIB MESYLATE",
        "brand": brand,
        "section": "mechanism_of_action",
    }


def search(*passages: dict[str, Any]) -> list[dict[str, Any]]:
    result = {"status": "found", "passages": list(passages)}
    return [
        {"type": "tool_call", "id": "a", "name": "search_labels", "args": {}},
        {"type": "tool_result", "id": "a", "name": "search_labels", "result": result},
    ]


def tokens(*texts: str) -> list[dict[str, Any]]:
    return [{"type": "token", "text": text} for text in texts]


def test_pick_takes_the_same_number_from_every_section_group_in_dataset_order() -> None:
    questions = [question(f"p{n}") for n in range(5)] + [
        question(f"d{n}", "dosing") for n in range(5)
    ]

    picked = pick(questions, per_group=2)

    assert [q.section_group for q in picked].count("pharmacology") == 2
    assert [q.section_group for q in picked].count("dosing") == 2
    assert picked == [q for q in questions if q in picked]


def test_pick_does_not_depend_on_the_order_of_the_dataset() -> None:
    questions = [question(f"p{n}") for n in range(6)]

    forward = {q.id for q in pick(questions, per_group=3)}
    backward = {q.id for q in pick(questions[::-1], per_group=3)}

    assert forward == backward


def test_pick_keeps_a_small_group_whole() -> None:
    questions = [question("p0"), question("o0", "otc_consumer")]

    assert pick(questions, per_group=3) == questions


def test_subset_keeps_the_order_of_the_ids() -> None:
    questions = [question("a"), question("b")]

    assert [q.id for q in subset(questions, ["b", "a"])] == ["b", "a"]


def test_subset_fails_on_an_id_the_dataset_no_longer_has() -> None:
    with pytest.raises(ValueError, match="gone"):
        subset([question("a")], ["a", "gone"])


def test_sample_joins_the_answer_and_heads_each_passage_once() -> None:
    events = [
        *search(passage("c1", 1, "Imatinib inhibits BCR-ABL.")),
        *search(passage("c1", 1, "Imatinib inhibits BCR-ABL."), passage("c2", 2, "Take it.")),
        *tokens("It inhibits ", "BCR-ABL [1]. "),
    ]

    found = sample(question("q"), events)

    assert found.answer == "It inhibits BCR-ABL [1]."
    assert found.contexts == [
        "[1] Gleevec (IMATINIB MESYLATE), mechanism_of_action: Imatinib inhibits BCR-ABL.",
        "[2] Gleevec (IMATINIB MESYLATE), mechanism_of_action: Take it.",
    ]


def test_sample_names_the_substance_alone_for_a_label_without_a_brand() -> None:
    events = search(passage("c1", 1, "Text.", brand=None))

    assert sample(question("q"), events).contexts == [
        "[1] IMATINIB MESYLATE, mechanism_of_action: Text."
    ]


def test_sample_without_a_label_search_has_no_contexts() -> None:
    events = [
        {"type": "tool_result", "id": "b", "name": "get_drug_properties", "result": {}},
        *tokens("Imatinib weighs 493.6 g/mol."),
    ]

    assert sample(question("q"), events).contexts == []


def test_samples_fail_when_the_cache_lacks_a_picked_question() -> None:
    answers = {"a": Answer("a", tokens("Yes."), 1.0)}

    with pytest.raises(ValueError, match="b"):
        samples([question("a"), question("b")], answers)
