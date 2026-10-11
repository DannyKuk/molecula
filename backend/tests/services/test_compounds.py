import ast
import inspect
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from molecula.services import compounds
from molecula.services.compounds import CompoundService, name_candidates
from molecula.store.compounds import CompoundRecord, CompoundStore, ConformerSource, Synonym
from molecula.store.structures import ConformerFiles

FETCHED_AT = datetime(2026, 10, 11, tzinfo=UTC)
SDF = "5291\n  stored conformer\n$$$$\n"


def record(cid: int, name: str, conformer_source: ConformerSource | None = "pubchem"):
    return CompoundRecord(
        cid=cid,
        name=name,
        inchikey=f"INCHIKEY-{cid}",
        smiles="C",
        formula="C",
        mw=100.0,
        xlogp=1.0,
        tpsa=10.0,
        hbd=1,
        hba=1,
        rotb=0,
        heavy_atoms=10,
        conformer_source=conformer_source,
        source="pubchem",
    )


@pytest.fixture
def store(conn: sqlite3.Connection) -> CompoundStore:
    store = CompoundStore(conn)
    store.save(
        record(5291, "imatinib"),
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias"), Synonym("Glamox", "pubchem")],
        FETCHED_AT,
    )
    store.save(
        record(3672, "ibuprofen"),
        [Synonym("ibuprofen", "name"), Synonym("Ibuflam", "alias"), Synonym("Advil", "alias")],
        FETCHED_AT,
    )
    store.save(record(4091, "metformin"), [Synonym("metformin", "name")], FETCHED_AT)
    store.save(record(60823, "atorvastatin"), [Synonym("atorvastatin", "name")], FETCHED_AT)
    store.save(
        record(56843331, "semaglutide", conformer_source=None),
        [Synonym("semaglutide", "name")],
        FETCHED_AT,
    )
    return store


@pytest.fixture
def conformers(tmp_path: Path) -> ConformerFiles:
    files = ConformerFiles(tmp_path / "structures" / "compounds")
    files.write(5291, SDF)
    return files


@pytest.fixture
def service(store: CompoundStore, conformers: ConformerFiles) -> CompoundService:
    return CompoundService(store, conformers)


@pytest.mark.parametrize("name", ["Ibuflam", "ibuflam", "IBUFLAM", "  Ibuflam "])
def test_alias_resolves_in_any_case(service: CompoundService, name: str) -> None:
    resolution = service.resolve(name)

    assert resolution.status == "found"
    assert resolution.compound is not None
    assert resolution.compound.name == "ibuprofen"
    assert (resolution.matched_alias, resolution.match_kind) == ("Ibuflam", "alias")
    assert resolution.query == name.strip()


def test_pubchem_synonym_resolves(service: CompoundService) -> None:
    resolution = service.resolve("glamox")

    assert resolution.compound is not None
    assert resolution.compound.cid == 5291
    assert resolution.match_kind == "pubchem"


@pytest.mark.parametrize(
    ("name", "cid"),
    [
        ("imatinib mesylate", 5291),
        ("Metformin HCl", 4091),
        ("metformin  hydrochloride", 4091),
        ("atorvastatin calcium trihydrate", 60823),
    ],
)
def test_salt_name_resolves_to_the_stored_parent(
    service: CompoundService, name: str, cid: int
) -> None:
    resolution = service.resolve(name)

    assert resolution.status == "found"
    assert resolution.compound is not None
    assert resolution.compound.cid == cid
    assert resolution.match_kind == "name"


@pytest.mark.parametrize("name", ["Vicodin", "notadrugxyz", "sodium chloride", "", "   "])
def test_name_outside_the_store_is_not_supported(service: CompoundService, name: str) -> None:
    resolution = service.resolve(name)

    assert resolution.status == "not_supported"
    assert resolution.compound is None
    assert resolution.matched_alias is None


def test_scope_name_wins_over_a_pubchem_synonym_of_another_compound(
    store: CompoundStore, service: CompoundService
) -> None:
    # Saved first, so the shared alias's oldest row belongs to the wrong compound.
    store.save(
        record(2519, "caffeine"),
        [Synonym("caffeine", "name"), Synonym("theophylline", "pubchem")],
        FETCHED_AT,
    )
    store.save(record(2153, "theophylline"), [Synonym("theophylline", "name")], FETCHED_AT)

    resolution = service.resolve("Theophylline")

    assert resolution.compound is not None
    assert resolution.compound.cid == 2153
    assert resolution.match_kind == "name"


def test_service_has_no_source_client() -> None:
    imports = {
        node.module
        for node in ast.walk(ast.parse(inspect.getsource(compounds)))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not any(module.startswith("molecula.sources") for module in imports)


def test_get_compound_carries_the_pubchem_source(service: CompoundService) -> None:
    compound = service.get_compound(5291)

    assert compound is not None
    assert compound.name == "imatinib"
    assert compound.source == "pubchem"
    assert compound.source_url == "https://pubchem.ncbi.nlm.nih.gov/compound/5291"


def test_get_compound_of_an_unknown_cid_is_none(service: CompoundService) -> None:
    assert service.get_compound(1) is None


def test_get_structure_returns_the_stored_conformer(service: CompoundService) -> None:
    structure = service.get_structure(5291)

    assert structure is not None
    assert (structure.sdf, structure.conformer_source) == (SDF, "pubchem")


@pytest.mark.parametrize(
    "cid",
    [
        56843331,  # semaglutide: a peptide without 3D
        3672,  # ibuprofen: stored with 3D, but its file is missing
        1,  # not stored
    ],
)
def test_get_structure_without_a_conformer_is_none(service: CompoundService, cid: int) -> None:
    assert service.get_structure(cid) is None


def test_list_compounds_returns_every_stored_compound_by_name(service: CompoundService) -> None:
    names = [compound.name for compound in service.list_compounds()]

    assert names == ["atorvastatin", "ibuprofen", "imatinib", "metformin", "semaglutide"]


@pytest.mark.parametrize(
    ("query", "candidates"),
    [
        ("imatinib", ["imatinib"]),
        ("imatinib mesylate", ["imatinib mesylate", "imatinib"]),
        ("Doxycycline Hyclate", ["Doxycycline Hyclate", "Doxycycline"]),
        ("sodium chloride", ["sodium chloride"]),
        ("medroxyprogesterone acetate", ["medroxyprogesterone acetate"]),
        ("", []),
    ],
)
def test_name_candidates(query: str, candidates: list[str]) -> None:
    assert name_candidates(query) == candidates
