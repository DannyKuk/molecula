"""Label update tests on recorded openFDA counts and searches (see `tests/openfda_replay.py`).
The store starts with the canonical labels the recorded searches give; a test makes one older."""

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

import httpx2
import pytest

from molecula.config import Settings
from molecula.ingest import update
from molecula.ingest.labels import canonical_labels
from molecula.ingest.update import Drug, update_labels, was_changed
from molecula.sources.http import SourceClient
from molecula.sources.openfda import PAGE_SIZE, LabelPage, OpenFdaClient
from molecula.store.compounds import CompoundStore
from molecula.store.label_updates import LabelChange, LabelUpdateRun, LabelUpdateStore
from molecula.store.labels import LabelRecord, LabelStore
from openfda_replay import FIXTURES, GLEEVEC, Replay
from store_records import compound_record

ACETAMINOPHEN = compound_record(1983, "acetaminophen")
IBUPROFEN = compound_record(3672, "ibuprofen")
IMATINIB = compound_record(5291, "imatinib")
COMPOUNDS = [ACETAMINOPHEN, IBUPROFEN, IMATINIB]
SEARCHES = {
    "acetaminophen": "labels_acetaminophen_selected.json",
    "ibuprofen": "labels_ibuprofen_selected.json",
    "imatinib": "labels_imatinib.json",
}
FETCHED_AT = datetime(2026, 10, 12, 8, 45, tzinfo=UTC)
NOW = datetime(2026, 11, 14, 3, 0, tzinfo=UTC)
OPENFDA_UPDATED = date(2026, 10, 20)


def recorded_canonical(name: str) -> tuple[LabelRecord, ...]:
    page = LabelPage.model_validate_json((FIXTURES / SEARCHES[name]).read_bytes())
    return canonical_labels(name, page.labels)


OLD_GLEEVEC = replace(recorded_canonical("imatinib")[0], effective_time="20200101")


class Reindexed:
    """A fake indexer that records which compounds it re-indexed with which labels."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, list[str]]] = []

    def __call__(self, cid: int, labels: Sequence[LabelRecord]) -> None:
        self.calls.append((cid, [label.set_id for label in labels]))


@pytest.fixture
def labels(conn: sqlite3.Connection) -> LabelStore:
    compounds, labels = CompoundStore(conn), LabelStore(conn)
    for compound in COMPOUNDS:
        compounds.save(compound, [], FETCHED_AT)
        labels.save(compound.cid, recorded_canonical(compound.name), FETCHED_AT)
    labels.save(IMATINIB.cid, (OLD_GLEEVEC,), FETCHED_AT)
    return labels


@pytest.fixture
def updates(conn: sqlite3.Connection) -> LabelUpdateStore:
    return LabelUpdateStore(conn)


@pytest.fixture
def run_update(
    replaying_client: Callable[..., SourceClient],
    labels: LabelStore,
    updates: LabelUpdateStore,
) -> Callable[..., tuple[LabelUpdateRun, Replay, Reindexed]]:
    def run(replay: Replay | None = None) -> tuple[LabelUpdateRun, Replay, Reindexed]:
        replay, reindexed = replay or Replay(), Reindexed()
        result = update_labels(
            COMPOUNDS,
            OpenFdaClient(replaying_client(replay)),
            labels,
            updates,
            reindexed,
            now=lambda: NOW,
        )
        return result, replay, reindexed

    return run


def searched_names(replay: Replay) -> list[str]:
    return [
        request.url.params["search"].removeprefix('openfda.generic_name:"').removesuffix('"')
        for request in replay.requests
        if "count" not in request.url.params
    ]


def earlier_run(source_updated: date) -> LabelUpdateRun:
    return LabelUpdateRun(
        started_at=FETCHED_AT,
        finished_at=FETCHED_AT,
        outcome="complete",
        source_updated=source_updated,
        drugs_checked=3,
        drugs_rechecked=0,
    )


def test_a_new_version_replaces_the_stored_label_and_only_that_drug_is_reindexed(
    run_update, labels: LabelStore, updates: LabelUpdateStore
) -> None:
    result, replay, reindexed = run_update()

    assert result.outcome == "complete"
    assert (result.drugs_checked, result.drugs_rechecked) == (3, 1)
    assert searched_names(replay) == ["imatinib"]
    assert reindexed.calls == [(IMATINIB.cid, [GLEEVEC])]
    [gleevec] = labels.get(IMATINIB.cid)
    assert gleevec.effective_time == "20260713"
    assert updates.changes() == [
        LabelChange(IMATINIB.cid, "rx", GLEEVEC, "20200101", GLEEVEC, "20260713")
    ]


def test_an_unchanged_drug_is_not_touched(
    run_update, labels: LabelStore, conn: sqlite3.Connection
) -> None:
    run_update()

    assert labels.get(IBUPROFEN.cid) == recorded_canonical("ibuprofen")
    fetched = conn.execute("SELECT DISTINCT fetched_at FROM label WHERE cid = ?", (IBUPROFEN.cid,))
    assert fetched.fetchall() == [(FETCHED_AT.isoformat(),)]


def test_a_withdrawn_or_newer_label_marks_its_drug() -> None:
    drug = Drug(IMATINIB, recorded_canonical("imatinib"))

    assert was_changed(drug, listed=set(), newer=set())
    assert was_changed(drug, listed={GLEEVEC}, newer={GLEEVEC})
    assert not was_changed(drug, listed={GLEEVEC}, newer=set())


def test_the_checks_bypass_the_http_cache(run_update) -> None:
    run_update()

    _, replay, _ = run_update()

    # The first run left its counts in the cache; the second asked openFDA again, and stopped
    # there since openFDA has published nothing new.
    assert [request.url.params["count"] for request in replay.requests] == ["set_id"]


def test_a_cached_label_search_is_fetched_again(
    run_update, replaying_client: Callable[..., SourceClient]
) -> None:
    OpenFdaClient(replaying_client(Replay())).labels("imatinib")

    _, replay, _ = run_update()

    assert searched_names(replay) == ["imatinib"]


def test_nothing_new_from_openfda_ends_the_run_after_one_request(
    run_update, labels: LabelStore, updates: LabelUpdateStore
) -> None:
    updates.add(earlier_run(OPENFDA_UPDATED))

    result, replay, reindexed = run_update()

    assert result.outcome == "nothing_new"
    assert len(replay.requests) == 1
    assert reindexed.calls == []
    assert labels.get(IMATINIB.cid) == (OLD_GLEEVEC,)
    assert updates.last_finished() == result


def test_new_data_from_openfda_runs_the_checks(run_update, updates: LabelUpdateStore) -> None:
    updates.add(earlier_run(date(2026, 10, 13)))

    result, _, reindexed = run_update()

    assert result.outcome == "complete"
    assert reindexed.calls == [(IMATINIB.cid, [GLEEVEC])]


def test_a_drug_that_fails_is_reported_and_the_run_is_incomplete(
    run_update, labels: LabelStore, updates: LabelUpdateStore
) -> None:
    busy = Replay({("imatinib", PAGE_SIZE, 0): httpx2.Response(500)})

    result, _, reindexed = run_update(busy)

    assert result.outcome == "incomplete"
    assert result.error and "imatinib" in result.error
    assert reindexed.calls == []
    assert labels.get(IMATINIB.cid) == (OLD_GLEEVEC,)
    assert updates.last_finished() is None


def test_a_failing_check_is_recorded_and_changes_nothing(
    replaying_client: Callable[..., SourceClient],
    labels: LabelStore,
    updates: LabelUpdateStore,
) -> None:
    def unavailable(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503)

    result = update_labels(
        COMPOUNDS,
        OpenFdaClient(replaying_client(unavailable)),
        labels,
        updates,
        Reindexed(),
        now=lambda: NOW,
    )

    assert result.outcome == "failed"
    assert result.error and "503" in result.error
    assert labels.get(IMATINIB.cid) == (OLD_GLEEVEC,)
    assert updates.last_finished() is None


def test_offline_exits_without_requests_or_changes(
    make_settings: Callable[..., Settings], caplog: pytest.LogCaptureFixture
) -> None:
    settings = make_settings(offline=True)

    assert update.run(settings) == 1

    assert "OFFLINE=1" in caplog.text
    assert not settings.db_path.exists()
