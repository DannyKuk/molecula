from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel


class Usage(BaseModel):
    """Tokens the models read and wrote over one or more calls, and what they cost in US
    dollars. None means a call didn't report it, so the sum isn't known either: a response
    without usage leaves the tokens and the cost unknown, one without a cost only the cost. A
    local model costs 0."""

    input_tokens: int | None = 0
    output_tokens: int | None = 0
    total_tokens: int | None = 0
    cost_usd: float | None = 0.0

    @classmethod
    def unreported(cls) -> Usage:
        return cls(input_tokens=None, output_tokens=None, total_tokens=None, cost_usd=None)

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=_sum(self.input_tokens, other.input_tokens),
            output_tokens=_sum(self.output_tokens, other.output_tokens),
            total_tokens=_sum(self.total_tokens, other.total_tokens),
            cost_usd=_sum(self.cost_usd, other.cost_usd),
        )


def _sum[N: (int, float)](left: N | None, right: N | None) -> N | None:
    return None if left is None or right is None else left + right


def usage_of(message: BaseMessage) -> Usage:
    """The usage of the model call that wrote `message`, from its `usage_metadata` or else the
    provider's own usage in `response_metadata["token_usage"]`, where the chat model also keeps
    the `cost` (`agent/llm.py`)."""
    if not isinstance(message, AIMessage):
        return Usage.unreported()
    token_usage: dict[str, Any] = message.response_metadata.get("token_usage") or {}
    cost = token_usage.get("cost")
    if message.usage_metadata is not None:
        usage = message.usage_metadata
        return Usage(
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=cost,
        )
    # OpenRouter repeats the role in every chunk of a stream, so the OpenAI client's
    # structured-output stream ends with the role "assistantassistant…", and LangChain leaves
    # `usage_metadata` empty for a message that isn't the assistant's.
    if "prompt_tokens" in token_usage:
        return Usage(
            input_tokens=token_usage["prompt_tokens"],
            output_tokens=token_usage["completion_tokens"],
            total_tokens=token_usage["total_tokens"],
            cost_usd=cost,
        )
    return Usage.unreported()
