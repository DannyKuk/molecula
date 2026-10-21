import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from molecula.store.compounds import CompoundStore, Synonym
from molecula.store.db import connect
from molecula.store.schema import MIGRATIONS, SCHEMA_VERSION, SchemaVersionError
from molecula.store.targets import DrugTargets, TargetStore
from store_records import ABL1, IMATINIB

# Two stores over one connection, each queried in a loop from its own thread, as the agent's
# parallel tool calls do. Run in a child process: a deadlock holds the GIL, so it would hang pytest.
TWO_STORES_IN_TWO_THREADS = """
import sys, threading, time
from pathlib import Path
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.targets import TargetStore

conn = connect(Path(sys.argv[1]))
compounds, targets = CompoundStore(conn), TargetStore(conn)
stop = time.monotonic() + 1.0

def find() -> None:
    while time.monotonic() < stop:
        compounds.find("Imatinib")

def get() -> None:
    while time.monotonic() < stop:
        targets.get(5291)

threads = [threading.Thread(target=find), threading.Thread(target=get)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
"""


def test_first_open_creates_file_and_schema(tmp_path: Path) -> None:
    path = tmp_path / "build" / "molecula.db"

    conn = connect(path)

    assert path.exists()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "http_cache" in tables


def test_reopening_keeps_the_data(tmp_path: Path) -> None:
    path = tmp_path / "molecula.db"
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO http_cache VALUES ('k', 'https://x', 200, NULL, x'00', '2026-01-01')"
        )
    conn.close()

    reopened = connect(path)

    assert reopened.execute("SELECT count(*) FROM http_cache").fetchone()[0] == 1


@pytest.mark.parametrize("stored_version", [SCHEMA_VERSION + 1, SCHEMA_VERSION + 10])
def test_refuses_a_newer_schema(tmp_path: Path, stored_version: int) -> None:
    path = tmp_path / "molecula.db"
    newer = sqlite3.connect(path)
    newer.execute(f"PRAGMA user_version = {stored_version}")
    newer.close()

    with pytest.raises(SchemaVersionError, match=str(stored_version)):
        connect(path)


def test_upgrades_a_version_1_store_and_keeps_the_cache(tmp_path: Path) -> None:
    path = tmp_path / "molecula.db"
    old = sqlite3.connect(path)
    old.executescript(MIGRATIONS[1])
    old.execute("INSERT INTO http_cache VALUES ('k', 'https://x', 200, NULL, x'00', '2026-01-01')")
    old.execute("PRAGMA user_version = 1")
    old.commit()
    old.close()

    conn = connect(path)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert conn.execute("SELECT count(*) FROM http_cache").fetchone()[0] == 1
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"compound", "synonym"} <= tables


def test_upgrades_a_version_2_store_and_keeps_the_compounds(tmp_path: Path) -> None:
    path = tmp_path / "molecula.db"
    old = sqlite3.connect(path)
    old.executescript(MIGRATIONS[1] + MIGRATIONS[2])
    old.execute(
        "INSERT INTO compound VALUES (2519, 'caffeine', 'K', 'C', 'F', 1.0, NULL, NULL,"
        " 0, 0, 0, 1, 0, NULL, 'pubchem', '2026-01-01')"
    )
    old.execute("PRAGMA user_version = 2")
    old.commit()
    old.close()

    conn = connect(path)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert conn.execute("SELECT count(*) FROM compound").fetchone()[0] == 1
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"target", "ligand_code", "complex_candidate"} <= tables


def test_upgrades_a_version_3_store_and_adds_the_label_tables(tmp_path: Path) -> None:
    path = tmp_path / "molecula.db"
    old = sqlite3.connect(path)
    old.executescript(MIGRATIONS[1] + MIGRATIONS[2] + MIGRATIONS[3])
    old.execute("PRAGMA user_version = 3")
    old.commit()
    old.close()

    conn = connect(path)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"label", "label_section"} <= tables
    assert "source_disclaimer" not in tables


def test_upgrades_a_version_5_store_dropping_the_disclaimer_and_keeping_its_labels(
    tmp_path: Path,
) -> None:
    path = tmp_path / "molecula.db"
    old = sqlite3.connect(path)
    old.executescript("".join(MIGRATIONS[version] for version in range(1, 6)))
    old.execute(
        "INSERT INTO compound VALUES (5291, 'imatinib', 'K', 'C', 'F', 1.0, NULL, NULL,"
        " 0, 0, 0, 1, 0, NULL, 'pubchem', '2026-01-01')"
    )
    old.execute(
        "INSERT INTO label VALUES ('gleevec', 5291, 'IMATINIB MESYLATE', 'Gleevec', 'rx',"
        " '20260713', 'https://dailymed', 'openfda', '2026-10-12')"
    )
    old.execute("INSERT INTO source_disclaimer VALUES ('openfda', 'Do not rely on openFDA.', '')")
    old.execute("PRAGMA user_version = 5")
    old.commit()
    old.close()

    conn = connect(path)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "source_disclaimer" not in tables
    assert conn.execute("SELECT set_id FROM label").fetchall() == [("gleevec",)]


def test_upgrades_a_version_4_store_keeping_its_labels_and_allowing_the_new_groups(
    tmp_path: Path,
) -> None:
    path = tmp_path / "molecula.db"
    old = sqlite3.connect(path)
    old.executescript("".join(MIGRATIONS[version] for version in range(1, 5)))
    old.execute(
        "INSERT INTO compound VALUES (5291, 'imatinib', 'K', 'C', 'F', 1.0, NULL, NULL,"
        " 0, 0, 0, 1, 0, NULL, 'pubchem', '2026-01-01')"
    )
    old.execute(
        "INSERT INTO label VALUES ('gleevec', 5291, 'IMATINIB MESYLATE', 'Gleevec', 'rx',"
        " '20260713', 'https://dailymed', 'openfda', '2026-10-12')"
    )
    old.executemany(
        "INSERT INTO label_section VALUES ('gleevec', ?, ?, ?, ?)",
        [
            ("indications_and_usage", "indications", "Ph+ CML.", 0),
            ("dosage", "dosing", "400 mg", 1),
        ],
    )
    old.execute("PRAGMA user_version = 4")
    old.commit()
    old.close()

    conn = connect(path)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert conn.execute(
        "SELECT section, section_group, text, sensitive FROM label_section ORDER BY rowid"
    ).fetchall() == [
        ("indications_and_usage", "indications", "Ph+ CML.", 0),
        ("dosage", "dosing", "400 mg", 1),
    ]
    conn.execute(
        "INSERT INTO label_section VALUES ('gleevec', 'pregnancy', 'specific_populations', 'x', 1)"
    )
    conn.execute("DELETE FROM label")
    assert conn.execute("SELECT count(*) FROM label_section").fetchone()[0] == 0


def test_the_store_uses_write_ahead_logging(tmp_path: Path) -> None:
    conn = connect(tmp_path / "molecula.db")

    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_two_stores_over_one_connection_dont_deadlock_across_threads(tmp_path: Path) -> None:
    path = tmp_path / "molecula.db"
    with connect(path) as conn:
        # Enough synonyms that each `find` spends a while in the `casefold` SQL function (#389).
        synonyms = [Synonym(f"imatinib synonym {n}", "pubchem") for n in range(2000)]
        CompoundStore(conn).save(IMATINIB, synonyms, datetime(2026, 10, 21, tzinfo=UTC))
        TargetStore(conn).save(IMATINIB.cid, DrugTargets(targets=(ABL1,)), datetime.now(UTC))
    conn.close()

    run = subprocess.run(
        [sys.executable, "-c", TWO_STORES_IN_TWO_THREADS, str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert run.returncode == 0, run.stderr
