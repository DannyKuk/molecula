from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from molecula.schemas.retrieval import LabelFilter, RetrievedChunk, Widening

# Earlier turns travel as question and answer text only, so ten messages stay around 15k
# tokens next to the current turn's tools and passages (about 5k, #125). An answer may be longer
# than a question: the longest in the first manual run was 2,308 characters, and a conversation
# must not be refused for an answer the server wrote.
MAX_MESSAGES = 10
MAX_MESSAGE_LENGTH = 4000
MAX_ANSWER_LENGTH = 8000


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_ANSWER_LENGTH)
    ]

    @model_validator(mode="after")
    def questions_are_shorter(self) -> Self:
        if self.role == "user" and len(self.content) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"a user message must have at most {MAX_MESSAGE_LENGTH} characters")
        return self


class ChatRequest(BaseModel):
    """The conversation so far, oldest first, ending with the user's new message. A longer
    conversation is sent as its latest messages."""

    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=MAX_MESSAGES)]

    @model_validator(mode="after")
    def ends_with_the_user(self) -> Self:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be the user's")
        return self


class Usage(BaseModel):
    """Tokens the chat model read and wrote for one answer, over all its calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class Source(BaseModel):
    """Where a fact the tools returned comes from: a label passage on DailyMed (`kind`
    "dailymed", with the label's date and `ref`, the number the answer cites it with as `[ref]`),
    a PubChem compound page or a ChEMBL target page."""

    model_config = ConfigDict(frozen=True)

    kind: str
    name: str
    url: str
    section: str | None = None
    effective_time: date | None = None
    ref: int | None = None


class TranslationStep(BaseModel):
    """One query translation step and the query it produced (#114)."""

    model_config = ConfigDict(frozen=True)

    step: str
    output: str


class Candidate(RetrievedChunk):
    """A chunk the label search scored, and whether it was kept or dropped below the threshold."""

    kept: bool


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    message: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    args: dict[str, Any]


class ToolResultEvent(BaseModel):
    """The tool's result as the model read it. `status` is the result's own status (`found`,
    `not_supported`, `invalid_arguments`), if it has one."""

    type: Literal["tool_result"] = "tool_result"
    id: str
    name: str
    status: str | None
    result: Any


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class SourcesEvent(BaseModel):
    """Where the answer's facts come from. A citation is `[n]` or, from some models, `【n】`.
    `unknown_refs` are numbers the answer cites that no source has: show them as plain text,
    not as a link."""

    type: Literal["sources"] = "sources"
    sources: list[Source]
    unknown_refs: list[int] = []


class RetrievalTraceEvent(BaseModel):
    """One label search, for the RAG panel (#41).

    `filter_source` says who chose the filter: `model` when the chat model extracted it from
    the question, `agent` when the agent named the drug and `filter.extracted` holds its
    arguments. `translation` is empty until a query translation step is built (#114).
    """

    type: Literal["retrieval_trace"] = "retrieval_trace"
    tool_call_id: str
    question: str
    translation: list[TranslationStep]
    filter: LabelFilter | None
    filter_source: Literal["model", "agent"]
    widened: list[Widening]
    candidates: list[Candidate]


class DoneEvent(BaseModel):
    """The answer is complete. `step_limit_reached` means the agent had to answer without
    further tool calls."""

    type: Literal["done"] = "done"
    usage: Usage
    step_limit_reached: bool


class ErrorEvent(BaseModel):
    """The answer stopped; `message` is written for the user."""

    type: Literal["error"] = "error"
    message: str


type ChatEvent = Annotated[
    StatusEvent
    | ToolCallEvent
    | ToolResultEvent
    | TokenEvent
    | SourcesEvent
    | RetrievalTraceEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
