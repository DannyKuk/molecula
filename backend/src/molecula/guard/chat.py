import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing

from molecula import prompts
from molecula.agent.agent import ChatAgent
from molecula.agent.decisions import DecisionModelError
from molecula.agent.llm import ChatModelError, describe_provider_error
from molecula.guard.canary import CanaryWatch, PromptLeaked
from molecula.guard.safety import REFUSED, InputCheck, InputCheckFailed, Verdict, fixed_answer
from molecula.schemas.chat import (
    ChatEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    ReplaceAnswerEvent,
    SourceCheckEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolResultEvent,
)
from molecula.schemas.source_check import SourceCheck, SourceCheckFailed
from molecula.schemas.usage import Usage

logger = logging.getLogger(__name__)

CHECKING = "Checking the question"
CHECKING_ANSWER = "Checking the answer against the sources"
CHECK_FAILED = "Molecula couldn't check this question, so it didn't answer it. Try again."


class GuardedChat:
    """The chat as the app serves it: every message is sorted by the input check before the
    agent sees it, and only `ok` and `overdose_emergency` reach the agent. An answer that
    repeats the system prompt is stopped before its canary goes out. Once the agent's answer is
    out, the source check judges its claims against the tool results it cites."""

    def __init__(
        self,
        check: InputCheck,
        agent: ChatAgent,
        source_check: SourceCheck,
        *,
        timeout_seconds: float,
    ) -> None:
        self._check = check
        self._agent = agent
        self._source_check = source_check
        self._timeout_seconds = timeout_seconds

    async def stream(self, conversation: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        """The agent's events with a `source_check` event before `done`, or a fixed answer as
        `token`, `sources` and `done`. `done` carries the category. An input check that fails
        ends with an `error` event and no answer. An answer that repeats the system prompt ends
        with `replace_answer`, `sources` and `done`, unchecked."""
        yield StatusEvent(message=CHECKING)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                verdict = await self._check.check(conversation)
        except TimeoutError:
            yield ErrorEvent(message=CHECK_FAILED)
            return
        except ChatModelError as error:
            logger.warning("Input check failed: %r", error)
            yield ErrorEvent(message=describe_provider_error(error))
            return
        except InputCheckFailed as error:
            logger.warning("Input check gave no category: %s", error)
            yield ErrorEvent(message=CHECK_FAILED)
            return
        except DecisionModelError as error:
            logger.warning("Input check's decision model failed: %r", error)
            yield ErrorEvent(message=CHECK_FAILED)
            return
        if verdict.category in REFUSED:
            for event in fixed(verdict):
                yield event
            return
        if verdict.category == "overdose_emergency":
            yield TokenEvent(text=emergency_line())
        try:
            async for event in self._answer(conversation, verdict):
                yield event
        except PromptLeaked as leak:
            logger.warning("Stopped an answer whose %s event held the system prompt's canary", leak)
            for event in stopped(verdict):
                yield event

    async def _answer(
        self, conversation: Sequence[ChatMessage], verdict: Verdict
    ) -> AsyncIterator[ChatEvent]:
        """The agent's events as the canary watch passes them, with the source check's verdict
        before `done`. Raises PromptLeaked once nothing more may be sent."""
        watch = CanaryWatch(self._agent.canary)
        answer: list[str] = []
        results: list[ToolResultEvent] = []
        async with aclosing(self._agent.stream(conversation)) as agent_events:
            async for agent_event in agent_events:
                for event in watch.passed(agent_event):
                    if isinstance(event, TokenEvent):
                        answer.append(event.text)
                    elif isinstance(event, ToolResultEvent):
                        results.append(event)
                    elif isinstance(event, DoneEvent):
                        yield StatusEvent(message=CHECKING_ANSWER)
                        checked, check_usage = await self._check_answer("".join(answer), results)
                        yield checked
                        event = event.model_copy(
                            update={
                                "category": verdict.category,
                                "usage_by_step": {
                                    "input_check": verdict.usage,
                                    **event.usage_by_step,
                                    "source_check": check_usage,
                                },
                            }
                        )
                    yield event

    async def _check_answer(
        self, answer: str, results: list[ToolResultEvent]
    ) -> tuple[SourceCheckEvent, Usage]:
        """The check's verdict; a check that fails leaves the answer shown but unchecked, and
        what its call used unknown."""
        try:
            async with asyncio.timeout(self._timeout_seconds):
                checked = await self._source_check.check(answer, results)
        except (SourceCheckFailed, TimeoutError) as error:
            logger.warning("Source check failed: %r", error)
            return SourceCheckEvent(checked=False), Usage.unreported()
        return SourceCheckEvent(checked=True, claims=checked.claims), checked.usage


def emergency_line() -> str:
    """The line an `overdose_emergency` answer starts with, a paragraph of its own so the
    agent's answer doesn't run on from it."""
    return fixed_answer("overdose_emergency") + "\n\n"


def stopped(verdict: Verdict) -> list[ChatEvent]:
    """The end of an answer that repeated the system prompt. What the agent's calls used is
    unknown, since its `done` never came, so `done` carries only the input check's usage."""
    text = prompts.load("guard/stopped_answer").strip()
    if verdict.category == "overdose_emergency":
        text = emergency_line() + text
    return [
        ReplaceAnswerEvent(text=text),
        SourcesEvent(sources=[]),
        DoneEvent(
            usage_by_step={"input_check": verdict.usage},
            step_limit_reached=False,
            category=verdict.category,
        ),
    ]


def fixed(verdict: Verdict) -> list[ChatEvent]:
    return [
        TokenEvent(text=fixed_answer(verdict.category)),
        SourcesEvent(sources=[]),
        DoneEvent(
            usage_by_step={"input_check": verdict.usage},
            step_limit_reached=False,
            category=verdict.category,
        ),
    ]
