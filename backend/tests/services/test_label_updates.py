import asyncio
import sqlite3
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

from molecula.services.label_updates import LabelUpdater, seconds_until, update_nightly
from molecula.store.label_updates import LabelChange, LabelUpdateRun, LabelUpdateStore

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
RUN = LabelUpdateRun(
    started_at=NOW,
    finished_at=NOW + timedelta(minutes=3),
    outcome="complete",
    source_updated=None,
    drugs_checked=133,
    drugs_rechecked=2,
    changes=(
        LabelChange(5291, "rx", "a", "20250101", "b", "20261020"),
        LabelChange(3672, "rx", "c", "20250101", "d", "20261020"),
        LabelChange(3672, "otc", "e", "20250101", "f", "20261020"),
    ),
)


class BlockingUpdate:
    """An update that runs until released."""

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls = 0

    def __call__(self) -> LabelUpdateRun:
        self.calls += 1
        self.started.set()
        assert self.release.wait(5)
        return RUN


@pytest.fixture
def runs(conn: sqlite3.Connection) -> LabelUpdateStore:
    return LabelUpdateStore(conn)


@pytest.fixture
def update() -> Iterator[BlockingUpdate]:
    update = BlockingUpdate()
    yield update
    update.release.set()


def wait_until_idle(updater: LabelUpdater) -> None:
    deadline = time.monotonic() + 5
    while updater.running:
        assert time.monotonic() < deadline, "the run did not end"
        time.sleep(0.01)


def test_a_run_goes_in_the_background_and_a_second_one_is_refused(
    runs: LabelUpdateStore, update: BlockingUpdate
) -> None:
    updater = LabelUpdater(runs, update, button=True)

    assert updater.start()
    assert update.started.wait(5)
    assert updater.running
    assert not updater.start()

    update.release.set()
    wait_until_idle(updater)

    assert update.calls == 1
    assert updater.start()


def test_a_failing_run_is_logged_and_lets_the_next_one_start(
    runs: LabelUpdateStore, caplog: pytest.LogCaptureFixture
) -> None:
    def failing() -> LabelUpdateRun:
        raise RuntimeError("index locked")

    updater = LabelUpdater(runs, failing, button=True)

    assert updater.start()
    wait_until_idle(updater)

    assert "index locked" in caplog.text
    assert updater.start()


def test_without_an_update_starting_says_why(runs: LabelUpdateStore) -> None:
    updater = LabelUpdater(runs, None, button=True, off_reason="OFFLINE=1")

    assert not updater.can_run
    with pytest.raises(RuntimeError, match="OFFLINE=1"):
        updater.start()


def test_status_counts_the_drugs_the_last_run_changed(
    runs: LabelUpdateStore, update: BlockingUpdate
) -> None:
    updater = LabelUpdater(runs, update, button=True)
    assert updater.status().last_run is None

    runs.add(RUN)
    status = updater.status()

    assert status.last_run is not None
    assert (status.last_run.finished_at, status.last_run.outcome) == (RUN.finished_at, "complete")
    assert status.last_run.drugs_changed == 2
    assert (status.running, status.can_start) == (False, True)


@pytest.mark.parametrize(("button", "can_run"), [(False, True), (True, False)])
def test_the_dashboard_may_start_a_run_only_with_the_button_on_and_an_update(
    runs: LabelUpdateStore, update: BlockingUpdate, button: bool, can_run: bool
) -> None:
    updater = LabelUpdater(runs, update if can_run else None, button=button)

    assert not updater.status().can_start


@pytest.mark.parametrize(
    ("now", "hours"),
    [
        (datetime(2026, 10, 21, 1, 0, tzinfo=UTC), 2),
        (datetime(2026, 10, 21, 3, 0, tzinfo=UTC), 24),
        (datetime(2026, 10, 21, 3, 0, 1, tzinfo=UTC), 24 - 1 / 3600),
        (datetime(2026, 10, 21, 23, 30, tzinfo=UTC), 3.5),
    ],
)
def test_seconds_until_the_next_run(now: datetime, hours: float) -> None:
    assert seconds_until(3, now) == pytest.approx(hours * 3600)


def run_nights(answers: list[bool]) -> list[datetime]:
    """Run the nightly loop on a fake clock from NOW until `start` was called once per answer;
    returns when it was called."""
    clock = [NOW]
    replies = iter(answers)
    starts: list[datetime] = []

    async def sleep(seconds: float) -> None:
        if len(starts) == len(answers):
            raise asyncio.CancelledError
        clock[0] += timedelta(seconds=seconds)

    def start() -> bool:
        starts.append(clock[0])
        return next(replies)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(update_nightly(start, 3, now=lambda: clock[0], sleep=sleep))
    return starts


def test_the_nightly_run_starts_once_a_day_at_the_hour() -> None:
    starts = run_nights([True, True, True])

    assert starts == [datetime(2026, 10, day, 3, 0, tzinfo=UTC) for day in (22, 23, 24)]


def test_a_night_whose_run_is_refused_is_skipped_and_the_next_night_tries_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    starts = run_nights([False, True])

    assert starts == [datetime(2026, 10, day, 3, 0, tzinfo=UTC) for day in (22, 23)]
    assert "skipped" in caplog.text
