import asyncio
from typing import Any

import httpx
import openai
import pytest

from fake_llm import ScriptedChatModel, answer_message, tool_call_message
from guard_fakes import CHECK_USAGE, FakeCheck
from molecula.agent.agent import ChatAgent
from molecula.agent.tool_registry import build_tools
from molecula.guard.chat import CHECK_FAILED, CHECKING, GuardedChat
from molecula.guard.safety import InputCheckFailed, fixed_answer
from molecula.schemas.chat import (
    ChatEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    StatusEvent,
    TokenEvent,
    Usage,
)
from molecula.schemas.guard import InputCategory
from tool_fakes import (
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
)

QUESTION = [ChatMessage(role="user", content="My son swallowed ten acetaminophen tablets.")]


def agent(*script: Any) -> tuple[ChatAgent, ScriptedChatModel]:
    model = ScriptedChatModel(script=list(script))
    tools = build_tools(
        FakeCompoundService(), FakeTargetService(), FakeFilterExtractor(), FakeLabelRetriever()
    )
    return ChatAgent(model, tools, max_steps=5, timeout_seconds=10), model


def run(chat: GuardedChat) -> list[ChatEvent]:
    async def collect() -> list[ChatEvent]:
        return [event async for event in chat.stream(QUESTION)]

    return asyncio.run(collect())


def answer(events: list[ChatEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TokenEvent))


def done(events: list[ChatEvent]) -> DoneEvent:
    last = events[-1]
    assert isinstance(last, DoneEvent)
    return last


def test_an_ok_message_is_answered_by_the_agent() -> None:
    chat_agent, model = agent(
        tool_call_message("get_targets", {"drug": "imatinib"}),
        answer_message("Imatinib blocks the ABL1 kinase."),
    )
    check = FakeCheck("ok")

    events = run(GuardedChat(check, chat_agent, timeout_seconds=5))

    assert check.checked == [QUESTION]
    assert events[0] == StatusEvent(message=CHECKING)
    assert answer(events) == "Imatinib blocks the ABL1 kinase."
    assert len(model.received) == 2
    assert done(events).category == "ok"


def test_the_answers_usage_counts_the_check_too() -> None:
    chat_agent, _ = agent(answer_message("Imatinib blocks the ABL1 kinase."))

    events = run(GuardedChat(FakeCheck("ok"), chat_agent, timeout_seconds=5))

    assert done(events).usage == CHECK_USAGE + Usage(
        input_tokens=12, output_tokens=8, total_tokens=20
    )


def test_a_possible_overdose_gets_the_emergency_line_first_and_then_the_agents_answer() -> None:
    chat_agent, _ = agent(answer_message("The label says an overdose can damage the liver."))

    events = run(GuardedChat(FakeCheck("overdose_emergency"), chat_agent, timeout_seconds=5))

    first_token = next(event for event in events if isinstance(event, TokenEvent))
    assert first_token.text == fixed_answer("overdose_emergency") + "\n\n"
    assert answer(events) == (
        fixed_answer("overdose_emergency") + "\n\nThe label says an overdose can damage the liver."
    )
    assert done(events).category == "overdose_emergency"


@pytest.mark.parametrize(
    "category", ["personal_medical_advice", "lethal_dose", "synthesis_or_misuse", "off_topic"]
)
def test_an_unsafe_or_off_topic_message_gets_its_fixed_answer_and_no_agent(
    category: InputCategory,
) -> None:
    chat_agent, model = agent()

    events = run(GuardedChat(FakeCheck(category), chat_agent, timeout_seconds=5))

    assert [event.type for event in events] == ["status", "token", "sources", "done"]
    assert answer(events) == fixed_answer(category)
    assert model.received == []
    assert done(events).category == category
    assert done(events).usage == CHECK_USAGE


def provider_timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", "http://llm.test/chat"))


@pytest.mark.parametrize(
    ("check", "message"),
    [
        (FakeCheck(error=InputCheckFailed("no category")), CHECK_FAILED),
        (FakeCheck(delay=1.0), CHECK_FAILED),
        (FakeCheck(error=provider_timeout()), "The language model didn't answer in time."),
    ],
    ids=["invalid output", "check timeout", "provider timeout"],
)
def test_a_check_that_fails_answers_nothing(check: FakeCheck, message: str) -> None:
    chat_agent, model = agent()

    events = run(GuardedChat(check, chat_agent, timeout_seconds=0.05))

    assert events[0] == StatusEvent(message=CHECKING)
    [error] = events[1:]
    assert isinstance(error, ErrorEvent)
    assert error.message.startswith(message)
    assert model.received == []
