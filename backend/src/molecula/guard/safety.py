from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, get_args

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from molecula import prompts
from molecula.agent.agent import to_langchain
from molecula.agent.decisions import DecisionModel
from molecula.schemas.chat import ChatMessage
from molecula.schemas.decisions import ChoiceAnswer, ChoiceQuestion, StateMessage
from molecula.schemas.guard import InputCategory, Language, SortedMessage
from molecula.schemas.usage import Usage, usage_of

CATEGORIES: tuple[InputCategory, ...] = get_args(InputCategory.__value__)
LANGUAGES: tuple[Language, ...] = get_args(Language.__value__)

# Categories that get only a fixed answer; `overdose_emergency` gets its fixed line and then
# the agent's answer.
REFUSED: frozenset[InputCategory] = frozenset(
    {
        "personal_medical_advice",
        "lethal_dose",
        "synthesis_or_misuse",
        "prompt_injection",
        "off_topic",
    }
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


@dataclass(frozen=True)
class SortedByDecision:
    """The decision model's answer for the category, with every category's probability."""

    answer: ChoiceAnswer
    usage: Usage


class DecisionModelInputCheck:
    """Sorts a message with one `choice` question to a decision model, which answers in one
    forward pass with a probability per category. The client's errors are raised as they come;
    the guard refuses on them."""

    def __init__(self, model: DecisionModel) -> None:
        self._model = model
        self._question = category_question()

    async def check(self, conversation: Sequence[ChatMessage]) -> Verdict:
        sorted_message = await self.sort(conversation)
        category = sorted_message.answer.choice
        if category not in CATEGORIES:
            raise InputCheckFailed(f"the decision model chose {category!r}, not a category")
        return Verdict(category, sorted_message.usage)

    async def sort(self, conversation: Sequence[ChatMessage]) -> SortedByDecision:
        # The conversation goes as its own messages, never into the question: it is untrusted.
        state = [StateMessage(role=m.role, content=m.content) for m in conversation]
        response = await self._model.decide(state, {"category": self._question})
        return SortedByDecision(response.choice("category"), response.usage.as_usage())


def category_question() -> ChoiceQuestion:
    return ChoiceQuestion(
        instructions=prompts.load("guard/input_check/question").strip(),
        criteria={
            category: prompts.load(f"guard/input_check/{category}").strip()
            for category in CATEGORIES
        },
    )


def fixed_answer(category: InputCategory, language: Language = "en") -> str:
    """The answer a refused category gets instead of the agent's, or the emergency line an
    `overdose_emergency` answer starts with, in `language`. The English texts sit in
    `prompts/guard/`, the others in a folder per language."""
    folder = "guard" if language == "en" else f"guard/{language}"
    return prompts.load(f"{folder}/{category}").strip()


def emergency_lines() -> list[str]:
    """The emergency line in every language, for leaving it out of an answer's claims."""
    return [fixed_answer("overdose_emergency", language) for language in LANGUAGES]
