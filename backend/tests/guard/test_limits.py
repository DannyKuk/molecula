from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from molecula.guard.limits import (
    ChatLimited,
    ChatLimits,
    DailyCostCap,
    RequestLimiter,
    in_words,
)
from molecula.schemas.usage import Usage

ANSWER = Usage(input_tokens=15000, output_tokens=800, total_tokens=15800, cost_usd=0.4)


class Clock:
    def __init__(self, start: datetime = datetime(2026, 10, 19, 22, 0, tzinfo=UTC)) -> None:
        self.at = start

    def now(self) -> datetime:
        return self.at

    def seconds(self) -> float:
        return self.at.timestamp()

    def advance(self, **elapsed: float) -> None:
        self.at += timedelta(**elapsed)


def limiter(clock: Clock, per_minute: int = 3, per_day: int = 10) -> RequestLimiter:
    return RequestLimiter(per_minute, per_day, clock=clock.seconds)


def turned_away(admit: Callable[..., None], *args: str) -> ChatLimited:
    with pytest.raises(ChatLimited) as raised:
        admit(*args)
    return raised.value


def test_the_request_over_the_minute_limit_is_turned_away_with_the_wait() -> None:
    clock = Clock()
    requests = limiter(clock)
    for _ in range(3):
        requests.admit("203.0.113.5")
        clock.advance(seconds=10)

    limited = turned_away(requests.admit, "203.0.113.5")

    assert limited.status == 429
    assert limited.retry_after == 30
    assert "Try again in 30 seconds" in limited.message


def test_the_limit_resets_after_the_window() -> None:
    clock = Clock()
    requests = limiter(clock)
    for _ in range(3):
        requests.admit("203.0.113.5")
    turned_away(requests.admit, "203.0.113.5")

    clock.advance(seconds=60)

    requests.admit("203.0.113.5")


def test_a_request_turned_away_is_not_counted() -> None:
    clock = Clock()
    requests = limiter(clock)
    for _ in range(3):
        requests.admit("203.0.113.5")
    for _ in range(5):
        turned_away(requests.admit, "203.0.113.5")

    clock.advance(seconds=60)

    for _ in range(3):
        requests.admit("203.0.113.5")


def test_the_day_limit_holds_over_many_minutes() -> None:
    clock = Clock()
    requests = limiter(clock)
    for _ in range(10):
        requests.admit("203.0.113.5")
        clock.advance(minutes=30)

    limited = turned_away(requests.admit, "203.0.113.5")

    assert limited.retry_after == 19 * 60 * 60
    assert "10 questions in the last day" in limited.message
    assert "Try again in 19 hours" in limited.message


def test_each_client_has_its_own_limit() -> None:
    requests = limiter(Clock())
    for _ in range(3):
        requests.admit("203.0.113.5")

    requests.admit("198.51.100.7")
    turned_away(requests.admit, "203.0.113.5")


def test_the_cost_cap_turns_requests_away_until_midnight_utc() -> None:
    clock = Clock()
    cap = DailyCostCap(1.0, now=clock.now)
    cap.add(0.6)
    cap.admit()
    cap.add(0.6)

    limited = turned_away(cap.admit)

    assert limited.status == 503
    assert limited.retry_after == 2 * 60 * 60
    assert "Try again after midnight UTC, in 2 hours" in limited.message
    clock.advance(hours=2)
    cap.admit()
    assert cap.spent_usd == 0.0


def test_the_cap_blocks_cloud_requests_and_not_local_ones() -> None:
    clock = Clock()
    cloud = ChatLimits(limiter(clock), DailyCostCap(1.0, now=clock.now), trust_proxy=False)
    local = ChatLimits(limiter(clock), None, trust_proxy=False)
    for limits in (cloud, local):
        limits.admit("203.0.113.5")
        limits.record(ANSWER.model_copy(update={"cost_usd": 1.5}))

    assert turned_away(cloud.admit, "203.0.113.5").status == 503
    local.admit("203.0.113.5")


def test_an_unknown_cost_counts_as_nothing_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cap = DailyCostCap(1.0, now=Clock().now)
    limits = ChatLimits(limiter(Clock()), cap, trust_proxy=False)

    limits.record(ANSWER)
    limits.record(Usage.unreported())

    assert cap.spent_usd == 0.4
    assert "cost is unknown" in caplog.text


@pytest.mark.parametrize(
    ("seconds", "words"),
    [(1, "1 second"), (42.2, "43 seconds"), (60, "1 minute"), (61, "2 minutes"), (7200, "2 hours")],
)
def test_a_wait_reads_in_the_largest_unit_rounded_up(seconds: float, words: str) -> None:
    assert in_words(seconds) == words
