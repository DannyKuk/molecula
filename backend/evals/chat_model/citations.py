"""Measure how the chat agent cites label passages (#129) on the retrieval questions.

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.citations

Asks the agent every question in `datasets/retrieval_questions.yaml`, one single-turn
conversation each, through `ChatAgent.stream` as the app wires it. Scores only the chat events,
so the same runner measures an older checkout of the agent too (put its `src` first on
PYTHONPATH). A citation is valid when it points at a source a tool returned in that answer:
`[n]` or `【n】` with the `ref` of a label passage (or, since #207, of a PubChem, ChEMBL or PDB
source), or a Markdown link to a passage's DailyMed page (the style before #129). `【n】` is
gpt-oss's own citation style; it is counted apart, as "square" (`[n]` and links only) next to
"any", to show what accepting it adds. An answer cites
the evidence when a passage it cites holds the question's evidence; a link only names a label,
so for links that is checked per label, not per passage.
Each answer is cached in data/build/eval/citations/, keyed by model, system prompt, tool
descriptions and `--variant` (name a code change the key can't see), so an interrupted run goes
on where it stopped.
"""

import argparse
import asyncio
import hashlib
import json
import re
import statistics
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from evals.retrieval.dataset import Question, load_questions
from fastapi import FastAPI

from molecula import prompts
from molecula.agent.agent import ChatAgent
from molecula.agent.llm import chat_model_name
from molecula.agent.tool_registry import build_tools
from molecula.config import Settings, get_settings
from molecula.main import lifespan, online_decision_model
from molecula.schemas.chat import ChatMessage

SQUARE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
FULL_WIDTH = re.compile(r"【(\d+(?:\s*,\s*\d+)*)】")
LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
OTHER_MARKER = re.compile(r"【[^】]*[^\d\s,】][^】]*】")


@dataclass(frozen=True)
class Answer:
    question_id: str
    events: list[dict[str, Any]]
    seconds: float


@dataclass(frozen=True)
class Scored:
    question_id: str
    error: bool
    used_passages: bool
    citations: int
    valid: int
    cites_square: bool
    cites_any: bool
    all_valid: bool
    full_width: bool
    other_marker: bool
    cites_evidence: bool
    evidence_returned: bool
    seconds: float
    output_tokens: int | None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", default="", help="names a change the cache key can't see")
    args = parser.parse_args()
    settings = get_settings()
    model_name = chat_model_name(settings)
    questions = load_questions()
    answers = asyncio.run(ask_all(settings, model_name, questions, args.variant))
    scored = [score(q, a) for q, a in zip(questions, answers, strict=True)]
    print(report(model_name, scored))
    save(settings, model_name, questions, answers, scored)
    return 0


async def ask_all(
    settings: Settings, model_name: str, questions: list[Question], variant: str = ""
) -> list[Answer]:
    app = FastAPI()
    async with lifespan(app):
        agent: ChatAgent | None = app.state.chat_agent
        if agent is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        cache = cache_path(settings, model_name, tool_descriptions(app), variant)
        cached = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        for number, question in enumerate(questions, start=1):
            if question.id in cached:
                continue
            cached[question.id] = await ask(agent, question)
            with cache.open("a", encoding="utf-8") as file:
                file.write(json.dumps(asdict(cached[question.id])) + "\n")
            print(
                f"{number}/{len(questions)} {question.id}: {cached[question.id].seconds:.1f} s",
                flush=True,
            )
    return [cached[question.id] for question in questions]


async def ask(agent: ChatAgent, question: Question) -> Answer:
    start = perf_counter()
    conversation = [ChatMessage(role="user", content=question.question)]
    events = [event.model_dump(mode="json") async for event in agent.stream(conversation)]
    return Answer(question.id, events, perf_counter() - start)


def tool_descriptions(app: FastAPI) -> str:
    state = app.state
    tools = build_tools(
        state.compound_service,
        state.target_service,
        state.complex_service,
        state.filter_extractor,
        state.label_retriever,
    )
    return "\n".join(f"{tool.name}: {tool.description}" for tool in tools)


def cache_path(settings: Settings, model_name: str, descriptions: str, variant: str = "") -> Path:
    name = answer_label(settings, model_name)
    setup = f"{name}\n{prompts.template('agent/system').text}\n{descriptions}"
    if variant:
        setup += f"\n{variant}"
    key = hashlib.sha256(setup.encode()).hexdigest()[:12]
    slug = name.replace("/", "_") + (f"-{variant}" if variant else "")
    return settings.build_dir / "eval" / "citations" / f"{slug}-{key}.jsonl"


def model_label(settings: Settings, model_name: str) -> str:
    """The model and, when one is set, its reasoning effort: `openai/gpt-oss-20b-medium`."""
    effort = settings.llm_reasoning_effort
    return f"{model_name}-{effort}" if effort else model_name


def answer_label(settings: Settings, model_name: str) -> str:
    """The model label and the answering agent's effort, unless it is the model's default:
    `openai/gpt-oss-20b-answer-medium` (#254)."""
    label = model_label(settings, model_name)
    effort = settings.answer_reasoning_effort
    return label if effort == "default" else f"{label}-answer-{effort}"


def chat_label(settings: Settings, model_name: str) -> str:
    """The answer label and the source check's effort, for evals that ask `POST /chat`, where
    the check runs after each answer: `openai/gpt-oss-20b-answer-medium-check-medium`. When a
    decision model sorts the messages (online, #226) and fills the label filter (#290), it is
    named too: `…-check-medium-input-jev-1.13-filter`."""
    label = f"{answer_label(settings, model_name)}-check-{settings.source_check_reasoning_effort}"
    decision_model = online_decision_model(settings)
    return label if decision_model is None else f"{label}-input-{decision_model.model}-filter"


def read_cache(cache: Path) -> dict[str, Answer]:
    if not cache.exists():
        return {}
    answers = (Answer(**json.loads(line)) for line in cache.read_text("utf-8").splitlines())
    return {answer.question_id: answer for answer in answers}


def score(question: Question, answer: Answer) -> Scored:
    events = answer.events
    text = "".join(e["text"] for e in events if e["type"] == "token")
    passages = [
        passage
        for e in events
        if e["type"] == "tool_result" and e["name"] == "search_labels"
        if isinstance(e["result"], dict)
        for passage in e["result"].get("passages", [])
    ]
    by_ref = {p["ref"]: p for p in passages if p.get("ref") is not None}
    by_url: dict[str, list[dict[str, Any]]] = {}
    for passage in passages:
        by_url.setdefault(passage["url"], []).append(passage)

    refs = tool_refs(e["result"] for e in events if e["type"] == "tool_result")
    square = numbers(SQUARE, text)
    full_width = numbers(FULL_WIDTH, text)
    urls = [url for url in LINK.findall(text) if "dailymed" in url]
    cited = [by_ref[ref] for ref in square + full_width if ref in by_ref]
    cited += [p for url in urls if url in by_url for p in by_url[url]]
    valid_square = sum(ref in refs for ref in square) + sum(url in by_url for url in urls)
    valid = valid_square + sum(ref in refs for ref in full_width)
    citations = len(square) + len(full_width) + len(urls)
    done = next((e for e in events if e["type"] == "done"), None)
    return Scored(
        question_id=question.id,
        error=done is None,
        used_passages=bool(passages),
        citations=citations,
        valid=valid,
        cites_square=valid_square > 0,
        cites_any=valid > 0,
        all_valid=citations > 0 and valid == citations,
        full_width=bool(full_width),
        other_marker=bool(OTHER_MARKER.search(text)),
        cites_evidence=any(holds_evidence(question, p) for p in cited),
        evidence_returned=any(holds_evidence(question, p) for p in passages),
        seconds=answer.seconds,
        output_tokens=done["usage"]["output_tokens"] if done else None,
    )


def tool_refs(results: Iterable[Any]) -> set[int]:
    """Every `ref` in the tool results: label passages, and since #207 PubChem, ChEMBL and PDB."""
    found: set[int] = set()
    pending = list(results)
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if isinstance(value.get("ref"), int):
                found.add(value["ref"])
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return found


def numbers(pattern: re.Pattern[str], text: str) -> list[int]:
    return [int(ref) for match in pattern.finditer(text) for ref in match[1].split(",")]


def holds_evidence(question: Question, passage: dict[str, Any]) -> bool:
    return passage["cid"] == question.cid and any(e in passage["text"] for e in question.passages)


def report(model_name: str, scored: list[Scored]) -> str:
    used = [s for s in scored if s.used_passages]
    found = [s for s in used if s.evidence_returned]

    def share(part: list[Scored], flag: str) -> str:
        count = sum(getattr(s, flag) for s in part)
        return f"{count / len(part):.2f} ({count})" if part else "-"

    seconds = sorted(s.seconds for s in scored)
    tokens = [s.output_tokens for s in scored if s.output_tokens is not None]
    citations = [s.citations for s in used]
    lines = [
        f"{model_name}, {len(scored)} questions, {len(used)} answers used label passages, "
        f"{sum(s.error for s in scored)} errors",
        "",
        "Of the answers that used passages:",
        "",
        "| Cite a passage: `[n]` or link | also `【n】` | Every citation valid | Use `【n】` "
        "| Other markers | Citations mean | Cite the evidence (when returned) |",
        "|---|---|---|---|---|---|---|",
        f"| {share(used, 'cites_square')} | {share(used, 'cites_any')} "
        f"| {share(used, 'all_valid')} | {share(used, 'full_width')} "
        f"| {share(used, 'other_marker')} | {statistics.mean(citations):.1f} "
        f"| {share(found, 'cites_evidence')} of {len(found)} |"
        if used
        else "| - | - | - | - | - | - | - |",
        "",
        f"Seconds p50 / p95: {statistics.median(seconds):.1f} / "
        f"{seconds[int(0.95 * (len(seconds) - 1))]:.1f}; output tokens mean: "
        f"{statistics.mean(tokens):.0f}"
        if tokens
        else "",
        "",
        "Used passages, cited none: " + ids(s for s in used if not s.cites_any),
        "Invalid citations: " + ids(s for s in used if s.valid < s.citations),
        "No passages: " + ids(s for s in scored if not s.used_passages),
    ]
    return "\n".join(lines)


def ids(scored: Iterable[Scored]) -> str:
    return ", ".join(s.question_id for s in scored) or "-"


def save(
    settings: Settings,
    model_name: str,
    questions: list[Question],
    answers: list[Answer],
    scored: list[Scored],
) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = settings.build_dir / "eval" / f"citations-{model_name.replace('/', '_')}-{stamp}.json"
    payload = {
        "model": model_name,
        "prompt": prompts.template("agent/system").text,
        "questions": [question.model_dump() for question in questions],
        "answers": [asdict(answer) for answer in answers],
        "scored": [asdict(s) for s in scored],
    }
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    raise SystemExit(main())
