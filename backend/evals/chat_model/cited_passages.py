"""Check every citation of answers about several drugs or a follow-up about another drug (#166).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.cited_passages --times 3

Runs each conversation of `datasets/cited_passages.yaml` `--times` times through
`ChatAgent.stream`, without the guard, as the follow-up 3D eval does: every turn but the last is
answered by the agent and goes back as text, then the last question is asked and scored. The
citation eval (`citations.py`) asks single-drug questions and checks only that some cited passage
holds the answer key; this one looks at every citation of the answer.

Counted by script, per cited sentence or list item:
- a citation names the wrong drug when the item or its claim (with its list's lead-in) names one
  of the dataset's drugs and the cited result is about none of them;
- a term miss is an item whose cited results hold under half of its distinctive words while one
  result it doesn't cite holds at least half: a passage cited for a fact another one states.
  German answers are not scored for it, since their words aren't in the English labels.
A tool call for a drug the last question doesn't name is counted apart. Judged by the source check
(`ChatModelSourceCheck`, as the chat runs it), per claim: `supported` when the results it cites
hold it, `held_elsewhere` when they don't but another returned result does, `unsupported` when no
result does. Every wrong-drug citation, term miss and cited `held_elsewhere` claim is printed
under the table to be read.

Answers are cached in data/build/eval/cited_passages/, keyed by model, system prompt, tool
descriptions and `--variant` (name a code change the key can't see), checks next to them, keyed
by the answers and the check's model and prompt.
"""

import argparse
import asyncio
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import yaml
from evals.chat_model.citations import answer_label, tool_descriptions
from evals.jsonl import append, jsonl_lines
from fastapi import FastAPI
from pydantic import BaseModel

from molecula import prompts
from molecula.agent.agent import ChatAgent
from molecula.agent.llm import chat_model_name, get_source_check_model
from molecula.config import Settings, get_settings
from molecula.guard.claims import refs, split_claims, split_sentences
from molecula.guard.source_check import ChatModelSourceCheck, cited_sources
from molecula.main import lifespan
from molecula.schemas.chat import ChatMessage, ToolResultEvent
from molecula.schemas.claims import CheckedClaim

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "cited_passages.yaml"
DRUG_FIELDS = ("substance", "brand", "name", "drug")
TERM = re.compile(r"[a-z]{6,}")
# Words a claim and any passage of the same section share, so they tell no passage apart.
COMMON_WORDS = frozenset(
    [
        "patients",
        "reported",
        "report",
        "severe",
        "serious",
        "monitor",
        "monitoring",
        "including",
        "include",
        "includes",
        "should",
        "treatment",
        "therapy",
        "associated",
        "occurred",
        "occurs",
        "adverse",
        "reaction",
        "reactions",
        "warning",
        "warnings",
        "precautions",
        "effects",
        "effect",
        "common",
        "commonly",
        "labels",
        "labeling",
        "compared",
        "between",
        "difference",
        "differences",
        "comparison",
        "increased",
        "increase",
        "because",
        "during",
        "before",
        "through",
        "medicine",
        "medicines",
        "products",
        "product",
        "people",
        "taking",
        "without",
        "within",
        "others",
        "especially",
    ]
)
TERMS_HELD = 0.5
EARLIER_ANSWER_TRIES = 3


class Conversation(BaseModel):
    id: str
    turns: list[str]
    drugs: list[str]
    language: Literal["en", "de"] = "en"


class Dataset(BaseModel):
    aliases: dict[str, list[str]]
    conversations: list[Conversation]


@dataclass(frozen=True)
class Asked:
    conversation_id: str
    history: list[str]
    events: list[dict[str, Any]]
    seconds: float

    @property
    def answer(self) -> str:
        return "".join(e["text"] for e in self.events if e["type"] == "token").strip()

    @property
    def failed(self) -> bool:
        return any(e["type"] == "error" for e in self.events)

    @property
    def results(self) -> list[ToolResultEvent]:
        return [
            ToolResultEvent.model_validate(e) for e in self.events if e["type"] == "tool_result"
        ]

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] == "tool_call"]


@dataclass(frozen=True)
class WrongDrug:
    claim: str
    ref: int
    claim_drugs: list[str]
    source_drug: str
    source: str


@dataclass(frozen=True)
class TermMiss:
    claim: str
    cited: list[str]
    holder: str


@dataclass(frozen=True)
class Scored:
    conversation_id: str
    failed: bool
    citations: int
    unknown_refs: int
    wrong_drug: list[WrongDrug]
    off_question_calls: list[str]
    term_scored: int
    term_misses: list[TermMiss]
    labels: Counter[str]
    held_elsewhere: list[CheckedClaim]
    seconds: float


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=3, help="runs per conversation")
    parser.add_argument("--only", action="append", help="run only this conversation id")
    parser.add_argument("--variant", default="", help="names a change the cache key can't see")
    args = parser.parse_args()
    settings = get_settings()
    dataset = load_dataset()
    conversations = [c for c in dataset.conversations if not args.only or c.id in args.only]
    asked, checks = asyncio.run(ask_all(settings, conversations, args.times, args.variant))
    scored = {
        c.id: [score(dataset.aliases, c, a, checks[cache_key(a)]) for a in asked[c.id]]
        for c in conversations
    }
    print(report(conversations, scored))
    return 0


def load_dataset(path: Path = DATASET) -> Dataset:
    return Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


async def ask_all(
    settings: Settings, conversations: list[Conversation], times: int, variant: str
) -> tuple[dict[str, list[Asked]], dict[str, list[CheckedClaim]]]:
    app = FastAPI()
    async with lifespan(app):
        agent: ChatAgent | None = app.state.chat_agent
        if agent is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        answers_cache = cache_path(settings, tool_descriptions(app), variant)
        checks_cache = check_cache_path(settings, answers_cache)
        asked = read_answers(answers_cache)
        checks = read_checks(checks_cache)
        answers_cache.parent.mkdir(parents=True, exist_ok=True)
        source_check = ChatModelSourceCheck(get_source_check_model(settings))
        for conversation in conversations:
            while len(asked[conversation.id]) < times:
                answer = await ask(agent, conversation)
                asked[conversation.id].append(answer)
                append(answers_cache, asdict(answer))
                print(f"{conversation.id} {len(asked[conversation.id])}: {answer.seconds:.1f} s")
            for answer in asked[conversation.id][:times]:
                key = cache_key(answer)
                if key not in checks:
                    checked = await source_check.check(answer.answer, answer.results)
                    checks[key] = list(checked.claims)
                    claims = [claim.model_dump(mode="json") for claim in checked.claims]
                    append(checks_cache, {"key": key, "claims": claims})
    return {c.id: asked[c.id][:times] for c in conversations}, checks


async def ask(agent: ChatAgent, conversation: Conversation) -> Asked:
    start = perf_counter()
    history: list[str] = []
    messages: list[ChatMessage] = []
    for turn in conversation.turns[:-1]:
        reply = await earlier_answer(agent, messages, turn)
        history.append(reply)
        messages += [
            ChatMessage(role="user", content=turn),
            ChatMessage(role="assistant", content=reply),
        ]
    messages.append(ChatMessage(role="user", content=conversation.turns[-1]))
    events = [event.model_dump(mode="json") async for event in agent.stream(messages)]
    return Asked(conversation.id, history, events, perf_counter() - start)


async def earlier_answer(agent: ChatAgent, messages: list[ChatMessage], turn: str) -> str:
    """An earlier turn's answer text, asked again when it failed: the frontend sends no failed
    turn as history."""
    conversation = [*messages, ChatMessage(role="user", content=turn)]
    for _ in range(EARLIER_ANSWER_TRIES):
        events = [event async for event in agent.stream(conversation)]
        if not any(event.type == "error" for event in events):
            text = "".join(event.text for event in events if event.type == "token").strip()
            if text:
                return text
    raise SystemExit(f"No answer in {EARLIER_ANSWER_TRIES} tries to: {turn}")


def cache_path(settings: Settings, descriptions: str, variant: str) -> Path:
    name = answer_label(settings, chat_model_name(settings))
    setup = f"{name}\n{prompts.template('agent/system').text}\n{descriptions}\n{variant}"
    key = hashlib.sha256(setup.encode()).hexdigest()[:12]
    slug = name.replace("/", "_") + (f"-{variant}" if variant else "")
    return settings.build_dir / "eval" / "cited_passages" / f"{slug}-{key}.jsonl"


def check_cache_path(settings: Settings, answers_cache: Path) -> Path:
    setup = f"{settings.source_check_reasoning_effort}\n{prompts.load('guard/source_check')}"
    key = hashlib.sha256(setup.encode()).hexdigest()[:12]
    return answers_cache.with_name(f"{answers_cache.stem}-check-{key}.jsonl")


def cache_key(answer: Asked) -> str:
    return hashlib.sha256(json.dumps(answer.events).encode()).hexdigest()[:16]


def read_answers(path: Path) -> defaultdict[str, list[Asked]]:
    asked: defaultdict[str, list[Asked]] = defaultdict(list)
    if path.exists():
        for line in jsonl_lines(path):
            answer = Asked(**json.loads(line))
            asked[answer.conversation_id].append(answer)
    return asked


def read_checks(path: Path) -> dict[str, list[CheckedClaim]]:
    if not path.exists():
        return {}
    entries = (json.loads(line) for line in jsonl_lines(path))
    return {e["key"]: [CheckedClaim.model_validate(c) for c in e["claims"]] for e in entries}


def score(
    aliases: dict[str, list[str]],
    conversation: Conversation,
    answer: Asked,
    checked: list[CheckedClaim],
) -> Scored:
    sources = cited_sources([result.result for result in answer.results])
    citations = unknown = 0
    wrong: list[WrongDrug] = []
    term_scored = 0
    term_misses: list[TermMiss] = []
    for claim in split_claims(answer.answer):
        for unit in cited_units(claim.text):
            unit_refs = refs(unit)
            unit_drugs = list(
                dict.fromkeys(drugs_named(aliases, unit) + drugs_named(aliases, claim.text))
            )
            terms = distinctive_terms(aliases, unit)
            if conversation.language == "en" and len(terms) >= 2:
                term_scored += 1
                miss = term_miss(unit, unit_refs, terms, sources)
                if miss is not None:
                    term_misses.append(miss)
            for ref in unit_refs:
                citations += 1
                if ref not in sources:
                    unknown += 1
                    continue
                source_drug = drug_of(aliases, sources[ref])
                if unit_drugs and source_drug is not None and source_drug not in unit_drugs:
                    wrong.append(WrongDrug(unit, ref, unit_drugs, source_drug, label(sources[ref])))
    return Scored(
        conversation_id=conversation.id,
        failed=answer.failed,
        citations=citations,
        unknown_refs=unknown,
        wrong_drug=wrong,
        off_question_calls=[
            drug
            for call in answer.tool_calls
            for drug in drugs_named(aliases, json.dumps(call["args"]))
            if drug not in conversation.drugs
        ],
        term_scored=term_scored,
        term_misses=term_misses,
        labels=Counter(claim.label for claim in checked if claim.refs),
        held_elsewhere=[c for c in checked if c.refs and c.label == "held_elsewhere"],
        seconds=answer.seconds,
    )


def cited_units(claim: str) -> list[str]:
    """The claim's sentences and list items that cite something. The source check takes a list
    whose items all cite one source as one claim; each item is checked against its own refs."""
    return [
        sentence
        for line in claim.splitlines()
        for sentence in split_sentences(line)
        if refs(sentence)
    ]


def distinctive_terms(aliases: dict[str, list[str]], text: str) -> set[str]:
    """The claim's long words, cut to six letters so `cytopenias` finds `cytopenia`, without
    drug names and the words every passage of a section shares."""
    names = {name for names in aliases.values() for name in names}
    words = TERM.findall(text.lower())
    return {word[:6] for word in words if word not in COMMON_WORDS and word not in names}


def terms_held(terms: set[str], source: dict[str, Any]) -> float:
    text = (source.get("text") or json.dumps(source)).lower()
    return sum(term in text for term in terms) / len(terms)


def term_miss(
    claim: str, refs: tuple[int, ...], terms: set[str], sources: dict[int, dict[str, Any]]
) -> TermMiss | None:
    """A claim whose cited results hold under half its terms while one result it doesn't cite
    holds at least half: a passage cited for a fact another one states."""
    cited = [sources[ref] for ref in refs if ref in sources]
    if terms_held(terms, {"text": " ".join(json.dumps(s) for s in cited)}) >= TERMS_HELD:
        return None
    others = [(terms_held(terms, s), ref) for ref, s in sources.items() if ref not in refs]
    held, holder = max(others, default=(0.0, 0))
    if held < TERMS_HELD:
        return None
    cited_labels = [f"[{ref}] {label(sources[ref])}" for ref in refs if ref in sources]
    return TermMiss(claim, cited_labels, f"[{holder}] {label(sources[holder])}")


def drugs_named(aliases: dict[str, list[str]], text: str) -> list[str]:
    return [
        drug
        for drug, names in aliases.items()
        if any(re.search(rf"\b{re.escape(name)}", text, re.IGNORECASE) for name in names)
    ]


def drug_of(aliases: dict[str, list[str]], source: dict[str, Any]) -> str | None:
    """The dataset drug a result is about, from its naming fields, never from its text."""
    named = drugs_named(aliases, " ".join(naming_fields(source)))
    return named[0] if named else None


def naming_fields(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [
            text
            for key, child in value.items()
            for text in ([child] if key in DRUG_FIELDS and isinstance(child, str) else [])
            + (naming_fields(child) if isinstance(child, dict) else [])
        ]
    return []


def label(source: dict[str, Any]) -> str:
    if "section" in source:
        return f"{source.get('brand') or source.get('substance')} · {source['section']}"
    return " ".join(naming_fields(source))[:60]


def report(conversations: list[Conversation], scored: dict[str, list[Scored]]) -> str:
    lines = [
        "| Conversation | Answers | Citations | Wrong drug | Unknown ref | Cited claims "
        "| Term-scored claims | Term misses | Supported | Held elsewhere | Unsupported "
        "| Off-question tool calls | Errors | Seconds p50 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    every = [s for c in conversations for s in scored[c.id]]
    for name, runs in [*((c.id, scored[c.id]) for c in conversations), ("**All**", every)]:
        labels = sum((s.labels for s in runs), Counter())
        cited = sum(labels.values())
        lines.append(
            f"| {name} | {len(runs)} | {sum(s.citations for s in runs)} "
            f"| {sum(len(s.wrong_drug) for s in runs)} | {sum(s.unknown_refs for s in runs)} "
            f"| {cited} | {sum(s.term_scored for s in runs)} "
            f"| {sum(len(s.term_misses) for s in runs)} "
            f"| {labels['supported']} | {labels['held_elsewhere']} "
            f"| {labels['unsupported']} | {sum(bool(s.off_question_calls) for s in runs)} "
            f"| {sum(s.failed for s in runs)} "
            f"| {statistics.median(s.seconds for s in runs):.1f} |"
        )
    lines += ["", "Wrong-drug citations:"]
    for s in every:
        for w in s.wrong_drug:
            lines.append(
                f"- {s.conversation_id}: [{w.ref}] {w.source} cited for {', '.join(w.claim_drugs)}"
                f": {w.claim}"
            )
    lines += ["", "Term misses (another result holds the claim's terms; German not scored):"]
    for s in every:
        for miss in s.term_misses:
            lines.append(
                f"- {s.conversation_id}: cites {', '.join(miss.cited)}; {miss.holder} holds it: "
                f"{miss.claim}"
            )
    lines += ["", "Held elsewhere, by the source check:"]
    for s in every:
        for claim in s.held_elsewhere:
            lines.append(
                f"- {s.conversation_id}: cites {list(claim.refs)}, held by {list(claim.held_by)}: "
                f"{claim.text}"
            )
    lines += ["", "Off-question tool calls:"]
    lines += [
        f"- {s.conversation_id}: {', '.join(s.off_question_calls)}"
        for s in every
        if s.off_question_calls
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
