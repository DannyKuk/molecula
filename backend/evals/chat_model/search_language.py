"""Ask German retrieval questions through the chat and see what the agent searches for (#114).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.search_language

The agent writes the `question` of each `search_labels` call itself. `evals.retrieval.
query_translation` showed that an English search question finds the answering passage more often
than a German one. This asks every fifth German retrieval question (`datasets/
retrieval_questions_de.yaml`) through `POST /chat` in-process and reports in which language the
agent wrote its search questions, and whether a search returned a passage from the answer key
among its first five. Answers are cached in `data/build/eval/search_language/`, keyed by the
model, every prompt file and the tool descriptions.
"""

import asyncio
import json
import re
from dataclasses import asdict
from typing import Any

import httpx
from evals.chat_model.citations import tool_descriptions
from evals.no_limits import without_chat_limits
from evals.retrieval.dataset import Question, load_questions
from evals.retrieval.query_translation import load_german
from evals.safety.run import Answer, cache_path, post_chat, read_cache

from molecula.agent.llm import chat_model_name
from molecula.config import get_settings
from molecula.main import app, lifespan

STRIDE = 5
TOP = 5
# Function words that English questions don't use; one is enough to call a search German.
GERMAN_WORDS = re.compile(
    r"\b(?:der|die|das|den|dem|des|und|ist|sind|wie|welche[nrs]?|bei|mit|nicht|darf|kann|"
    r"ich|eine[mnrs]?|von|zu|auf|für|wird|werden|oder|nach|gegen|wofür|wann)\b|[äöüß]",
    re.IGNORECASE,
)


def main() -> int:
    questions = load_questions()[::STRIDE]
    german = load_german(load_questions())
    model_name, answers = asyncio.run(ask_all(questions, german))
    searches = 0
    in_german = 0
    found = 0
    lines = []
    for question in questions:
        answer = answers[question.id]
        asked = search_questions(answer)
        searches += len(asked)
        in_german += sum(bool(GERMAN_WORDS.search(text)) for text in asked)
        hit = answered(question, answer)
        found += hit
        lines.append(f"- {question.id}: {'hit' if hit else 'miss'}; {' | '.join(asked) or '-'}")
    print(f"{model_name}, {len(questions)} German questions, {searches} label searches\n")
    print(f"- searches written in German: {in_german} of {searches}")
    print(
        f"- questions with an answering passage in a search's top {TOP}: "
        f"{found} of {len(questions)}"
    )
    print("\n" + "\n".join(lines))
    return 0


async def ask_all(
    questions: list[Question], german: dict[str, str]
) -> tuple[str, dict[str, Answer]]:
    async with lifespan(app):
        if app.state.chat is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        settings = get_settings()
        model_name = chat_model_name(settings)
        cache = cache_path(settings, model_name, tool_descriptions(app), "search_language")
        answers = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        without_chat_limits(app)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
            for question in questions:
                if question.id in answers:
                    continue
                messages = [{"role": "user", "content": german[question.id]}]
                answers[question.id] = await post_chat(client, question.id, messages)
                with cache.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(asdict(answers[question.id])) + "\n")
                print(f"{question.id}: {answers[question.id].seconds:.1f} s", flush=True)
    return model_name, answers


def search_questions(answer: Answer) -> list[str]:
    return [
        event["args"].get("question", "")
        for event in answer.events
        if event["type"] == "tool_call" and event["name"] == "search_labels"
    ]


def answered(question: Question, answer: Answer) -> bool:
    """Whether a label search returned a passage of the answer key among its first `TOP`."""
    return any(
        passage.get("cid") == question.cid and any(p in passage["text"] for p in question.passages)
        for result in label_results(answer)
        for passage in result.get("passages", [])[:TOP]
    )


def label_results(answer: Answer) -> list[dict[str, Any]]:
    return [
        event["result"]
        for event in answer.events
        if event["type"] == "tool_result"
        and event["name"] == "search_labels"
        and isinstance(event["result"], dict)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
