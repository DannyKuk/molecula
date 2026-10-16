"""The `/v1/systemone` wire format that decision models speak: Jev on OpenRouter and decision
models served by LM Studio (https://docs.typesafe.ai/api)."""

from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# The API's limits: at most 255 options for a choice, 2 to 10 levels for a score.
MAX_CHOICE_OPTIONS = 255
MAX_SCORE_LEVELS = 10


class NoulCriteria(BaseModel):
    model_config = ConfigDict(frozen=True)

    true: str
    false: str


class NoulQuestion(BaseModel):
    """A yes/no question; the answer is the probability of yes."""

    model_config = ConfigDict(frozen=True)

    type: Literal["noul"] = "noul"
    instructions: str
    criteria: NoulCriteria | None = None


class ChoiceQuestion(BaseModel):
    """One of the options, each with a description."""

    model_config = ConfigDict(frozen=True)

    type: Literal["choice"] = "choice"
    instructions: str
    criteria: Annotated[dict[str, str], Field(min_length=2, max_length=MAX_CHOICE_OPTIONS)]


class ScoreQuestion(BaseModel):
    """A level on an ordered scale, lowest first."""

    model_config = ConfigDict(frozen=True)

    type: Literal["score"] = "score"
    instructions: str
    criteria: Annotated[list[str], Field(min_length=2, max_length=MAX_SCORE_LEVELS)]


Question = Annotated[NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")]


class StateMessage(BaseModel):
    """One message of a conversation sent as the state."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class DecisionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    state: str | list[StateMessage]
    questions: Annotated[dict[str, Question], Field(min_length=1)]


class NoulAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["noul"]
    noul: Annotated[float, Field(ge=0.0, le=1.0)]


class ChoiceAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]
    confidence: float


class ScoreAnswer(BaseModel):
    """`score` is the expected level index, so it can fall between two levels. `legend` and
    `probabilities` are keyed by the level index as a string."""

    model_config = ConfigDict(frozen=True)

    type: Literal["score"]
    score: float
    legend: dict[str, str]
    probabilities: dict[str, float]
    confidence: float


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]
AnswerT = TypeVar("AnswerT", NoulAnswer, ChoiceAnswer, ScoreAnswer)


class DecisionUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0


class DecisionResponse(BaseModel):
    """The answers keyed by the request's question ids. `model` is the server's name for the
    model, which on OpenRouter carries a date the request didn't."""

    model_config = ConfigDict(frozen=True)

    model: str
    answers: dict[str, Answer]
    usage: DecisionUsage = Field(default_factory=DecisionUsage)

    def noul(self, key: str) -> NoulAnswer:
        return self._answer(key, NoulAnswer)

    def choice(self, key: str) -> ChoiceAnswer:
        return self._answer(key, ChoiceAnswer)

    def score(self, key: str) -> ScoreAnswer:
        return self._answer(key, ScoreAnswer)

    def _answer(self, key: str, kind: type[AnswerT]) -> AnswerT:
        answer = self.answers[key]
        if not isinstance(answer, kind):
            raise TypeError(f"answer {key!r} is a {answer.type}, not a {kind.__name__}")
        return answer
