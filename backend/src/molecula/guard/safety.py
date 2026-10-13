from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from molecula import prompts
from molecula.agent.agent import to_langchain
from molecula.schemas.chat import ChatMessage, Usage
from molecula.schemas.guard import InputCategory, SortedMessage

# Categories that get only a fixed answer; `overdose_emergency` gets its fixed line and then
# the agent's answer.
REFUSED: frozenset[InputCategory] = frozenset(
    {"personal_medical_advice", "lethal_dose", "synthesis_or_misuse", "off_topic"}
)


class InputCheckFailed(Exception):
    """The check gave no category, so the message must not be answered."""


@dataclass(frozen=True)
class Verdict:
    category: InputCategory
    usage: Usage = field(default_factory=Usage)


class InputCheck(Protocol):
    async def check(self, conversation: Sequence[ChatMessage]) -> Verdict:
        """The category of the conversation's last message, read with the messages before it.
        Raises InputCheckFailed when it can't tell."""
        ...


class ChatModelInputCheck:
    """Sorts a message by asking the chat model for a `SortedMessage`. Provider errors are
    raised as they come, like the agent's."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def check(self, conversation: Sequence[ChatMessage]) -> Verdict:
        structured = self._model.with_structured_output(SortedMessage, include_raw=True)
        # The conversation goes in its own messages, never into the prompt: it is untrusted text.
        result = await structured.ainvoke(
            [SystemMessage(prompts.load("guard/classify")), *to_langchain(conversation)]
        )
        sorted_message = result["parsed"]
        if not isinstance(sorted_message, SortedMessage):
            raise InputCheckFailed(result["parsing_error"] or "the model returned no category")
        return Verdict(sorted_message.category, usage_of(result["raw"]))


def usage_of(message: BaseMessage) -> Usage:
    usage = message.usage_metadata if isinstance(message, AIMessage) else None
    if usage is None:
        return Usage()
    return Usage(
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
    )


def fixed_answer(category: InputCategory) -> str:
    """The answer a refused category gets instead of the agent's, or the emergency line an
    `overdose_emergency` answer starts with."""
    return prompts.load(f"guard/{category}").strip()
