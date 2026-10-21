import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from threading import Event

import pytest
from fastapi.testclient import TestClient

from molecula.api import dependencies
from molecula.main import app
from molecula.services.label_updates import LabelUpdater
from molecula.store.label_updates import LabelUpdateRun, LabelUpdateStore

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
RUN = LabelUpdateRun(
    started_at=NOW,
    finished_at=NOW,
    outcome="nothing_new",
    source_updated=None,
    drugs_checked=133,
    drugs_rechecked=0,
)


@pytest.fixture
def release() -> Iterator[Event]:
    release = Event()
    yield release
    release.set()


@pytest.fixture
def client_with(conn: sqlite3.Connection, release: Event) -> Iterator[Callable[..., TestClient]]:
    """Makes a client whose label update runs until `release` is set."""

    def make(*, button: bool, can_run: bool = True) -> TestClient:
        def update() -> LabelUpdateRun:
            release.wait(5)
            return RUN

        updater = LabelUpdater(
            LabelUpdateStore(conn),
            update if can_run else None,
            button=button,
            off_reason="OFFLINE=1: a label update needs openFDA.",
        )
        app.dependency_overrides[dependencies.label_updater] = lambda: updater
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def test_with_the_button_off_the_route_is_not_found(
    client_with: Callable[..., TestClient],
) -> None:
    assert client_with(button=False).post("/labels/update").status_code == 404


def test_the_button_starts_a_run_and_a_second_press_is_refused(
    client_with: Callable[..., TestClient],
) -> None:
    client = client_with(button=True)

    first = client.post("/labels/update")
    second = client.post("/labels/update")

    assert first.status_code == 202
    assert first.json()["running"] is True
    assert second.status_code == 409


def test_a_backend_that_cannot_update_says_why(client_with: Callable[..., TestClient]) -> None:
    response = client_with(button=True, can_run=False).post("/labels/update")

    assert response.status_code == 503
    assert "OFFLINE=1" in response.json()["detail"]
