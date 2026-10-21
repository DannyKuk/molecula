import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

from molecula.store.schema import SchemaVersionError, ensure_schema


class StoreConnection(sqlite3.Connection):
    """A connection with the one lock that every store over it holds while it uses it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # One lock per connection, not per store: a query that calls `casefold` waits for the GIL
        # while holding SQLite's connection mutex, and another store's thread reading rows waits
        # for that mutex while holding the GIL (#389).
        self.lock = Lock()


def connect(path: Path) -> StoreConnection:
    """Open the store at `path`, creating the file and the schema on first use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync routes in a thread pool, so the connection is shared across threads.
    conn = sqlite3.connect(path, check_same_thread=False, factory=StoreConnection)
    # SQLite's NOCASE and lower() fold only A to Z, so "östradiol" wouldn't find "Östradiol".
    conn.create_function("casefold", 1, str.casefold, deterministic=True)
    conn.execute("PRAGMA foreign_keys = ON")
    # Readers see the last committed state while a label update writes, instead of waiting.
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        ensure_schema(conn)
    except SchemaVersionError:
        conn.close()
        raise
    return conn
