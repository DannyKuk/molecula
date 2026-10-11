import sqlite3
from pathlib import Path

from molecula.store.schema import SchemaVersionError, ensure_schema


def connect(path: Path) -> sqlite3.Connection:
    """Open the store at `path`, creating the file and the schema on first use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync routes in a thread pool, so the connection is shared across threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        ensure_schema(conn)
    except SchemaVersionError:
        conn.close()
        raise
    return conn
