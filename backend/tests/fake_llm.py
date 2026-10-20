"""A scripted chat model for tests: it answers each call with the next message of its script."""

import json
import re
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.messages.tool import tool_call_chunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field, InstanceOf

DEFAULT_USAGE = UsageMetadata(input_tokens=12, output_tokens=8, total_tokens=20)
DEFAULT_COST = 0.0002
# What `secrets.token_hex(16)` gives `ChatAgent` in the app: 32 hex digits.
CANARY = "5eed" * 8


def tool_call_message(
    name: str, args: dict[str, Any], call_id: str = "call_1", content: str = ""
) -> AIMessage:
    """A model turn that asks for one tool call."""
    return AIMessage(content=content, tool_calls=[{"name": name, "args": args, "id": call_id}])


def answer_message(text: str) -> AIMessage:
    return AIMessage(content=text)


class ScriptedChatModel(BaseChatModel):
    """Answers each call, invoked or streamed, with the next message of `script`, or raises it
    when the script holds an exception (a provider error).

    A message without its own `usage_metadata` gets `usage`, and `cost` as the chat models
    in `agent/llm.py` keep it; None leaves either out, as a provider that doesn't report it.
    `bind_tools` records the tool
    names and returns the model itself, so agents that bind tools can drive it. `received`
    holds the messages each call was given. A streamed answer comes a word at a time, or in
    pieces of `chunk_size` characters when that is set.
    """

    script: list[InstanceOf[AIMessage] | InstanceOf[Exception]]
    usage: UsageMetadata | None = Field(default_factory=lambda: DEFAULT_USAGE.copy())
    cost: float | None = DEFAULT_COST
    received: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[str] = Field(default_factory=list)
    chunk_size: int | None = None

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        self.bound_tools = [convert_to_openai_tool(tool)["function"]["name"] for tool in tools]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next_message(messages))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        for message_chunk in _chunks(self._next_message(messages), self.chunk_size):
            chunk = ChatGenerationChunk(message=message_chunk)
            if run_manager:
                run_manager.on_llm_new_token(chunk.text, chunk=chunk)
            yield chunk

    def _next_message(self, messages: list[BaseMessage]) -> AIMessage:
        if len(self.received) >= len(self.script):
            raise AssertionError(
                f"The scripted model was called {len(self.received) + 1} times "
                f"but has only {len(self.script)} messages"
            )
        self.received.append(list(messages))
        message = self.script[len(self.received) - 1]
        if isinstance(message, Exception):
            raise message
        if message.usage_metadata is None and self.usage is not None:
            message = message.model_copy(update={"usage_metadata": self.usage})
            if self.cost is not None:
                metadata = {**message.response_metadata, "token_usage": {"cost": self.cost}}
                message = message.model_copy(update={"response_metadata": metadata})
        return message


def _chunks(message: AIMessage, size: int | None) -> Iterator[AIMessageChunk]:
    """The message split the way a provider streams it: text a word (or `size` characters) at
    a time, then one chunk with the tool calls and the token usage."""
    text = message.content if isinstance(message.content, str) else ""
    if size is None:
        pieces = re.split(r"(\s+)", text)
    else:
        pieces = [text[start : start + size] for start in range(0, len(text), size)]
    for token in pieces:
        if token:
            yield AIMessageChunk(content=token, id=message.id)
    yield AIMessageChunk(
        content="",
        id=message.id,
        tool_call_chunks=[
            tool_call_chunk(
                name=call["name"], args=json.dumps(call["args"]), id=call["id"], index=i
            )
            for i, call in enumerate(message.tool_calls)
        ],
        usage_metadata=message.usage_metadata,
        response_metadata=message.response_metadata,
        chunk_position="last",
    )
