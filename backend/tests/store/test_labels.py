import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.labels import LabelRecord, LabelSection, LabelStore

FIRST_FETCH = datetime(2026, 10, 11, tzinfo=UTC)
LATER_FETCH = datetime(2026, 11, 1, tzinfo=UTC)

IBUPROFEN = CompoundRecord(
    cid=3672,
    name="ibuprofen",
    inchikey="HEFNNWSXXWATRW-UHFFFAOYSA-N",
    smiles="CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    formula="C13H18O2",
    mw=206.28,
    xlogp=3.5,
    tpsa=37.3,
    hbd=1,
    hba=2,
    rotb=4,
    heavy_atoms=15,
    conformer_source="pubchem",
    source="pubchem",
)
RX = LabelRecord(
    set_id="rx-set-id",
    substance="IBUPROFEN",
    brand="Motrin",
    product_type="rx",
    effective_time="20250101",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=rx-set-id",
    sections=(
        LabelSection("clinical_pharmacology", "pharmacology", "Ibuprofen inhibits COX.", False),
        LabelSection("dosage_and_administration", "dosing", "400 mg every 4 hours.", True),
    ),
)
OTC = LabelRecord(
    set_id="otc-set-id",
    substance="IBUPROFEN",
    brand="Advil",
    product_type="otc",
    effective_time="20240601",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=otc-set-id",
    sections=(LabelSection("purpose", "otc_consumer", "Pain reliever/fever reducer", False),),
)
DISCLAIMER = "Do not rely on openFDA to make decisions regarding medical care."


@pytest.fixture
def store(conn: sqlite3.Connection) -> LabelStore:
    CompoundStore(conn).save(IBUPROFEN, [], FIRST_FETCH)
    return LabelStore(conn)


def test_round_trips_labels_with_their_sections_prescription_first(store: LabelStore) -> None:
    store.save(3672, (RX, OTC), FIRST_FETCH)

    assert store.get(3672) == (RX, OTC)


def test_compound_without_labels_gives_none(store: LabelStore) -> None:
    assert store.get(3672) == ()


def test_rows_record_source_and_fetch_time(store: LabelStore, conn: sqlite3.Connection) -> None:
    store.save(3672, (RX,), FIRST_FETCH)

    row = conn.execute("SELECT source, fetched_at FROM label").fetchone()
    assert row == ("openfda", FIRST_FETCH.isoformat())


def test_saving_the_same_labels_changes_nothing(
    store: LabelStore, conn: sqlite3.Connection
) -> None:
    store.save(3672, (RX, OTC), FIRST_FETCH)
    changes = conn.total_changes

    store.save(3672, (RX, OTC), LATER_FETCH)

    assert conn.total_changes == changes


def test_a_new_canonical_label_replaces_the_old_and_its_sections(
    store: LabelStore, conn: sqlite3.Connection
) -> None:
    store.save(3672, (RX, OTC), FIRST_FETCH)
    newer = replace(RX, set_id="newer-set-id", effective_time="20260101")

    store.save(3672, (newer,), LATER_FETCH)

    assert store.get(3672) == (newer,)
    stale = conn.execute(
        "SELECT count(*) FROM label_section WHERE set_id IN ('rx-set-id', 'otc-set-id')"
    ).fetchone()
    assert stale == (0,)


def test_one_label_per_product_type(store: LabelStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.save(3672, (RX, replace(RX, set_id="second-rx")), FIRST_FETCH)


def test_deleting_the_compound_deletes_its_labels(
    store: LabelStore, conn: sqlite3.Connection
) -> None:
    store.save(3672, (RX, OTC), FIRST_FETCH)

    with conn:
        conn.execute("DELETE FROM compound WHERE cid = 3672")

    assert store.get(3672) == ()
    assert conn.execute("SELECT count(*) FROM label_section").fetchone() == (0,)


def test_disclaimer_is_stored_once_per_source(store: LabelStore, conn: sqlite3.Connection) -> None:
    store.save_disclaimer("openfda", DISCLAIMER, FIRST_FETCH)
    changes = conn.total_changes

    store.save_disclaimer("openfda", DISCLAIMER, LATER_FETCH)

    assert store.disclaimer("openfda") == DISCLAIMER
    assert conn.total_changes == changes
    assert conn.execute("SELECT count(*) FROM source_disclaimer").fetchone() == (1,)


def test_a_changed_disclaimer_replaces_the_old(store: LabelStore) -> None:
    store.save_disclaimer("openfda", DISCLAIMER, FIRST_FETCH)

    store.save_disclaimer("openfda", "New wording.", LATER_FETCH)

    assert store.disclaimer("openfda") == "New wording."


def test_unknown_source_has_no_disclaimer(store: LabelStore) -> None:
    assert store.disclaimer("openfda") is None
