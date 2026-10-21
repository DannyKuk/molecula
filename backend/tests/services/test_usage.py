import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, date, datetime, timedelta

import pytest

from molecula.schemas.chat import (
    ChatEvent,
    DoneEvent,
    ErrorEvent,
    StatusEvent,
    TokenEvent,
    ToolCallEvent,
)
from molecula.schemas.stats import RequestRecord, UsageDay
from molecula.schemas.usage import Usage
from molecula.services.usage import UsageLog, percentile
from molecula.store.usage import UsageStore

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
ANSWER_USAGE = Usage(input_tokens=1200, output_tokens=300, total_tokens=1500, cost_usd=0.002)


class Clock:
    """Moves on by `step` seconds each time it is read."""

    def __init__(self, step: float) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def log(store: UsageStore, *, step: float = 1.5) -> UsageLog:
    return UsageLog(store, "openai/gpt-oss-20b", now=lambda: NOW, clock=Clock(step))


async def stream(events: Iterable[ChatEvent]) -> AsyncIterator[ChatEvent]:
    for event in events:
        yield event


async def drain(events: AsyncIterator[ChatEvent]) -> list[ChatEvent]:
    return [event async for event in events]


ANSWERED = [
    StatusEvent(message="Checking the question"),
    ToolCallEvent(id="1", name="search_labels", args={"question": "imatinib nausea"}),
    ToolCallEvent(id="2", name="get_targets", args={"drug": "imatinib"}),
    TokenEvent(text="Imatinib can cause nausea."),
    DoneEvent(usage_by_step={"answer": ANSWER_USAGE}, step_limit_reached=False, category="ok"),
]


def test_an_answered_request_is_recorded_with_its_metadata(usage_store: UsageStore) -> None:
    events = asyncio.run(drain(log(usage_store).recorded(stream(ANSWERED))))

    assert events == ANSWERED
    [record] = usage_store.since(NOW - timedelta(days=1))
    assert record.started_at == NOW
    assert record.model == "openai/gpt-oss-20b"
    assert record.outcome == "answered"
    assert record.latency_ms == 1500
    assert (record.input_tokens, record.output_tokens, record.cost_usd) == (1200, 300, 0.002)
    assert record.tools == ["search_labels", "get_targets"]
    assert record.category == "ok"
    assert record.step_limit_reached is False
    assert record.error_kind is None


def test_the_record_holds_no_message_text_and_no_tool_arguments(
    usage_store: UsageStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO", logger="molecula.services.usage"):
        asyncio.run(drain(log(usage_store).recorded(stream(ANSWERED))))

    [record] = usage_store.since(NOW - timedelta(days=1))
    stored = record.model_dump_json()
    [line] = [r.getMessage() for r in caplog.records if r.name == "molecula.services.usage"]
    assert json.loads(line) == json.loads(stored)
    for text in ("nausea", "imatinib", "Imatinib"):
        assert text not in stored


def test_an_error_is_recorded_with_its_kind(usage_store: UsageStore) -> None:
    events = [StatusEvent(message="Checking"), ErrorEvent(kind="timeout", message="Too long.")]

    asyncio.run(drain(log(usage_store).recorded(stream(events))))

    [record] = usage_store.since(NOW - timedelta(days=1))
    assert (record.outcome, record.error_kind) == ("error", "timeout")
    assert record.cost_usd is None and record.category is None


def test_a_failing_stream_is_recorded_as_a_server_error_and_still_fails(
    usage_store: UsageStore,
) -> None:
    async def broken() -> AsyncIterator[ChatEvent]:
        yield StatusEvent(message="Checking")
        raise RuntimeError("a bug")

    with pytest.raises(RuntimeError):
        asyncio.run(drain(log(usage_store).recorded(broken())))

    [record] = usage_store.since(NOW - timedelta(days=1))
    assert (record.outcome, record.error_kind) == ("error", "server_error")


def test_a_client_that_leaves_before_the_end_is_recorded_as_stopped(
    usage_store: UsageStore,
) -> None:
    async def leave_after_the_first_tool_call() -> None:
        events = log(usage_store).recorded(stream(ANSWERED))
        async for event in events:
            if isinstance(event, ToolCallEvent):
                break
        await events.aclose()

    asyncio.run(leave_after_the_first_tool_call())

    [record] = usage_store.since(NOW - timedelta(days=1))
    assert record.outcome == "stopped"
    assert record.tools == ["search_labels"]
    assert record.input_tokens is None


def test_a_limited_request_is_recorded_without_usage(usage_store: UsageStore) -> None:
    log(usage_store).limited()

    [record] = usage_store.since(NOW - timedelta(days=1))
    assert (record.outcome, record.latency_ms, record.tools) == ("limited", 0, [])


def record(
    started_at: datetime,
    latency_ms: int = 1000,
    *,
    outcome: str = "answered",
    tools: list[str] | None = None,
    category: str | None = "ok",
    error_kind: str | None = None,
    cost_usd: float | None = 0.001,
) -> RequestRecord:
    return RequestRecord.model_validate(
        {
            "id": f"{started_at.isoformat()}-{latency_ms}-{outcome}",
            "started_at": started_at,
            "model": "openai/gpt-oss-20b",
            "outcome": outcome,
            "latency_ms": latency_ms,
            "input_tokens": 100 if cost_usd is not None else None,
            "output_tokens": 10 if cost_usd is not None else None,
            "cost_usd": cost_usd,
            "tools": tools or [],
            "category": category,
            "error_kind": error_kind,
        }
    )


def test_stats_sum_each_day_and_the_whole_range(usage_store: UsageStore) -> None:
    today = NOW.replace(hour=1)
    yesterday = today - timedelta(days=1)
    for latency in range(100, 2001, 100):
        usage_store.add(record(today, latency, tools=["search_labels"]))
    usage_store.add(record(today, 99_999, outcome="error", category=None, error_kind="timeout"))
    usage_store.add(record(yesterday, 500, tools=["get_targets", "search_labels"]))
    usage_store.add(record(yesterday, 0, outcome="limited", category=None, cost_usd=None))
    usage_store.add(record(yesterday, 300, category="off_topic"))
    usage_store.add(record(today - timedelta(days=5), 700))

    stats = log(usage_store).stats(days=3)

    assert [day.date for day in stats.days] == [
        date(2026, 10, 19),
        date(2026, 10, 20),
        date(2026, 10, 21),
    ]
    assert stats.days[0] == UsageDay(
        date=date(2026, 10, 19),
        requests=0,
        outcomes={},
        latency_p50_ms=None,
        latency_p95_ms=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
    )
    assert stats.days[1].requests == 3
    assert stats.days[1].outcomes == {"answered": 2, "limited": 1}
    assert stats.days[1].latency_p50_ms == 300
    assert stats.days[2].requests == 21
    assert stats.days[2].outcomes == {"answered": 20, "error": 1}
    # The error's latency is left out: it isn't an answer's.
    assert (stats.days[2].latency_p50_ms, stats.days[2].latency_p95_ms) == (1000, 1900)
    assert stats.days[2].input_tokens == 2100
    assert stats.days[2].cost_usd == pytest.approx(0.021)
    assert stats.tool_calls == {"search_labels": 21, "get_targets": 1}
    assert stats.categories == {"ok": 21, "off_topic": 1}
    assert stats.errors == {"timeout": 1}


def test_a_day_starts_at_midnight_utc(usage_store: UsageStore) -> None:
    usage_store.add(record(datetime(2026, 10, 20, 23, 59, tzinfo=UTC)))
    usage_store.add(record(datetime(2026, 10, 21, 0, 0, tzinfo=UTC)))

    stats = log(usage_store).stats(days=2)

    assert [day.requests for day in stats.days] == [1, 1]


def test_an_empty_log_gives_zeros(usage_store: UsageStore) -> None:
    stats = log(usage_store).stats(days=7)

    assert len(stats.days) == 7
    assert all(day.requests == 0 and day.cost_usd == 0 for day in stats.days)
    assert stats.tool_calls == {} and stats.categories == {} and stats.errors == {}


@pytest.mark.parametrize(
    ("values", "p", "expected"),
    [([], 95, None), ([7], 50, 7), ([7], 95, 7), ([1, 2, 3, 4], 50, 2), ([1, 2, 3, 4], 95, 4)],
)
def test_percentile_is_the_nearest_rank(values: list[int], p: int, expected: int | None) -> None:
    assert percentile(values, p) == expected
