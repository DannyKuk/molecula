from typing import Any

import pytest
from evals.retrieval.benchmark_export import page_data
from evals.retrieval.dataset import Question

from molecula.schemas.retrieval import Chunk


def chunk(id: str, text: str, cid: int = 5291) -> Chunk:
    return Chunk(
        id=id,
        text=text,
        cid=cid,
        substance="IMATINIB MESYLATE",
        brand="Gleevec",
        product_type="rx",
        section="mechanism_of_action",
        section_group="pharmacology",
        sensitive=False,
        set_id="gleevec",
        effective_time="20260713",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    )


CHUNKS = {
    c.id: c
    for c in [
        chunk("evidence", "Imatinib inhibits the BCR-ABL tyrosine kinase."),
        chunk("pooled", "Take Gleevec with a meal and a large glass of water."),
        chunk("unrelated", "Store at room temperature."),
        chunk("other-drug", "Inhibits the BCR-ABL tyrosine kinase.", cid=1),
    ]
}
QUESTIONS = [
    Question(
        id="imatinib-mechanism",
        question="How does Gleevec work?",
        cid=5291,
        drug="imatinib",
        section_group="pharmacology",
        evidence="inhibits the BCR-ABL tyrosine kinase",
        origin="hand",
    ),
    Question(
        id="imatinib-food",
        question="Should Gleevec be taken with food?",
        cid=5291,
        drug="imatinib",
        section_group="dosing",
        evidence="should be taken with food",
        pooled_evidence=["Take Gleevec with a meal"],
        origin="sampled",
    ),
]


def saved(in_drug: list[str], whole_index: list[str]) -> dict[str, Any]:
    """A question as a run saves it, with the ranks of an older answer key that never hit."""
    return {
        "id": "",
        "query_ms": 5.0,
        "rank_in_drug": None,
        "rank_whole_index": None,
        "top_in_drug": [{"chunk": c, "score": 0.5} for c in in_drug],
        "top_whole_index": [{"chunk": c, "score": 0.5} for c in whole_index],
    }


def row(label: str, query_ms: float, *questions: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": label,
        "model": f"org/{label}",
        "dimensions": 384,
        "build_device": "cuda:0",
        "build_seconds": 10.0,
        "build_vram_peak_gb": 0.2,
        "query_device": "cuda:0",
        "index_mb": 106.83,
        "query_ms_p50": query_ms,
        "query_ms_p95": query_ms,
        "in_drug": None,
        "whole_index": None,
        "recall_at_5_by_group": None,
        "missed_in_drug": None,
        "questions": list(questions),
    }


RUN = {
    "run": {"date": "2026-10-12T12:20:47+00:00", "chunks": 4, "top_k": 10},
    "questions": [{"id": q.id} for q in QUESTIONS],
    "results": [
        row(
            "bge-small",
            6.3,
            saved(["unrelated", "evidence"], ["other-drug", "unrelated"]),
            saved(["pooled", "unrelated"], ["other-drug", "pooled"]),
        ),
        row(
            "qwen3-8b",
            39.0,
            saved(["evidence", "unrelated"], ["evidence", "other-drug"]),
            saved(["unrelated", "evidence"], ["other-drug", "unrelated"]),
        ),
    ],
}
CPU_RUN = {"results": [{"label": "bge-small", "query_ms_p50": 7.66}]}


def export(run: dict[str, Any] = RUN) -> dict[str, Any]:
    return page_data("embeddings-test", run, CPU_RUN, QUESTIONS, CHUNKS)


def test_ranks_come_from_the_current_answer_key_including_pooled_passages() -> None:
    ranks = export()["ranks"]

    assert ranks["bge-small"] == {"in_drug": [2, 1], "whole_index": [None, 2]}
    assert ranks["qwen3-8b"] == {"in_drug": [1, None], "whole_index": [1, None]}


def test_recall_at_5_for_the_table_agrees_with_the_ranks() -> None:
    models = {m["label"]: m for m in export()["models"]}

    assert models["bge-small"]["recall_at_5"] == {"in_drug": 1.0, "whole_index": 0.5}
    assert models["qwen3-8b"]["recall_at_5"] == {"in_drug": 0.5, "whole_index": 0.5}


def test_cpu_query_time_comes_from_the_cpu_pass_and_is_null_without_one() -> None:
    small, large = export()["models"]

    assert (small["query_ms"], small["query_device"], small["cpu_query_ms"]) == (6, "gpu", 8)
    assert large["cpu_query_ms"] is None
    assert (small["weights_mb"], large["weights_mb"]) == (133, 15100)


def test_each_top_chunk_is_stored_once_with_its_text_and_no_other_chunk() -> None:
    data = export()

    assert data["top_chunk"] == {
        "bge-small": ["unrelated", "pooled"],
        "qwen3-8b": ["evidence", "unrelated"],
    }
    assert set(data["chunks"]) == {"evidence", "pooled", "unrelated"}
    assert data["chunks"]["pooled"] == {
        "section": "mechanism_of_action",
        "brand": "Gleevec",
        "text": "Take Gleevec with a meal and a large glass of water.",
    }


def test_questions_carry_their_pooled_evidence_but_not_the_key_internals() -> None:
    food = export()["questions"][1]

    assert food == {
        "id": "imatinib-food",
        "question": "Should Gleevec be taken with food?",
        "drug": "imatinib",
        "section_group": "dosing",
        "evidence": "should be taken with food",
        "pooled_evidence": ["Take Gleevec with a meal"],
    }


def test_a_run_made_with_other_questions_is_refused() -> None:
    with pytest.raises(ValueError, match="other questions"):
        export(RUN | {"questions": [{"id": "imatinib-mechanism"}]})


def test_a_model_without_a_known_weight_size_fails_instead_of_showing_none() -> None:
    unknown = RUN | {"results": [RUN["results"][0] | {"label": "new-model"}]}

    with pytest.raises(KeyError, match="new-model"):
        export(unknown)
