import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from molecula.store.compounds import CompoundRecord, CompoundStore, Synonym, SynonymMatch
from molecula.store.labels import LabelRecord, LabelSection, LabelStore

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


def test_find_matches_an_alias_ignoring_case(store: CompoundStore) -> None:
    store.save(
        CAFFEINE, [Synonym("caffeine", "name"), Synonym("Guaranine", "pubchem")], FIRST_FETCH
    )

    match = store.find("GUARANINE")

    assert match == SynonymMatch(CAFFEINE, "Guaranine", "pubchem")


@pytest.mark.parametrize(
    ("stored", "name"),
    [("Östradiol", "östradiol"), ("Östradiol", "ÖSTRADIOL"), ("Valproinsäure", "VALPROINSÄURE")],
)
def test_find_ignores_the_case_of_letters_outside_a_to_z(
    store: CompoundStore, stored: str, name: str
) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name"), Synonym(stored, "alias")], FIRST_FETCH)

    assert store.find(name) == SynonymMatch(CAFFEINE, stored, "alias")


def test_find_matches_a_label_brand_ignoring_the_case_of_letters_outside_a_to_z(
    conn: sqlite3.Connection, store: CompoundStore
) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)
    save_label(conn, CAFFEINE.cid, "Wachmacher Ölig")

    assert store.find("wachmacher-ölig") == SynonymMatch(CAFFEINE, "Wachmacher Ölig", "brand")


def test_find_prefers_a_scope_name_over_another_compounds_synonym(store: CompoundStore) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name"), Synonym("theine", "pubchem")], FIRST_FETCH)
    theine = replace(CAFFEINE, cid=99, name="theine")
    store.save(theine, [Synonym("theine", "name")], FIRST_FETCH)

    match = store.find("theine")

    assert match == SynonymMatch(theine, "theine", "name")


def save_label(conn: sqlite3.Connection, cid: int, brand: str) -> None:
    label = LabelRecord(
        set_id=f"label-{cid}",
        substance="CAFFEINE",
        brand=brand,
        product_type="otc",
        effective_time="20260101",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=label",
        sections=(LabelSection("otc_purpose", "otc_consumer", "Alertness aid.", False),),
    )
    LabelStore(conn).save(cid, (label,), FIRST_FETCH)


@pytest.mark.parametrize("name", ["stay awake", "STAY-AWAKE", "Stay Awake"])
def test_find_matches_a_label_brand_ignoring_case_and_hyphens(
    conn: sqlite3.Connection, store: CompoundStore, name: str
) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)
    save_label(conn, CAFFEINE.cid, "Stay Awake")

    assert store.find(name) == SynonymMatch(CAFFEINE, "Stay Awake", "brand")


def test_find_prefers_a_synonym_over_a_label_brand(
    conn: sqlite3.Connection, store: CompoundStore
) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)
    theine = replace(CAFFEINE, cid=99, name="theine")
    store.save(theine, [Synonym("theine", "name"), Synonym("Wake Up", "alias")], FIRST_FETCH)
    save_label(conn, CAFFEINE.cid, "Wake Up")

    assert store.find("wake up") == SynonymMatch(theine, "Wake Up", "alias")


def test_find_a_brand_only_as_a_whole_name(conn: sqlite3.Connection, store: CompoundStore) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)
    save_label(conn, CAFFEINE.cid, "Stay Awake")

    assert store.find("Stay") is None


def test_find_unknown_alias_gives_none(store: CompoundStore) -> None:
    assert store.find("caffeine") is None


def test_scope_aliases_leave_out_names_and_pubchem_synonyms(store: CompoundStore) -> None:
    store.save(
        CAFFEINE,
        [
            Synonym("caffeine", "name"),
            Synonym("Koffein", "alias"),
            Synonym("Guaranine", "pubchem"),
            Synonym("Coffein", "alias"),
        ],
        FIRST_FETCH,
    )
    store.save(replace(CAFFEINE, cid=99, name="theine"), [Synonym("theine", "name")], FIRST_FETCH)

    assert store.scope_aliases() == {2519: ["Koffein", "Coffein"]}


def test_all_lists_compounds_by_name(store: CompoundStore) -> None:
    store.save(replace(CAFFEINE, cid=99, name="Theine"), [], FIRST_FETCH)
    store.save(CAFFEINE, [], FIRST_FETCH)

    assert [compound.name for compound in store.all()] == ["caffeine", "Theine"]


def test_prune_deletes_the_compounds_not_kept_with_their_synonyms(store: CompoundStore) -> None:
    theine = replace(CAFFEINE, cid=99, name="theine")
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)
    store.save(theine, [Synonym("theine", "name")], FIRST_FETCH)

    removed = store.prune({2519})

    assert removed == [theine]
    assert store.get(99) is None
    assert store.synonyms(99) == []
    assert store.get(2519) == CAFFEINE
    assert store.synonyms(2519) == [Synonym("caffeine", "name")]


def test_prune_keeping_every_compound_changes_nothing(
    store: CompoundStore, conn: sqlite3.Connection
) -> None:
    store.save(CAFFEINE, [], FIRST_FETCH)
    changes = conn.total_changes

    assert store.prune({2519, 99}) == []
    assert conn.total_changes == changes


def test_label_brands_lists_each_brand_of_a_compound_once(
    conn: sqlite3.Connection, store: CompoundStore
) -> None:
    store.save(CAFFEINE, [Synonym("caffeine", "name")], FIRST_FETCH)
    save_label(conn, CAFFEINE.cid, "Stay Awake")

    assert store.label_brands() == {CAFFEINE.cid: ["Stay Awake"]}


def test_label_brands_without_labels_is_empty(store: CompoundStore) -> None:
    assert store.label_brands() == {}
