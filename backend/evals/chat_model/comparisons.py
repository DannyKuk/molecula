"""Ask questions about two drugs and count which drugs got a label search or a target lookup (#254).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.comparisons --times 3

Asks each question of `datasets/comparison_questions.yaml` `--times` times through
`ChatAgent.stream`, without the guard, as the from-memory eval does. A comparison of how drugs
work, what they are used for or their side effects needs each drug's label (`search_labels`) or
targets (`get_targets`); a 3D view or the chemical properties alone leave the rest to memory.
Whether an answer adds facts from memory is judged by reading it; the report gives the counts the
script can see: which drugs got evidence, the tools called, errors and seconds.
"""

import argparse
import asyncio
import hashlib
import json
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

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "comparison_questions.yaml"
EVIDENCE_TOOLS = ("search_labels", "get_targets")


class ComparisonQuestion(BaseModel):
    id: str
    question: str
    drugs: list[str]
    kind: Literal["3d_comparison", "comparison", "control"]


@dataclass(frozen=True)
class Asked:
    question_id: str
    events: list[dict[str, Any]]
    seconds: float

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] == "tool_call"]

    @property
    def failed(self) -> bool:
        return any(e["type"] == "error" for e in self.events)

    def has_evidence_for(self, drug: str) -> bool:
        return any(
            call["name"] in EVIDENCE_TOOLS and drug in json.dumps(call["args"]).lower()
            for call in self.tool_calls
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=3, help="askings per question")
    args = parser.parse_args()
    settings = get_settings()
    questions = load_questions()
    asked = asyncio.run(ask_all(settings, questions, args.times))
    print(report(questions, asked))
    return 0


def load_questions(path: Path = DATASET) -> list[ComparisonQuestion]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [ComparisonQuestion.model_validate(entry) for entry in entries]


async def ask_all(
    settings: Settings, questions: list[ComparisonQuestion], times: int
) -> dict[str, list[Asked]]:
    app = FastAPI()
    async with lifespan(app):
        agent: ChatAgent | None = app.state.chat_agent
        if agent is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        cache = cache_path(settings, tool_descriptions(app))
        asked = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        for question in questions:
            while len(asked[question.id]) < times:
                answer = await ask(agent, question)
                asked[question.id].append(answer)
                with cache.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(asdict(answer)) + "\n")
                print(
                    f"{question.id} {len(asked[question.id])}: {answer.seconds:.1f} s", flush=True
                )
    return {question.id: asked[question.id][:times] for question in questions}


async def ask(agent: ChatAgent, question: ComparisonQuestion) -> Asked:
    start = perf_counter()
    conversation = [ChatMessage(role="user", content=question.question)]
    events = [event.model_dump(mode="json") async for event in agent.stream(conversation)]
    return Asked(question.id, events, perf_counter() - start)


def cache_path(settings: Settings, descriptions: str) -> Path:
    name = answer_label(settings, chat_model_name(settings))
    setup = f"{name}\n{prompts.load('agent/system')}\n{descriptions}"
    key = hashlib.sha256(setup.encode()).hexdigest()[:12]
    return settings.build_dir / "eval" / "comparisons" / f"{name.replace('/', '_')}-{key}.jsonl"


def read_cache(cache: Path) -> defaultdict[str, list[Asked]]:
    asked: defaultdict[str, list[Asked]] = defaultdict(list)
    if cache.exists():
        for line in cache.read_text("utf-8").splitlines():
            answer = Asked(**json.loads(line))
            asked[answer.question_id].append(answer)
    return asked


def report(questions: list[ComparisonQuestion], asked: dict[str, list[Asked]]) -> str:
    lines = [
        "| Question | Kind | Evidence for every drug | Errors | Seconds p50 | Tools |",
        "|---|---|---|---|---|---|",
    ]
    for question in questions:
        answers = asked[question.id]
        complete = sum(all(a.has_evidence_for(d) for d in question.drugs) for a in answers)
        tools = "; ".join(", ".join(c["name"] for c in a.tool_calls) for a in answers)
        lines.append(
            f"| {question.id} | {question.kind} | {complete} of {len(answers)} "
            f"| {sum(a.failed for a in answers)} "
            f"| {statistics.median(a.seconds for a in answers):.1f} | {tools} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
