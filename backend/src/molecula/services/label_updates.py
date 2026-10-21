import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from threading import Lock, Thread

from molecula.schemas.stats import LabelUpdateStatus, LastLabelUpdate
from molecula.store.label_updates import LabelUpdateRun, LabelUpdateStore

logger = logging.getLogger(__name__)


class LabelUpdater:
    """Runs the label update inside the backend, one run at a time, in a thread of its own so
    the app keeps answering. `update` is None when the backend can't update: `off_reason`
    says why."""

    def __init__(
        self,
        runs: LabelUpdateStore,
        update: Callable[[], LabelUpdateRun] | None,
        *,
        button: bool,
        off_reason: str | None = None,
    ) -> None:
        self._runs = runs
        self._update = update
        self._lock = Lock()
        self.button = button
        self.off_reason = off_reason

    @property
    def can_run(self) -> bool:
        return self._update is not None

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def start(self) -> bool:
        """Start a run and return at once; False when a run is still going."""
        if self._update is None:
            raise RuntimeError(self.off_reason or "The backend can't update the labels")
        if not self._lock.acquire(blocking=False):
            return False
        Thread(target=self._run, args=(self._update,), name="label-update", daemon=True).start()
        return True

    def _run(self, update: Callable[[], LabelUpdateRun]) -> None:
        # A run cut short, by an error or by the backend stopping, is safe to repeat: the update
        # re-indexes a drug before it saves the drug's labels (#341).
        try:
            update()
        except Exception:
            logger.exception("The label update stopped with an error")
        finally:
            self._lock.release()

    def status(self) -> LabelUpdateStatus:
        last = self._runs.latest()
        return LabelUpdateStatus(
            last_run=(
                LastLabelUpdate(
                    finished_at=last.finished_at,
                    outcome=last.outcome,
                    drugs_changed=len({change.cid for change in last.changes}),
                )
                if last
                else None
            ),
            running=self.running,
            can_start=self.button and self.can_run,
        )


async def update_nightly(
    start: Callable[[], bool],
    hour: int,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Start a label update with `start` every day at `hour` UTC until cancelled. A run still
    going at that hour is left alone, and that day has no new one."""
    while True:
        await sleep(seconds_until(hour, now()))
        if start():
            logger.info("The nightly label update started")
        else:
            logger.warning("The nightly label update was skipped: an earlier run is still going")


def seconds_until(hour: int, now: datetime) -> float:
    """Seconds from `now` to the next `hour`:00 UTC; at the hour itself, the next day's."""
    now = now.astimezone(UTC)
    next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()
