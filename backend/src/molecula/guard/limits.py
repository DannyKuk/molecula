import logging
import math
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from molecula.schemas.usage import Usage

logger = logging.getLogger(__name__)

MINUTE = 60.0
DAY = 24 * 60 * 60.0


class ChatLimited(Exception):
    """A chat request turned away: `status` 429 for a client over its limit, 503 once the day's
    cost limit is reached. `message` is written for the user."""

    def __init__(self, status: int, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.retry_after = retry_after


class RequestLimiter:
    """Counts each client's requests over the last minute and the last day. Counters live in
    memory, for one backend, and start again when it restarts."""

    def __init__(
        self, per_minute: int, per_day: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limits = ((MINUTE, per_minute), (DAY, per_day))
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}

    def admit(self, client: str) -> None:
        """Counts a request from `client`. Raises ChatLimited, without counting it, when the
        client is at a limit."""
        now = self._clock()
        self._forget_before(now - DAY)
        requests = self._requests.setdefault(client, deque())
        for window, limit in self._limits:
            recent = [at for at in requests if at > now - window]
            if len(recent) >= limit:
                wait = recent[-limit] + window - now
                raise ChatLimited(
                    429,
                    f"You've asked {counted(limit, 'question')} in the last {per(window)}, "
                    f"the most Molecula takes. Try again in {in_words(wait)}.",
                    math.ceil(wait),
                )
        requests.append(now)

    def _forget_before(self, start: float) -> None:
        for client in list(self._requests):
            requests = self._requests[client]
            while requests and requests[0] <= start:
                requests.popleft()
            if not requests:
                del self._requests[client]


class DailyCostCap:
    """What the cloud models cost today (UTC), against a limit. Starts again each UTC day and
    when the backend restarts."""

    def __init__(
        self, limit_usd: float, now: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._limit_usd = limit_usd
        self._now = now
        self._day = now().date()
        self._spent_usd = 0.0

    @property
    def spent_usd(self) -> float:
        self._start_new_day()
        return self._spent_usd

    def add(self, cost_usd: float) -> None:
        self._start_new_day()
        self._spent_usd += cost_usd

    def admit(self) -> None:
        """Raises ChatLimited once today's cost has reached the limit."""
        if self.spent_usd < self._limit_usd:
            return
        now = self._now()
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
        wait = (midnight - now).total_seconds()
        raise ChatLimited(
            503,
            "Molecula has used up today's budget for the language model. Try again after "
            f"midnight UTC, in {in_words(wait)}.",
            math.ceil(wait),
        )

    def _start_new_day(self) -> None:
        today = self._now().date()
        if today != self._day:
            self._day = today
            self._spent_usd = 0.0


class ChatLimits:
    """The limits a chat request passes before it is answered: the day's cost limit, when the
    chat runs on a cloud model, then the client's request limit."""

    def __init__(
        self, requests: RequestLimiter, cost_cap: DailyCostCap | None, *, trust_proxy: bool
    ) -> None:
        self.requests = requests
        self.cost_cap = cost_cap
        self.trust_proxy = trust_proxy

    def admit(self, client: str) -> None:
        """Counts the request. Raises ChatLimited when a limit turns it away; a request turned
        away isn't counted."""
        if self.cost_cap is not None:
            self.cost_cap.admit()
        self.requests.admit(client)

    def record(self, usage: Usage) -> None:
        """Adds an answer's cost to the day's. A cost no model call reported counts as 0."""
        if self.cost_cap is None:
            return
        if usage.cost_usd is None:
            logger.warning("An answer's cost is unknown; the daily cost limit counts it as 0")
            return
        self.cost_cap.add(usage.cost_usd)


def per(window: float) -> str:
    return "minute" if window == MINUTE else "day"


def in_words(seconds: float) -> str:
    """A wait as the user reads it, rounded up: "40 seconds", "1 minute", "5 hours"."""
    seconds = math.ceil(seconds)
    if seconds < MINUTE:
        return counted(seconds, "second")
    if seconds < 60 * MINUTE:
        return counted(math.ceil(seconds / MINUTE), "minute")
    return counted(math.ceil(seconds / (60 * MINUTE)), "hour")


def counted(count: int, unit: str) -> str:
    return f"{count} {unit}" if count == 1 else f"{count} {unit}s"
