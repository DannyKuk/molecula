import json
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, ToolCall, ToolMessage
from langchain_core.tools import BaseTool

from molecula.agent.channel_markers import ChannelMarkerFilter, without_channel_markers
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
)
from molecula.schemas.tools import LabelDrugsNotSupported, LabelPassages, ToolResult
from molecula.schemas.usage import Usage, usage_of
from molecula.tools.base import Progress, progress_of


class AgentRun:
    """Turns the agent graph's stream into chat events, and collects the sources, the answer
    and the usage of the model calls for the end of the answer: the agent's own and those of
    the label searches' filter extraction."""

    def __init__(self, max_steps: int, tools: Sequence[BaseTool]) -> None:
        self.max_steps = max_steps
        self.progress_by_tool: dict[str, Progress | None] = {
            tool.name: progress_of(tool) for tool in tools
        }
        self.model_calls = 0
        self.answer_usage = Usage()
        self.label_filter_usage = Usage()
        self.calls: dict[str, ToolCall] = {}
        self.sources: dict[tuple[str, str | None, int | None], Source] = {}
        self.answer = ""
        self.markers = ChannelMarkerFilter()

    def events(self, mode: str, data: Any) -> Iterator[ChatEvent]:
        if mode == "messages":
            chunk, metadata = data
            if (
                metadata.get("langgraph_node") == "model"
                and isinstance(chunk, AIMessageChunk)
                and chunk.text
            ):
                yield from tokens(self.markers.feed(chunk.text))
            return
        for update in data.values():
            for message in (update or {}).get("messages", []):
                if isinstance(message, AIMessage):
                    yield from self.model_reply(message)
                elif isinstance(message, ToolMessage):
                    yield from self.tool_reply(message)

    def model_reply(self, message: AIMessage) -> Iterator[ChatEvent]:
        yield from tokens(self.markers.flush())
        self.model_calls += 1
        self.answer_usage += usage_of(message)
        if message.tool_calls:
            # Some models write a line before they call a tool ("I'll look up the labels."),
            # which would otherwise run into the first sentence of the answer (#399).
            yield from tokens(paragraph_break(without_channel_markers(message.text)))
        else:
            self.answer = without_channel_markers(message.text)
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
            label_filter = artifact.retrieval.filter
            if label_filter is not None and label_filter.extraction_usage is not None:
                self.label_filter_usage += label_filter.extraction_usage
        if isinstance(artifact, ToolResult):
            for source in artifact.sources():
                self.sources.setdefault((source.url, source.section, source.ref), source)

    def finish(self) -> Iterator[ChatEvent]:
        refs = {source.ref for source in self.sources.values()}
        unknown = [ref for ref in cited_refs(self.answer) if ref not in refs]
        yield SourcesEvent(sources=list(self.sources.values()), unknown_refs=unknown)
        yield DoneEvent(
            usage_by_step={"answer": self.answer_usage, "label_filter": self.label_filter_usage},
            step_limit_reached=self.model_calls >= self.max_steps,
        )

    def status_of(self, call: ToolCall) -> str:
        """What a tool call is doing, for the user to read while they wait."""
        progress = self.progress_by_tool.get(call["name"])
        # Every registered tool has its own text (tests/agent/test_tool_registry.py); this is
        # for a call to a tool the model wasn't given.
        if progress is None:
            return f"Running {call['name']}"
        return progress(call["args"])


def tokens(text: str) -> Iterator[TokenEvent]:
    if text:
        yield TokenEvent(text=text)


def paragraph_break(text: str) -> str:
    """What `text` needs at its end so that what follows starts a paragraph of its own: none
    after no text, else enough newlines to make a blank line. A single newline isn't enough,
    because Markdown runs the next line into the same paragraph."""
    if not text.strip():
        return ""
    end = text.rstrip(" \t")
    newlines = len(end) - len(end.rstrip("\n"))
    return "\n" * max(0, 2 - newlines)


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
        mode=retrieval.mode,
        min_score=retrieval.min_score,
        section_group_boost=retrieval.section_group_boost,
    )
