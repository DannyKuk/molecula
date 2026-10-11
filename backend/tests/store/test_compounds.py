import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from molecula.store.compounds import CompoundRecord, CompoundStore, Synonym

FIRST_FETCH = datetime(2026, 10, 11, tzinfo=UTC)
LATER_FETCH = datetime(2026, 11, 1, tzinfo=UTC)

CAFFEINE = CompoundRecord(
    cid=2519,
    name="caffeine",
    inchikey="RYYVLZVUVIJVGH-UHFFFAOYSA-N",
    smiles="CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    formula="C8H10N4O2",
    mw=194.19,
    xlogp=-0.1,
    tpsa=58.4,
    hbd=0,
    hba=3,
    rotb=0,
    heavy_atoms=14,
    conformer_source="pubchem",
    source="pubchem",
)


@pytest.fixture
def store(conn: sqlite3.Connection) -> CompoundStore:
    return CompoundStore(conn)


def fetched_at(conn: sqlite3.Connection, cid: int) -> str:
    return conn.execute("SELECT fetched_at FROM compound WHERE cid = ?", (cid,)).fetchone()[0]


def test_round_trips_a_compound_and_its_synonyms(store: CompoundStore) -> None:
    synonyms = [Synonym("caffeine", "name"), Synonym("Guaranine", "pubchem")]

    store.save(CAFFEINE, synonyms, FIRST_FETCH)

    assert store.get(2519) == CAFFEINE
    assert store.synonyms(2519) == synonyms


def test_unknown_cid_gives_none(store: CompoundStore) -> None:
    assert store.get(1) is None


def test_saving_the_same_data_changes_nothing(
    store: CompoundStore, conn: sqlite3.Connection
) -> None:
    synonyms = [Synonym("caffeine", "name")]
    store.save(CAFFEINE, synonyms, FIRST_FETCH)
    changes = conn.total_changes

    store.save(CAFFEINE, synonyms, LATER_FETCH)

    assert conn.total_changes == changes
    assert fetched_at(conn, 2519) == FIRST_FETCH.isoformat()


def test_changed_data_is_updated_with_the_new_fetch_time(
    store: CompoundStore, conn: sqlite3.Connection
) -> None:
    store.save(CAFFEINE, [], FIRST_FETCH)

    store.save(replace(CAFFEINE, tpsa=58.5), [], LATER_FETCH)

    stored = store.get(2519)
    assert stored is not None
    assert stored.tpsa == 58.5
    assert fetched_at(conn, 2519) == LATER_FETCH.isoformat()


def test_an_alias_is_stored_once_with_its_first_kind(store: CompoundStore) -> None:
    store.save(
        CAFFEINE,
        [Synonym("caffeine", "name"), Synonym("Caffeine", "pubchem"), Synonym("CAFFEINE", "alias")],
        FIRST_FETCH,
    )

    assert store.synonyms(2519) == [Synonym("caffeine", "name")]


def test_peptide_without_conformer_has_no_3d(
    store: CompoundStore, conn: sqlite3.Connection
) -> None:
    store.save(replace(CAFFEINE, conformer_source=None), [], FIRST_FETCH)

    assert conn.execute("SELECT has_3d FROM compound WHERE cid = 2519").fetchone()[0] == 0


def test_a_name_moving_to_another_cid_replaces_the_old_compound(store: CompoundStore) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)

    store.save(replace(CAFFEINE, cid=99), [Synonym("caffeine", "name")], LATER_FETCH)

    assert store.get(2519) is None
    assert store.synonyms(2519) == []
    assert store.get(99) is not None
