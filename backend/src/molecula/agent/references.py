import re
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from molecula.schemas.tools import LabelPassages

CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class References:
    """The reference numbers of one answer's label passages, from 1 in the order they were
    found. A passage that two searches find keeps its first number."""

    def __init__(self) -> None:
        self._refs: dict[str, int] = {}

    def ref_of(self, chunk_id: str) -> int:
        return self._refs.setdefault(chunk_id, len(self._refs) + 1)


class NumberPassages(AgentMiddleware):
    """Renumbers each label search's passages with the answer's `References`, the run context,
    before the model reads them, so passages from several searches never share a number."""

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        message = await handler(request)
        if isinstance(message, ToolMessage) and isinstance(message.artifact, LabelPassages):
            references: References = request.runtime.context
            passages = message.artifact.renumbered(references.ref_of)
            return message.model_copy(
                update={"content": passages.model_dump_json(), "artifact": passages}
            )
        return message


def cited_refs(answer: str) -> list[int]:
    """The numbers an answer cites as `[n]` or `[n, m]`, in order, each once."""
    refs = (int(ref) for match in CITATION.finditer(answer) for ref in match[1].split(","))
    return list(dict.fromkeys(refs))
