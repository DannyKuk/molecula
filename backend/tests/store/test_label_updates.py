import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from molecula.store.compounds import CompoundStore
from molecula.store.label_updates import LabelChange, LabelUpdateRun, LabelUpdateStore
from molecula.store.labels import LabelStore
from store_records import GLEEVEC, IMATINIB

FETCHED = datetime(2026, 10, 12, 8, 45, tzinfo=UTC)
RUN = LabelUpdateRun(
    started_at=datetime(2026, 11, 1, 3, 0, tzinfo=UTC),
    finished_at=datetime(2026, 11, 1, 3, 2, tzinfo=UTC),
    outcome="complete",
    source_updated=date(2026, 10, 27),
    drugs_checked=133,
    drugs_rechecked=4,
    changes=(LabelChange(5291, "rx", "old", "20250101", "new", "20261020"),),
)


@pytest.fixture
def updates(conn: sqlite3.Connection) -> LabelUpdateStore:
    return LabelUpdateStore(conn)


def test_a_run_and_its_changes_are_stored(updates: LabelUpdateStore) -> None:
    updates.add(RUN)

    assert updates.last_finished() == replace(RUN, changes=())
    assert updates.changes() == list(RUN.changes)


def test_the_latest_run_is_the_newest_of_any_outcome_with_its_changes(
    updates: LabelUpdateStore,
) -> None:
    failed = replace(
        RUN, started_at=datetime(2026, 10, 31, tzinfo=UTC), outcome="failed", changes=()
    )
    updates.add(failed)
    updates.add(RUN)
    later = replace(RUN, started_at=datetime(2026, 11, 2, tzinfo=UTC), outcome="failed")

    assert updates.latest() == RUN

    updates.add(replace(later, changes=(), error="openFDA stopped answering"))

    assert updates.latest() == replace(later, changes=(), error="openFDA stopped answering")


def test_before_any_run_there_is_no_latest(updates: LabelUpdateStore) -> None:
    assert updates.latest() is None


@pytest.mark.parametrize("outcome", ["incomplete", "failed"])
def test_a_run_that_did_not_check_every_drug_is_not_the_last_finished(
    updates: LabelUpdateStore, outcome: str
) -> None:
    updates.add(RUN)
    later = replace(RUN, started_at=datetime(2026, 11, 2, tzinfo=UTC), changes=())

    updates.add(replace(later, outcome=outcome, error="openFDA stopped answering"))

    assert updates.last_finished() == replace(RUN, changes=())


def test_labels_are_current_since_the_last_finished_run(updates: LabelUpdateStore) -> None:
    updates.add(RUN)

    assert updates.current_since() == RUN.started_at


def test_before_any_run_labels_are_current_since_the_oldest_fetch(
    updates: LabelUpdateStore, conn: sqlite3.Connection
) -> None:
    CompoundStore(conn).save(IMATINIB, [], FETCHED)
    LabelStore(conn).save(5291, (GLEEVEC,), FETCHED)

    assert updates.current_since() == FETCHED


def test_an_empty_store_is_current_since_never(updates: LabelUpdateStore) -> None:
    assert updates.current_since() is None
