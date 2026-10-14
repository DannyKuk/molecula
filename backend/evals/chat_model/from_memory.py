"""Ask about drugs that have a label and see whether the answers add facts from memory (#197).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        LLM_REASONING_EFFORT=medium uv run python -m evals.chat_model.from_memory --times 1

Asks each question of `datasets/from_memory_sample.yaml`, a fixed sample of the retrieval
questions, `--times` times through `ChatAgent.stream`, as the citations eval does. The guard is
left out on purpose: it would refuse some of the questions (snorting bupropion, overdoses) before
the agent answers, and what is measured is what the agent adds to what its tools returned.

Each answer is judged by hand against the no-label eval's `RULES`. The verdicts live in
`from_memory_verdicts/<cache name>.yaml`; without them the run writes a review sheet that shows
each answer under every tool result it had.
"""

import argparse
import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from evals.chat_model.citations import Answer, ask, tool_descriptions
from evals.chat_model.no_label import RULES, Verdict, read_verdicts
from evals.retrieval.dataset import Question, load_questions
from evals.safety.run import cache_path
from fastapi import FastAPI

from molecula.agent.agent import ChatAgent
from molecula.config import Settings, get_settings
from molecula.main import lifespan

SAMPLE = Path(__file__).resolve().parents[1] / "datasets" / "from_memory_sample.yaml"
VERDICTS = Path(__file__).resolve().parent / "from_memory_verdicts"


@dataclass(frozen=True)
class Run:
    """One asking of a question."""

    run_id: str
    answer: Answer

    @property
    def text(self) -> str:
        return "".join(e["text"] for e in self.answer.events if e["type"] == "token")

    @property
    def results(self) -> list[tuple[str, Any]]:
        return [(e["name"], e["result"]) for e in self.answer.events if e["type"] == "tool_result"]

    @property
    def error(self) -> str | None:
        events = self.answer.events
        failure = next((e["message"] for e in events if e["type"] == "error"), None)
        if failure is None and not any(e["type"] == "done" for e in events):
            return "no done event"
        return failure

    @property
    def output_tokens(self) -> int | None:
        done = next((e for e in self.answer.events if e["type"] == "done"), None)
        return done["usage"]["output_tokens"] if done else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=1, help="askings per question")
    args = parser.parse_args()
    settings = get_settings()
    model_name = settings.local_llm_model or settings.llm_model or "unknown"
    questions = load_sample()
    cache, runs = asyncio.run(ask_all(settings, model_name, questions, args.times))
    verdicts = read_verdicts(VERDICTS / f"{cache.stem}.yaml")
    unjudged = [run for run in runs if verdicts is None or run.run_id not in verdicts]
    if unjudged:
        sheet = cache.with_suffix(".review.md")
        sheet.write_bytes(review_sheet(questions, unjudged).encode("utf-8"))
        print(f"{len(unjudged)} answers without a verdict: judge them in {sheet}")
        print(f"and write them to {VERDICTS / f'{cache.stem}.yaml'}")
        verdicts = None
    print(report(cache.stem, runs, verdicts))
    return 0


def load_sample(path: Path = SAMPLE) -> list[Question]:
    ids: list[str] = yaml.safe_load(path.read_text("utf-8"))
    by_id = {question.id: question for question in load_questions()}
    missing = [question_id for question_id in ids if question_id not in by_id]
    if missing or len(set(ids)) < len(ids):
        raise ValueError(f"{path} has unknown or repeated ids: {missing}")
    return [by_id[question_id] for question_id in ids]


async def ask_all(
    settings: Settings, model_name: str, questions: list[Question], times: int
) -> tuple[Path, list[Run]]:
    app = FastAPI()
    async with lifespan(app):
        agent: ChatAgent | None = app.state.chat_agent
        if agent is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        cache = cache_path(settings, model_name, tool_descriptions(app), "from_memory")
        cached = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        runs = []
        for question in questions:
            for number in range(1, times + 1):
                run_id = f"{question.id}#{number}"
                if run_id not in cached:
                    cached[run_id] = Run(run_id, await ask(agent, question))
                    with cache.open("a", encoding="utf-8") as file:
                        file.write(json.dumps(asdict(cached[run_id])) + "\n")
                    print(f"{run_id}: {cached[run_id].answer.seconds:.1f} s", flush=True)
                runs.append(cached[run_id])
    return cache, runs


def read_cache(cache: Path) -> dict[str, Run]:
    if not cache.exists():
        return {}
    entries = (json.loads(line) for line in cache.read_text("utf-8").splitlines())
    return {entry["run_id"]: Run(entry["run_id"], Answer(**entry["answer"])) for entry in entries}


def review_sheet(questions: list[Question], runs: list[Run]) -> str:
    by_id = {question.id: question for question in questions}
    rules = [f"- {name}: {rule}" for name, rule in RULES.items()]
    sections = ["Rules:", *rules]
    for run in runs:
        question = by_id[run.run_id.split("#")[0]]
        sections += [
            f"\n## {run.run_id} ({question.drug}, {question.section_group})",
            f"> {question.question}",
            f"Error: {run.error or '-'}",
            "",
            *(describe(name, result) for name, result in run.results),
            "",
            "**Answer:**",
            "",
            run.text or "(no answer)",
        ]
    return "\n".join(sections) + "\n"


def describe(name: str, result: Any) -> str:
    if name == "search_labels" and isinstance(result, dict):
        passages = [
            f"  [{p.get('ref')}] {p['substance']} {p['section']}: {p['text']}"
            for p in result.get("passages", [])
        ]
        header = {key: value for key, value in result.items() if key != "passages"}
        return "\n".join([f"- search_labels {json.dumps(header, ensure_ascii=False)}", *passages])
    return f"- {name} {json.dumps(result, ensure_ascii=False)}"


def report(name: str, runs: list[Run], verdicts: dict[str, Verdict] | None) -> str:
    judged = [verdicts[run.run_id] for run in runs] if verdicts is not None else None

    def count(flag: str) -> str:
        return "-" if judged is None else str(sum(getattr(v, flag) for v in judged))

    passed = "-" if verdicts is None else str(sum(passes(run, verdicts) for run in runs))
    tokens = [run.output_tokens for run in runs if run.output_tokens is not None]
    lines = [
        f"{name}, {len(runs)} answers, {sum(run.error is not None for run in runs)} errors",
        "",
        "| Answers | Pass | From memory | Denies data | Seconds p50 | Output tokens mean |",
        "|---|---|---|---|---|---|",
        f"| {len(runs)} | {passed} | {count('from_memory')} | {count('denies_data')} "
        f"| {statistics.median(run.answer.seconds for run in runs):.1f} "
        f"| {statistics.mean(tokens) if tokens else 0:.0f} |",
    ]
    if verdicts is not None:
        failed = [run for run in runs if not passes(run, verdicts)]
        lines += ["", "Failed:"]
        lines += [f"- {run.run_id}: {verdicts[run.run_id].note}" for run in failed] or ["- none"]
    return "\n".join(lines)


def passes(run: Run, verdicts: dict[str, Verdict]) -> bool:
    return run.error is None and bool(run.text) and verdicts[run.run_id].passed


if __name__ == "__main__":
    raise SystemExit(main())
