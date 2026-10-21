import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from molecula.schemas.stats import RequestRecord

# Runtime data has no migrations of its own yet: a new column needs one before it ships.
SCHEMA = """
CREATE TABLE IF NOT EXISTS request (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    model TEXT,
    outcome TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    tools TEXT NOT NULL,
    category TEXT,
    step_limit_reached INTEGER,
    error_kind TEXT
);

CREATE INDEX IF NOT EXISTS request_started_at ON request (started_at);
"""
COLUMNS = tuple(RequestRecord.model_fields)


def connect_usage(path: Path) -> sqlite3.Connection:
    """Open the usage log at `path`, creating the file and its table on first use. Not the
    store's `connect`: the usage log isn't part of the store and has none of its tables."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


class UsageStore:
    """The usage log's requests. The chat writes from the event loop while `/stats` reads in
    the thread pool, so one lock keeps them off the shared connection at the same time."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    def add(self, record: RequestRecord) -> None:
        row = record.model_dump()
        row["started_at"] = record.started_at.isoformat()
        row["tools"] = json.dumps(record.tools)
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT INTO request ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in COLUMNS)})",
                [row[column] for column in COLUMNS],
            )

    def since(self, start: datetime) -> list[RequestRecord]:
        """The requests started at or after `start` (UTC), oldest first."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {', '.join(COLUMNS)} FROM request WHERE started_at >= ? "
                "ORDER BY started_at",
                (start.isoformat(),),
            ).fetchall()
        return [to_record(row) for row in rows]


def to_record(row: tuple[object, ...]) -> RequestRecord:
    fields = dict(zip(COLUMNS, row, strict=True))
    fields["tools"] = json.loads(str(fields["tools"]))
    return RequestRecord.model_validate(fields)
