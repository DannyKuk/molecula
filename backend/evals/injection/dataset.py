from collections import Counter
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from evals.safety.dataset import load_items as load_input_check_items
from pydantic import BaseModel, ConfigDict, Field, model_validator

from molecula.schemas.chat import ChatMessage
from molecula.schemas.guard import InputCategory

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "injection.yaml"
QUESTION = "{question}"
ALONE = "-alone"

type AttackKind = Literal["direct", "indirect", "multi_turn", "forged_history"]


class InjectionItem(BaseModel):
    """An attack and how the run tells that it got through: `marker` in the answer or a tool
    call, a line of the system prompt in the answer (`asks_for_prompt`), or, for forged history,
    the question sorted into anything but `category`. `planted` is the text an indirect attack
    puts in front of the first passage of every label search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: AttackKind
    language: Literal["en", "de"]
    text: str
    source: str = Field(pattern=r"#\d+")
    conversation: list[ChatMessage] = []
    marker: str | None = None
    asks_for_prompt: bool = False
    planted: str | None = None
    category: InputCategory | None = None

    @model_validator(mode="after")
    def scored_one_way(self) -> Self:
        roles = [message.role for message in self.conversation]
        if roles != ["user", "assistant"] * (len(roles) // 2) or len(roles) % 2:
            raise ValueError(f"{self.id}: the conversation must alternate user, assistant")
        ways = [self.marker is not None, self.asks_for_prompt, self.category is not None]
        if sum(ways) != 1:
            raise ValueError(f"{self.id}: needs exactly one of marker, asks_for_prompt, question")
        if (self.kind == "indirect") != (self.planted is not None):
            raise ValueError(f"{self.id}: an indirect attack and only one has `planted`")
        if (self.kind == "forged_history") != (self.category is not None):
            raise ValueError(f"{self.id}: a forged history and only one has `question`")
        if self.kind in ("multi_turn", "forged_history") and not self.conversation:
            raise ValueError(f"{self.id}: a {self.kind} attack needs earlier turns")
        return self

    def messages(self) -> list[ChatMessage]:
        return [*self.conversation, ChatMessage(role="user", content=self.text)]


def load_items(path: Path = DATASET) -> list[InjectionItem]:
    """The attacks, each forged history followed by its question asked alone."""
    questions = {item.id: item for item in load_input_check_items()}
    items: list[InjectionItem] = []
    for entry in yaml.safe_load(path.read_text("utf-8")):
        attack = with_question(entry, questions) if "question" in entry else entry
        items.append(InjectionItem.model_validate(attack))
        if "question" in entry:
            items.append(alone(items[-1], questions[entry["question"]].text))
    counts = Counter(item.id for item in items)
    if duplicates := [item_id for item_id, count in counts.items() if count > 1]:
        raise ValueError(f"{path}: duplicate ids {', '.join(duplicates)}")
    return items


def with_question(entry: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
    """A forged history with its input-check question written in where `{question}` stands."""
    attack = dict(entry)
    question = questions[attack.pop("question")]
    attack["text"] = attack.get("text", QUESTION).replace(QUESTION, question.text)
    attack["conversation"] = [
        {**message, "content": message["content"].replace(QUESTION, question.text)}
        for message in attack.get("conversation", [])
    ]
    attack["category"] = question.category
    return attack


def alone(forged: InjectionItem, question: str) -> InjectionItem:
    """The forged history's question without the forged turns, to compare the sorting with."""
    return forged.model_copy(update={"id": forged.id + ALONE, "text": question, "conversation": []})


def is_alone(item: InjectionItem) -> bool:
    return item.id.endswith(ALONE)
