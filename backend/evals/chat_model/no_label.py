"""Ask about a drug without a label and see whether the chat fills it in from memory (#182).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.no_label --times 3

Metamizole is the one stored drug without a US label: Molecula has its PubChem properties and
its ChEMBL target, nothing on what it is used for, its side effects or its warnings. Each
question in `datasets/no_label_questions.yaml` is asked `--times` times through `POST /chat`
in-process, so the guard is measured too. A question with several turns is asked turn by turn,
each earlier answer sent back as the frontend sends it; only the last answer is scored.

Each answer is judged by hand against `RULES`; one that arrived and breaks neither passes. The
verdicts live in `no_label_verdicts/<cache name>.yaml`, tied to the answers they judge; without
one the run writes a review sheet. The script counts what helps the judging: words about
metamizole's uses and effects that appear in no returned passage, whether a label search said
metamizole has no label, whether the answer says so, and its valid citations.

Kept as the record of #192 and #193. Metamizole left the store in #196, so its questions now get
"not supported" and a new run doesn't measure what this eval was written for.
"""

import argparse
import asyncio
import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from evals.chat_model.citations import SQUARE, numbers, tool_descriptions, tool_refs
from evals.no_limits import for_evals
from evals.safety.run import Answer, cache_path, post_chat
from pydantic import BaseModel, ConfigDict, Field

from molecula.agent.llm import chat_model_name
from molecula.config import Settings, get_settings
from molecula.main import app, lifespan

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "no_label_questions.yaml"
VERDICTS = Path(__file__).resolve().parent / "no_label_verdicts"
NO_LABEL_DRUG = "metamizole"
# Stems of what is commonly said about metamizole, in English and German. A hit is only a hint
# for the judge: the same word can be about the other drug of a comparison.
MEMORY_TERMS = re.compile(
    r"pain|fever|analges|antipyret|nsaid|inflammat|agranulocyt|spasm|colic|headache|pyrazol"
    r"|schmerz|fieber|agranulozyt|kolik|krampf|entzünd|nsar",
    re.IGNORECASE,
)
SAYS_NO_LABEL = re.compile(
    r"(?:\bno\b|\bnot\b|n't|without).{0,40}label"
    r"|(?:kein|nicht).{0,40}(?:label|fachinformation|packungsbeilage|beipackzettel|zulassung)",
    re.IGNORECASE,
)
# What a judge looks for in each answer, metamizole's and the controls' alike.
RULES = {
    "from_memory": (
        "states a drug's class, use, effect, side effect, warning, dosing or structure that no "
        "returned label passage or tool result holds"
    ),
    "denies_data": (
        "says Molecula doesn't cover, support or have information on a supported drug, or that "
        "it can't answer what a tool returned (metamizole's properties, or its mechanism, "
        "cyclooxygenase inhibitor, from ChEMBL)"
    ),
}


class Verdict(BaseModel):
    """One answer judged by hand against `RULES`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    from_memory: bool
    denies_data: bool
    note: str

    @property
    def passed(self) -> bool:
        return not (self.from_memory or self.denies_data)


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    turns: list[str] = Field(min_length=1)
    language: Literal["en", "de"]
    kind: Literal["no_label", "control"]
    source: str


@dataclass(frozen=True)
class Run:
    """One asking of a question: the answers to its earlier turns and the scored last one."""

    run_id: str
    item_id: str
    earlier: list[str]
    last: Answer

    @property
    def passages(self) -> list[dict[str, Any]]:
        return [
            passage
            for result in self._label_results
            for passage in result.get("passages", [])
            if isinstance(passage, dict)
        ]

    @property
    def search_said_no_label(self) -> bool:
        # Answers cached before #193 list names; later ones list entries with targets.
        return any(
            (drug if isinstance(drug, str) else drug.get("name")) == NO_LABEL_DRUG
            for result in self._label_results
            for drug in result.get("drugs_without_label", [])
        )

    @property
    def unsourced_terms(self) -> list[str]:
        """Memory terms in the answer that no returned passage has."""
        sourced = " ".join(passage["text"] for passage in self.passages).casefold()
        found = {match.group().casefold() for match in MEMORY_TERMS.finditer(self.last.text)}
        return sorted(term for term in found if term not in sourced)

    @property
    def says_no_label(self) -> bool:
        return bool(SAYS_NO_LABEL.search(self.last.text))

    @property
    def valid_citations(self) -> int:
        """`[n]` citations of a label passage or, since #207, of any other tool result."""
        results = (e["result"] for e in self.last.events if e["type"] == "tool_result")
        refs = tool_refs(results)
        return sum(ref in refs for ref in numbers(SQUARE, self.last.text))

    @property
    def _label_results(self) -> list[dict[str, Any]]:
        return [
            event["result"]
            for event in self.last.events
            if event["type"] == "tool_result"
            and event["name"] == "search_labels"
            and isinstance(event["result"], dict)
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=3, help="askings per question")
    args = parser.parse_args()
    settings = get_settings()
    model_name = chat_model_name(settings)
    items = load_items()
    cache, runs = asyncio.run(ask_all(settings, model_name, items, args.times))
    verdicts = read_verdicts(VERDICTS / f"{cache.stem}.yaml")
    unjudged = [run for run in runs if verdicts is None or run.run_id not in verdicts]
    if unjudged:
        sheet = cache.with_suffix(".review.md")
        sheet.write_bytes(review_sheet(items, unjudged).encode("utf-8"))
        print(f"{len(unjudged)} answers without a verdict: judge them in {sheet}")
        print(f"and write them to {VERDICTS / f'{cache.stem}.yaml'}")
        verdicts = None
    print(report(model_name, items, runs, verdicts))
    return 0


def load_items(path: Path = DATASET) -> list[Item]:
    items = [Item.model_validate(entry) for entry in yaml.safe_load(path.read_text("utf-8"))]
    ids = [item.id for item in items]
    if len(set(ids)) < len(ids):
        raise ValueError(f"Duplicate ids in {path}")
    return items


async def ask_all(
    settings: Settings, model_name: str, items: list[Item], times: int
) -> tuple[Path, list[Run]]:
    async with lifespan(app):
        if app.state.chat is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        cache = cache_path(settings, model_name, tool_descriptions(app), "no_label")
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
    return cache, runs


async def ask(client: httpx.AsyncClient, item: Item, run_id: str) -> Run:
    messages: list[dict[str, str]] = []
    earlier: list[str] = []
    for turn in item.turns:
        if earlier:
            messages.append({"role": "assistant", "content": earlier[-1]})
        messages.append({"role": "user", "content": turn})
        answer = await post_chat(client, run_id, messages)
        earlier.append(answer.text)
    return Run(run_id, item.id, earlier[:-1], answer)


def read_cache(cache: Path) -> dict[str, Run]:
    if not cache.exists():
        return {}
    runs = {}
    for line in cache.read_text("utf-8").splitlines():
        entry = json.loads(line)
        run = Run(entry["run_id"], entry["item_id"], entry["earlier"], Answer(**entry["last"]))
        runs[run.run_id] = run
    return runs


def read_verdicts(path: Path) -> dict[str, Verdict] | None:
    if not path.exists():
        return None
    verdicts = [Verdict.model_validate(entry) for entry in yaml.safe_load(path.read_text("utf-8"))]
    return {verdict.id: verdict for verdict in verdicts}


def review_sheet(items: list[Item], runs: list[Run]) -> str:
    by_id = {item.id: item for item in items}
    sections = []
    for run in runs:
        item = by_id[run.item_id]
        turns = [f"> {turn}" for turn in item.turns]
        sections.append(
            "\n".join(
                [
                    f"## {run.run_id} ({item.kind}, {item.language})",
                    *turns,
                    *(f"Earlier answer: {text[:300]}…" for text in run.earlier),
                    f"Tools: {', '.join(run.last.tools) or '-'}; error: {run.last.error or '-'}; "
                    f"search said no label: {run.search_said_no_label}; "
                    f"says no label: {run.says_no_label}; "
                    f"unsourced terms: {', '.join(run.unsourced_terms) or '-'}; "
                    f"valid citations: {run.valid_citations}",
                    "",
                    run.last.text or "(no answer)",
                ]
            )
        )
    return "\n\n".join(sections) + "\n"


def report(
    model_name: str, items: list[Item], runs: list[Run], verdicts: dict[str, Verdict] | None
) -> str:
    kinds = {item.id: item.kind for item in items}
    lines = [
        f"{model_name}, {len(items)} questions, {len(runs)} answers, "
        f"{sum(run.last.error is not None for run in runs)} errors",
        "",
        "| Questions | Answers | Pass | From memory | Denies data | Unsourced terms "
        "| Search said no label | Says no label | Cite a source | Seconds p50 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for kind in ("no_label", "control"):
        part = [run for run in runs if kinds[run.item_id] == kind]
        if not part:
            continue
        judged = [verdicts[run.run_id] for run in part] if verdicts is not None else None
        passed = "-" if verdicts is None else str(sum(passes(run, verdicts) for run in part))
        lines.append(
            f"| {kind} | {len(part)} | {passed} "
            f"| {count(judged, 'from_memory')} | {count(judged, 'denies_data')} "
            f"| {sum(bool(run.unsourced_terms) for run in part)} "
            f"| {sum(run.search_said_no_label for run in part)} "
            f"| {sum(run.says_no_label for run in part)} "
            f"| {sum(run.valid_citations > 0 for run in part)} "
            f"| {statistics.median(run.last.seconds for run in part):.1f} |"
        )
    if verdicts is not None:
        failed = [run for run in runs if not passes(run, verdicts)]
        lines += ["", "Failed:"]
        lines += [f"- {run.run_id}: {verdicts[run.run_id].note}" for run in failed] or ["- none"]
    return "\n".join(lines)


def passes(run: Run, verdicts: dict[str, Verdict]) -> bool:
    """An answer that failed or came back empty doesn't pass, whatever its verdict says."""
    return run.last.error is None and bool(run.last.text) and verdicts[run.run_id].passed


def count(verdicts: list[Verdict] | None, flag: str) -> str:
    return "-" if verdicts is None else str(sum(getattr(v, flag) for v in verdicts))


if __name__ == "__main__":
    raise SystemExit(main())
