import asyncio
import logging
from collections.abc import AsyncIterator, Sequence

from molecula.agent.agent import ChatAgent
from molecula.agent.decisions import DecisionModelError
from molecula.agent.llm import ChatModelError, describe_provider_error
from molecula.guard.safety import REFUSED, InputCheck, InputCheckFailed, Verdict, fixed_answer
from molecula.schemas.chat import (
    ChatEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    SourceCheckEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolResultEvent,
    Usage,
)
from molecula.schemas.source_check import SourceCheck, SourceCheckFailed

logger = logging.getLogger(__name__)

CHECKING = "Checking the question"
CHECKING_ANSWER = "Checking the answer against the sources"
CHECK_FAILED = "Molecula couldn't check this question, so it didn't answer it. Try again."


class GuardedChat:
    """The chat as the app serves it: every message is sorted by the input check before the
    agent sees it, and only `ok` and `overdose_emergency` reach the agent. Once the agent's
    answer is out, the source check judges its claims against the tool results it cites."""

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
        ends with an `error` event and no answer."""
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
            # A paragraph of its own, so the agent's answer doesn't run on from it.
            yield TokenEvent(text=fixed_answer("overdose_emergency") + "\n\n")
        answer: list[str] = []
        results: list[ToolResultEvent] = []
        async for event in self._agent.stream(conversation):
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
                        "usage": verdict.usage + event.usage + check_usage,
                    }
                )
            yield event

    async def _check_answer(
        self, answer: str, results: list[ToolResultEvent]
    ) -> tuple[SourceCheckEvent, Usage]:
        """The check's verdict; a check that fails leaves the answer shown but unchecked."""
        try:
            async with asyncio.timeout(self._timeout_seconds):
                checked = await self._source_check.check(answer, results)
        except (SourceCheckFailed, TimeoutError) as error:
            logger.warning("Source check failed: %r", error)
            return SourceCheckEvent(checked=False), Usage()
        return SourceCheckEvent(checked=True, claims=checked.claims), checked.usage


def fixed(verdict: Verdict) -> list[ChatEvent]:
    return [
        TokenEvent(text=fixed_answer(verdict.category)),
        SourcesEvent(sources=[]),
        DoneEvent(usage=verdict.usage, step_limit_reached=False, category=verdict.category),
    ]
