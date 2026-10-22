import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from evals.chat_model.benchmark_export import ModelRun, load, page_data
from evals.chat_model.comparisons import ComparisonQuestion
from evals.retrieval.dataset import Question

SAMPLE = [
    Question(
        id="imatinib-food",
        question="Should Gleevec be taken with food?",
        cid=5291,
        drug="imatinib",
        section_group="dosing",
        evidence="should be taken with food",
        origin="sampled",
    )
]
COMPARISONS = [
    ComparisonQuestion(
        id="compare-ibuprofen-naproxen",
        question="Compare ibuprofen and naproxen",
        drugs=["ibuprofen", "naproxen"],
        kind="comparison",
    ),
    ComparisonQuestion(
        id="3d-ibuprofen-aspirin",
        question="Show me a 3d model of ibuprofen and compare it to aspirin",
        drugs=["ibuprofen", "aspirin"],
        kind="3d_comparison",
    ),
]
CLOUD = ModelRun("org/cloud-model", "cloud-fm", "cloud-cmp", default=True)
LOCAL = ModelRun("org/local-model", "local-fm", "local-cmp", local=True)


def tool_call(name: str, **args: Any) -> dict[str, Any]:
    return {"type": "tool_call", "id": name, "name": name, "args": args}


def tokens(text: str) -> list[dict[str, Any]]:
    return [{"type": "token", "text": part} for part in text.split("|")]


def done(cost: float | None = None) -> dict[str, Any]:
    return {"type": "done", "usage": {"output_tokens": 10, "cost_usd": cost}}


def search(passage: str) -> list[dict[str, Any]]:
    return [
        tool_call("search_labels", drug="Gleevec", question="food?"),
        {
            "type": "tool_result",
            "name": "search_labels",
            "result": {"passages": [{"cid": 5291, "text": passage}]},
        },
    ]


def write_lines(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")


def write_verdicts(path: Path, flags: dict[str, tuple[bool, bool]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"id": answer_id, "from_memory": memory, "denies_data": denies, "note": f"{answer_id} note"}
        for answer_id, (memory, denies) in flags.items()
    ]
    path.write_text(yaml.safe_dump(entries), encoding="utf-8")


def memory_run(run_id: str, events: list[dict[str, Any]], seconds: float) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "answer": {"question_id": run_id.split("#")[0], "events": events, "seconds": seconds},
    }


def comparison(question_id: str, events: list[dict[str, Any]], seconds: float) -> dict[str, Any]:
    return {"question_id": question_id, "events": events, "seconds": seconds}


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    eval_dir, memory_verdicts, comparison_verdicts = (
        tmp_path / "eval",
        tmp_path / "from_memory_verdicts",
        tmp_path / "comparisons_verdicts",
    )
    write_lines(
        eval_dir / "from_memory" / "cloud-fm.jsonl",
        [
            memory_run(
                "imatinib-food#1",
                [
                    *search("Gleevec should be taken with food."),
                    *tokens("Take it| with food."),
                    done(0.01),
                ],
                4.0,
            ),
            memory_run(
                "imatinib-food#2",
                [*search("Store at room temperature."), *tokens("With a meal."), done(0.02)],
                6.0,
            ),
        ],
    )
    write_verdicts(
        memory_verdicts / "cloud-fm.yaml",
        {"imatinib-food#1": (False, False), "imatinib-food#2": (True, False)},
    )
    write_lines(
        eval_dir / "comparisons" / "cloud-cmp.jsonl",
        [
            comparison(
                "compare-ibuprofen-naproxen",
                [
                    tool_call("search_labels", drug="ibuprofen"),
                    tool_call("search_labels", drug="naproxen"),
                    *tokens("Both are NSAIDs."),
                    done(0.03),
                ],
                7.0,
            ),
            comparison(
                "3d-ibuprofen-aspirin",
                [
                    tool_call("get_complex", drug="ibuprofen"),
                    *tokens("No aspirin data."),
                    done(0.01),
                ],
                9.0,
            ),
        ],
    )
    write_verdicts(
        comparison_verdicts / "cloud-cmp.yaml",
        {"compare-ibuprofen-naproxen#1": (False, False), "3d-ibuprofen-aspirin#1": (False, True)},
    )
    write_lines(
        eval_dir / "from_memory" / "local-fm.jsonl",
        [memory_run("imatinib-food#1", [*tokens("With food."), done()], 20.0)],
    )
    write_verdicts(memory_verdicts / "local-fm.yaml", {"imatinib-food#1": (False, False)})
    write_lines(
        eval_dir / "comparisons" / "local-cmp.jsonl",
        [
            comparison(
                "compare-ibuprofen-naproxen",
                [
                    tool_call("search_labels", drug="ibuprofen"),
                    tool_call("search_labels", drug="naproxen"),
                    {"type": "error", "message": "The model took too long."},
                ],
                180.0,
            ),
            comparison(
                "compare-ibuprofen-naproxen",
                [tool_call("compare_drugs", drugs=["ibuprofen", "naproxen"]), *tokens("Same.")],
                30.0,
            ),
        ],
    )
    write_verdicts(
        comparison_verdicts / "local-cmp.yaml",
        {
            "compare-ibuprofen-naproxen#1": (False, False),
            "compare-ibuprofen-naproxen#2": (False, False),
        },
    )
    return eval_dir, memory_verdicts, comparison_verdicts


def export(folders: tuple[Path, Path, Path]) -> dict[str, Any]:
    results = [load(run, *folders) for run in (CLOUD, LOCAL)]
    return page_data(results, SAMPLE, COMPARISONS)


def model(data: dict[str, Any], model_id: str) -> dict[str, Any]:
    return next(entry for entry in data["models"] if entry["id"] == model_id)


def test_label_question_counts_come_from_the_verdicts_and_the_returned_passages(
    folders: tuple[Path, Path, Path],
) -> None:
    cloud = model(export(folders), "org/cloud-model")

    assert cloud["from_memory"] == {
        "answers": 2,
        "passed": 1,
        "from_memory": 1,
        "denies_data": 0,
        "passage_returned": 1,
        "errors": 0,
        "seconds_p50": 5.0,
        "cost_usd": 0.03,
    }


def test_each_answer_keeps_its_text_tools_and_verdict_note(
    folders: tuple[Path, Path, Path],
) -> None:
    answer = model(export(folders), "org/cloud-model")["answers"]["from_memory"][0]

    assert answer["id"] == "imatinib-food#1"
    assert answer["question"] == "imatinib-food"
    assert answer["text"] == "Take it with food."
    assert answer["tools"] == [
        {"name": "search_labels", "args": {"drug": "Gleevec", "question": "food?"}}
    ]
    assert answer["note"] == "imatinib-food#1 note"
    assert answer["passed"] and answer["passage_returned"]


def test_comparisons_count_evidence_per_kind_and_seconds_on_plain_comparisons(
    folders: tuple[Path, Path, Path],
) -> None:
    compared = model(export(folders), "org/cloud-model")["comparisons"]

    assert compared["evidence"] == {
        "comparison": {"of": 1, "found": 1},
        "3d_comparison": {"of": 1, "found": 0},
    }
    assert compared["passed"] == 1
    assert compared["denies_data"] == 1
    assert compared["seconds_p50"] == 7.0
    assert compared["cost_usd"] == 0.04


def test_a_failed_answer_is_never_counted_clean_but_keeps_its_evidence(
    folders: tuple[Path, Path, Path],
) -> None:
    local = model(export(folders), "org/local-model")
    failed, answered = local["answers"]["comparisons"]

    assert failed["id"] == "compare-ibuprofen-naproxen#1"
    assert failed["error"] and not failed["passed"] and failed["evidence"]
    assert answered["id"] == "compare-ibuprofen-naproxen#2"
    assert answered["passed"] and not answered["evidence"]
    assert local["comparisons"]["errors"] == 1
    assert local["comparisons"]["passed"] == 1


def test_a_local_model_has_no_cost_and_names_the_gpu(folders: tuple[Path, Path, Path]) -> None:
    data = export(folders)
    local, cloud = model(data, "org/local-model"), model(data, "org/cloud-model")

    assert local["from_memory"]["cost_usd"] is None
    assert local["comparisons"]["cost_usd"] is None
    assert local["gpu"] == data["meta"]["gpu"]
    assert cloud["gpu"] is None
    assert cloud["default"] and not local["default"]


def test_an_answer_without_a_verdict_stops_the_export(folders: tuple[Path, Path, Path]) -> None:
    _, memory_verdicts, _ = folders
    write_verdicts(memory_verdicts / "cloud-fm.yaml", {"imatinib-food#1": (False, False)})

    with pytest.raises(ValueError, match="imatinib-food#2 has no verdict"):
        export(folders)


def test_a_missing_cache_stops_the_export(folders: tuple[Path, Path, Path]) -> None:
    eval_dir, _, _ = folders
    (eval_dir / "comparisons" / "local-cmp.jsonl").unlink()

    with pytest.raises(FileNotFoundError, match=r"local-cmp.jsonl is missing"):
        export(folders)
