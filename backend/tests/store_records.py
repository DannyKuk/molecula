"""Store records shared by the tests: a compound record builder, and imatinib, its Gleevec label,
an ibuprofen prescription label (Motrin), imatinib's ABL1 target and a stub of its hero complex as
the store holds them. `tool_fakes.py` has the API schema counterparts (`Compound`, `Target`)."""

from dataclasses import replace
from typing import Any

from molecula.schemas.complexes import Complex, Ligand
from molecula.store.compounds import CompoundRecord
from molecula.store.labels import LabelRecord, LabelSection
from molecula.store.targets import TargetRecord


def compound_record(cid: int, name: str, **overrides: Any) -> CompoundRecord:
    record = CompoundRecord(
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
        conformer_source="pubchem",
        source="pubchem",
    )
    return replace(record, **overrides)


IMATINIB = CompoundRecord(
    cid=5291,
    name="imatinib",
    inchikey="KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    smiles="CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
    formula="C29H31N7O",
    mw=493.6,
    xlogp=3.5,
    tpsa=86.3,
    hbd=2,
    hba=7,
    rotb=7,
    heavy_atoms=37,
    conformer_source="pubchem",
    source="pubchem",
)
GLEEVEC = LabelRecord(
    set_id="gleevec",
    substance="IMATINIB MESYLATE",
    brand="Gleevec",
    product_type="rx",
    effective_time="20260713",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    sections=(
        LabelSection("indications_and_usage", "indications", "1 INDICATIONS Ph+ CML.", False),
        LabelSection("mechanism_of_action", "pharmacology", "Inhibits BCR-ABL.", False),
    ),
)
MOTRIN = LabelRecord(
    set_id="rx-set-id",
    substance="IBUPROFEN",
    brand="Motrin",
    product_type="rx",
    effective_time="20250101",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=rx-set-id",
    sections=(
        LabelSection("clinical_pharmacology", "pharmacology", "Ibuprofen inhibits COX.", False),
        LabelSection("dosage_and_administration", "dosing", "400 mg every 4 hours.", True),
    ),
)
ABL1 = TargetRecord(
    target_chembl_id="CHEMBL1862",
    molecule_chembl_id="CHEMBL1642",
    name="Tyrosine-protein kinase ABL1",
    target_type="SINGLE PROTEIN",
    organism="Homo sapiens",
    mechanism="Tyrosine-protein kinase ABL inhibitor",
    action_type="INHIBITOR",
    accessions=("P00519",),
    gene_symbols=("ABL1",),
)
# Only the identifying fields; the geometry is tested on recorded structures (ingest).
IMATINIB_COMPLEX = Complex(
    pdb_id="2HYY",
    ligand=Ligand(code="STI", chain="A", number=600, atoms=[], bonds=[]),
    trace=[],
    pocket=[],
    contacts=[],
    showcase=True,
)
