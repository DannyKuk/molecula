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
    3: """
CREATE TABLE target (
    cid INTEGER NOT NULL REFERENCES compound (cid) ON DELETE CASCADE,
    target_chembl_id TEXT NOT NULL,
    molecule_chembl_id TEXT NOT NULL,
    name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    organism TEXT,
    mechanism TEXT NOT NULL,
    action_type TEXT,
    accessions TEXT NOT NULL,
    gene_symbols TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (cid, target_chembl_id)
);

CREATE TABLE ligand_code (
    cid INTEGER NOT NULL REFERENCES compound (cid) ON DELETE CASCADE,
    code TEXT NOT NULL,
    matched_on TEXT NOT NULL CHECK (matched_on IN ('inchikey', 'connectivity')),
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (cid, code)
);

CREATE TABLE complex_candidate (
    cid INTEGER NOT NULL,
    target_chembl_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    pdb_id TEXT NOT NULL,
    ligand_code TEXT NOT NULL,
    title TEXT,
    resolution REAL,
    organism TEXT,
    taxonomy_id INTEGER,
    chains TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (cid, target_chembl_id, rank),
    UNIQUE (cid, target_chembl_id, pdb_id, ligand_code),
    FOREIGN KEY (cid, target_chembl_id) REFERENCES target (cid, target_chembl_id)
        ON DELETE CASCADE,
    FOREIGN KEY (cid, ligand_code) REFERENCES ligand_code (cid, code) ON DELETE CASCADE
);
""",
    # Stores built before #180 also have a `source_disclaimer` table, which nothing reads any
    # more. It was dropped from here rather than in a new version, so opening such a store
    # changes nothing in it.
    4: """
CREATE TABLE label (
    set_id TEXT PRIMARY KEY,
    cid INTEGER NOT NULL REFERENCES compound (cid) ON DELETE CASCADE,
    substance TEXT NOT NULL,
    brand TEXT,
    product_type TEXT NOT NULL CHECK (product_type IN ('rx', 'otc')),
    effective_time TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE (cid, product_type)
);

CREATE TABLE label_section (
    set_id TEXT NOT NULL REFERENCES label (set_id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    section_group TEXT NOT NULL CHECK (section_group IN (
        'pharmacology', 'indications', 'dosing', 'warnings', 'contraindications',
        'interactions', 'adverse_reactions', 'otc_consumer'
    )),
    text TEXT NOT NULL,
    sensitive INTEGER NOT NULL,
    PRIMARY KEY (set_id, section)
);
""",
    # SQLite can't change a CHECK constraint, so label_section is rebuilt with the new groups.
    5: """
CREATE TABLE label_section_new (
    set_id TEXT NOT NULL REFERENCES label (set_id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    section_group TEXT NOT NULL CHECK (section_group IN (
        'pharmacology', 'indications', 'dosing', 'warnings', 'contraindications',
        'interactions', 'adverse_reactions', 'otc_consumer', 'specific_populations',
        'patient_information', 'product', 'abuse_dependence', 'clinical_studies', 'overdosage'
    )),
    text TEXT NOT NULL,
    sensitive INTEGER NOT NULL,
    PRIMARY KEY (set_id, section)
);
INSERT INTO label_section_new SELECT set_id, section, section_group, text, sensitive
    FROM label_section ORDER BY rowid;
DROP TABLE label_section;
ALTER TABLE label_section_new RENAME TO label_section;
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
