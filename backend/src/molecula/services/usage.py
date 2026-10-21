import logging
import math
import sqlite3
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, date, datetime, timedelta

from molecula.schemas.chat import ChatEvent, DoneEvent, ErrorEvent, ToolCallEvent
from molecula.schemas.stats import Outcome, RequestRecord, UsageDay, UsageStats
from molecula.store.usage import UsageStore

logger = logging.getLogger(__name__)


class UsageLog:
    """Records each chat request in the usage log and as one JSON line in the app's log, and
    sums the log up for `/stats`."""

    def __init__(
        self,
        store: UsageStore,
        model: str | None,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._model = model
        self._now = now
        self._clock = clock

    async def recorded(self, events: AsyncIterator[ChatEvent]) -> AsyncIterator[ChatEvent]:
        """The events, recorded as one request once the stream ends, fails or is left."""
        started_at, start = self._now(), self._clock()
        tools: list[str] = []
        done: DoneEvent | None = None
        error_kind = None
        try:
            async for event in events:
                if isinstance(event, ToolCallEvent):
                    tools.append(event.name)
                elif isinstance(event, DoneEvent):
                    done = event
                elif isinstance(event, ErrorEvent):
                    error_kind = event.kind
                yield event
        except Exception:
            error_kind = "server_error"
            raise
        finally:
            outcome: Outcome = (
                "answered" if done else "error" if error_kind is not None else "stopped"
            )
            usage = done.usage if done else None
            self.add(
                RequestRecord(
                    id=uuid.uuid4().hex,
                    started_at=started_at,
                    model=self._model,
                    outcome=outcome,
                    latency_ms=round((self._clock() - start) * 1000),
                    input_tokens=usage.input_tokens if usage else None,
                    output_tokens=usage.output_tokens if usage else None,
                    cost_usd=usage.cost_usd if usage else None,
                    tools=tools,
                    category=done.category if done else None,
                    step_limit_reached=done.step_limit_reached if done else None,
                    error_kind=error_kind,
                )
            )

    def limited(self) -> None:
        """Records a request a rate or cost limit turned away."""
        self.add(
            RequestRecord(
                id=uuid.uuid4().hex,
                started_at=self._now(),
                model=self._model,
                outcome="limited",
                latency_ms=0,
            )
        )

    def add(self, record: RequestRecord) -> None:
        """Logs the request and stores it. A request the usage log can't store is only logged:
        recording it must never stop an answer."""
        logger.info("%s", record.model_dump_json())
        try:
            self._store.add(record)
        except sqlite3.Error:
            logger.exception("The usage log could not store request %s", record.id)

    def stats(self, days: int) -> UsageStats:
        """The last `days` UTC days, today included."""
        first = self._now().astimezone(UTC).date() - timedelta(days=days - 1)
        records = self._store.since(datetime.combine(first, datetime.min.time(), UTC))
        return summarize(records, [first + timedelta(days=n) for n in range(days)])


def summarize(records: Sequence[RequestRecord], days: Sequence[date]) -> UsageStats:
    by_day: dict[date, list[RequestRecord]] = {day: [] for day in days}
    for record in records:
        by_day.setdefault(record.started_at.astimezone(UTC).date(), []).append(record)
    return UsageStats(
        days=[summarize_day(day, by_day[day]) for day in days],
        tool_calls=dict(Counter(tool for record in records for tool in record.tools)),
        categories=dict(Counter(r.category for r in records if r.category is not None)),
        errors=dict(Counter(r.error_kind for r in records if r.error_kind is not None)),
    )


def summarize_day(day: date, records: Sequence[RequestRecord]) -> UsageDay:
    latencies = sorted(r.latency_ms for r in records if r.outcome == "answered")
    return UsageDay(
        date=day,
        requests=len(records),
        outcomes=dict(Counter(r.outcome for r in records)),
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        input_tokens=sum(r.input_tokens or 0 for r in records),
        output_tokens=sum(r.output_tokens or 0 for r in records),
        cost_usd=sum(r.cost_usd or 0.0 for r in records),
    )


def percentile(ordered: Sequence[int], p: int) -> int | None:
    """The nearest-rank percentile of `ordered` values, None for none."""
    if not ordered:
        return None
    return ordered[math.ceil(p / 100 * len(ordered)) - 1]
