from typing import Literal

from pydantic import BaseModel, ConfigDict

type Coordinates = tuple[float, float, float]
type SecondaryStructure = Literal["helix", "sheet", "coil"]
type BondOrder = Literal["single", "double", "triple", "aromatic"]
type ContactKind = Literal["hbond", "contact"]


class Residue(BaseModel):
    """A polymer residue, named as the depositor numbered it (author chain and residue number)."""

    model_config = ConfigDict(frozen=True)

    chain: str
    number: int
    ins_code: str = ""
    name: str


class Atom(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    element: str
    xyz: Coordinates


class TraceResidue(Residue):
    """One residue of the backbone trace, at its CA atom."""

    sse: SecondaryStructure
    xyz: Coordinates


class PocketResidue(Residue):
    """A residue with a heavy atom within the contact distance of the ligand, with all its heavy
    atoms."""

    atoms: list[Atom]


class Bond(BaseModel):
    """A ligand bond between two indices into the ligand's atoms."""

    model_config = ConfigDict(frozen=True)

    atoms: tuple[int, int]
    order: BondOrder


class Ligand(BaseModel):
    """The ligand copy shown, as its chem-comp code and author chain and residue number."""

    model_config = ConfigDict(frozen=True)

    code: str
    chain: str
    number: int
    atoms: list[Atom]
    bonds: list[Bond]


class Contact(BaseModel):
    """An atom pair between a pocket residue and the ligand.

    `hbond`: a nitrogen or oxygen pair close enough for a hydrogen bond. `contact`: the closest
    heavy-atom pair of a pocket residue, one per residue.
    """

    model_config = ConfigDict(frozen=True)

    kind: ContactKind
    residue: Residue
    residue_atom: str
    ligand_atom: int
    distance: float


class Complex(BaseModel):
    """One drug-target complex, ready for the 3D viewer: coordinates in Å from the PDB entry,
    heavy atoms only."""

    model_config = ConfigDict(frozen=True)

    pdb_id: str
    ligand: Ligand
    trace: list[TraceResidue]
    pocket: list[PocketResidue]
    contacts: list[Contact]
