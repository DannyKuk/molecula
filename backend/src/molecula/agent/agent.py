import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from molecula import prompts
from molecula.agent.events import AgentRun
from molecula.agent.llm import ChatModelError, describe_provider_error
from molecula.agent.references import NumberPassages, References
from molecula.schemas.chat import ChatEvent, ChatMessage, ErrorEvent

logger = logging.getLogger(__name__)


class ChatAgent:
    """The tool-calling agent behind the chat: it answers a conversation and reports each step
    as a `ChatEvent`."""

    def __init__(
        self,
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        *,
        max_steps: int,
        timeout_seconds: float,
    ) -> None:
        self._graph = create_agent(
            model,
            tools,
            system_prompt=prompts.load("agent/system"),
            middleware=[StepLimit(max_steps), NumberPassages()],
            context_schema=References,
        )
        self._tools = tools
        self._max_steps = max_steps
        self._timeout_seconds = timeout_seconds

    async def stream(self, conversation: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        """Status, tool calls and results, answer tokens and retrieval traces as they happen,
        then the sources and `done`; or an `error` event when the model fails or runs out of
        time."""
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
    return [
        HumanMessage(message.content) if message.role == "user" else AIMessage(message.content)
        for message in conversation
    ]
