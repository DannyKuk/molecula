from dataclasses import replace
from pathlib import Path

import pytest

from molecula.store.index import Chunk
from molecula.store.keywords import KeywordIndex

INTERACTIONS = Chunk(
    id="zocor:drug_interactions:0",
    text="Strong CYP3A4 inhibitors are contraindicated. Ondansetron, a 5-HT3 blocker, is fine.",
    cid=54454,
    substance="SIMVASTATIN",
    brand="Zocor",
    product_type="rx",
    section="drug_interactions",
    section_group="interactions",
    sensitive=False,
    set_id="zocor",
    effective_time="20260713",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=zocor",
)
WARNINGS = replace(
    INTERACTIONS,
    id="zofran:warnings_and_cautions:0",
    text="QT prolongation has been reported. Take 5 mg with water.",
    cid=4595,
    substance="ONDANSETRON",
    brand=None,
    section="warnings_and_cautions",
    section_group="warnings",
    set_id="zofran",
)
OVERDOSAGE = replace(
    WARNINGS,
    id="zofran-odt:overdosage:0",
    text="Overdose of the 5\u2011HT3 antagonist caused hypotension.",
    product_type="otc",
    section="overdosage",
    section_group="overdosage",
    sensitive=True,
    set_id="zofran-odt",
)
CHUNKS = [INTERACTIONS, WARNINGS, OVERDOSAGE]


@pytest.fixture
def keywords(tmp_path: Path) -> KeywordIndex:
    keywords = KeywordIndex(tmp_path / "bm25.db")
    keywords.rebuild(CHUNKS)
    return keywords


def found_ids(keywords: KeywordIndex, question: str, where: dict | None = None) -> list[str]:
    return [chunk.id for chunk, _ in keywords.search(question, 10, where)]


def test_a_code_like_term_is_found_in_any_case(keywords: KeywordIndex) -> None:
    assert found_ids(keywords, "cyp3a4") == [INTERACTIONS.id]


def test_a_hyphenated_term_matches_as_a_whole_with_either_hyphen(keywords: KeywordIndex) -> None:
    assert sorted(found_ids(keywords, "5-HT3")) == sorted([INTERACTIONS.id, OVERDOSAGE.id])
    assert WARNINGS.id not in found_ids(keywords, "5-HT3")


def test_word_forms_are_stemmed(keywords: KeywordIndex) -> None:
    assert found_ids(keywords, "prolonged QT") == [WARNINGS.id]


def test_any_term_of_a_question_matches_and_the_best_match_is_first(
    keywords: KeywordIndex,
) -> None:
    assert found_ids(keywords, "Is QT prolongation reported with ondansetron?")[0] == WARNINGS.id


@pytest.mark.parametrize("question", ['don\'t "take" NOT * (this) OR', "AND", "^5-HT3:"])
def test_query_syntax_in_a_question_is_read_as_words(keywords: KeywordIndex, question: str) -> None:
    keywords.search(question, 10)


@pytest.mark.parametrize("question", ["", "?!", "   "])
def test_a_question_without_words_finds_nothing(keywords: KeywordIndex, question: str) -> None:
    assert keywords.search(question, 10) == []


def test_the_filter_narrows_like_the_vector_index(keywords: KeywordIndex) -> None:
    assert found_ids(keywords, "5-HT3", {"set_id": {"$in": ["zofran", "zofran-odt"]}}) == [
        OVERDOSAGE.id
    ]
    assert found_ids(keywords, "5-HT3", {"product_type": "rx"}) == [INTERACTIONS.id]
    both = {"$and": [{"cid": {"$in": [4595]}}, {"section_group": {"$in": ["warnings"]}}]}
    assert found_ids(keywords, "QT hypotension", both) == [WARNINGS.id]


def test_a_filter_on_another_field_is_refused(keywords: KeywordIndex) -> None:
    with pytest.raises(ValueError, match="text"):
        keywords.search("QT", 10, {"text": "QT"})


def test_found_chunks_come_back_whole(keywords: KeywordIndex) -> None:
    [(chunk, score)] = keywords.search("hypotension", 10)

    assert chunk == OVERDOSAGE
    assert score > 0


def test_n_limits_the_results(keywords: KeywordIndex) -> None:
    assert len(keywords.search("5-HT3 QT", 1)) == 1


def test_a_missing_index_finds_nothing(tmp_path: Path) -> None:
    keywords = KeywordIndex(tmp_path / "bm25.db")

    assert not keywords.exists()
    assert keywords.search("QT", 10) == []


def test_a_rebuild_replaces_the_chunks(keywords: KeywordIndex) -> None:
    keywords.rebuild([WARNINGS])

    assert found_ids(keywords, "5-HT3 QT CYP3A4") == [WARNINGS.id]


def test_replace_drug_swaps_one_compounds_chunks_and_keeps_the_others(
    keywords: KeywordIndex,
) -> None:
    newer = replace(WARNINGS, text="Serotonin syndrome has been reported.")

    keywords.replace_drug(4595, [newer])

    assert sorted(found_ids(keywords, "QT serotonin CYP3A4 hypotension")) == sorted(
        [newer.id, INTERACTIONS.id]
    )
