import io

import biotite.structure as struc
import biotite.structure.io.pdbx as pdbx
import numpy as np
from biotite.structure import AtomArray
from rdkit import Chem
from rdkit.Chem import AllChem

from molecula.schemas.complexes import (
    Atom,
    Bond,
    BondOrder,
    Complex,
    Contact,
    ContactKind,
    Coordinates,
    Ligand,
    PocketResidue,
    Residue,
    SecondaryStructure,
    TraceResidue,
)

CONTACT_DISTANCE = 4.0
HBOND_DISTANCE = 3.3
HBOND_ELEMENTS = ["N", "O"]
HYDROGENS = ["H", "D"]
# mmCIF coordinates have three decimals, so rounding to three loses nothing.
COORDINATE_DECIMALS = 3
DISTANCE_DECIMALS = 2
# P-SEA labels from biotite's annotate_sse.
SECONDARY_STRUCTURE: dict[str, SecondaryStructure] = {"a": "helix", "b": "sheet", "c": "coil"}
BOND_ORDERS: dict[Chem.BondType, BondOrder] = {
    Chem.BondType.SINGLE: "single",
    Chem.BondType.DOUBLE: "double",
    Chem.BondType.TRIPLE: "triple",
    Chem.BondType.AROMATIC: "aromatic",
}


class ComplexError(Exception):
    """The structure can't be turned into a complex: the ligand copy is missing or its atoms don't
    match the SMILES."""


def build_complex(mmcif: str, ligand_code: str, ligand_copy: str, smiles: str) -> Complex:
    """The complex around one ligand copy, given as author chain and residue number (`A/201`).

    Only the protein and that ligand copy are kept, so waters, ions, buffer molecules and any other
    ligand are dropped. The pocket is every residue with a heavy atom within 4.0 Å of the ligand,
    in any chain; the trace covers the chains the pocket is in. Contacts are each pocket residue's
    closest atom pair, plus every N/O pair within 3.3 Å as a hydrogen bond.
    """
    cif = pdbx.CIFFile.read(io.StringIO(mmcif))
    structure = pdbx.get_structure(cif, model=1, use_author_fields=True)
    structure = structure[~np.isin(structure.element, HYDROGENS)]
    is_ligand = ligand_mask(structure, ligand_code, ligand_copy)
    if not is_ligand.any():
        raise ComplexError(f"no {ligand_code} at {ligand_copy}")
    ligand = structure[is_ligand]
    protein = structure[struc.filter_amino_acids(structure) & ~is_ligand]
    pocket = pocket_residues(protein, ligand)
    chains = list(dict.fromkeys(str(residue.chain_id[0]) for residue in pocket))
    return Complex(
        pdb_id=cif.block["entry"]["id"].as_item(),
        ligand=Ligand(
            code=ligand_code,
            chain=str(ligand.chain_id[0]),
            number=int(ligand.res_id[0]),
            atoms=[atom(ligand, i) for i in range(len(ligand))],
            bonds=ligand_bonds(ligand, smiles),
        ),
        trace=[
            residue for chain in chains for residue in trace(protein[protein.chain_id == chain])
        ],
        pocket=[
            PocketResidue(
                **residue_of(atoms).model_dump(),
                atoms=[atom(atoms, i) for i in range(len(atoms))],
            )
            for atoms in pocket
        ],
        contacts=sorted(
            (contact for residue in pocket for contact in contacts(residue, ligand)),
            key=lambda contact: (contact.kind != "hbond", contact.distance),
        ),
    )


def ligand_mask(structure: AtomArray, code: str, copy: str) -> np.ndarray:
    chain, _, number = copy.rpartition("/")
    return (
        (structure.res_name == code)
        & (structure.chain_id == chain)
        & (structure.res_id == int(number))
    )


def ligand_bonds(ligand: AtomArray, smiles: str) -> list[Bond]:
    """The ligand's bonds with the orders of the SMILES, since PDB entries give neither bond orders
    nor hydrogens. Which atoms are bonded comes from biotite's copy of the chem-comp dictionary,
    by atom name."""
    mol = Chem.RWMol()
    for element in ligand.element:
        mol.AddAtom(Chem.Atom(element.capitalize()))
    for first, second, _ in struc.connect_via_residue_names(ligand).as_array():
        mol.AddBond(int(first), int(second), Chem.BondType.SINGLE)
    template = Chem.MolFromSmiles(smiles)
    if template is None:
        raise ComplexError(f"RDKit can't parse the SMILES {smiles}")
    try:
        typed = AllChem.AssignBondOrdersFromTemplate(template, mol.GetMol())
    except ValueError as error:
        raise ComplexError(f"{ligand.res_name[0]} atoms don't match the SMILES {smiles}") from error
    return [
        Bond(
            atoms=(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()),
            order=BOND_ORDERS[bond.GetBondType()],
        )
        for bond in typed.GetBonds()
    ]


def pocket_residues(protein: AtomArray, ligand: AtomArray) -> list[AtomArray]:
    near = distances(protein, ligand).min(axis=1) <= CONTACT_DISTANCE
    positions = np.unique(struc.get_residue_positions(protein, np.flatnonzero(near)))
    starts = struc.get_residue_starts(protein, add_exclusive_stop=True)
    return [protein[starts[position] : starts[position + 1]] for position in positions]


def contacts(residue: AtomArray, ligand: AtomArray) -> list[Contact]:
    pair_distances = distances(residue, ligand)
    closest = np.unravel_index(pair_distances.argmin(), pair_distances.shape)
    polar = np.isin(residue.element, HBOND_ELEMENTS)[:, None] & np.isin(
        ligand.element, HBOND_ELEMENTS
    )
    hbonds = zip(*np.nonzero(polar & (pair_distances <= HBOND_DISTANCE)), strict=True)
    return [contact("hbond", residue, ligand, pair_distances, pair) for pair in hbonds] + [
        contact("contact", residue, ligand, pair_distances, closest)
    ]


def contact(
    kind: ContactKind,
    residue: AtomArray,
    ligand: AtomArray,
    pair_distances: np.ndarray,
    pair: tuple[np.intp, np.intp],
) -> Contact:
    residue_atom, ligand_atom = pair
    return Contact(
        kind=kind,
        residue=residue_of(residue),
        residue_atom=str(residue.atom_name[residue_atom]),
        ligand_atom=int(ligand_atom),
        distance=round(float(pair_distances[residue_atom, ligand_atom]), DISTANCE_DECIMALS),
    )


def trace(chain: AtomArray) -> list[TraceResidue]:
    """The chain's CA atoms with P-SEA secondary structure, which needs only the CA atoms, so it
    works on any entry, also those without the depositor's helix and sheet records."""
    return [
        TraceResidue(
            **residue_of(residue).model_dump(),
            sse=SECONDARY_STRUCTURE.get(str(label), "coil"),
            xyz=xyz(residue[residue.atom_name == "CA"].coord[0]),
        )
        for residue, label in zip(struc.residue_iter(chain), struc.annotate_sse(chain), strict=True)
        if "CA" in residue.atom_name
    ]


def distances(first: AtomArray, second: AtomArray) -> np.ndarray:
    """Distances between every atom of `first` (rows) and `second` (columns)."""
    return np.linalg.norm(first.coord[:, None, :] - second.coord[None, :, :], axis=-1)


def residue_of(atoms: AtomArray) -> Residue:
    return Residue(
        chain=str(atoms.chain_id[0]),
        number=int(atoms.res_id[0]),
        ins_code=str(atoms.ins_code[0]),
        name=str(atoms.res_name[0]),
    )


def atom(atoms: AtomArray, index: int) -> Atom:
    return Atom(
        name=str(atoms.atom_name[index]),
        element=str(atoms.element[index]).capitalize(),
        xyz=xyz(atoms.coord[index]),
    )


def xyz(coord: np.ndarray) -> Coordinates:
    x, y, z = (round(float(value), COORDINATE_DECIMALS) for value in coord)
    return x, y, z
