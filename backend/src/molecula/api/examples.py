"""Response examples for the OpenAPI docs, built from the response models so they can't drift."""

from datetime import date

from molecula.schemas.complexes import (
    Atom,
    Bond,
    Complex,
    Contact,
    Ligand,
    PocketResidue,
    Residue,
    TraceResidue,
)
from molecula.schemas.compounds import Compound, Resolution, Suggestion, SupportedDrug
from molecula.schemas.labels import DrugLabels, Label, LabelSection
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
NOT_SUPPORTED = Resolution(
    query="Gleevek",
    status="not_supported",
    suggestions=[Suggestion(alias="Gleevec", cid=5291, name="imatinib")],
)

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

IMATINIB_LABELS = DrugLabels(
    cid=5291,
    labels=[
        Label(
            set_id="211ef2da-2868-4a77-8055-1cb2cd78e24b",
            substance="IMATINIB MESYLATE",
            brand="Gleevec",
            product_type="rx",
            effective_time=date(2026, 7, 13),
            sections=[
                LabelSection(
                    section="indications_and_usage",
                    section_group="indications",
                    text="1 INDICATIONS AND USAGE Gleevec is a kinase inhibitor indicated for the"
                    " treatment of: Newly diagnosed adult and pediatric patients with Philadelphia"
                    " chromosome positive chronic myeloid leukemia (Ph+ CML) in chronic phase. …",
                    sensitive=False,
                ),
                LabelSection(
                    section="dosage_and_administration",
                    section_group="dosing",
                    text="2 DOSAGE AND ADMINISTRATION Adults with Ph+ CML CP ( 2.2 ): 400 mg/day …",
                    sensitive=True,
                ),
                LabelSection(
                    section="mechanism_of_action",
                    section_group="pharmacology",
                    text="12.1 Mechanism of Action Imatinib mesylate is a protein-tyrosine kinase"
                    " inhibitor that inhibits the BCR-ABL tyrosine kinase, …",
                    sensitive=False,
                ),
            ],
            source="openfda",
            source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=211ef2da-2868-4a77-8055-1cb2cd78e24b",
        )
    ],
)

MET318 = Residue(chain="A", number=318, name="MET")

# Imatinib's hero complex cut down to one pocket residue and five ligand atoms; the real one has
# 263 trace residues, 23 pocket residues and 37 ligand atoms.
IMATINIB_COMPLEX = Complex(
    pdb_id="2HYY",
    ligand=Ligand(
        code="STI",
        chain="A",
        number=600,
        atoms=[
            Atom(name="C1", element="C", xyz=(22.827, 11.725, 13.78)),
            Atom(name="C6", element="C", xyz=(22.036, 12.177, 14.839)),
            Atom(name="C5", element="C", xyz=(20.668, 11.809, 14.959)),
            Atom(name="C4", element="C", xyz=(20.14, 11.001, 13.947)),
            Atom(name="N3", element="N", xyz=(20.892, 10.57, 12.904)),
        ],
        bonds=[
            Bond(atoms=(0, 1), order="aromatic"),
            Bond(atoms=(1, 2), order="aromatic"),
            Bond(atoms=(2, 3), order="aromatic"),
            Bond(atoms=(3, 4), order="aromatic"),
        ],
    ),
    trace=[
        TraceResidue(chain="A", number=317, name="PHE", sse="sheet", xyz=(18.655, 7.862, 11.634)),
        TraceResidue(chain="A", number=318, name="MET", sse="sheet", xyz=(20.028, 10.404, 9.18)),
        TraceResidue(chain="A", number=319, name="THR", sse="coil", xyz=(23.289, 9.376, 7.45)),
    ],
    pocket=[
        PocketResidue(
            chain="A",
            number=318,
            name="MET",
            atoms=[
                Atom(name="N", element="N", xyz=(19.652, 9.668, 10.399)),
                Atom(name="CA", element="C", xyz=(20.028, 10.404, 9.18)),
                Atom(name="C", element="C", xyz=(21.52, 10.344, 8.9)),
                Atom(name="O", element="O", xyz=(22.317, 10.826, 9.705)),
                Atom(name="CB", element="C", xyz=(19.45, 11.818, 9.212)),
                Atom(name="CG", element="C", xyz=(17.912, 11.763, 9.312)),
                Atom(name="SD", element="S", xyz=(17.241, 12.123, 7.721)),
                Atom(name="CE", element="C", xyz=(16.827, 10.502, 7.029)),
            ],
        )
    ],
    contacts=[
        Contact(kind="hbond", residue=MET318, residue_atom="N", ligand_atom=4, distance=2.94),
        Contact(kind="contact", residue=MET318, residue_atom="N", ligand_atom=4, distance=2.94),
    ],
    target="ABL1 (BCR-ABL)",
    organism="Homo sapiens",
    showcase=True,
)

SDF = """5291
  -OEChem-10112613423D

 68 72  0     0  0  0  0  0  0999 V2000
   -0.8276    0.2486   -1.0418 O   0  0  0  0  0  0  0  0  0  0  0  0
...
M  END
$$$$
"""
