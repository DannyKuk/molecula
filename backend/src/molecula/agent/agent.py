import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from typing import Any

import openai
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from molecula import prompts
from molecula.schemas.chat import (
    Candidate,
    ChatEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    RetrievalTraceEvent,
    Source,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    Usage,
)
from molecula.schemas.tools import (
    DrugComparison,
    DrugProperties,
    DrugTargetList,
    LabelDrugsNotSupported,
    LabelPassages,
    ResolvedDrug,
)

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
            middleware=[StepLimit(max_steps)],
        )
        self._max_steps = max_steps
        self._timeout_seconds = timeout_seconds

    async def stream(self, conversation: Sequence[ChatMessage]) -> AsyncIterator[ChatEvent]:
        """Status, tool calls and results, answer tokens and retrieval traces as they happen,
        then the sources and `done`; or an `error` event when the model fails or runs out of
        time."""
        run = AgentRun(self._max_steps)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async for mode, data in self._graph.astream(
                    {"messages": to_langchain(conversation)},
                    stream_mode=["messages", "updates"],
                ):
                    for event in run.events(mode, data):
                        yield event
        except TimeoutError:
            yield ErrorEvent(
                message=f"The answer took longer than {self._timeout_seconds:g} seconds. "
                "Try again, or ask a narrower question."
            )
            return
        except openai.APIError as error:
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


class AgentRun:
    """Turns the agent graph's stream into chat events, and collects the sources and token
    usage for the end of the answer."""

    def __init__(self, max_steps: int) -> None:
        self.max_steps = max_steps
        self.model_calls = 0
        self.usage = Usage()
        self.calls: dict[str, ToolCall] = {}
        self.sources: dict[tuple[str, str | None], Source] = {}

    def events(self, mode: str, data: Any) -> Iterator[ChatEvent]:
        if mode == "messages":
            chunk, metadata = data
            if (
                metadata.get("langgraph_node") == "model"
                and isinstance(chunk, AIMessageChunk)
                and chunk.text
            ):
                yield TokenEvent(text=chunk.text)
            return
        for update in data.values():
            for message in (update or {}).get("messages", []):
                if isinstance(message, AIMessage):
                    yield from self.model_reply(message)
                elif isinstance(message, ToolMessage):
                    yield from self.tool_reply(message)

    def model_reply(self, message: AIMessage) -> Iterator[ChatEvent]:
        self.model_calls += 1
        if message.usage_metadata:
            self.usage.input_tokens += message.usage_metadata["input_tokens"]
            self.usage.output_tokens += message.usage_metadata["output_tokens"]
            self.usage.total_tokens += message.usage_metadata["total_tokens"]
        for call in message.tool_calls:
            call_id = call["id"] or ""
            self.calls[call_id] = call
            yield StatusEvent(message=progress(call))
            yield ToolCallEvent(id=call_id, name=call["name"], args=call["args"])

    def tool_reply(self, message: ToolMessage) -> Iterator[ChatEvent]:
        call = self.calls.get(message.tool_call_id)
        result = parse_result(message.text)
        yield ToolResultEvent(
            id=message.tool_call_id,
            name=message.name or (call["name"] if call else ""),
            status=result.get("status") if isinstance(result, dict) else None,
            result=result,
        )
        artifact = message.artifact
        if isinstance(artifact, LabelPassages | LabelDrugsNotSupported):
            yield retrieval_trace(message.tool_call_id, artifact, call)
        if isinstance(artifact, BaseModel):
            for source in sources_of(artifact):
                self.sources.setdefault((source.url, source.section), source)

    def finish(self) -> Iterator[ChatEvent]:
        yield SourcesEvent(sources=list(self.sources.values()))
        yield DoneEvent(usage=self.usage, step_limit_reached=self.model_calls >= self.max_steps)


def to_langchain(conversation: Sequence[ChatMessage]) -> list[BaseMessage]:
    return [
        HumanMessage(message.content) if message.role == "user" else AIMessage(message.content)
        for message in conversation
    ]


def progress(call: ToolCall) -> str:
    """What a tool call is doing, for the user to read while they wait."""
    args = call["args"]
    match call["name"]:
        case "resolve_drug":
            return f"Looking up {args.get('name', 'the drug')}"
        case "get_properties":
            return f"Getting the properties of {args.get('drug', 'the drug')}"
        case "get_targets":
            return f"Finding the targets of {args.get('drug', 'the drug')}"
        case "search_labels" if args.get("drug"):
            return f"Searching the {args['drug']} label"
        case "search_labels":
            return "Searching the drug labels"
        case "compare_drugs":
            return f"Comparing {', '.join(args.get('drugs', []))}"
        case name:
            return f"Running {name}"


def parse_result(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def retrieval_trace(
    call_id: str, artifact: LabelPassages | LabelDrugsNotSupported, call: ToolCall | None
) -> RetrievalTraceEvent:
    retrieval = artifact.retrieval
    candidates = [Candidate(**chunk.model_dump(), kept=True) for chunk in retrieval.chunks] + [
        Candidate(**chunk.model_dump(), kept=False) for chunk in retrieval.dropped
    ]
    return RetrievalTraceEvent(
        tool_call_id=call_id,
        question=retrieval.question,
        translation=[],
        filter=retrieval.filter,
        filter_source="agent" if call and call["args"].get("drug") else "model",
        widened=retrieval.widened,
        candidates=candidates,
    )


def sources_of(result: BaseModel) -> list[Source]:
    match result:
        case LabelPassages(passages=passages):
            return [
                Source(
                    kind="dailymed",
                    name=passage.brand or passage.substance.lower(),
                    url=passage.url,
                    section=passage.section,
                    effective_time=passage.effective_time,
                )
                for passage in passages
            ]
        case ResolvedDrug():
            return [Source(kind=result.source, name=result.name, url=result.source_url)]
        case DrugProperties(compound=compound):
            return [Source(kind=compound.source, name=compound.name, url=compound.source_url)]
        case DrugTargetList(targets=targets):
            return [
                Source(kind=target.source, name=target.name, url=target.source_url)
                for target in targets
            ]
        case DrugComparison(drugs=drugs):
            return [source for drug in drugs for source in sources_of(drug)]
        case _:
            return []


def describe_provider_error(error: openai.APIError) -> str:
    """What went wrong with the chat model, for the user."""
    match error:
        case openai.APITimeoutError():
            return "The language model didn't answer in time. Try again."
        case openai.APIConnectionError():
            return "Molecula couldn't reach the language model. Check that its server is running."
        case openai.RateLimitError():
            return "The language model is busy right now (rate limit). Try again in a minute."
        case openai.AuthenticationError() | openai.PermissionDeniedError():
            return "The language model refused Molecula's API key. Check OPENROUTER_API_KEY."
        case openai.NotFoundError():
            return "The language model wasn't found. Check LLM_MODEL or LOCAL_LLM_MODEL."
        case openai.BadRequestError():
            return (
                "The language model rejected the request, for example because the "
                "conversation is longer than it can read. Start a new conversation."
            )
        case _:
            return "The language model failed. Try again."
