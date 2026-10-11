import logging

from rdkit import Chem
from rdkit.Chem import AllChem

logger = logging.getLogger(__name__)

# A fixed seed makes ETKDG reproducible, so re-running the ingest writes the same file.
EMBED_SEED = 0xF00D


def embed_conformer(cid: int, smiles: str) -> str | None:
    """A 3D conformer as SDF from ETKDG plus MMFF, or None when RDKit can't embed the molecule."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        logger.warning("CID %d: RDKit can't parse the SMILES", cid)
        return None
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = EMBED_SEED
    if AllChem.EmbedMolecule(mol, params) != 0:
        logger.warning("CID %d: RDKit found no 3D embedding", cid)
        return None
    # Without MMFF parameters (some metals) the ETKDG geometry is kept as it is.
    if AllChem.MMFFHasAllMoleculeParams(mol):
        AllChem.MMFFOptimizeMolecule(mol, maxIters=2000)
    mol.SetProp("_Name", str(cid))
    return Chem.MolToMolBlock(mol) + "$$$$\n"
