"""Ask for a drug in 3D in a follow-up turn and count whether `get_complex` was called (#173).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.followup_3d --times 5

Runs each conversation of `datasets/followup_3d.yaml` `--times` times through `ChatAgent.stream`,
without the guard, as the comparisons eval does. The first question is answered by the agent, and
its answer goes back as text only, as the frontend sends earlier turns (`conversationWith` in
`frontend/lib/chat-turn.ts`); then the follow-up is asked. The 3D view opens only for a
`get_complex` result (`structuresOf` in `frontend/lib/tool-cards.ts`), so a follow-up without one
shows no view. As a baseline, each follow-up is also asked as the first question of a new chat.

The report counts the answers whose `get_complex` call resolved to the expected drug, the
statuses it returned, and two text heuristics: whether the answer mentions the view under it
(below, shown, view; unten, angezeigt, Ansicht) and whether a sentence says there is no 3D
structure without saying it is about the drug bound to its target. Every answer the heuristics
flag, and every answer without the `get_complex` call, is printed under the table to be read.
Each run is cached in data/build/eval/followup_3d/, keyed by model, system prompt and tool
descriptions, so an interrupted run goes on where it stopped.
"""

import argparse
import asyncio
import hashlib
import json
import re
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import yaml
from evals.chat_model.citations import answer_label, tool_descriptions
from fastapi import FastAPI
from pydantic import BaseModel

from molecula import prompts
from molecula.agent.agent import ChatAgent
from molecula.agent.llm import chat_model_name
from molecula.config import Settings, get_settings
from molecula.main import lifespan
from molecula.schemas.chat import ChatMessage

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "followup_3d.yaml"
FIRST_ANSWER_TRIES = 3
SENTENCE = re.compile(r"[^.!?\n]+")
VIEW = re.compile(
    r"\b(below|beneath|under (this|the) answer|view(er)?|shown|displayed|you can see|visible"
    r"|unten|darunter|ansicht|angezeigt|zu sehen|dargestellt|sichtbar)\b",
    re.IGNORECASE,
)
NO_3D = re.compile(
    r"(\bno\b|\bnot\b|n't\b|\bkein\w*|\bnicht\b)[^.!?\n]{0,60}"
    r"(3d|3-d|three-dimensional|structure|model|struktur|modell)"
    r"|(can't|cannot|can not|unable to)\s[^.!?\n]{0,30}(show|render|display)",
    re.IGNORECASE,
)
BOUND_TO_TARGET = re.compile(
    r"bound|bind|target|complex|protein|receptor|enzyme|gebunden|bindet|ziel|komplex|rezeptor"
    r"|enzym",
    re.IGNORECASE,
)


class FollowupConversation(BaseModel):
    id: str
    first: str
    followup: str
    drug: str
    expected: Literal["found", "no_complex"]


@dataclass(frozen=True)
class Asked:
    key: str
    first_answer: str | None
    events: list[dict[str, Any]]
    seconds: float

    @property
    def answer(self) -> str:
        return "".join(e["text"] for e in self.events if e["type"] == "token").strip()

    @property
    def failed(self) -> bool:
        return any(e["type"] == "error" for e in self.events)

    @property
    def complex_results(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] == "tool_result" and e["name"] == "get_complex"]

    @property
    def tool_calls(self) -> list[str]:
        return [
            f"{e['name']}({e['args'].get('drug', '')})" if e["name"] == "get_complex" else e["name"]
            for e in self.events
            if e["type"] == "tool_call"
        ]

    def complex_for(self, drug: str) -> dict[str, Any] | None:
        for event in self.complex_results:
            result = event["result"]
            if isinstance(result, dict) and str(result.get("name", "")).lower() == drug:
                return event
        return None

    @property
    def mentions_view(self) -> bool:
        return bool(VIEW.search(self.answer))

    @property
    def claims_no_3d(self) -> bool:
        return any(
            NO_3D.search(sentence) and not BOUND_TO_TARGET.search(sentence)
            for sentence in SENTENCE.findall(self.answer)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=5, help="runs per conversation")
    parser.add_argument("--only", action="append", help="run only this conversation id")
    args = parser.parse_args()
    settings = get_settings()
    conversations = [c for c in load_conversations() if not args.only or c.id in args.only]
    asked = asyncio.run(ask_all(settings, conversations, args.times))
    print(report(conversations, asked))
    return 0


def load_conversations(path: Path = DATASET) -> list[FollowupConversation]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [FollowupConversation.model_validate(entry) for entry in entries]


def followup_key(conversation: FollowupConversation) -> str:
    return f"followup:{conversation.id}"


def first_question_key(conversation: FollowupConversation) -> str:
    """Keyed by the question, so a follow-up two conversations share is asked alone once."""
    return f"first:{conversation.followup}"


async def ask_all(
    settings: Settings, conversations: list[FollowupConversation], times: int
) -> dict[str, list[Asked]]:
    app = FastAPI()
    async with lifespan(app):
        agent: ChatAgent | None = app.state.chat_agent
        if agent is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        cache = cache_path(settings, tool_descriptions(app))
        asked = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        for conversation in conversations:
            for key, history in (
                (followup_key(conversation), conversation.first),
                (first_question_key(conversation), None),
            ):
                while len(asked[key]) < times:
                    answer = await ask(agent, key, conversation.followup, history)
                    asked[key].append(answer)
                    with cache.open("a", encoding="utf-8") as file:
                        file.write(json.dumps(asdict(answer)) + "\n")
                    print(f"{key} {len(asked[key])}: {answer.seconds:.1f} s", flush=True)
    return {key: answers[:times] for key, answers in asked.items()}


async def ask(agent: ChatAgent, key: str, question: str, first: str | None) -> Asked:
    start = perf_counter()
    conversation: list[ChatMessage] = []
    first_answer = None
    if first is not None:
        first_answer = await answer_first(agent, first)
        conversation = [
            ChatMessage(role="user", content=first),
            ChatMessage(role="assistant", content=first_answer),
        ]
    conversation.append(ChatMessage(role="user", content=question))
    events = [event.model_dump(mode="json") async for event in agent.stream(conversation)]
    return Asked(key, first_answer, events, perf_counter() - start)


async def answer_first(agent: ChatAgent, question: str) -> str:
    """The first turn's answer text, asked again when it failed: the frontend sends no failed
    turn as history."""
    for _ in range(FIRST_ANSWER_TRIES):
        conversation = [ChatMessage(role="user", content=question)]
        events = [event async for event in agent.stream(conversation)]
        if not any(event.type == "error" for event in events):
            text = "".join(event.text for event in events if event.type == "token").strip()
            if text:
                return text
    raise SystemExit(f"No answer in {FIRST_ANSWER_TRIES} tries to the first question: {question}")


def cache_path(settings: Settings, descriptions: str) -> Path:
    name = answer_label(settings, chat_model_name(settings))
    setup = f"{name}\n{prompts.load('agent/system')}\n{descriptions}"
    key = hashlib.sha256(setup.encode()).hexdigest()[:12]
    return settings.build_dir / "eval" / "followup_3d" / f"{name.replace('/', '_')}-{key}.jsonl"


def read_cache(cache: Path) -> defaultdict[str, list[Asked]]:
    asked: defaultdict[str, list[Asked]] = defaultdict(list)
    if cache.exists():
        for line in cache.read_text("utf-8").splitlines():
            answer = Asked(**json.loads(line))
            asked[answer.key].append(answer)
    return asked


def report(conversations: list[FollowupConversation], asked: dict[str, list[Asked]]) -> str:
    lines = [
        "| Conversation | Turn | get_complex for the drug | Statuses | View mentioned "
        '| "No 3D" claim | Errors | Seconds p50 | Tools |',
        "|---|---|---|---|---|---|---|---|---|",
    ]
    flagged: list[str] = []
    reported: set[str] = set()
    for conversation in conversations:
        for turn, key in (
            ("follow-up", followup_key(conversation)),
            ("first question", first_question_key(conversation)),
        ):
            answers = asked.get(key, [])
            if not answers or key in reported:
                continue
            reported.add(key)
            results = [a.complex_for(conversation.drug) for a in answers]
            statuses = ", ".join(r["status"] if r else "-" for r in results)
            tools = "; ".join(", ".join(a.tool_calls) or "none" for a in answers)
            lines.append(
                f"| {conversation.id} | {turn} | {sum(r is not None for r in results)} of "
                f"{len(answers)} | {statuses} | {sum(a.mentions_view for a in answers)} "
                f"| {sum(a.claims_no_3d for a in answers)} | {sum(a.failed for a in answers)} "
                f"| {statistics.median(a.seconds for a in answers):.1f} | {tools} |"
            )
            flagged.extend(
                f"### {conversation.id}, {turn} {number}\n\n{a.answer}\n"
                for number, (a, r) in enumerate(zip(answers, results, strict=True), 1)
                if r is None or a.claims_no_3d or not a.mentions_view
            )
    return "\n".join([*lines, "", "## Answers to read", "", *flagged])


if __name__ == "__main__":
    raise SystemExit(main())
