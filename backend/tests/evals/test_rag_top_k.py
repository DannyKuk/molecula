from datetime import date
from typing import Any

import pytest
from evals.rag.top_k import Search, check_replay, replay, traced
from evals.retrieval.dataset import Question

from molecula.schemas.retrieval import LabelFilter, LabelQuery, Retrieval, RetrievedChunk

QUESTION = Question(
    id="imatinib-mechanism",
    question="How does Gleevec work?",
    cid=5291,
    drug="imatinib",
    section_group="pharmacology",
    evidence="inhibits the BCR-ABL tyrosine kinase",
    origin="hand",
)
FILTER = LabelFilter(extracted=LabelQuery(substances=["Gleevec"]))


def chunk(id: str, text: str, cid: int = 5291) -> RetrievedChunk:
    return RetrievedChunk(
        id=id,
        text=text,
        score=0.5,
        cid=cid,
        substance="IMATINIB MESYLATE",
        brand="Gleevec",
        product_type="rx",
        section="mechanism_of_action",
        section_group="pharmacology",
        sensitive=False,
        set_id="gleevec",
        effective_time=date(2026, 7, 13),
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    )


class FakeRetriever:
    def __init__(self, chunks: dict[str, list[RetrievedChunk]]) -> None:
        self._chunks = chunks

    def retrieve(self, question: str, label_filter: LabelFilter | None = None) -> Retrieval:
        return Retrieval(
            question=question, filter=label_filter, chunks=self._chunks[question], dropped=[]
        )


def trace(question: str, kept: list[str], dropped: list[str]) -> dict[str, Any]:
    candidates = [{"id": c, "kept": True} for c in kept] + [
        {"id": c, "kept": False} for c in dropped
    ]
    return {
        "type": "retrieval_trace",
        "question": question,
        "filter": FILTER.model_dump(mode="json"),
        "candidates": candidates,
    }


def test_traced_keeps_each_search_with_its_filter_and_kept_chunks() -> None:
    events = [{"type": "token", "text": "x"}, trace("How does it work?", ["a", "b"], ["c"])]

    assert traced("q", events) == [Search("q", "How does it work?", FILTER, ["a", "b"])]


def test_replay_counts_a_question_once_when_any_search_returns_its_evidence() -> None:
    searches = [
        Search(QUESTION.id, "first", FILTER, []),
        Search(QUESTION.id, "second", FILTER, []),
    ]
    retriever = FakeRetriever(
        {
            "first": [chunk("a", "Store at room temperature.")],
            "second": [chunk("b", "Imatinib inhibits the BCR-ABL tyrosine kinase.")],
        }
    )

    result = replay([QUESTION], searches, retriever, top_k=5)

    assert (result.answered, result.questions, result.chunks_per_search) == (1, 1, 1.0)


def test_replay_does_not_count_the_evidence_in_another_drugs_label() -> None:
    searches = [Search(QUESTION.id, "first", FILTER, [])]
    retriever = FakeRetriever({"first": [chunk("a", "inhibits the BCR-ABL tyrosine kinase", 1)]})

    assert replay([QUESTION], searches, retriever, top_k=5).answered == 0


def test_check_replay_stops_when_the_index_returns_other_chunks() -> None:
    searches = [Search(QUESTION.id, "first", FILTER, ["a"])]
    retriever = FakeRetriever({"first": [chunk("b", "Other text.")]})

    with pytest.raises(SystemExit, match="1 of 1 searches"):
        check_replay(searches, retriever, top_k=5)


def test_check_replay_passes_when_the_chunks_match() -> None:
    searches = [Search(QUESTION.id, "first", FILTER, ["a"])]
    retriever = FakeRetriever({"first": [chunk("a", "Text.")]})

    check_replay(searches, retriever, top_k=5)
