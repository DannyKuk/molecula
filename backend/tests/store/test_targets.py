import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.targets import (
    CandidateRecord,
    DrugTargets,
    LigandCode,
    TargetRecord,
    TargetStore,
)

FIRST_FETCH = datetime(2026, 10, 11, tzinfo=UTC)
LATER_FETCH = datetime(2026, 11, 1, tzinfo=UTC)

IMATINIB = CompoundRecord(
    cid=5291,
    name="imatinib",
    inchikey="KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    smiles="CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
    formula="C29H31N7O",
    mw=493.6,
    xlogp=3.5,
    tpsa=86.3,
    hbd=2,
    hba=7,
    rotb=7,
    heavy_atoms=37,
    conformer_source="pubchem",
    source="pubchem",
)
ABL1 = TargetRecord(
    target_chembl_id="CHEMBL1862",
    molecule_chembl_id="CHEMBL1642",
    name="Tyrosine-protein kinase ABL1",
    target_type="SINGLE PROTEIN",
    organism="Homo sapiens",
    mechanism="Tyrosine-protein kinase ABL inhibitor",
    action_type="INHIBITOR",
    accessions=("P00519",),
    gene_symbols=("ABL1",),
)
STI = LigandCode("STI", "inchikey")
IEP = CandidateRecord(
    target_chembl_id="CHEMBL1862",
    rank=1,
    pdb_id="1IEP",
    ligand_code="STI",
    title="CRYSTAL STRUCTURE OF THE C-ABL KINASE DOMAIN IN COMPLEX WITH STI-571.",
    resolution=2.1,
    organism="Mus musculus",
    taxonomy_id=10090,
    chains=("A", "B"),
)
DRUG = DrugTargets(targets=(ABL1,), ligand_codes=(STI,), candidates=(IEP,))


@pytest.fixture
def store(conn: sqlite3.Connection) -> TargetStore:
    CompoundStore(conn).save(IMATINIB, [], FIRST_FETCH)
    return TargetStore(conn)


def test_round_trips_targets_ligand_codes_and_candidates(store: TargetStore) -> None:
    store.save(5291, DRUG, FIRST_FETCH)

    assert store.get(5291) == DRUG


def test_compound_without_rows_gives_empty_targets(store: TargetStore) -> None:
    assert store.get(5291) == DrugTargets()


def test_rows_record_source_and_fetch_time(store: TargetStore, conn: sqlite3.Connection) -> None:
    store.save(5291, DRUG, FIRST_FETCH)

    for table, source in [
        ("target", "chembl"),
        ("ligand_code", "rcsb"),
        ("complex_candidate", "rcsb"),
    ]:
        row = conn.execute(f"SELECT source, fetched_at FROM {table}").fetchone()
        assert row == (source, FIRST_FETCH.isoformat())


def test_saving_the_same_data_changes_nothing(store: TargetStore, conn: sqlite3.Connection) -> None:
    store.save(5291, DRUG, FIRST_FETCH)
    changes = conn.total_changes

    store.save(5291, DRUG, LATER_FETCH)

    assert conn.total_changes == changes


def test_new_data_replaces_the_old(store: TargetStore) -> None:
    store.save(5291, DRUG, FIRST_FETCH)
    better = replace(IEP, resolution=1.9)

    store.save(5291, replace(DRUG, candidates=(better,)), LATER_FETCH)

    assert store.get(5291).candidates == (better,)


def test_candidate_must_belong_to_a_stored_target(store: TargetStore) -> None:
    orphan = replace(IEP, target_chembl_id="CHEMBL1913")

    with pytest.raises(sqlite3.IntegrityError):
        store.save(5291, replace(DRUG, candidates=(orphan,)), FIRST_FETCH)


def test_deleting_the_compound_deletes_its_rows(
    store: TargetStore, conn: sqlite3.Connection
) -> None:
    store.save(5291, DRUG, FIRST_FETCH)

    with conn:
        conn.execute("DELETE FROM compound WHERE cid = 5291")

    assert store.get(5291) == DrugTargets()
