"""Sort every message of the input-check set several times with the guard alone (#162).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.safety.repeat --times 10 --category ok

`run` asks each message once, and at temperature 0.2 one sort can be luck: a message the guard
gets wrong half the time passes a single run as often as not. This asks only the guard, through
the same `ChatModelInputCheck` the chat uses, and prints how often each message lands in its
category. To compare two classify prompts, run it on each branch.
"""

import argparse
import asyncio
from collections import Counter

from evals.safety.dataset import InputCheckItem, load_items

from molecula.agent.llm import get_chat_model
from molecula.config import get_settings
from molecula.guard.safety import ChatModelInputCheck, InputCheckFailed
from molecula.schemas.chat import ChatMessage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=10, help="sorts per message")
    parser.add_argument("--category", help="only the messages that belong in this category")
    args = parser.parse_args()
    items = [i for i in load_items() if args.category in (None, i.category)]
    input_check = ChatModelInputCheck(get_chat_model(get_settings()))
    results = asyncio.run(sort_all(input_check, items, args.times))
    print(report(items, results, args.times))


async def sort_all(
    input_check: ChatModelInputCheck, items: list[InputCheckItem], times: int
) -> dict[str, Counter[str]]:
    results = {}
    for number, item in enumerate(items, start=1):
        conversation = item.messages()
        sorts = [await sort_once(input_check, conversation) for _ in range(times)]
        results[item.id] = Counter(sorts)
        print(f"{number}/{len(items)} {item.id}: {results[item.id][item.category]}/{times}")
    return results


async def sort_once(input_check: ChatModelInputCheck, conversation: list[ChatMessage]) -> str:
    try:
        return (await input_check.check(conversation)).category
    except InputCheckFailed:
        return "failed"


def report(items: list[InputCheckItem], results: dict[str, Counter[str]], times: int) -> str:
    lines = [
        f"{times} sorts per message",
        "",
        "| Message | Category | Sorted into it | Otherwise |",
        "|---|---|---|---|",
    ]
    for item in items:
        counts = results[item.id]
        otherwise = ", ".join(
            f"{category} {count}" for category, count in counts.items() if category != item.category
        )
        lines.append(f"| {item.id} | {item.category} | {counts[item.category]} | {otherwise} |")
    lines += ["", *summary(items, results)]
    return "\n".join(lines)


def summary(items: list[InputCheckItem], results: dict[str, Counter[str]]) -> list[str]:
    ok = [results[item.id] for item in items if item.category == "ok"]
    unsafe = [results[item.id] for item in items if item.category != "ok"]
    ok_sorts = sum(counts.total() for counts in ok)
    false_alarms = ok_sorts - sum(counts["ok"] for counts in ok)
    missed = sum(counts["ok"] for counts in unsafe)
    return [
        f"False alarms (`ok` sorted as something else): {false_alarms} of {ok_sorts} sorts",
        f"Missed (unsafe sorted as `ok`): {missed} of {sum(c.total() for c in unsafe)} sorts",
    ]


if __name__ == "__main__":
    main()
