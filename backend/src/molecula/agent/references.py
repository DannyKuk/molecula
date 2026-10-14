import re
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from molecula.schemas.tools import ToolResult

# gpt-oss often cites in its own full-width brackets, 【1】, even when asked for [1] (#129).
CITATION = re.compile(r"[\[【](\d+(?:\s*,\s*\d+)*)[\]】]")


class References:
    """The reference numbers of one answer's sources, from 1 in the order they were found. A
    label passage is keyed by its chunk id, any other source by its URL, so a passage or page
    that two tool calls find keeps its first number."""

    def __init__(self) -> None:
        self._refs: dict[str, int] = {}

    def ref_of(self, key: str) -> int:
        return self._refs.setdefault(key, len(self._refs) + 1)


class NumberSources(AgentMiddleware):
    """Renumbers each tool result's sources with the answer's `References`, the run context,
    before the model reads them, so sources from several calls never share a number."""

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        message = await handler(request)
        if isinstance(message, ToolMessage) and isinstance(message.artifact, ToolResult):
            references: References = request.runtime.context
            result = message.artifact.renumbered(references.ref_of)
            return message.model_copy(
                update={"content": result.model_dump_json(), "artifact": result}
            )
        return message


def cited_refs(answer: str) -> list[int]:
    """The numbers an answer cites as `[n]`, `[n, m]` or `【n】`, in order, each once."""
    refs = (int(ref) for match in CITATION.finditer(answer) for ref in match[1].split(","))
    return list(dict.fromkeys(refs))
