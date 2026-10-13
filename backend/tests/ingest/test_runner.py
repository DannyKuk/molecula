import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from molecula.config import Settings
from molecula.ingest.runner import StepReport, log_failures, run_step, store_and_sources
from molecula.sources.errors import OfflineError, SourceResponseError, SourceUnavailable


@dataclass(frozen=True)
class Item:
    name: str


ITEMS = [Item("caffeine"), Item("ibuprofen"), Item("imatinib")]


class StepError(Exception):
    pass


class Step:
    """Ingests items by upper-casing their names, raising the error set for an item instead."""

    def __init__(self, errors: dict[str, Exception] | None = None) -> None:
        self.errors = errors or {}
        self.tried: list[str] = []

    def __call__(self, item: Item) -> str:
        self.tried.append(item.name)
        if error := self.errors.get(item.name):
            raise error
        return item.name.upper()


def test_a_clean_run_is_complete() -> None:
    report = StepReport()

    results = run_step(ITEMS, Step(), report)

    assert results == ["CAFFEINE", "IBUPROFEN", "IMATINIB"]
    assert report.complete


def test_a_failing_item_is_reported_and_the_rest_still_run() -> None:
    step = Step({"caffeine": SourceResponseError("https://example.org", 500)})
    report = StepReport()

    results = run_step(ITEMS, step, report)

    assert results == ["IBUPROFEN", "IMATINIB"]
    assert report.failures == {"caffeine": "https://example.org: HTTP 500"}
    assert report.not_attempted == []
    assert not report.complete


def test_a_source_that_stops_answering_stops_the_run() -> None:
    step = Step({"ibuprofen": SourceUnavailable("PubChem kept answering 429")})
    report = StepReport()

    results = run_step(ITEMS, step, report)

    assert results == ["CAFFEINE"]
    assert step.tried == ["caffeine", "ibuprofen"]
    assert report.failures == {"ibuprofen": "PubChem kept answering 429"}
    assert report.not_attempted == ["imatinib"]
    assert not report.complete


def test_a_source_that_stops_answering_on_the_last_item_leaves_nothing_untried() -> None:
    report = StepReport()

    run_step(ITEMS, Step({"imatinib": SourceUnavailable("down")}), report)

    assert list(report.failures) == ["imatinib"]
    assert report.not_attempted == []


def test_a_step_can_catch_its_own_errors() -> None:
    report = StepReport()

    results = run_step(
        ITEMS, Step({"caffeine": StepError("two parents")}), report, catch=(StepError,)
    )

    assert results == ["IBUPROFEN", "IMATINIB"]
    assert report.failures == {"caffeine": "two parents"}


def test_an_error_the_step_does_not_catch_propagates() -> None:
    with pytest.raises(KeyError):
        run_step(ITEMS, Step({"caffeine": KeyError("bug")}), StepReport())


def offline_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, offline=True)


def test_store_and_sources_close_when_the_step_ends(tmp_path: Path) -> None:
    with store_and_sources(offline_settings(tmp_path)) as (conn, http):
        conn.execute("SELECT 1")
        with pytest.raises(OfflineError):
            http.get("https://example.org")

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_store_and_sources_close_when_the_step_raises(tmp_path: Path) -> None:
    with (
        pytest.raises(StepError),
        store_and_sources(offline_settings(tmp_path)) as (conn, _),
    ):
        raise StepError

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_failures_are_logged_with_the_source_that_stopped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    report = StepReport(failures={"ibuprofen": "down"}, not_attempted=["imatinib", "caffeine"])

    log_failures(report, "openFDA")

    assert "failed: ibuprofen: down" in caplog.text
    assert "stopped because openFDA stopped answering; 2 compounds not attempted" in caplog.text


def test_a_complete_report_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    log_failures(StepReport(), "PubChem")

    assert caplog.text == ""
