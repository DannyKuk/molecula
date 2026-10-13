import ast
import inspect
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from molecula.schemas.targets import DrugTargets, Target
from molecula.services import targets
from molecula.services.targets import TargetService
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.targets import DrugTargets as StoredTargets
from molecula.store.targets import TargetRecord, TargetStore
from tool_fakes import IMATINIB

FETCHED_AT = datetime(2026, 10, 11, tzinfo=UTC)
FLUTICASONE_CID = 5311101


def compound(cid: int, name: str) -> CompoundRecord:
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
        conformer_source="pubchem",
        source="pubchem",
    )


# Imatinib's targets as the targets ingest step stores them from the recorded ChEMBL responses.
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
PDGFRB = replace(
    ABL1,
    target_chembl_id="CHEMBL1913",
    name="Platelet-derived growth factor receptor beta",
    mechanism="Platelet-derived growth factor receptor beta inhibitor",
    accessions=("P09619",),
    gene_symbols=("PDGFRB",),
)
KIT = replace(
    ABL1,
    target_chembl_id="CHEMBL1936",
    name="Mast/stem cell growth factor receptor Kit",
    mechanism="Stem cell growth factor receptor inhibitor",
    accessions=("P10721",),
    gene_symbols=("KIT",),
)
BCR_ABL = replace(
    ABL1,
    target_chembl_id="CHEMBL2096618",
    name="Bcr/Abl fusion protein",
    target_type="CHIMERIC PROTEIN",
    mechanism="Bcr/Abl fusion protein inhibitor",
    accessions=("P00519", "P11274"),
    gene_symbols=("ABL1", "BCR"),
)


@pytest.fixture
def service(conn: sqlite3.Connection) -> TargetService:
    compounds = CompoundStore(conn)
    compounds.save(compound(5291, "imatinib"), [], FETCHED_AT)
    compounds.save(compound(FLUTICASONE_CID, "fluticasone"), [], FETCHED_AT)
    store = TargetStore(conn)
    store.save(5291, StoredTargets(targets=(ABL1, PDGFRB, KIT, BCR_ABL)), FETCHED_AT)
    return TargetService(store, compounds)


def test_imatinib_has_its_targets_in_stored_order(service: TargetService) -> None:
    drug = service.get_targets(5291)

    assert drug is not None
    assert drug.cid == 5291
    assert [target.gene_symbols for target in drug.targets] == [
        ["ABL1"],
        ["PDGFRB"],
        ["KIT"],
        ["ABL1", "BCR"],
    ]


def test_target_carries_the_mechanism_and_links_to_chembl(service: TargetService) -> None:
    drug = service.get_targets(5291)

    assert drug is not None
    assert drug.targets[0] == Target(
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
    )


def test_supported_drug_without_targets_has_an_empty_list(service: TargetService) -> None:
    assert service.get_targets(FLUTICASONE_CID) == DrugTargets(cid=FLUTICASONE_CID, targets=[])


def test_unknown_cid_is_none(service: TargetService) -> None:
    assert service.get_targets(1) is None


def test_a_resolved_drug_has_its_targets(service: TargetService) -> None:
    assert service.targets_of(IMATINIB) == service.get_targets(5291)


def test_service_has_no_source_client() -> None:
    imports = {
        node.module
        for node in ast.walk(ast.parse(inspect.getsource(targets)))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not any(module.startswith("molecula.sources") for module in imports)
