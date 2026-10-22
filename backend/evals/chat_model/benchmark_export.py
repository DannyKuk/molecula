"""Export the chat-model benchmark of 2026-10-22 as the JSON the benchmark page reads (#404).

    uv run python -m evals.chat_model.benchmark_export [--eval-dir DIR]

Reads the five runs at medium of `docs/decisions/chat-model.md` from the from-memory and
comparisons caches and their hand verdicts, and writes per model the counts of both evals and per
answer the question, the answer text, the tools it called and the verdict. Every count is computed
here from the answers, so the page and the doc's tables can be compared line by line. The caches
aren't committed, so this runs on the machine that made them.
"""

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.chat_model import comparisons, from_memory
from evals.chat_model.comparisons import Asked, ComparisonQuestion
from evals.chat_model.from_memory import Run, evidence_returned, passes
from evals.chat_model.no_label import Verdict, read_verdicts
from evals.retrieval.dataset import Question

from molecula.config import get_settings

OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "lib"
    / "benchmarks"
    / "chat-models-2026-10-22.json"
)
COMPARISON_VERDICTS = Path(__file__).resolve().parent / "comparisons_verdicts"
SOURCE = "docs/decisions/chat-model.md"
GPU = "RX 7900 XTX"


@dataclass(frozen=True)
class ModelRun:
    """One model's two cache files, named as the eval wrote them."""

    model: str
    from_memory: str
    comparisons: str
    local: bool = False
    default: bool = False


RUNS = [
    ModelRun(
        "openai/gpt-6-luna",
        "openai_gpt-6-luna-answer-medium-check-medium-input-jev-1.13-filter-88aaa57ada7e",
        "openai_gpt-6-luna-answer-medium-4d81d48666c8",
        default=True,
    ),
    ModelRun(
        "anthropic/claude-haiku-5.5",
        "anthropic_claude-haiku-5.5-answer-medium-check-medium-input-jev-1.13-filter-d8ae9463f385",
        "anthropic_claude-haiku-5.5-answer-medium-ab3294feb4e8",
    ),
    ModelRun(
        "deepseek/deepseek-v4.1-flash",
        "deepseek_deepseek-v4.1-flash-answer-medium-check-medium-input-jev-1.13-filter-3e700f353954",
        "deepseek_deepseek-v4.1-flash-answer-medium-fdaeb9762527",
    ),
    ModelRun(
        "openai/gpt-oss-20b",
        "openai_gpt-oss-20b-answer-medium-check-medium-5a8ca37fbfef",
        "openai_gpt-oss-20b-answer-medium-55888610f9f1",
        local=True,
        default=True,
    ),
    ModelRun(
        "zai-org/glm-4.7-flash",
        "zai-org_glm-4.7-flash-answer-medium-check-medium-9350730e12e5",
        "zai-org_glm-4.7-flash-answer-medium-6e61f93f92a7",
        local=True,
    ),
]


@dataclass(frozen=True)
class ModelResults:
    run: ModelRun
    from_memory: list[Run]
    from_memory_verdicts: dict[str, Verdict]
    comparisons: list[Asked]
    comparison_verdicts: dict[str, Verdict]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=get_settings().build_dir / "eval",
        help="the folder that holds from_memory/ and comparisons/",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT, help="where the JSON is written")
    args = parser.parse_args()

    try:
        results = [
            load(run, args.eval_dir, from_memory.VERDICTS, COMPARISON_VERDICTS) for run in RUNS
        ]
        data = page_data(results, from_memory.load_sample(), comparisons.load_questions())
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{args.out}: {args.out.stat().st_size / 1e3:.0f} kB")
    print(summary(data))
    return 0


def load(
    run: ModelRun, eval_dir: Path, from_memory_verdicts: Path, comparison_verdicts: Path
) -> ModelResults:
    caches = {
        "from_memory": eval_dir / "from_memory" / f"{run.from_memory}.jsonl",
        "comparisons": eval_dir / "comparisons" / f"{run.comparisons}.jsonl",
    }
    for cache in caches.values():
        if not cache.exists():
            raise FileNotFoundError(f"{cache} is missing: run the eval on this machine first")
    asked = comparisons.read_cache(caches["comparisons"])
    return ModelResults(
        run=run,
        from_memory=list(from_memory.read_cache(caches["from_memory"]).values()),
        from_memory_verdicts=verdicts(from_memory_verdicts / f"{run.from_memory}.yaml"),
        comparisons=[answer for answers in asked.values() for answer in answers],
        comparison_verdicts=verdicts(comparison_verdicts / f"{run.comparisons}.yaml"),
    )


def verdicts(path: Path) -> dict[str, Verdict]:
    found = read_verdicts(path)
    if found is None:
        raise FileNotFoundError(f"{path} is missing: judge the answers first")
    return found


def page_data(
    results: list[ModelResults],
    sample: list[Question],
    comparison_questions: list[ComparisonQuestion],
) -> dict[str, Any]:
    """The page's JSON. Raises ValueError when an answer has no verdict."""
    by_id = {question.id: question for question in sample}
    by_comparison = {question.id: question for question in comparison_questions}
    models = []
    for result in results:
        memory = [
            memory_answer(run, by_id, result.from_memory_verdicts) for run in result.from_memory
        ]
        compared = comparison_answers(result.comparisons, by_comparison, result.comparison_verdicts)
        models.append(
            {
                "id": result.run.model,
                "name": result.run.model.split("/")[-1],
                "local": result.run.local,
                "default": result.run.default,
                "gpu": GPU if result.run.local else None,
                "from_memory": {
                    **memory_summary(memory),
                    "cost_usd": cost(result, [run.answer.events for run in result.from_memory]),
                },
                "comparisons": {
                    **comparison_summary(compared),
                    "cost_usd": cost(result, [asked.events for asked in result.comparisons]),
                },
                "answers": {"from_memory": memory, "comparisons": compared},
            }
        )
    return {
        "meta": {
            "date": "2026-10-22",
            "effort": "medium",
            "gpu": GPU,
            "source": SOURCE,
        },
        "questions": {
            "from_memory": [
                question.model_dump(include={"id", "question", "drug", "section_group"})
                for question in sample
            ],
            "comparisons": [
                question.model_dump(include={"id", "question", "drugs", "kind"})
                for question in comparison_questions
            ],
        },
        "models": models,
    }


def memory_answer(
    run: Run, questions: dict[str, Question], verdicts: dict[str, Verdict]
) -> dict[str, Any]:
    verdict = judged(run.run_id, verdicts)
    return {
        "id": run.run_id,
        "question": run.run_id.split("#")[0],
        **answer_fields(run.answer.events, run.answer.seconds, verdict),
        "error": run.error is not None,
        "passed": passes(run, verdicts),
        "passage_returned": evidence_returned(questions[run.run_id.split("#")[0]], run),
    }


def comparison_answers(
    answers: list[Asked],
    questions: dict[str, ComparisonQuestion],
    verdicts: dict[str, Verdict],
) -> list[dict[str, Any]]:
    """The comparison answers, numbered per question in cache order as the verdict files are."""
    rows = []
    asked: dict[str, int] = {}
    for answer in answers:
        asked[answer.question_id] = asked.get(answer.question_id, 0) + 1
        answer_id = f"{answer.question_id}#{asked[answer.question_id]}"
        verdict = judged(answer_id, verdicts)
        question = questions[answer.question_id]
        rows.append(
            {
                "id": answer_id,
                "question": answer.question_id,
                **answer_fields(answer.events, answer.seconds, verdict),
                "error": answer.failed,
                "passed": not answer.failed and verdict.passed,
                "evidence": all(answer.has_evidence_for(drug) for drug in question.drugs),
                "kind": question.kind,
            }
        )
    return rows


def judged(answer_id: str, verdicts: dict[str, Verdict]) -> Verdict:
    if answer_id not in verdicts:
        raise ValueError(f"{answer_id} has no verdict")
    return verdicts[answer_id]


def answer_fields(events: list[dict[str, Any]], seconds: float, verdict: Verdict) -> dict[str, Any]:
    return {
        "text": "".join(e["text"] for e in events if e["type"] == "token"),
        "tools": [
            {"name": e["name"], "args": e["args"]} for e in events if e["type"] == "tool_call"
        ],
        "seconds": round(seconds, 2),
        "from_memory": verdict.from_memory,
        "denies_data": verdict.denies_data,
        "note": verdict.note,
    }


def memory_summary(answers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "answers": len(answers),
        "passed": sum(a["passed"] for a in answers),
        "from_memory": sum(a["from_memory"] for a in answers),
        "denies_data": sum(a["denies_data"] for a in answers),
        "passage_returned": sum(a["passage_returned"] for a in answers),
        "errors": sum(a["error"] for a in answers),
        "seconds_p50": round(statistics.median(a["seconds"] for a in answers), 1),
    }


def comparison_summary(answers: list[dict[str, Any]]) -> dict[str, Any]:
    def kind(name: str) -> list[dict[str, Any]]:
        return [a for a in answers if a["kind"] == name]

    return {
        "answers": len(answers),
        "passed": sum(a["passed"] for a in answers),
        "from_memory": sum(a["from_memory"] for a in answers),
        "denies_data": sum(a["denies_data"] for a in answers),
        "errors": sum(a["error"] for a in answers),
        "evidence": {
            name: {"of": len(kind(name)), "found": sum(a["evidence"] for a in kind(name))}
            for name in ("comparison", "3d_comparison")
        },
        "seconds_p50": round(statistics.median(a["seconds"] for a in kind("comparison")), 1),
    }


def cost(result: ModelResults, runs: list[list[dict[str, Any]]]) -> float | None:
    """OpenRouter's cost of the run, summed from each answer's done event; none on a local model."""
    if result.run.local:
        return None
    done = [next((e for e in events if e["type"] == "done"), None) for events in runs]
    return round(sum(e["usage"].get("cost_usd") or 0 for e in done if e is not None), 4)


def summary(data: dict[str, Any]) -> str:
    """The counts as the doc's two tables lay them out, to compare before committing."""
    lines = [
        "| Model | Pass | From memory | Denies data | Right passage | s p50 "
        "| Evidence | 3D evidence | No flag | From memory | Denies data | Failed | s p50 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for model in data["models"]:
        memory, compared = model["from_memory"], model["comparisons"]
        evidence = compared["evidence"]
        lines.append(
            f"| {model['name']} | {memory['passed']} | {memory['from_memory']} "
            f"| {memory['denies_data']} | {memory['passage_returned']} | {memory['seconds_p50']} "
            f"| {evidence['comparison']['found']} of {evidence['comparison']['of']} "
            f"| {evidence['3d_comparison']['found']} of {evidence['3d_comparison']['of']} "
            f"| {compared['passed']} | {compared['from_memory']} | {compared['denies_data']} "
            f"| {compared['errors']} | {compared['seconds_p50']} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
