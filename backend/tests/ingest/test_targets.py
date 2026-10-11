"""Targets ingest tests on recorded ChEMBL and RCSB responses (see the `*_replay.py` helpers)."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

import chembl_replay
import rcsb_replay
from chembl_replay import BUPRENORPHINE, DOXYCYCLINE, FLUTICASONE, GLIMEPIRIDE
from molecula.config import Settings
from molecula.ingest.targets import (
    TargetsReport,
    ingest_targets,
    pick_molecule,
    run,
    unique_by_target,
)
from molecula.ingest.targets_report import render
from molecula.sources.chembl import ChemblClient
from molecula.sources.http import SourceClient
from molecula.sources.rcsb import RcsbClient
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.http_cache import HttpCache
from molecula.store.targets import DrugTargets, LigandCode, TargetStore

HUMAN = 9606


def compound(cid: int, name: str, inchikey: str, smiles: str = "C") -> CompoundRecord:
    return CompoundRecord(
        cid=cid,
        name=name,
        inchikey=inchikey,
        smiles=smiles,
        formula="C",
        mw=1.0,
        xlogp=None,
        tpsa=None,
        hbd=0,
        hba=0,
        rotb=0,
        heavy_atoms=1,
        conformer_source=None,
        source="pubchem",
    )


IMATINIB = compound(5291, "imatinib", chembl_replay.IMATINIB)
ACETAMINOPHEN = compound(1983, "acetaminophen", chembl_replay.ACETAMINOPHEN)


class Sources:
    """Serves ChEMBL and RCSB requests from their recorded responses, by host."""

    def __init__(
        self,
        chembl: Callable[[httpx2.Request], httpx2.Response] | None = None,
        rcsb: Callable[[httpx2.Request], httpx2.Response] | None = None,
    ) -> None:
        self._chembl = chembl or chembl_replay.Replay()
        self._rcsb = rcsb or rcsb_replay.Replay()
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        handler = self._chembl if request.url.host == "www.ebi.ac.uk" else self._rcsb
        return handler(request)


@pytest.fixture
def store(conn: sqlite3.Connection) -> TargetStore:
    compounds = CompoundStore(conn)
    for record in (IMATINIB, ACETAMINOPHEN):
        compounds.save(record, [], datetime(2026, 10, 11, tzinfo=UTC))
    return TargetStore(conn)


@pytest.fixture
def clients(cache: HttpCache) -> Callable[..., tuple[ChemblClient, RcsbClient]]:
    def make(sources: Sources | None = None) -> tuple[ChemblClient, RcsbClient]:
        http = SourceClient(
            cache,
            offline=False,
            transport=httpx2.MockTransport(sources or Sources()),
            sleep=lambda _: None,
        )
        return ChemblClient(http), RcsbClient(http)

    return make


@pytest.fixture
def ingest(clients, store: TargetStore) -> Callable[..., TargetsReport]:
    def run_ingest(compounds: list[CompoundRecord], sources: Sources | None = None):
        return ingest_targets(compounds, *clients(sources), store)

    return run_ingest


def test_imatinib_end_to_end(ingest, store: TargetStore) -> None:
    report = ingest([IMATINIB])

    assert report.failures == {}
    drug = store.get(5291)
    assert [t.target_chembl_id for t in drug.targets] == [
        "CHEMBL1862",
        "CHEMBL1913",
        "CHEMBL1936",
        "CHEMBL2096618",
    ]
    abl1 = drug.targets[0]
    assert (abl1.name, abl1.accessions, abl1.gene_symbols) == (
        "Tyrosine-protein kinase ABL1",
        ("P00519",),
        ("ABL1",),
    )
    # Found through the parent CHEMBL941; ChEMBL records the mechanism on the mesylate salt.
    assert abl1.molecule_chembl_id == "CHEMBL1642"
    assert drug.ligand_codes == (LigandCode("STI", "inchikey"),)
    [iep] = [
        c for c in drug.candidates if c.pdb_id == "1IEP" and c.target_chembl_id == "CHEMBL1862"
    ]
    assert (iep.ligand_code, iep.resolution, iep.organism, iep.chains) == (
        "STI",
        2.1,
        "Mus musculus",
        ("A", "B"),
    )


def test_candidates_rank_human_first_then_by_resolution(ingest, store: TargetStore) -> None:
    ingest([IMATINIB])

    abl1 = [c for c in store.get(5291).candidates if c.target_chembl_id == "CHEMBL1862"]
    assert [c.rank for c in abl1] == list(range(1, len(abl1) + 1))
    human = [c for c in abl1 if c.taxonomy_id == HUMAN]
    assert abl1[: len(human)] == human
    assert [c.resolution for c in human] == sorted(c.resolution for c in human)
    assert abl1[0].pdb_id == "3PYY"


def test_target_without_entries_has_no_candidates(ingest, store: TargetStore) -> None:
    ingest([IMATINIB])

    candidates = store.get(5291).candidates
    assert not [c for c in candidates if c.target_chembl_id == "CHEMBL1913"]
    kit = [c.pdb_id for c in candidates if c.target_chembl_id == "CHEMBL1936"]
    assert kit == ["1T46", "8S16"]


def test_molecule_only_drug_is_stored_without_candidates(ingest, store: TargetStore) -> None:
    report = ingest([ACETAMINOPHEN])

    assert report.failures == {}
    drug = store.get(1983)
    assert [t.target_chembl_id for t in drug.targets] == [
        "CHEMBL2094253",
        "CHEMBL2243",
        "CHEMBL4794",
    ]
    assert drug.ligand_codes == (LigandCode("TYL", "inchikey"),)
    assert drug.candidates == ()


def test_rerun_is_served_from_the_cache_and_changes_nothing(
    ingest, store: TargetStore, conn: sqlite3.Connection
) -> None:
    ingest([IMATINIB, ACETAMINOPHEN])
    rows_before = dump(conn)
    changes_before = conn.total_changes

    second_run = Sources()
    ingest([IMATINIB, ACETAMINOPHEN], second_run)

    assert second_run.requests == []
    assert conn.total_changes == changes_before
    assert dump(conn) == rows_before


def test_a_failing_drug_is_reported_and_the_rest_stored(ingest, store: TargetStore) -> None:
    broken = chembl_replay.Replay({chembl_replay.mechanisms_of("CHEMBL112"): httpx2.Response(500)})

    report = ingest([ACETAMINOPHEN, IMATINIB], Sources(chembl=broken))

    assert list(report.failures) == ["acetaminophen"]
    assert "HTTP 500" in report.failures["acetaminophen"]
    assert store.get(1983) == DrugTargets()
    assert store.get(5291).targets


def test_run_stops_when_a_source_stops_answering(ingest, store: TargetStore) -> None:
    def throttled(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429)

    report = ingest([ACETAMINOPHEN, IMATINIB], Sources(rcsb=throttled))

    assert list(report.failures) == ["acetaminophen"]
    assert report.not_attempted == ["imatinib"]
    assert store.get(5291) == DrugTargets()


def test_unnamed_exact_match_falls_back_to_the_connectivity_block(clients) -> None:
    chembl, _ = clients()

    pick = pick_molecule(chembl, compound(3476, "glimepiride", GLIMEPIRIDE))

    assert pick is not None
    assert (pick.molecule.chembl_id, pick.matched_on) == ("CHEMBL1481", "connectivity")
    assert pick.others == ["CHEMBL149223"]
    assert pick.mechanisms


def test_the_named_molecule_wins_and_the_others_are_reported(clients) -> None:
    chembl, _ = clients()

    pick = pick_molecule(chembl, compound(644073, "buprenorphine", BUPRENORPHINE))

    assert pick is not None
    assert (pick.molecule.chembl_id, pick.matched_on) == ("CHEMBL511142", "connectivity")
    assert len(pick.others) == 4


def test_another_tautomer_is_found_by_name_through_the_parent(clients) -> None:
    chembl, _ = clients()

    pick = pick_molecule(chembl, compound(54671203, "doxycycline", DOXYCYCLINE))

    assert pick is not None
    assert (pick.molecule.chembl_id, pick.matched_on) == ("CHEMBL1200699", "name")
    assert pick.molecule.parent_chembl_id == "CHEMBL1433"
    assert pick.mechanisms


def test_drug_without_mechanisms_keeps_its_exact_match(clients) -> None:
    chembl, _ = clients()

    pick = pick_molecule(chembl, compound(5311101, "fluticasone", FLUTICASONE))

    assert pick is not None
    assert (pick.molecule.chembl_id, pick.matched_on) == ("CHEMBL1201396", "inchikey")
    assert pick.mechanisms == []


def test_no_match_anywhere_gives_no_molecule(clients) -> None:
    chembl, _ = clients()

    assert pick_molecule(chembl, compound(1, "notadrugxyz", DOXYCYCLINE)) is None


def test_mechanisms_repeated_across_salts_give_one_target_each(clients) -> None:
    chembl, _ = clients()
    pick = pick_molecule(chembl, compound(54671203, "doxycycline", DOXYCYCLINE))
    assert pick is not None

    unique = unique_by_target(pick.mechanisms)

    targets = [m.target_chembl_id for m in unique]
    assert len(targets) == len(set(targets))
    assert len(unique) < len(pick.mechanisms)


def test_report_lists_each_drug_and_its_candidates(ingest) -> None:
    report = ingest([ACETAMINOPHEN, IMATINIB])

    text = render(report)

    assert "- 2 compounds stored: 2 with targets, 1 with complex candidates." in text
    assert "## imatinib (CID 5291)" in text
    assert "| 1 | 3PYY | STI | 1.85 | Homo sapiens | A,B |" in text
    assert "| 1IEP | STI | 2.1 | Mus musculus | A,B |" in text
    assert "- Ligand codes: TYL (inchikey)" in text


def test_offline_run_on_an_empty_store_writes_an_empty_report(tmp_path: Path) -> None:
    exit_code = run(Settings(data_dir=tmp_path, offline=True))

    assert exit_code == 0
    report = (tmp_path / "build" / "complex_candidates.md").read_text(encoding="utf-8")
    assert "- 0 compounds stored" in report


def dump(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [
        *conn.execute("SELECT rowid, * FROM target ORDER BY rowid"),
        *conn.execute("SELECT rowid, * FROM ligand_code ORDER BY rowid"),
        *conn.execute("SELECT rowid, * FROM complex_candidate ORDER BY rowid"),
    ]
