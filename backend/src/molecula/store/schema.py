import sqlite3

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE http_cache (
    key TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    status INTEGER NOT NULL,
    content_type TEXT,
    body BLOB NOT NULL,
    fetched_at TEXT NOT NULL
);
"""


class SchemaVersionError(Exception):
    """The store was built with a schema version this code doesn't know."""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the schema in an empty database; refuse one with any other version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version == 0:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return
    raise SchemaVersionError(
        f"store has schema version {version}, this code knows {SCHEMA_VERSION}; "
        "update the code or rebuild the store"
    )
