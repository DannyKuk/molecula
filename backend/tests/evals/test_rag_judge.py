from pathlib import Path

from evals.rag.judge import report, scores_path, summary


def test_summary_averages_the_scores_that_exist_and_counts_the_rest() -> None:
    assert summary([1.0, 0.5, None, float("nan")]) == "0.75 (2 missing)"


def test_summary_without_scores_is_a_dash() -> None:
    assert summary([None]) == "-"


def test_report_has_a_row_per_section_group_and_one_for_all() -> None:
    judged = [
        {"section_group": "dosing", "faithfulness": 1.0, "answer_relevancy": 0.9},
        {"section_group": "dosing", "faithfulness": 0.5, "answer_relevancy": 0.7},
        {"section_group": "abuse_dependence", "faithfulness": None, "answer_relevancy": 0.8},
    ]

    rows = report(judged, "org/judge", "org/embeddings").splitlines()[4:]

    assert rows == [
        "| abuse_dependence | 1 | - | 0.80 |",
        "| dosing | 2 | 0.75 | 0.80 |",
        "| **all** | 3 | 0.75 (1 missing) | 0.80 |",
    ]


def test_scores_path_changes_with_the_samples_and_names_the_judge(tmp_path: Path) -> None:
    samples = tmp_path / "answers.samples.jsonl"
    samples.write_text('{"id": "a"}\n', encoding="utf-8")
    first = scores_path(samples, "anthropic/claude-haiku-5.5")
    samples.write_text('{"id": "b"}\n', encoding="utf-8")

    assert first.name.startswith("answers.anthropic_claude-haiku-5.5.ragas-")
    assert first.parent == tmp_path
    assert scores_path(samples, "anthropic/claude-haiku-5.5") != first
