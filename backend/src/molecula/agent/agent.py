import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.types import Command

from molecula import prompts
from molecula.agent.channel_markers import without_channel_markers, without_control_tokens
from molecula.agent.events import AgentRun
from molecula.agent.llm import ChatModelError, describe_provider_error
from molecula.agent.references import NumberSources
from molecula.schemas.chat import ChatEvent, ChatMessage, ErrorEvent
from molecula.schemas.tools import References

logger = logging.getLogger(__name__)

# A model at a high reasoning effort can spend the last allowed call on a tool call, which
# StepLimit drops, leaving no answer text (#199).
NO_ANSWER = "Molecula couldn't finish this answer. Ask again, or ask a narrower question."


class ChatAgent:
    """The tool-calling agent behind the chat: it answers a conversation and reports each step
    as a `ChatEvent`. `canary` goes into the first line of the system prompt, so an answer that
    contains it is repeating the prompt (#203)."""

    def __init__(
        self,
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        *,
        canary: str,
        max_steps: int,
        timeout_seconds: float,
    ) -> None:
        self._graph = create_agent(
            model,
            tools,
            system_prompt=prompts.load("agent/system", canary=canary),
            middleware=[StepLimit(max_steps), WithoutControlTokens(), NumberSources()],
            context_schema=References,
        )
        self._tools = tools
        self._canary = canary
        self._max_steps = max_steps
        self._timeout_seconds = timeout_seconds

    @property
    def canary(self) -> str:
        return self._canary

    async def stream(self, conversation: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        """Status, tool calls and results, answer tokens and retrieval traces as they happen,
        then the sources and `done`; or an `error` event when the model fails, runs out of
        time or ends without answer text."""
        run = AgentRun(self._max_steps, self._tools)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async for mode, data in self._graph.astream(
                    {"messages": to_langchain(conversation)},
                    stream_mode=["messages", "updates"],
                    context=References(),
                ):
                    for event in run.events(mode, data):
                        yield event
        except TimeoutError:
            yield ErrorEvent(
                message=f"The answer took longer than {self._timeout_seconds:g} seconds. "
                "Try again, or ask a narrower question."
            )
            return
        except ChatModelError as error:
            logger.warning("Chat model call failed: %r", error)
            yield ErrorEvent(message=describe_provider_error(error))
            return
        if not run.answer.strip():
            logger.warning("The model gave no answer text after %d calls", run.model_calls)
            yield ErrorEvent(message=NO_ANSWER)
            return
        for event in run.finish():
            yield event


class StepLimit(AgentMiddleware):
    """Makes the last model call a request may take without tools, so a model that keeps
    calling tools still ends with an answer instead of an error."""

    def __init__(self, max_steps: int) -> None:
        super().__init__()
        self.max_steps = max_steps

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        if steps_taken(request.messages) < self.max_steps - 1:
            return await handler(request)
        system_prompt = request.system_message.text if request.system_message else ""
        last_step = request.override(
            tools=[],
            system_message=SystemMessage(
                prompts.load("agent/step_limit", system_prompt=system_prompt)
            ),
        )
        response = await handler(last_step)
        # A model can still write a tool call it was given no tool for; running it would
        # exceed the limit.
        return ModelResponse(
            result=[without_tool_calls(message) for message in response.result],
            structured_response=response.structured_response,
        )


class WithoutControlTokens(AgentMiddleware):
    """Takes chat-format control tokens out of every tool result before the model reads it, so
    label text can't pass itself off as a system turn (#329). It wraps `NumberSources`, which
    writes the result's content afresh."""

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        message = await handler(request)
        if isinstance(message, ToolMessage) and isinstance(message.content, str):
            return message.model_copy(update={"content": without_control_tokens(message.content)})
        return message


def steps_taken(messages: Sequence[AnyMessage]) -> int:
    """Model calls since the user's latest message."""
    taken = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        taken += isinstance(message, AIMessage)
    return taken


def without_tool_calls(message: BaseMessage) -> BaseMessage:
    if isinstance(message, AIMessage) and message.tool_calls:
        return message.model_copy(update={"tool_calls": [], "invalid_tool_calls": []})
    return message


def to_langchain(conversation: Sequence[ChatMessage]) -> list[BaseMessage]:
    """The conversation as LangChain messages. An earlier answer loses its channel markers, so
    one sent before they were stripped doesn't teach the model to write them."""
    return [
        HumanMessage(message.content)
        if message.role == "user"
        else AIMessage(without_channel_markers(message.content))
        for message in conversation
    ]
