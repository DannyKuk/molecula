from molecula.guard.claims import refs, split_claims
from molecula.guard.safety import fixed_answer
from molecula.schemas.source_check import Claim


def texts(answer: str) -> list[str]:
    return [claim.text for claim in split_claims(answer)]


def test_each_sentence_is_a_claim_with_the_refs_it_cites() -> None:
    answer = "Ibuprofen is an NSAID [1]. It can cause stomach bleeding [2][3]. Ask a pharmacist."

    assert split_claims(answer) == [
        Claim(text="Ibuprofen is an NSAID [1].", refs=(1,)),
        Claim(text="It can cause stomach bleeding [2][3].", refs=(2, 3)),
        Claim(text="Ask a pharmacist.", refs=()),
    ]


def test_a_citation_after_the_full_stop_belongs_to_the_sentence_before() -> None:
    answer = "The starting dose is 10 mg once daily. [1] Higher doses need a doctor's advice [2]."

    assert texts(answer) == [
        "The starting dose is 10 mg once daily. [1]",
        "Higher doses need a doctor's advice [2].",
    ]


def test_numbers_and_abbreviations_dont_end_a_sentence() -> None:
    answer = (
        "Ulcers occurred in fewer than 0.1 % of patients, e.g. in long trials [1]. "
        "Call 911 in the U.S. or 112 in the EU. Doses vs. placebo differed [2]."
    )

    assert texts(answer) == [
        "Ulcers occurred in fewer than 0.1 % of patients, e.g. in long trials [1].",
        "Call 911 in the U.S. or 112 in the EU.",
        "Doses vs. placebo differed [2].",
    ]


def test_a_list_under_one_citation_is_one_claim() -> None:
    answer = "**Imatinib (CID 5291)**\n- Formula: C29H31N7O\n- Molecular weight: 493.6 g/mol [1]"

    assert split_claims(answer) == [Claim(text=answer, refs=(1,))]


def test_a_list_citing_the_same_source_on_every_item_is_one_claim() -> None:
    answer = "- Molecular weight: 493.6 g/mol [1]\n- XLogP: 3.5 [1]"

    assert texts(answer) == [answer]


def test_a_list_whose_items_cite_different_sources_is_a_claim_per_item() -> None:
    answer = "- Uses: pain and fever [1]\n- Side effects: stomach bleeding [2]"

    assert split_claims(answer) == [
        Claim(text="- Uses: pain and fever [1]", refs=(1,)),
        Claim(text="- Side effects: stomach bleeding [2]", refs=(2,)),
    ]


def test_a_lead_in_ending_in_a_colon_belongs_to_its_list() -> None:
    answer = (
        "Do not use it with an MAOI [1]. Common MAOIs include:\n\n- Phenelzine\n- Selegiline\n\n"
        "They raise blood pressure."
    )

    assert texts(answer) == [
        "Do not use it with an MAOI [1].",
        "Common MAOIs include:\n- Phenelzine\n- Selegiline",
        "They raise blood pressure.",
    ]


def test_the_lead_in_goes_with_each_item_when_the_items_are_claims_of_their_own() -> None:
    answer = "**Ibuprofen**\n\n- Used for pain [1]\n- Can cause ulcers [2]"

    assert texts(answer) == [
        "**Ibuprofen**\n- Used for pain [1]",
        "**Ibuprofen**\n- Can cause ulcers [2]",
    ]


def test_a_table_is_a_list_of_rows_without_its_rule() -> None:
    answer = "| Drug | Weight |\n|---|---|\n| imatinib | 493.6 [1] |\n| metformin | 129.2 [1] |"

    assert texts(answer) == [
        "| Drug | Weight |\n| imatinib | 493.6 [1] |\n| metformin | 129.2 [1] |"
    ]


def test_a_heading_before_a_paragraph_and_a_horizontal_rule_are_no_claims() -> None:
    answer = "## Dosing\n\nTake it once daily [1].\n\n---\n\nStore it below 25 °C [2]."

    assert texts(answer) == ["Take it once daily [1].", "Store it below 25 °C [2]."]


def test_full_width_citations_are_read_like_square_ones() -> None:
    answer = "It is not a cure for herpes【1】【3】. Store it at room temperature【2】."

    assert [claim.refs for claim in split_claims(answer)] == [(1, 3), (2,)]


def test_citations_alone_cite_the_claim_before_them() -> None:
    answer = "These are the most frequent side effects.\n\n[1][2]"

    assert split_claims(answer) == [
        Claim(text="These are the most frequent side effects. [1][2]", refs=(1, 2))
    ]


def test_a_german_answer_is_split_at_its_sentences_not_its_abbreviations() -> None:
    answer = (
        "Metformin wird bei Typ-2-Diabetes eingesetzt, z. B. zusammen mit Bewegung [2]. "
        "Atorvastatin senkt das LDL-Cholesterin bzw. das Risiko eines Herzinfarkts [6][7]."
    )

    assert texts(answer) == [
        "Metformin wird bei Typ-2-Diabetes eingesetzt, z. B. zusammen mit Bewegung [2].",
        "Atorvastatin senkt das LDL-Cholesterin bzw. das Risiko eines Herzinfarkts [6][7].",
    ]


def test_the_guards_emergency_line_is_left_out() -> None:
    emergency = fixed_answer("overdose_emergency")
    answer = f"{emergency}\n\nOverdose can cause drowsiness and vomiting [1]."

    assert split_claims(answer, leave_out=[emergency]) == [
        Claim(text="Overdose can cause drowsiness and vomiting [1].", refs=(1,))
    ]


def test_refs_reads_every_citation_style_once() -> None:
    assert refs("A [2, 1]. B【3】 C [2] D [x]") == (1, 2, 3)


def test_an_empty_answer_has_no_claims() -> None:
    assert split_claims("") == []
