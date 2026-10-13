"""Complex processing on the recorded 1IEP mmCIF: imatinib (STI) in mouse ABL1, two copies.

The hero set shows imatinib in 2HYY; 1IEP is the entry the contacts were verified on
(`docs/data-plan.md` §5.4), with its copies at A/201 and B/202.
"""

from collections import Counter

import pytest
from rdkit import Chem

from molecula.ingest.complexes import ComplexError, build_complex
from molecula.schemas.complexes import Complex, Ligand
from rcsb_replay import FIXTURES

MMCIF = (FIXTURES / "1IEP.cif").read_text(encoding="utf-8")
IMATINIB = "Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C"
RDKIT_ORDERS = {
    "single": Chem.BondType.SINGLE,
    "double": Chem.BondType.DOUBLE,
    "triple": Chem.BondType.TRIPLE,
    "aromatic": Chem.BondType.AROMATIC,
}


@pytest.fixture(scope="module")
def chain_a() -> Complex:
    return build_complex(MMCIF, "STI", "A/201", IMATINIB)


@pytest.fixture(scope="module")
def chain_b() -> Complex:
    return build_complex(MMCIF, "STI", "B/202", IMATINIB)


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
    template = Chem.MolFromSmiles(IMATINIB)

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
        build_complex(MMCIF, "STI", "C/201", IMATINIB)


def test_ligand_code_must_match_the_copy() -> None:
    with pytest.raises(ComplexError, match="no IBP at A/201"):
        build_complex(MMCIF, "IBP", "A/201", IMATINIB)


def test_smiles_of_another_molecule_is_an_error() -> None:
    with pytest.raises(ComplexError, match="don't match the SMILES"):
        build_complex(MMCIF, "STI", "A/201", "CC(C)Cc1ccc(cc1)C(C)C(=O)O")


def test_unparsable_smiles_is_an_error() -> None:
    with pytest.raises(ComplexError, match="can't parse"):
        build_complex(MMCIF, "STI", "A/201", "not a smiles")
