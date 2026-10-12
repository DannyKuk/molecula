from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from langchain_core.embeddings import Embeddings

from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import DrugFilter, LabelFilter, LabelQuery
from molecula.store.index import Chunk, LabelIndex

MODEL = "keyword-fake"
VOCABULARY = ["nausea", "kinase", "bleeding", "fever", "pain"]


class KeywordEmbeddings(Embeddings):
    """Counts the vocabulary words in a text, plus a constant so no vector is zero."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        words = text.casefold().split()
        vector = np.array([0.1, *(float(words.count(word)) for word in VOCABULARY)])
        return (vector / np.linalg.norm(vector)).tolist()


IMATINIB_SIDE_EFFECTS = Chunk(
    id="gleevec:adverse_reactions:0",
    text="nausea and fluid retention",
    cid=5291,
    substance="IMATINIB MESYLATE",
    brand="Gleevec",
    product_type="rx",
    section="adverse_reactions",
    section_group="adverse_reactions",
    sensitive=False,
    set_id="gleevec",
    effective_time="20260713",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
)
IMATINIB_MECHANISM = replace(
    IMATINIB_SIDE_EFFECTS,
    id="gleevec:mechanism_of_action:0",
    text="inhibits the bcr-abl kinase",
    section="mechanism_of_action",
    section_group="pharmacology",
)
IBUPROFEN_SIDE_EFFECTS = replace(
    IMATINIB_SIDE_EFFECTS,
    id="ibuprofen-rx:adverse_reactions:0",
    text="nausea heartburn and bleeding",
    cid=3672,
    substance="IBUPROFEN",
    brand=None,
    set_id="ibuprofen-rx",
)
IBUPROFEN_PURPOSE = replace(
    IBUPROFEN_SIDE_EFFECTS,
    id="advil:purpose:0",
    text="pain reliever and fever reducer",
    brand="Advil",
    product_type="otc",
    section="purpose",
    section_group="otc_consumer",
    set_id="advil",
)
CHUNKS = [IMATINIB_SIDE_EFFECTS, IMATINIB_MECHANISM, IBUPROFEN_SIDE_EFFECTS, IBUPROFEN_PURPOSE]


@pytest.fixture
def index(tmp_path: Path) -> LabelIndex:
    index = LabelIndex(tmp_path / "chroma")
    index.rebuild(CHUNKS, KeywordEmbeddings().embed_documents([c.text for c in CHUNKS]), MODEL)
    return index


def retriever(index: LabelIndex, top_k: int = 10, min_score: float = -1.0) -> LabelRetriever:
    return LabelRetriever(index, KeywordEmbeddings(), top_k=top_k, min_score=min_score)


def label_filter(
    drugs: list[DrugFilter] | None = None, unsupported: list[str] | None = None, **fields
) -> LabelFilter:
    return LabelFilter(
        extracted=LabelQuery(), drugs=drugs or [], unsupported=unsupported or [], **fields
    )


IMATINIB = DrugFilter(name="Gleevec", cid=5291, generic="imatinib", set_ids=["gleevec"])
IBUPROFEN = DrugFilter(
    name="ibuprofen", cid=3672, generic="ibuprofen", set_ids=["ibuprofen-rx", "advil"]
)


def found_ids(index: LabelIndex, question: str, label_filter: LabelFilter | None) -> list[str]:
    return [chunk.id for chunk in retriever(index).retrieve(question, label_filter).chunks]


def test_the_filter_narrows_to_the_drug_and_the_section_group(index: LabelIndex) -> None:
    narrowed = label_filter([IMATINIB], section_groups=["adverse_reactions"])

    assert found_ids(index, "nausea", narrowed) == [IMATINIB_SIDE_EFFECTS.id]


def test_two_drugs_search_the_labels_of_both(index: LabelIndex) -> None:
    narrowed = label_filter([IMATINIB, IBUPROFEN], section_groups=["adverse_reactions"])

    assert found_ids(index, "nausea and bleeding", narrowed) == [
        IBUPROFEN_SIDE_EFFECTS.id,
        IMATINIB_SIDE_EFFECTS.id,
    ]


def test_without_section_groups_every_part_of_the_drugs_label_is_searched(
    index: LabelIndex,
) -> None:
    narrowed = label_filter([IMATINIB], ignored_section_groups=["side_effects"])

    assert set(found_ids(index, "kinase", narrowed)) == {
        IMATINIB_MECHANISM.id,
        IMATINIB_SIDE_EFFECTS.id,
    }


def test_an_empty_filter_searches_everything(index: LabelIndex) -> None:
    everything = {chunk.id for chunk in CHUNKS}

    assert set(found_ids(index, "nausea", label_filter())) == everything
    assert set(found_ids(index, "nausea", None)) == everything


def test_the_product_type_alone_narrows_the_whole_index(index: LabelIndex) -> None:
    assert found_ids(index, "fever", label_filter(product_type="otc")) == [IBUPROFEN_PURPOSE.id]


def test_only_unsupported_drugs_find_nothing(index: LabelIndex) -> None:
    retrieval = retriever(index).retrieve("nausea", label_filter(unsupported=["Celexa"]))

    assert retrieval.chunks == [] and retrieval.dropped == []


def test_a_drug_without_labels_finds_nothing(index: LabelIndex) -> None:
    metamizole = DrugFilter(name="metamizole", cid=3111, generic="metamizole", set_ids=[])

    assert found_ids(index, "nausea", label_filter([metamizole])) == []


def test_top_k_limits_the_candidates(index: LabelIndex) -> None:
    retrieval = retriever(index, top_k=2).retrieve("nausea")

    assert len(retrieval.chunks) == 2


def test_candidates_below_the_threshold_are_dropped_but_kept_for_the_trace(
    index: LabelIndex,
) -> None:
    retrieval = retriever(index, min_score=0.5).retrieve("nausea", label_filter([IMATINIB]))

    assert [chunk.id for chunk in retrieval.chunks] == [IMATINIB_SIDE_EFFECTS.id]
    assert [chunk.id for chunk in retrieval.dropped] == [IMATINIB_MECHANISM.id]
    assert retrieval.dropped[0].score < 0.5 <= retrieval.chunks[0].score


def test_results_carry_what_a_citation_needs(index: LabelIndex) -> None:
    narrowed = label_filter([IMATINIB], section_groups=["adverse_reactions"])

    retrieval = retriever(index).retrieve("nausea", narrowed)

    chunk = retrieval.chunks[0]
    assert chunk.url == IMATINIB_SIDE_EFFECTS.url
    assert chunk.section_group == "adverse_reactions"
    assert chunk.effective_time == date(2026, 7, 13)
    assert retrieval.filter == narrowed
    assert retrieval.question == "nausea"


def test_a_full_filter_that_finds_something_is_not_widened(index: LabelIndex) -> None:
    narrowed = label_filter([IMATINIB], section_groups=["adverse_reactions"])

    assert retriever(index).retrieve("nausea", narrowed).widened == []


def test_a_brands_label_without_the_section_widens_to_the_drugs_other_labels(
    index: LabelIndex,
) -> None:
    advil = DrugFilter(
        name="Advil", cid=3672, generic="ibuprofen", set_ids=["advil"], narrowed=True
    )

    retrieval = retriever(index).retrieve(
        "nausea", label_filter([advil], section_groups=["adverse_reactions"])
    )

    assert [chunk.id for chunk in retrieval.chunks] == [IBUPROFEN_SIDE_EFFECTS.id]
    assert retrieval.widened == ["labels"]


def test_a_section_no_label_of_the_drug_has_widens_to_every_section(index: LabelIndex) -> None:
    retrieval = retriever(index).retrieve(
        "kinase", label_filter([IMATINIB], section_groups=["overdosage"])
    )

    assert {chunk.cid for chunk in retrieval.chunks} == {IMATINIB.cid}
    assert retrieval.chunks[0].id == IMATINIB_MECHANISM.id
    assert retrieval.widened == ["section_groups"]


def test_a_product_type_without_the_section_widens_to_every_product_type(
    index: LabelIndex,
) -> None:
    retrieval = retriever(index).retrieve(
        "kinase", label_filter(product_type="otc", section_groups=["pharmacology"])
    )

    assert [chunk.id for chunk in retrieval.chunks] == [IMATINIB_MECHANISM.id]
    assert retrieval.widened == ["labels"]
