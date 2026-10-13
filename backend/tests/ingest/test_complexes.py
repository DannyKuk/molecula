"""Complex processing and the complexes ingest step.

The contacts are checked on the recorded 1IEP mmCIF: imatinib (STI) in mouse ABL1, two copies. The
hero set shows imatinib in 2HYY; 1IEP is the entry the contacts were verified on
(`docs/data-plan.md` §5.4), with its copies at A/201 and B/202. The special cases from the hero
review (#7) run on cropped hero entries (`rcsb_replay.CROPPED`).
"""

import io
import sqlite3
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import biotite.structure.io.pdbx as pdbx
import httpx2
import pytest
from rdkit import Chem

from molecula.ingest.complexes import ComplexError, ComplexesReport, build_complex, ingest_complexes
from molecula.ingest.hero_set import HeroComplex
from molecula.schemas.complexes import Complex, Ligand
from molecula.sources.http import SourceClient
from molecula.sources.rcsb import RcsbClient
from molecula.store.compounds import CompoundStore
from molecula.store.structures import ComplexFiles
from rcsb_replay import CROPPED, Replay, recorded_smiles, recorded_structure
from store_records import IMATINIB, compound_record

MMCIF = recorded_structure("1IEP")
IMATINIB_SMILES = "Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C"
RDKIT_ORDERS = {
    "single": Chem.BondType.SINGLE,
    "double": Chem.BondType.DOUBLE,
    "triple": Chem.BondType.TRIPLE,
    "aromatic": Chem.BondType.AROMATIC,
}


@pytest.fixture(scope="module")
def chain_a() -> Complex:
    return build_complex(MMCIF, "STI", "A/201", IMATINIB_SMILES)


@pytest.fixture(scope="module")
def chain_b() -> Complex:
    return build_complex(MMCIF, "STI", "B/202", IMATINIB_SMILES)


def hbonds(complex_: Complex) -> list[tuple[str, int, str, str, float]]:
    ligand_atoms = complex_.ligand.atoms
    return [
        (
            contact.residue.name,
            contact.residue.number,
            contact.residue_atom,
            ligand_atoms[contact.ligand_atom].name,
            contact.distance,
        )
        for contact in complex_.contacts
        if contact.kind == "hbond"
    ]


def as_mol(ligand: Ligand) -> Chem.Mol:
    mol = Chem.RWMol()
    for atom in ligand.atoms:
        mol.AddAtom(Chem.Atom(atom.element))
    for bond in ligand.bonds:
        mol.AddBond(*bond.atoms, RDKIT_ORDERS[bond.order])
    for bond in mol.GetBonds():
        bond.SetIsAromatic(bond.GetBondType() == Chem.BondType.AROMATIC)
    for atom in mol.GetAtoms():
        atom.SetIsAromatic(any(bond.GetIsAromatic() for bond in atom.GetBonds()))
    Chem.SanitizeMol(mol)
    return mol


def test_chain_a_gives_the_six_published_hydrogen_bonds(chain_a) -> None:
    assert hbonds(chain_a) == [
        ("ILE", 360, "O", "N51", 2.67),
        ("THR", 315, "OG1", "N13", 2.88),
        ("MET", 318, "N", "N3", 2.90),
        ("ASP", 381, "N", "O29", 2.90),
        ("GLU", 286, "OE2", "N21", 3.00),
        ("HIS", 361, "O", "N51", 3.19),
    ]


def test_chain_b_gives_five_of_them_without_his361(chain_b) -> None:
    assert hbonds(chain_b) == [
        ("ILE", 360, "O", "N51", 2.74),
        ("ASP", 381, "N", "O29", 2.89),
        ("THR", 315, "OG1", "N13", 2.93),
        ("MET", 318, "N", "N3", 2.94),
        ("GLU", 286, "OE2", "N21", 3.03),
    ]


def test_every_pocket_residue_has_one_closest_contact_within_4_angstrom(chain_a) -> None:
    closest = [contact for contact in chain_a.contacts if contact.kind == "contact"]
    pocket = [(residue.chain, residue.number, residue.name) for residue in chain_a.pocket]

    assert sorted((c.residue.chain, c.residue.number, c.residue.name) for c in closest) == pocket
    assert all(contact.distance <= 4.0 for contact in closest)
    assert {("A", 315, "THR"), ("A", 360, "ILE"), ("A", 381, "ASP")} <= set(pocket)


def test_pocket_and_trace_stay_in_the_ligand_copy_chain(chain_a, chain_b) -> None:
    # The two ABL1 molecules of 1IEP don't touch each other's imatinib.
    assert {residue.chain for residue in chain_a.pocket + chain_a.trace} == {"A"}
    assert {residue.chain for residue in chain_b.pocket + chain_b.trace} == {"B"}


def test_waters_and_chloride_ions_are_dropped(chain_a) -> None:
    names = {residue.name for residue in chain_a.pocket + chain_a.trace}
    elements = {atom.element for residue in chain_a.pocket for atom in residue.atoms}

    assert not names & {"HOH", "CL", "STI"}
    assert elements <= {"C", "N", "O", "S"}


def test_pocket_residues_keep_all_their_heavy_atoms(chain_a) -> None:
    [thr315] = [residue for residue in chain_a.pocket if residue.number == 315]

    assert [atom.name for atom in thr315.atoms] == ["N", "CA", "C", "O", "CB", "OG1", "CG2"]


def test_ligand_is_the_requested_copy_with_its_heavy_atoms(chain_a) -> None:
    ligand = chain_a.ligand

    assert (chain_a.pdb_id, ligand.code, ligand.chain, ligand.number) == ("1IEP", "STI", "A", 201)
    assert len(ligand.atoms) == 37
    [n51] = [atom for atom in ligand.atoms if atom.name == "N51"]
    assert (n51.element, n51.xyz) == ("N", (18.337, 46.794, 22.821))


def test_imatinib_bond_orders_match_its_smiles(chain_a) -> None:
    ligand = chain_a.ligand
    template = Chem.MolFromSmiles(IMATINIB_SMILES)

    assert Counter(bond.order for bond in ligand.bonds) == {
        "aromatic": 24,
        "single": 16,
        "double": 1,
    }
    assert Counter(bond.order for bond in ligand.bonds) == Counter(
        str(bond.GetBondType()).lower() for bond in template.GetBonds()
    )
    [double] = [bond for bond in ligand.bonds if bond.order == "double"]
    assert {ligand.atoms[i].name for i in double.atoms} == {"C22", "O29"}
    assert Chem.MolToSmiles(as_mol(ligand)) == Chem.MolToSmiles(template)


def test_trace_has_every_residue_of_the_chain_with_secondary_structure(chain_a) -> None:
    trace = chain_a.trace

    assert len(trace) == 274
    assert (trace[0].number, trace[-1].number) == (225, 498)
    assert {residue.sse for residue in trace} == {"helix", "sheet", "coil"}


def test_json_round_trips_through_the_schema(chain_a) -> None:
    assert Complex.model_validate_json(chain_a.model_dump_json()) == chain_a


def test_unknown_ligand_copy_is_an_error() -> None:
    with pytest.raises(ComplexError, match="no STI at C/201"):
        build_complex(MMCIF, "STI", "C/201", IMATINIB_SMILES)


def test_ligand_code_must_match_the_copy() -> None:
    with pytest.raises(ComplexError, match="no IBP at A/201"):
        build_complex(MMCIF, "IBP", "A/201", IMATINIB_SMILES)


def test_smiles_of_another_molecule_is_an_error() -> None:
    with pytest.raises(ComplexError, match="don't match the SMILES"):
        build_complex(MMCIF, "STI", "A/201", "CC(C)Cc1ccc(cc1)C(C)C(=O)O")


def test_unparsable_smiles_is_an_error() -> None:
    with pytest.raises(ComplexError, match="can't parse"):
        build_complex(MMCIF, "STI", "A/201", "not a smiles")


def build_hero(pdb_id: str, ligand_copy: str, **options: Any) -> Complex:
    code = CROPPED[pdb_id]
    return build_complex(
        recorded_structure(pdb_id), code, ligand_copy, recorded_smiles(code), **options
    )


@pytest.fixture(scope="module")
def azithromycin() -> Complex:
    return build_hero("8E42", "I/3002")


def pocket_names(complex_: Complex) -> list[str]:
    return [f"{residue.chain}/{residue.name}{residue.number}" for residue in complex_.pocket]


def test_azithromycin_pocket_is_the_23s_rrna_of_the_exit_tunnel(azithromycin) -> None:
    assert pocket_names(azithromycin) == [
        "I/PSU746",
        "I/5MU747",
        "I/A2058",
        "I/A2059",
        "I/A2062",
        "I/2MA2503",
        "I/G2505",
        "I/C2610",
        "I/C2611",
        "P/LYS90",
    ]
    assert hbonds(azithromycin) == [("A", 2058, "N1", "O2A", 3.11)]


def test_nucleotides_are_traced_at_their_p_atom_without_secondary_structure(azithromycin) -> None:
    rna = [residue for residue in azithromycin.trace if residue.chain == "I"]
    protein = [residue for residue in azithromycin.trace if residue.chain == "P"]
    [a2058] = [residue for residue in azithromycin.pocket if residue.number == 2058]
    [phosphorus] = [atom for atom in a2058.atoms if atom.name == "P"]

    assert rna and all(residue.sse is None for residue in rna)
    assert protein and all(residue.sse is not None for residue in protein)
    assert next(residue.xyz for residue in rna if residue.number == 2058) == phosphorus.xyz


def test_trace_leaves_out_chains_outside_the_pocket(azithromycin) -> None:
    cif = pdbx.CIFFile.read(io.StringIO(recorded_structure("8E42")))
    recorded_chains = set(pdbx.get_structure(cif, model=1, use_author_fields=True).chain_id)

    # The cropped entry also holds ribosomal proteins of chains M and N, near but not touching.
    assert {"I", "M", "N", "P"} <= recorded_chains
    assert {residue.chain for residue in azithromycin.trace} == {"I", "P"}


def test_only_the_hero_ligand_is_kept_when_the_entry_holds_another_drug(azithromycin) -> None:
    # Tiamulin (MUL) is bound next to azithromycin in 8E42.
    names = {residue.name for residue in azithromycin.pocket + azithromycin.trace}

    assert azithromycin.ligand.code == "ZIT"
    assert "MUL" not in names


def test_aspirin_keeps_the_acetylated_ser530_and_drops_diclofenac() -> None:
    aspirin = build_hero("3N8Y", "B/900")

    assert "B/OAS530" in pocket_names(aspirin)
    assert ("OAS", 530, "OAC", "O1'", 2.89) in hbonds(aspirin)
    assert "DIF" not in {residue.name for residue in aspirin.pocket + aspirin.trace}


def test_dolutegravir_pocket_spans_the_integrase_and_the_viral_dna() -> None:
    dolutegravir = build_hero("9C9M", "O/101")

    assert {residue.chain for residue in dolutegravir.pocket} == {"I", "N", "O"}
    assert {"N/DG18", "O/DC20", "O/DA21"} <= set(pocket_names(dolutegravir))
    dna = [residue for residue in dolutegravir.trace if residue.chain in {"N", "O"}]
    assert dna and all(residue.sse is None for residue in dna)


def test_atorvastatin_pocket_spans_both_chains_of_the_hmgcr_dimer() -> None:
    atorvastatin = build_hero("1HWK", "A/2")

    assert {residue.chain for residue in atorvastatin.pocket} == {"A", "B"}
    assert {residue.chain for residue in atorvastatin.trace} == {"A", "B"}


def test_excluded_chain_leaves_losartans_pocket_and_trace() -> None:
    with_nanobody = build_hero("9EAI", "A/1401")
    losartan = build_hero("9EAI", "A/1401", exclude_chains=["B"])

    assert {"B/ILE104", "B/TYR106"} <= set(pocket_names(with_nanobody))
    assert {residue.chain for residue in losartan.pocket + losartan.trace} == {"A"}
    assert losartan.pocket == [r for r in with_nanobody.pocket if r.chain == "A"]


def test_smiles_with_explicit_hydrogens_still_gives_the_bond_orders() -> None:
    # The chem-comp spells out a hydrogen on zanamivir's guanidine to fix the C=N geometry.
    assert recorded_smiles("ZMR").startswith("[H]/N=C")

    zanamivir = build_hero("3B7E", "B/1002")

    assert len(zanamivir.ligand.atoms) == 23
    assert Counter(bond.order for bond in zanamivir.ligand.bonds) == {"single": 19, "double": 4}


ZANAMIVIR = compound_record(60855, "zanamivir")
IMATINIB_HERO = HeroComplex(
    drug="imatinib",
    pdb="1IEP",
    ligand_code="STI",
    ligand_copy="A/201",
    chain="A",
    target="ABL1",
    organism="Mus musculus",
    showcase=True,
    note="the verified contacts",
)
ZANAMIVIR_HERO = HeroComplex(
    drug="Zanamivir",
    pdb="3B7E",
    ligand_code="ZMR",
    ligand_copy="B/1002",
    chain="B",
    target="NA",
    organism="Influenza A virus",
    caption="Neuraminidase of a 1918 strain.",
    note="explicit hydrogen in the SMILES",
)


@pytest.fixture
def files(tmp_path: Path) -> ComplexFiles:
    return ComplexFiles(tmp_path / "structures" / "complexes")


@pytest.fixture
def ingest(
    conn: sqlite3.Connection, replaying_client: Callable[..., SourceClient], files: ComplexFiles
) -> Callable[..., ComplexesReport]:
    compounds = CompoundStore(conn)
    for record in (IMATINIB, ZANAMIVIR):
        compounds.save(record, [], datetime(2026, 10, 13, tzinfo=UTC))

    def run(heroes: list[HeroComplex], handler: Replay | None = None) -> ComplexesReport:
        rcsb = RcsbClient(replaying_client(handler or Replay()))
        return ingest_complexes(heroes, rcsb, compounds, files)

    return run


def test_each_hero_is_stored_as_json_named_by_its_cid(ingest, files: ComplexFiles) -> None:
    report = ingest([IMATINIB_HERO, ZANAMIVIR_HERO])

    assert report.complete
    assert [(stored.hero.drug, stored.cid) for stored in report.stored] == [
        ("imatinib", 5291),
        ("Zanamivir", 60855),
    ]
    imatinib = Complex.model_validate_json(files.read(5291) or "")
    zanamivir = Complex.model_validate_json(files.read(60855) or "")
    assert imatinib == build_complex(MMCIF, "STI", "A/201", IMATINIB_SMILES).model_copy(
        update={"target": "ABL1", "organism": "Mus musculus", "showcase": True}
    )
    assert (
        zanamivir.pdb_id,
        zanamivir.target,
        zanamivir.organism,
        zanamivir.caption,
        zanamivir.showcase,
    ) == ("3B7E", "NA", "Influenza A virus", "Neuraminidase of a 1918 strain.", False)


def test_hero_whose_drug_isnt_stored_is_reported_and_the_rest_built(ingest, files) -> None:
    caffeine = IMATINIB_HERO.model_copy(update={"drug": "caffeine"})

    report = ingest([caffeine, ZANAMIVIR_HERO])

    assert report.failures == {
        "caffeine": "caffeine isn't in the store; run the compounds step first"
    }
    assert files.read(60855) is not None


def test_missing_ligand_copy_is_reported(ingest, files: ComplexFiles) -> None:
    wrong_copy = IMATINIB_HERO.model_copy(update={"ligand_copy": "C/201"})

    report = ingest([wrong_copy])

    assert report.failures == {"imatinib": "no STI at C/201"}
    assert files.read(5291) is None


def test_run_stops_when_rcsb_stops_answering(ingest, files: ComplexFiles) -> None:
    def throttled(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429)

    report = ingest([IMATINIB_HERO, ZANAMIVIR_HERO], throttled)

    assert list(report.failures) == ["imatinib"]
    assert report.not_attempted == ["Zanamivir"]
    assert files.read(5291) is None


def test_complete_run_removes_complexes_that_left_the_hero_set(ingest, files) -> None:
    files.write(2244, "{}")

    report = ingest([ZANAMIVIR_HERO])

    assert report.pruned == [2244]
    assert files.read(2244) is None


def test_incomplete_run_removes_nothing(ingest, files: ComplexFiles) -> None:
    files.write(2244, "{}")
    caffeine = IMATINIB_HERO.model_copy(update={"drug": "caffeine"})

    report = ingest([caffeine, ZANAMIVIR_HERO])

    assert report.pruned == []
    assert files.read(2244) == "{}"


def test_chem_comp_without_a_smiles_is_reported(ingest, files: ComplexFiles) -> None:
    without_descriptor = httpx2.Response(200, json={"chem_comp": {"id": "ZMR"}})

    report = ingest(
        [ZANAMIVIR_HERO], Replay({"GET /rest/v1/core/chemcomp/ZMR": without_descriptor})
    )

    assert report.failures == {"Zanamivir": "the chem-comp record of ZMR has no SMILES"}
    assert files.read(60855) is None
