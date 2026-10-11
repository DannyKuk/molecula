"""Response examples for the OpenAPI docs, built from the response models so they can't drift."""

from molecula.schemas.compounds import Compound, Resolution, SupportedDrug
from molecula.schemas.targets import DrugTargets, Target

IMATINIB = Compound(
    cid=5291,
    name="imatinib",
    inchikey="KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    smiles="CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
    formula="C29H31N7O",
    molecular_weight=493.6,
    xlogp=3.5,
    tpsa=86.3,
    hbond_donors=2,
    hbond_acceptors=7,
    rotatable_bonds=7,
    heavy_atoms=37,
    has_3d=True,
    conformer_source="pubchem",
    source="pubchem",
    source_url="https://pubchem.ncbi.nlm.nih.gov/compound/5291",
)

SUPPORTED_DRUGS = [
    SupportedDrug(cid=5291, name="imatinib", aliases=["Gleevec", "Glivec"], has_3d=True),
    SupportedDrug(
        cid=56843331, name="semaglutide", aliases=["Ozempic", "Wegovy", "Rybelsus"], has_3d=False
    ),
]

FOUND = Resolution(
    query="Gleevec",
    status="found",
    compound=IMATINIB,
    matched_alias="Gleevec",
    match_kind="alias",
)
NOT_SUPPORTED = Resolution(query="Vicodin", status="not_supported")

IMATINIB_TARGETS = DrugTargets(
    cid=5291,
    targets=[
        Target(
            target_chembl_id="CHEMBL1862",
            name="Tyrosine-protein kinase ABL1",
            target_type="SINGLE PROTEIN",
            organism="Homo sapiens",
            mechanism="Tyrosine-protein kinase ABL inhibitor",
            action_type="INHIBITOR",
            accessions=["P00519"],
            gene_symbols=["ABL1"],
            source="chembl",
            source_url="https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1862",
        ),
        Target(
            target_chembl_id="CHEMBL2096618",
            name="Bcr/Abl fusion protein",
            target_type="CHIMERIC PROTEIN",
            organism="Homo sapiens",
            mechanism="Bcr/Abl fusion protein inhibitor",
            action_type="INHIBITOR",
            accessions=["P00519", "P11274"],
            gene_symbols=["ABL1", "BCR"],
            source="chembl",
            source_url="https://www.ebi.ac.uk/chembl/explore/target/CHEMBL2096618",
        ),
    ],
)

SDF = """5291
  -OEChem-10112613423D

 68 72  0     0  0  0  0  0  0999 V2000
   -0.8276    0.2486   -1.0418 O   0  0  0  0  0  0  0  0  0  0  0  0
...
M  END
$$$$
"""
