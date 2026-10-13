import ast
import inspect
import sqlite3
from datetime import UTC, date, datetime

import pytest

from molecula.schemas.labels import DrugLabels, Label, LabelSection
from molecula.services import labels
from molecula.services.labels import LabelService
from molecula.store.compounds import CompoundStore
from molecula.store.labels import LabelRecord, LabelStore
from molecula.store.labels import LabelSection as StoredSection
from store_records import MOTRIN, compound_record

FETCHED_AT = datetime(2026, 10, 12, tzinfo=UTC)
IBUPROFEN_CID = 3672
METAMIZOLE_CID = 3111
DISCLAIMER = "Do not rely on openFDA to make decisions regarding medical care."


OTC = LabelRecord(
    set_id="otc-set-id",
    substance="IBUPROFEN",
    brand=None,
    product_type="otc",
    effective_time="20240601",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=otc-set-id",
    sections=(StoredSection("purpose", "otc_consumer", "Pain reliever/fever reducer", False),),
)


@pytest.fixture
def store(conn: sqlite3.Connection) -> LabelStore:
    compounds = CompoundStore(conn)
    compounds.save(compound_record(IBUPROFEN_CID, "ibuprofen"), [], FETCHED_AT)
    compounds.save(compound_record(METAMIZOLE_CID, "metamizole"), [], FETCHED_AT)
    store = LabelStore(conn)
    store.save(IBUPROFEN_CID, (OTC, MOTRIN), FETCHED_AT)
    return store


@pytest.fixture
def service(store: LabelStore, conn: sqlite3.Connection) -> LabelService:
    return LabelService(store, CompoundStore(conn))


def test_prescription_label_comes_before_the_otc_label(service: LabelService) -> None:
    drug = service.get_labels(IBUPROFEN_CID)

    assert drug is not None
    assert [(label.set_id, label.product_type) for label in drug.labels] == [
        ("rx-set-id", "rx"),
        ("otc-set-id", "otc"),
    ]


def test_label_carries_its_metadata_sections_and_dailymed_link(service: LabelService) -> None:
    drug = service.get_labels(IBUPROFEN_CID)

    assert drug is not None
    assert drug.labels[0] == Label(
        set_id="rx-set-id",
        substance="IBUPROFEN",
        brand="Motrin",
        product_type="rx",
        effective_time=date(2025, 1, 1),
        sections=[
            LabelSection(
                section="clinical_pharmacology",
                section_group="pharmacology",
                text="Ibuprofen inhibits COX.",
                sensitive=False,
            ),
            LabelSection(
                section="dosage_and_administration",
                section_group="dosing",
                text="400 mg every 4 hours.",
                sensitive=True,
            ),
        ],
        source="openfda",
        source_url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=rx-set-id",
    )
    assert drug.labels[1].brand is None


def test_labels_come_with_the_stored_disclaimer(service: LabelService, store: LabelStore) -> None:
    store.save_disclaimer("openfda", DISCLAIMER, FETCHED_AT)

    drug = service.get_labels(IBUPROFEN_CID)

    assert drug is not None
    assert drug.disclaimer == DISCLAIMER
    assert service.disclaimer() == DISCLAIMER


def test_disclaimer_is_none_before_the_labels_step_stored_one(service: LabelService) -> None:
    drug = service.get_labels(IBUPROFEN_CID)

    assert drug is not None
    assert drug.disclaimer is None


def test_supported_drug_without_a_us_label_has_an_empty_list(
    service: LabelService, store: LabelStore
) -> None:
    store.save_disclaimer("openfda", DISCLAIMER, FETCHED_AT)

    assert service.get_labels(METAMIZOLE_CID) == DrugLabels(
        cid=METAMIZOLE_CID, labels=[], disclaimer=DISCLAIMER
    )


def test_unknown_cid_is_none(service: LabelService) -> None:
    assert service.get_labels(1) is None


def test_service_has_no_source_client() -> None:
    imports = {
        node.module
        for node in ast.walk(ast.parse(inspect.getsource(labels)))
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert not any(module.startswith("molecula.sources") for module in imports)
