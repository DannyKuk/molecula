"""Ask about drug names Molecula doesn't know and see how the chat words it (#181, #190).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.not_found --times 3

Each question in `datasets/not_found_questions.yaml` names a drug Molecula doesn't know: a typo
of a brand, a generic or a German name, a name with no close match, or a real drug that isn't
stored. It is asked `--times` times through `POST /chat` in-process, so the guard is measured
too. Each answer is judged by hand against `RULES`; one that arrived and breaks none passes. The
verdicts live in `not_found_verdicts/<cache name>.yaml`; without them the run writes a review
sheet. Two hints help the judging: whether the answer writes every suggested name as the tools
returned it, and which stored drug names it gives that neither the question nor a tool did.
"""

import argparse
import asyncio
import json
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from evals.chat_model.citations import tool_descriptions
from evals.chat_model.no_label import Run, ask, read_cache
from evals.no_limits import for_evals
from evals.safety.run import cache_path
from pydantic import BaseModel, ConfigDict, Field

from molecula.agent.llm import chat_model_name
from molecula.config import Settings, get_settings
from molecula.main import app, lifespan
from molecula.services.compounds import CompoundService

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "not_found_questions.yaml"
VERDICTS = Path(__file__).resolve().parent / "not_found_verdicts"
RULES = {
    "denies_data": (
        "says Molecula has no data on, or doesn't cover, a drug it suggested or named, or states "
        "something false about a drug it guessed"
    ),
    "misses_suggestion": (
        "with suggestions, offers none of them by the name it was returned with, or puts "
        "another name of the drug first; without, doesn't ask which drug is meant, or points at "
        "suggestions that weren't returned"
    ),
    "names_other_drug": "names a drug, or a name of one, that neither the user nor a tool gave",
    "answers_unasked": (
        "answers about a suggested or guessed drug as if the user had meant it, also after the "
        "agent looked up a corrected spelling itself"
    ),
}


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    turns: list[str] = Field(min_length=1)
    typed: str
    suggestions: list[str]
    language: Literal["en", "de"]
    source: str


class Verdict(BaseModel):
    """One answer judged by hand against `RULES`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    denies_data: bool
    misses_suggestion: bool
    names_other_drug: bool
    answers_unasked: bool
    note: str

    @property
    def passed(self) -> bool:
        return not (
            self.denies_data
            or self.misses_suggestion
            or self.names_other_drug
            or self.answers_unasked
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=3, help="askings per question")
    args = parser.parse_args()
    settings = get_settings()
    model_name = chat_model_name(settings)
    items = load_items()
    cache, runs, hints = asyncio.run(ask_all(settings, model_name, items, args.times))
    verdicts = read_verdicts(VERDICTS / f"{cache.stem}.yaml")
    unjudged = [run for run in runs if verdicts is None or run.run_id not in verdicts]
    if unjudged:
        sheet = cache.with_suffix(".review.md")
        sheet.write_bytes(review_sheet(items, unjudged, hints).encode("utf-8"))
        print(f"{len(unjudged)} answers without a verdict: judge them in {sheet}")
        print(f"and write them to {VERDICTS / f'{cache.stem}.yaml'}")
        verdicts = None
    print(report(model_name, runs, hints, verdicts))
    return 0


def load_items(path: Path = DATASET) -> list[Item]:
    items = [Item.model_validate(entry) for entry in yaml.safe_load(path.read_text("utf-8"))]
    ids = [item.id for item in items]
    if len(set(ids)) < len(ids):
        raise ValueError(f"Duplicate ids in {path}")
    return items


async def ask_all(
    settings: Settings, model_name: str, items: list[Item], times: int
) -> tuple[Path, list[Run], dict[str, dict[str, Any]]]:
    async with lifespan(app):
        if app.state.chat is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        cache = cache_path(settings, model_name, tool_descriptions(app), "not_found")
        cached = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        runs = []
        for_evals(app)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
            for item in items:
                for number in range(1, times + 1):
                    run_id = f"{item.id}#{number}"
                    if run_id not in cached:
                        cached[run_id] = await ask(client, item, run_id)
                        with cache.open("a", encoding="utf-8") as file:
                            file.write(json.dumps(asdict(cached[run_id])) + "\n")
                        print(f"{run_id}: {cached[run_id].last.seconds:.1f} s", flush=True)
                    runs.append(cached[run_id])
        by_id = {item.id: item for item in items}
        compounds = app.state.compound_service
        hints = {run.run_id: judge_hints(compounds, by_id[run.item_id], run) for run in runs}
    return cache, runs, hints


def judge_hints(compounds: CompoundService, item: Item, run: Run) -> dict[str, Any]:
    """Whether the answer writes each suggested name as returned, and the stored drug names it
    gives that neither the question nor a tool result holds."""
    returned = [suggestion for result in tool_results(run) for suggestion in suggestions_in(result)]
    text = run.last.text
    given = " ".join([*item.turns, *(json.dumps(r) for r in tool_results(run))]).casefold()
    unreturned = sorted(
        {
            mention.text
            for mention in compounds.find_mentions(text)
            if mention.text.casefold() not in given
        }
    )
    aliases = sorted({suggestion["alias"] for suggestion in returned})
    return {
        "suggested": aliases,
        "offers_all": all(alias.casefold() in text.casefold() for alias in aliases),
        "unreturned_names": unreturned,
        "tool_calls": [
            f"{event['name']}({json.dumps(event['args'], ensure_ascii=False)})"
            for event in run.last.events
            if event["type"] == "tool_call"
        ],
    }


def tool_results(run: Run) -> list[dict[str, Any]]:
    return [
        event["result"]
        for event in run.last.events
        if event["type"] == "tool_result" and isinstance(event["result"], dict)
    ]


def suggestions_in(value: Any) -> list[dict[str, Any]]:
    """Every suggestion in a tool result, however deep: `compare_drugs` and `search_labels` nest
    their not-supported entries."""
    if isinstance(value, dict):
        own = value.get("suggestions") if value.get("status") == "not_supported" else None
        nested = [s for child in value.values() for s in suggestions_in(child)]
        return [*(own or []), *nested]
    if isinstance(value, list):
        return [s for child in value for s in suggestions_in(child)]
    return []


def read_verdicts(path: Path) -> dict[str, Verdict] | None:
    if not path.exists():
        return None
    verdicts = [Verdict.model_validate(entry) for entry in yaml.safe_load(path.read_text("utf-8"))]
    return {verdict.id: verdict for verdict in verdicts}


def review_sheet(items: list[Item], runs: list[Run], hints: dict[str, dict[str, Any]]) -> str:
    by_id = {item.id: item for item in items}
    sections = []
    for run in runs:
        item = by_id[run.item_id]
        hint = hints[run.run_id]
        sections.append(
            "\n".join(
                [
                    f"## {run.run_id} ({item.language}; typed {item.typed}; "
                    f"expected suggestions: {', '.join(item.suggestions) or 'none'})",
                    *(f"> {turn}" for turn in item.turns),
                    f"Tools: {'; '.join(hint['tool_calls']) or '-'}",
                    f"Suggested: {', '.join(hint['suggested']) or '-'}; "
                    f"offers all: {hint['offers_all']}; "
                    f"unreturned names: {', '.join(hint['unreturned_names']) or '-'}; "
                    f"error: {run.last.error or '-'}",
                    "",
                    run.last.text or "(no answer)",
                ]
            )
        )
    return "\n\n".join(sections) + "\n"


def report(
    model_name: str,
    runs: list[Run],
    hints: dict[str, dict[str, Any]],
    verdicts: dict[str, Verdict] | None,
) -> str:
    with_suggestions = [run for run in runs if hints[run.run_id]["suggested"]]
    lines = [
        f"{model_name}, {len(runs)} answers, {sum(run.last.error is not None for run in runs)} "
        f"errors, {statistics.median(run.last.seconds for run in runs):.1f} s p50",
        "",
        f"- offers every suggestion as returned (hint): "
        f"{sum(hints[run.run_id]['offers_all'] for run in with_suggestions)} "
        f"of {len(with_suggestions)} with suggestions",
        f"- names a stored drug no one gave (hint): "
        f"{sum(bool(hints[run.run_id]['unreturned_names']) for run in runs)} of {len(runs)}",
    ]
    if verdicts is None:
        return "\n".join(lines)
    judged = [verdicts[run.run_id] for run in runs]
    lines += [
        f"- pass: {sum(passes(run, verdicts) for run in runs)} of {len(runs)}",
        *(f"- {rule}: {sum(getattr(v, rule) for v in judged)}" for rule in RULES),
        "",
        "Failed:",
    ]
    failed = [run for run in runs if not passes(run, verdicts)]
    lines += [f"- {run.run_id}: {verdicts[run.run_id].note}" for run in failed] or ["- none"]
    return "\n".join(lines)


def passes(run: Run, verdicts: dict[str, Verdict]) -> bool:
    """An answer that failed or came back empty doesn't pass, whatever its verdict says."""
    return run.last.error is None and bool(run.last.text) and verdicts[run.run_id].passed


if __name__ == "__main__":
    raise SystemExit(main())
