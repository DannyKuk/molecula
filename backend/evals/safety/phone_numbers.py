"""Ask each overdose message several times through the chat and count the phone numbers (#168).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.safety.phone_numbers --times 10

`run` asks each message once, which hides a number the model writes in one answer of three.
This asks the `overdose_emergency` messages through the same in-process `POST /chat` and prints
how many answers name a phone number other than 911 and 112, and which ones. Nothing is cached;
`--save answers.jsonl` keeps every answer's text, to judge by hand (#149).
"""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

import httpx
from evals.no_limits import without_chat_limits
from evals.safety.dataset import InputCheckItem, load_items
from evals.safety.run import Answer, ask

from molecula.main import app, lifespan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=10, help="answers per message")
    parser.add_argument("--save", type=Path, help="write every answer's text to this .jsonl file")
    args = parser.parse_args()
    items = [i for i in load_items() if i.judged and i.category == "overdose_emergency"]
    print(asyncio.run(count_all(items, args.times, args.save)))


async def count_all(items: list[InputCheckItem], times: int, save: Path | None) -> str:
    lines = [
        f"{times} answers per message",
        "",
        "| Message | Answers with another number | Numbers |",
        "|---|---|---|",
    ]
    async with lifespan(app):
        if app.state.chat is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        without_chat_limits(app)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
            for item in items:
                answers = [await ask(client, item) for _ in range(times)]
                with_numbers = sum(bool(answer.other_phone_numbers) for answer in answers)
                numbers = Counter(n for answer in answers for n in answer.other_phone_numbers)
                listed = ", ".join(f"{n} ({count})" for n, count in numbers.items()) or "-"
                lines.append(f"| {item.id} | {with_numbers} of {times} | {listed} |")
                print(f"{item.id}: {with_numbers} of {times}", flush=True)
                if save:
                    append_answers(save, item, answers)
    return "\n".join(lines)


def append_answers(path: Path, item: InputCheckItem, answers: list[Answer]) -> None:
    with path.open("a", encoding="utf-8") as file:
        for answer in answers:
            line = {"id": item.id, "category": answer.category, "text": answer.text}
            file.write(json.dumps(line, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
