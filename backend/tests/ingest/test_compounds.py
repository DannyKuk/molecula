import sqlite3
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from molecula.config import Settings
from molecula.ingest.compounds import SYNONYM_LIMIT, ingest_compounds, run
from molecula.ingest.scope import Scope
from molecula.sources.pubchem import PubChemClient
from molecula.store.compounds import CompoundStore, Synonym
from molecula.store.structures import ConformerFiles
from pubchem_replay import Replay


def scope(*drugs: dict[str, object]) -> Scope:
    return Scope.model_validate({"drugs": list(drugs)})


@pytest.fixture
def store(conn: sqlite3.Connection) -> CompoundStore:
    return CompoundStore(conn)


@pytest.fixture
def conformers(tmp_path: Path) -> ConformerFiles:
    return ConformerFiles(tmp_path / "structures" / "compounds")


@pytest.fixture
def ingest(
    pubchem: Callable[..., PubChemClient], store: CompoundStore, conformers: ConformerFiles
) -> Callable[..., object]:
    def run_ingest(drugs: Scope, handler: Replay | None = None):
        return ingest_compounds(drugs, pubchem(handler), store, conformers)

    return run_ingest


def test_stores_one_drug_end_to_end(ingest, store, conformers) -> None:
    report = ingest(scope({"name": "imatinib", "aliases": ["Gleevec", "Glivec"]}))

    assert report.failures == {}
    imatinib = store.get(5291)
    assert imatinib is not None
    assert imatinib.name == "imatinib"
    assert imatinib.inchikey == "KTUFNOKKBVMGRW-UHFFFAOYSA-N"
    assert (imatinib.has_3d, imatinib.conformer_source) == (True, "pubchem")
    sdf = conformers.read(5291)
    assert sdf is not None
    assert sdf.splitlines()[0] == "5291"
    synonyms = store.synonyms(5291)
    assert synonyms[:3] == [
        Synonym("imatinib", "name"),
        Synonym("Gleevec", "alias"),
        Synonym("Glivec", "alias"),
    ]
    assert all(synonym.kind == "pubchem" for synonym in synonyms[3:])
    assert len(synonyms) <= 3 + SYNONYM_LIMIT


@pytest.mark.parametrize(
    ("name", "cid", "expected"),
    [
        ("imatinib", 5291, ("C29H31N7O", 493.6, 3.5, 86.3, 2, 7, 7, 37)),
        ("caffeine", 2519, ("C8H10N4O2", 194.19, -0.1, 58.4, 0, 3, 0, 14)),
        ("ibuprofen", 3672, ("C13H18O2", 206.28, 3.5, 37.3, 1, 2, 4, 15)),
    ],
)
def test_stored_properties_match_the_spike_report(
    ingest, store, name: str, cid: int, expected: tuple[object, ...]
) -> None:
    ingest(scope({"name": name}))

    compound = store.get(cid)
    assert compound is not None
    stored = (compound.formula, compound.mw, compound.xlogp, compound.tpsa, compound.hbd,
              compound.hba, compound.rotb, compound.heavy_atoms)  # fmt: skip
    assert stored == expected


def test_small_molecule_without_pubchem_conformer_gets_one_from_rdkit(
    ingest, store, conformers
) -> None:
    ingest(scope({"name": "ritonavir"}))

    ritonavir = store.get(392622)
    assert ritonavir is not None
    assert (ritonavir.has_3d, ritonavir.conformer_source) == (True, "rdkit")
    sdf = conformers.read(392622)
    assert sdf is not None
    z_coordinates = {line.split()[2] for line in sdf.splitlines()[4:20]}
    assert z_coordinates != {"0.0000"}


def test_peptide_is_stored_without_3d(ingest, store, conformers) -> None:
    ingest(scope({"name": "semaglutide"}))

    semaglutide = store.get(56843331)
    assert semaglutide is not None
    assert semaglutide.has_3d is False
    assert semaglutide.conformer_source is None
    assert conformers.read(56843331) is None


def test_rerun_is_served_from_the_cache_and_changes_nothing(
    ingest, conn: sqlite3.Connection, conformers
) -> None:
    drugs = scope(
        {"name": "imatinib", "aliases": ["Gleevec"]}, {"name": "ritonavir"}, {"name": "semaglutide"}
    )
    ingest(drugs)
    rows_before = dump(conn)
    files_before = {path: path.stat().st_mtime_ns for path in conformers.path(0).parent.iterdir()}
    changes_before = conn.total_changes

    second_run = Replay()
    ingest(drugs, second_run)

    assert second_run.requests == []
    assert conn.total_changes == changes_before
    assert dump(conn) == rows_before
    assert {path: path.stat().st_mtime_ns for path in files_before} == files_before


def test_a_failing_drug_is_reported_and_the_rest_stored(ingest, store) -> None:
    report = ingest(scope({"name": "notadrugxyz"}, {"name": "caffeine"}))

    assert list(report.failures) == ["notadrugxyz"]
    assert [compound.name for compound in report.stored] == ["caffeine"]
    assert store.get(2519) is not None


def test_a_mixture_without_a_single_parent_is_a_failure(ingest, store) -> None:
    two_parents = httpx2.Response(200, json={"IdentifierList": {"CID": [2519, 3672]}})
    handler = Replay({"/compound/cid/2519/cids/JSON?cids_type=parent": two_parents})

    report = ingest(scope({"name": "caffeine"}), handler)

    assert "2 parent compounds" in report.failures["caffeine"]
    assert store.get(2519) is None


def test_run_stops_when_pubchem_stops_answering(pubchem, store, conformers) -> None:
    requests: list[httpx2.Request] = []

    def throttled(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(429)

    drugs = scope({"name": "caffeine"}, {"name": "ibuprofen"}, {"name": "imatinib"})
    report = ingest_compounds(drugs, pubchem(throttled), store, conformers)

    assert list(report.failures) == ["caffeine"]
    assert report.not_attempted == ["ibuprofen", "imatinib"]
    assert all("/name/caffeine/" in str(request.url) for request in requests)


def test_offline_run_on_an_empty_store_fails_without_requests(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "scope.yaml").write_text("drugs:\n  - name: caffeine\n", encoding="utf-8")

    exit_code = run(Settings(data_dir=tmp_path, offline=True))

    assert exit_code == 1
    assert "OFFLINE=1, not requesting" in caplog.text


def dump(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [
        *conn.execute("SELECT * FROM compound ORDER BY cid"),
        *conn.execute("SELECT rowid, * FROM synonym ORDER BY rowid"),
    ]
