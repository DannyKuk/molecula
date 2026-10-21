from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from molecula.schemas.chat import ErrorKind
from molecula.schemas.guard import InputCategory

type Outcome = Literal["answered", "error", "stopped", "limited"]


class RequestRecord(BaseModel):
    """One chat request in the usage log. It holds no question or answer text, no tool
    arguments (they carry the drug names from the question) and no client address.

    `outcome` is `answered` when the stream reached `done` (a fixed answer too: `category` says
    which), `error` when it ended with an error, `stopped` when the client left before the end
    and `limited` when a rate or cost limit turned the request away. Tokens and cost are None
    when no `done` said them or a model call didn't report them; `tools` are the names of the
    tools called, in order."""

    model_config = ConfigDict(frozen=True)

    id: str
    started_at: datetime
    model: str | None
    outcome: Outcome
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    tools: list[str] = []
    category: InputCategory | None = None
    step_limit_reached: bool | None = None
    error_kind: ErrorKind | None = None


class UsageDay(BaseModel):
    """One UTC day of chat requests. Latency is over the answered requests, and None on a day
    without one; tokens and cost add up what was reported."""

    date: date
    requests: int
    outcomes: dict[Outcome, int]
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    input_tokens: int
    output_tokens: int
    cost_usd: float


class UsageStats(BaseModel):
    """The chat's use over the last `days` UTC days, today included: one entry per day, oldest
    first, also for days without a request; then tool calls per tool, how the guard sorted
    the questions, and errors per kind, over the whole range."""

    days: list[UsageDay]
    tool_calls: dict[str, int]
    categories: dict[InputCategory, int]
    errors: dict[ErrorKind, int]


class KnowledgeBaseStats(BaseModel):
    """What the store holds. `drugs` are the compounds in scope; `chunks` are the label passages
    in the search index; `conformers` and `complexes` are the 3D structure files. The label
    dates are the oldest and newest label fetch, None before labels are built."""

    drugs: int
    labels: int
    label_sections: int
    chunks: int
    targets: int
    conformers: int
    complexes: int
    schema_version: int
    labels_fetched_from: datetime | None
    labels_fetched_to: datetime | None


class Stats(BaseModel):
    knowledge_base: KnowledgeBaseStats
    usage: UsageStats
