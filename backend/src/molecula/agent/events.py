import json
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, ToolCall, ToolMessage
from langchain_core.tools import BaseTool

from molecula.agent.references import cited_refs
from molecula.schemas.chat import (
    Candidate,
    ChatEvent,
    DoneEvent,
    RetrievalTraceEvent,
    Source,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    Usage,
)
from molecula.schemas.tools import LabelDrugsNotSupported, LabelPassages, ToolResult
from molecula.tools.base import Progress, progress_of


class AgentRun:
    """Turns the agent graph's stream into chat events, and collects the sources, the answer
    and the token usage for the end of the answer. `disclaimer` goes with any answer that has
    a label passage among its sources."""

    def __init__(
        self, max_steps: int, tools: Sequence[BaseTool], disclaimer: str | None = None
    ) -> None:
        self.max_steps = max_steps
        self.disclaimer = disclaimer
        self.progress_by_tool: dict[str, Progress | None] = {
            tool.name: progress_of(tool) for tool in tools
        }
        self.model_calls = 0
        self.usage = Usage()
        self.calls: dict[str, ToolCall] = {}
        self.sources: dict[tuple[str, str | None, int | None], Source] = {}
        self.answer = ""

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
        if not message.tool_calls:
            self.answer = message.text
        for call in message.tool_calls:
            call_id = call["id"] or ""
            self.calls[call_id] = call
            yield StatusEvent(message=self.status_of(call))
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
        if isinstance(artifact, ToolResult):
            for source in artifact.sources():
                self.sources.setdefault((source.url, source.section, source.ref), source)

    def finish(self) -> Iterator[ChatEvent]:
        refs = {source.ref for source in self.sources.values()}
        unknown = [ref for ref in cited_refs(self.answer) if ref not in refs]
        uses_labels = any(source.kind == "dailymed" for source in self.sources.values())
        yield SourcesEvent(
            sources=list(self.sources.values()),
            unknown_refs=unknown,
            disclaimer=self.disclaimer if uses_labels else None,
        )
        yield DoneEvent(usage=self.usage, step_limit_reached=self.model_calls >= self.max_steps)

    def status_of(self, call: ToolCall) -> str:
        """What a tool call is doing, for the user to read while they wait."""
        progress = self.progress_by_tool.get(call["name"])
        # Every registered tool has its own text (tests/agent/test_tool_registry.py); this is
        # for a call to a tool the model wasn't given.
        if progress is None:
            return f"Running {call['name']}"
        return progress(call["args"])


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
