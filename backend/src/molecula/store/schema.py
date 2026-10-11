import sqlite3

# Each entry upgrades the store from the previous version to its key.
MIGRATIONS = {
    1: """
CREATE TABLE http_cache (
    key TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    status INTEGER NOT NULL,
    content_type TEXT,
    body BLOB NOT NULL,
    fetched_at TEXT NOT NULL
);
""",
    2: """
CREATE TABLE compound (
    cid INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    inchikey TEXT NOT NULL,
    smiles TEXT NOT NULL,
    formula TEXT NOT NULL,
    mw REAL NOT NULL,
    xlogp REAL,
    tpsa REAL,
    hbd INTEGER NOT NULL,
    hba INTEGER NOT NULL,
    rotb INTEGER NOT NULL,
    heavy_atoms INTEGER NOT NULL,
    has_3d INTEGER NOT NULL,
    conformer_source TEXT CHECK (conformer_source IN ('pubchem', 'rdkit')),
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    CHECK (has_3d = (conformer_source IS NOT NULL))
);

CREATE TABLE synonym (
    alias TEXT NOT NULL COLLATE NOCASE,
    cid INTEGER NOT NULL REFERENCES compound (cid) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('name', 'alias', 'pubchem')),
    PRIMARY KEY (alias, cid)
);

CREATE INDEX synonym_cid ON synonym (cid);
""",
}
SCHEMA_VERSION = max(MIGRATIONS)


class SchemaVersionError(Exception):
    """The store was built with a schema version this code doesn't know."""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Bring an empty or older store up to `SCHEMA_VERSION`; refuse a newer one."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"store has schema version {version}, this code knows {SCHEMA_VERSION}; "
            "update the code or rebuild the store"
        )
    for target in range(version + 1, SCHEMA_VERSION + 1):
        conn.executescript(f"BEGIN; {MIGRATIONS[target]} PRAGMA user_version = {target}; COMMIT;")
