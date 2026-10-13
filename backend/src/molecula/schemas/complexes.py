from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

type Coordinates = tuple[float, float, float]
type SecondaryStructure = Literal["helix", "sheet", "coil"]
type BondOrder = Literal["single", "double", "triple", "aromatic"]
type ContactKind = Literal["hbond", "contact"]

RCSB_ENTRY_URL = "https://www.rcsb.org/structure/{pdb_id}"


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
    """One residue of the backbone trace: an amino acid at its CA atom with its secondary
    structure, or a nucleotide at its P atom, whose `sse` is None."""

    sse: SecondaryStructure | None
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
    heavy atoms only.

    `target` (the gene symbol, with a note where one is needed, such as "ABL1 (BCR-ABL)") and
    `organism` say what the drug is bound to, from the reviewed entry in `data/hero_set.yaml`.
    `caption` is shown with the structure when it isn't simply the drug in its main target;
    `showcase` marks the cleanest complexes, for the landing page and demos.
    """

    model_config = ConfigDict(frozen=True)

    pdb_id: str
    ligand: Ligand
    trace: list[TraceResidue]
    pocket: list[PocketResidue]
    contacts: list[Contact]
    target: str | None = None
    organism: str | None = None
    caption: str | None = None
    showcase: bool = False

    @computed_field
    @property
    def source_url(self) -> str:
        return RCSB_ENTRY_URL.format(pdb_id=self.pdb_id)
