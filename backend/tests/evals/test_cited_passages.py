from typing import Any

from evals.chat_model.cited_passages import Asked, Conversation, load_dataset, score

from molecula.schemas.claims import CheckedClaim

ALIASES = {
    "imatinib": ["imatinib", "gleevec"],
    "ibuprofen": ["ibuprofen", "advil"],
    "naproxen": ["naproxen", "aleve"],
}
CONVERSATION = Conversation(
    id="weights",
    turns=["How does imatinib work?", "Ibuprofen and naproxen?"],
    drugs=["ibuprofen", "naproxen"],
)


def passage(ref: int, substance: str, brand: str, text: str) -> dict[str, Any]:
    return {
        "chunk_id": f"chunk-{ref}",
        "ref": ref,
        "substance": substance,
        "brand": brand,
        "section": "indications_and_usage",
        "text": text,
    }


def search(drug: str, *passages: dict[str, Any]) -> list[dict[str, Any]]:
    call = {"type": "tool_call", "id": drug, "name": "search_labels", "args": {"drug": drug}}
    result = {"status": "found", "drugs": [drug], "passages": list(passages)}
    return [
        call,
        {
            "type": "tool_result",
            "id": drug,
            "name": "search_labels",
            "status": "found",
            "result": result,
        },
    ]


def answer(text: str, *events: dict[str, Any]) -> Asked:
    tokens = [{"type": "token", "text": text}, {"type": "done"}]
    return Asked(CONVERSATION.id, [], [*events, *tokens], 1.0)


def checked(
    text: str, refs: tuple[int, ...], label: str, held_by: tuple[int, ...] = ()
) -> CheckedClaim:
    return CheckedClaim(text=text, refs=refs, label=label, decided_by="model", held_by=held_by)


def test_a_passage_of_another_drug_cited_for_a_named_drug_is_a_wrong_drug_citation() -> None:
    asked = answer(
        "Ibuprofen relieves pain [1]. Naproxen relieves pain [2].",
        *search(
            "imatinib",
            passage(
                1, "IMATINIB MESYLATE", "Gleevec", "Gleevec treats leukaemia, unlike ibuprofen."
            ),
        ),
        *search("naproxen", passage(2, "NAPROXEN", "Aleve", "Aleve relieves pain.")),
    )

    scored = score(ALIASES, CONVERSATION, asked, [])

    assert scored.citations == 2
    assert [(w.ref, w.claim_drugs, w.source_drug) for w in scored.wrong_drug] == [
        (1, ["ibuprofen"], "imatinib")
    ]
    assert scored.off_question_calls == ["imatinib"]


def test_a_claim_that_names_no_drug_or_cites_its_own_drug_is_never_wrong_drug() -> None:
    asked = answer(
        "Advil relieves pain [1]. It is taken with food [1].",
        *search("ibuprofen", passage(1, "IBUPROFEN", "Advil", "Advil relieves pain.")),
    )

    scored = score(ALIASES, CONVERSATION, asked, [])

    assert scored.wrong_drug == []
    assert scored.citations == 2


def test_a_ref_no_tool_returned_is_counted_as_unknown() -> None:
    asked = answer("Ibuprofen relieves pain [7].")

    scored = score(ALIASES, CONVERSATION, asked, [])

    assert (scored.citations, scored.unknown_refs, scored.wrong_drug) == (1, 1, [])


def test_the_source_check_labels_are_counted_for_cited_claims_only() -> None:
    claims = [
        checked("Ibuprofen relieves pain [1].", (1,), "supported"),
        checked("Naproxen relieves pain [1].", (1,), "held_elsewhere", (2,)),
        checked("Ask your pharmacist.", (), "not_a_claim"),
    ]

    scored = score(ALIASES, CONVERSATION, answer(""), claims)

    assert scored.labels == {"supported": 1, "held_elsewhere": 1}
    assert [claim.held_by for claim in scored.held_elsewhere] == [(2,)]


def test_the_dataset_loads_and_names_only_drugs_it_has_aliases_for() -> None:
    dataset = load_dataset()

    assert len({c.id for c in dataset.conversations}) == len(dataset.conversations)
    assert all(drug in dataset.aliases for c in dataset.conversations for drug in c.drugs)


def test_a_claim_whose_terms_only_an_uncited_passage_holds_is_a_term_miss() -> None:
    asked = answer(
        "Ibuprofen can cause cytopenias such as neutropenia [1]. Ibuprofen can cause "
        "hepatotoxicity and jaundice [2].",
        *search(
            "ibuprofen",
            passage(1, "IBUPROFEN", "Advil", "Hepatotoxicity and jaundice have occurred."),
            passage(2, "IBUPROFEN", "Advil", "Cytopenias such as neutropenia may occur."),
        ),
    )

    scored = score(ALIASES, CONVERSATION, asked, [])

    assert scored.term_scored == 2
    assert [(m.cited, m.holder) for m in scored.term_misses] == [
        (["[1] Advil · indications_and_usage"], "[2] Advil · indications_and_usage"),
        (["[2] Advil · indications_and_usage"], "[1] Advil · indications_and_usage"),
    ]


def test_a_cited_passage_holding_most_terms_or_a_german_claim_is_no_term_miss() -> None:
    held = answer(
        "Ibuprofen can cause cytopenias such as neutropenia and agranulocytosis [1].",
        *search(
            "ibuprofen",
            passage(1, "IBUPROFEN", "Advil", "Cytopenias such as neutropenia may occur."),
            passage(2, "IBUPROFEN", "Advil", "Agranulocytosis, cytopenias, neutropenia."),
        ),
    )
    german = CONVERSATION.model_copy(update={"language": "de"})

    assert score(ALIASES, CONVERSATION, held, []).term_misses == []
    assert score(ALIASES, german, held, []).term_scored == 0


def test_each_item_of_a_list_citing_one_passage_is_checked_on_its_own() -> None:
    asked = answer(
        "Warnings on the ibuprofen label:\n"
        "- Cytopenias such as neutropenia may occur [1]\n"
        "- Hepatotoxicity and jaundice have occurred [1]",
        *search(
            "ibuprofen",
            passage(1, "IBUPROFEN", "Advil", "Cytopenias such as neutropenia may occur."),
            passage(2, "IBUPROFEN", "Advil", "Hepatotoxicity and jaundice have occurred."),
        ),
    )

    scored = score(ALIASES, CONVERSATION, asked, [])

    assert (scored.citations, scored.term_scored) == (2, 2)
    assert [m.claim for m in scored.term_misses] == [
        "- Hepatotoxicity and jaundice have occurred [1]"
    ]


def test_a_drug_named_in_the_lists_lead_in_may_be_cited_for_its_items() -> None:
    asked = answer(
        "Naproxen's label lists:\n"
        "- Like ibuprofen, it can cause skin reactions [1]\n"
        "- It can cause tinnitus [2]",
        *search(
            "naproxen",
            passage(1, "NAPROXEN", "Aleve", "Skin reactions may occur."),
            passage(2, "NAPROXEN", "Aleve", "Tinnitus was reported."),
        ),
    )

    assert score(ALIASES, CONVERSATION, asked, []).wrong_drug == []
