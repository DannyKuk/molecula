from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from molecula.guard.validation import has_control_characters
from molecula.schemas.claims import CheckedClaim
from molecula.schemas.guard import InputCategory
from molecula.schemas.retrieval import LabelFilter, RetrievalMode, RetrievedChunk, Widening
from molecula.schemas.usage import Usage

# Earlier turns travel as question and answer text only, so ten messages stay around 15k
# tokens next to the current turn's tools and passages (about 5k, #125). An answer may be longer
# than a question: the longest in the first manual run was 2,308 characters, and a conversation
# must not be refused for an answer the server wrote.
MAX_MESSAGES = 10
MAX_MESSAGE_LENGTH = 4000
MAX_ANSWER_LENGTH = 8000


class ChatMessage(BaseModel):
    """One message. The rules raise sentences the chat shows as they are (`guard/validation.py`)."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True)]

    @model_validator(mode="after")
    def content_is_readable_text(self) -> Self:
        if not self.content:
            raise ValueError("A message can't be empty.")
        if has_control_characters(self.content):
            raise ValueError("A message can't contain control characters.")
        if self.role == "user" and len(self.content) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"A message can have at most {MAX_MESSAGE_LENGTH} characters.")
        if len(self.content) > MAX_ANSWER_LENGTH:
            raise ValueError(f"An earlier answer can have at most {MAX_ANSWER_LENGTH} characters.")
        return self


class ChatModel(BaseModel):
    """A model that writes the answers, by its id on its server, and whether that server is the
    local one."""

    model_config = ConfigDict(frozen=True)

    name: str
    local: bool


class ModelChoicesResponse(BaseModel):
    """The models a user may pick to write the answers (#37), the default first."""

    models: list[ChatModel]
    default: str


class ChatRequest(BaseModel):
    """The conversation so far, oldest first, ending with the user's new message. A longer
    conversation is sent as its latest messages. `model` is the name of one of the models
    `GET /models` lists; without it the default writes the answer."""

    messages: list[ChatMessage]
    model: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None

    @field_validator("messages", mode="before")
    @classmethod
    def has_one_to_ten_messages(cls, messages: Any) -> Any:
        """Counted before the messages are read, so a huge conversation costs nothing."""
        if isinstance(messages, list) and not messages:
            raise ValueError("A conversation needs at least one message.")
        if isinstance(messages, list) and len(messages) > MAX_MESSAGES:
            raise ValueError(
                f"A conversation can have at most {MAX_MESSAGES} messages: send the latest ones."
            )
        return messages

    @model_validator(mode="after")
    def ends_with_the_user(self) -> Self:
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be the user's.")
        return self


class Source(BaseModel):
    """Where a fact the tools returned comes from: a label passage on DailyMed (`kind`
    "dailymed", with the label's date and `ref`, the number the answer cites it with as `[ref]`),
    a PubChem compound page, a ChEMBL target page or an RCSB entry page (`kind` "rcsb")."""

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
    `not_supported`, `no_complex`, `invalid_arguments`), if it has one."""

    type: Literal["tool_result"] = "tool_result"
    id: str
    name: str
    status: str | None
    result: Any


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ReplaceAnswerEvent(BaseModel):
    """The answer streamed so far is withdrawn: show `text` in its place. The guard sends it
    when an answer repeats the system prompt (#203)."""

    type: Literal["replace_answer"] = "replace_answer"
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
    arguments. `translation` stays empty: #114 measured a query translation step and didn't
    build it. `mode` is the ranking the search used, `min_score` the similarity a candidate needed
    to be kept and `section_group_boost` what a candidate in the filter's section groups counted
    higher in the ranking.
    """

    type: Literal["retrieval_trace"] = "retrieval_trace"
    tool_call_id: str
    question: str
    translation: list[TranslationStep]
    filter: LabelFilter | None
    filter_source: Literal["model", "agent"]
    widened: list[Widening]
    candidates: list[Candidate]
    mode: RetrievalMode
    min_score: float
    section_group_boost: float


class SourceCheckEvent(BaseModel):
    """The source check's verdict on the answer just sent, one entry per claim in the answer's
    order: `supported` when the results it cites hold it, `unsupported` when they don't,
    `not_a_claim` when it states nothing about a drug. The answer is shown either way; this
    only marks it. `checked` is false when the check failed, and then there are no claims."""

    type: Literal["source_check"] = "source_check"
    checked: bool
    claims: list[CheckedClaim] = []


type UsageStep = Literal["input_check", "answer", "label_filter", "source_check"]


class DoneEvent(BaseModel):
    """The answer is complete. `usage` is what all its model calls used, `usage_by_step` the
    same split by the step that made the calls: the input check, the agent's answer, the label
    searches' filter extraction and the source check. `step_limit_reached` means the agent had
    to answer without further tool calls. `category` is how the guard sorted the question;
    anything but `ok` and `overdose_emergency` got a fixed answer. It is None from an agent
    without a guard."""

    type: Literal["done"] = "done"
    usage_by_step: dict[UsageStep, Usage] = {}
    step_limit_reached: bool
    category: InputCategory | None = None

    @computed_field
    @property
    def usage(self) -> Usage:
        return sum(self.usage_by_step.values(), Usage())


type ErrorKind = Literal[
    "input_check_failed", "model_error", "timeout", "no_answer", "server_error"
]


class ErrorEvent(BaseModel):
    """The answer stopped; `message` is written for the user. `kind` says why, for the usage
    log: the input check gave no category, a model call failed, the answer ran out of time,
    the model ended without answer text, or the server failed."""

    type: Literal["error"] = "error"
    kind: ErrorKind
    message: str


type ChatEvent = Annotated[
    StatusEvent
    | ToolCallEvent
    | ToolResultEvent
    | TokenEvent
    | ReplaceAnswerEvent
    | SourcesEvent
    | RetrievalTraceEvent
    | SourceCheckEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
