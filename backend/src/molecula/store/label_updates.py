from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from molecula.schemas.labels import ProductType, UpdateOutcome
from molecula.store.db import StoreConnection

# Runs that checked every drug: the next run may start where they started.
FINISHED: tuple[UpdateOutcome, ...] = ("complete", "nothing_new")
RUN_COLUMNS = (
    "id, started_at, finished_at, outcome, source_updated, drugs_checked, drugs_rechecked, error"
)
CHANGE_COLUMNS = "cid, product_type, old_set_id, old_effective_time, new_set_id, new_effective_time"


@dataclass(frozen=True)
class LabelChange:
    """A drug's canonical label of one product type before and after an update; None where it
    had none."""

    cid: int
    product_type: ProductType
    old_set_id: str | None
    old_effective_time: str | None
    new_set_id: str | None
    new_effective_time: str | None


@dataclass(frozen=True)
class LabelUpdateRun:
    """One label update: when it ran, openFDA's publication date it saw, how many drugs it
    checked and fetched again, and what changed."""

    started_at: datetime
    finished_at: datetime
    outcome: UpdateOutcome
    source_updated: date | None
    drugs_checked: int
    drugs_rechecked: int
    changes: tuple[LabelChange, ...] = ()
    error: str | None = None


class LabelUpdateStore:
    """The `label_update` and `label_change` tables."""

    def __init__(self, conn: StoreConnection) -> None:
        self._conn = conn
        self._lock = conn.lock

    def add(self, run: LabelUpdateRun) -> None:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO label_update (started_at, finished_at, outcome, source_updated,"
                " drugs_checked, drugs_rechecked, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run.started_at.isoformat(),
                    run.finished_at.isoformat(),
                    run.outcome,
                    run.source_updated.isoformat() if run.source_updated else None,
                    run.drugs_checked,
                    run.drugs_rechecked,
                    run.error,
                ),
            )
            self._conn.executemany(
                "INSERT INTO label_change (update_id, cid, product_type, old_set_id,"
                " old_effective_time, new_set_id, new_effective_time)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        cursor.lastrowid,
                        change.cid,
                        change.product_type,
                        change.old_set_id,
                        change.old_effective_time,
                        change.new_set_id,
                        change.new_effective_time,
                    )
                    for change in run.changes
                ],
            )

    def last_finished(self) -> LabelUpdateRun | None:
        """The latest run that checked every drug, without its changes."""
        placeholders = ", ".join("?" for _ in FINISHED)
        with self._lock:
            row = self._conn.execute(
                f"SELECT {RUN_COLUMNS} FROM label_update WHERE outcome IN ({placeholders})"
                " ORDER BY started_at DESC LIMIT 1",
                FINISHED,
            ).fetchone()
        return run_from_row(row[1:]) if row else None

    def latest(self) -> LabelUpdateRun | None:
        """The latest run, whatever its outcome, with its changes."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {RUN_COLUMNS} FROM label_update ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            rows = self._conn.execute(
                f"SELECT {CHANGE_COLUMNS} FROM label_change WHERE update_id = ?"
                " ORDER BY cid, product_type",
                (row[0],),
            ).fetchall()
        return replace(run_from_row(row[1:]), changes=tuple(LabelChange(*c) for c in rows))

    def changes(self) -> list[LabelChange]:
        """Every recorded change, oldest run first."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {CHANGE_COLUMNS} FROM label_change ORDER BY update_id, cid, product_type"
            ).fetchall()
        return [LabelChange(*row) for row in rows]

    def current_since(self) -> datetime | None:
        """Since when the store's labels are known to be current: the start of the last run that
        checked every drug, or else the oldest label fetch. Not the newest fetch: an update from
        there would miss a label that changed after an earlier fetch of another one."""
        if run := self.last_finished():
            return run.started_at
        with self._lock:
            oldest = self._conn.execute("SELECT MIN(fetched_at) FROM label").fetchone()[0]
        return datetime.fromisoformat(oldest) if oldest else None


def run_from_row(row: tuple[Any, ...]) -> LabelUpdateRun:
    started, finished, outcome, updated, checked, rechecked, error = row
    return LabelUpdateRun(
        started_at=datetime.fromisoformat(started),
        finished_at=datetime.fromisoformat(finished),
        outcome=outcome,
        source_updated=date.fromisoformat(updated) if updated else None,
        drugs_checked=checked,
        drugs_rechecked=rechecked,
        error=error,
    )
