"""Labels ingest tests: canonical selection on hand-made labels, the step on recorded openFDA
searches (see `tests/openfda_replay.py`)."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from molecula.config import Settings
from molecula.ingest.labels import (
    LabelsReport,
    canonical_labels,
    ingest_labels,
    kept_sections,
    run,
)
from molecula.sources.http import SourceClient
from molecula.sources.openfda import PAGE_SIZE, Label, OpenFdaClient, OpenFdaFields
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.http_cache import HttpCache
from molecula.store.labels import LabelStore
from openfda_replay import Replay

RX = "HUMAN PRESCRIPTION DRUG"
OTC = "HUMAN OTC DRUG"
GLEEVEC = "211ef2da-2868-4a77-8055-1cb2cd78e24b"
MECHANISM = ("mechanism_of_action",)


def compound(cid: int, name: str) -> CompoundRecord:
    return CompoundRecord(
        cid=cid,
        name=name,
        inchikey="K",
        smiles="C",
        formula="C",
        mw=1.0,
        xlogp=None,
        tpsa=None,
        hbd=0,
        hba=0,
        rotb=0,
        heavy_atoms=1,
        conformer_source=None,
        source="pubchem",
    )


IMATINIB = compound(5291, "imatinib")
IBUPROFEN = compound(3672, "ibuprofen")
ACETAMINOPHEN = compound(1983, "acetaminophen")
# openFDA has US labels only; a store that named the drug paracetamol would find none.
PARACETAMOL = compound(1983, "paracetamol")


def label(
    set_id: str,
    substances: list[str],
    *,
    product_type: str = RX,
    effective_time: str = "20250101",
    application: str = "ANDA000001",
    brand: str | None = None,
    route: tuple[str, ...] = ("ORAL",),
    sections: tuple[str, ...] = ("indications_and_usage",),
) -> Label:
    generic = " AND ".join(substances)
    return Label(
        set_id=set_id,
        effective_time=effective_time,
        openfda=OpenFdaFields(
            generic_name=[generic],
            brand_name=[brand or generic],
            substance_name=substances,
            product_type=[product_type],
            application_number=[application],
            route=list(route),
        ),
        sections={section: [f"{section} text"] for section in sections},
    )


def chosen(name: str, labels: list[Label]) -> list[str]:
    return [record.set_id for record in canonical_labels(name, labels)]


def test_combination_products_are_never_chosen() -> None:
    combinations = [
        label("first", ["ACETAMINOPHEN", "HYDROCODONE BITARTRATE"], sections=MECHANISM),
        label("second", ["HYDROCODONE BITARTRATE", "ACETAMINOPHEN"], sections=MECHANISM),
    ]

    assert chosen("acetaminophen", combinations) == []


def test_a_label_of_another_drug_is_never_chosen() -> None:
    assert chosen("naloxone", [label("other", ["NALTREXONE HYDROCHLORIDE"])]) == []


def test_salt_labels_count_as_the_parent() -> None:
    assert chosen("imatinib", [label("salt", ["IMATINIB MESYLATE"])]) == ["salt"]


def test_a_label_with_a_mechanism_section_wins() -> None:
    labels = [
        label("brand", ["IBUPROFEN"], application="NDA017463", brand="Motrin"),
        label("mechanism", ["IBUPROFEN"], sections=MECHANISM),
    ]

    assert chosen("ibuprofen", labels) == ["mechanism"]


def test_the_brand_label_wins_over_a_newer_generic() -> None:
    labels = [
        label("generic", ["IMATINIB MESYLATE"], effective_time="20260901"),
        label("brand", ["IMATINIB MESYLATE"], application="NDA021588", brand="Gleevec"),
    ]

    assert chosen("imatinib", labels) == ["brand"]


def test_an_nda_label_under_the_generic_name_is_not_the_brand() -> None:
    labels = [
        label("authorized-generic", ["IMATINIB MESYLATE"], application="NDA021588"),
        label("newer", ["IMATINIB MESYLATE"], effective_time="20260901"),
    ]

    assert chosen("imatinib", labels) == ["newer"]


def test_a_biologic_brand_counts_as_the_brand() -> None:
    labels = [
        label(
            "biosimilar", ["INSULIN GLARGINE"], application="BLA761201", effective_time="20260901"
        ),
        label("brand", ["INSULIN GLARGINE"], application="BLA021081", brand="Lantus"),
    ]

    assert chosen("insulin glargine", labels) == ["brand"]


def test_then_the_newest_label_wins() -> None:
    labels = [
        label("older", ["CAFFEINE"], effective_time="20240101"),
        label("newer", ["CAFFEINE"], effective_time="20260101"),
    ]

    assert chosen("caffeine", labels) == ["newer"]


def test_then_the_most_kept_sections_win() -> None:
    labels = [
        label("unkept", ["CAFFEINE"], sections=("spl_unclassified_section", "overdosage")),
        label("kept", ["CAFFEINE"], sections=("indications_and_usage", "contraindications")),
    ]

    assert chosen("caffeine", labels) == ["kept"]


def test_the_usual_route_comes_before_a_mechanism_section() -> None:
    labels = [
        label("injection", ["IBUPROFEN"], route=("INTRAVENOUS",), sections=MECHANISM),
        label("tablet-1", ["IBUPROFEN"]),
        label("tablet-2", ["IBUPROFEN"], effective_time="20200101"),
    ]

    assert chosen("ibuprofen", labels) == ["tablet-1"]


def test_routes_count_as_one_value_in_any_order() -> None:
    labels = [
        label("oral", ["DEXAMETHASONE"], sections=MECHANISM),
        label("im-iv", ["DEXAMETHASONE"], route=("INTRAMUSCULAR", "INTRAVENOUS")),
        label("iv-im", ["DEXAMETHASONE"], route=("INTRAVENOUS", "INTRAMUSCULAR")),
        label("im", ["DEXAMETHASONE"], route=("INTRAMUSCULAR",)),
    ]

    assert chosen("dexamethasone", labels) == ["im-iv"]


def test_equally_common_routes_go_by_name_and_no_route_loses() -> None:
    labels = [
        label("topical", ["CLOTRIMAZOLE"], route=("TOPICAL",)),
        label("oral", ["CLOTRIMAZOLE"], route=("ORAL",)),
        label("none", ["CLOTRIMAZOLE"], route=(), sections=MECHANISM),
    ]

    assert chosen("clotrimazole", labels) == ["oral"]
    assert chosen("clotrimazole", [labels[2]]) == ["none"]


def test_a_full_tie_goes_to_the_first_set_id() -> None:
    labels = [label("b", ["CAFFEINE"]), label("a", ["CAFFEINE"]), label("c", ["CAFFEINE"])]

    assert chosen("caffeine", labels) == ["a"]


def test_one_prescription_and_one_otc_label() -> None:
    labels = [
        label("rx-1", ["IBUPROFEN"]),
        label("rx-2", ["IBUPROFEN"], effective_time="20200101"),
        label("otc-1", ["IBUPROFEN"], product_type=OTC),
    ]

    assert chosen("ibuprofen", labels) == ["rx-1", "otc-1"]


def test_another_form_counts_when_there_is_no_label_of_the_parent() -> None:
    propionate = label("propionate", ["FLUTICASONE PROPIONATE"], product_type=OTC)
    furoate = label("furoate", ["FLUTICASONE FUROATE"])

    assert chosen("fluticasone", [propionate, furoate]) == ["furoate", "propionate"]


def test_a_label_of_the_parent_wins_over_a_newer_one_of_another_form() -> None:
    labels = [
        label("plain", ["ESTRADIOL"], effective_time="20200101"),
        label("ester", ["ESTRADIOL VALERATE"], effective_time="20260101"),
    ]

    assert chosen("estradiol", labels) == ["plain"]


@pytest.fixture
def store(conn: sqlite3.Connection) -> LabelStore:
    compounds = CompoundStore(conn)
    for record in (IMATINIB, IBUPROFEN, ACETAMINOPHEN):
        compounds.save(record, [], datetime(2026, 10, 11, tzinfo=UTC))
    return LabelStore(conn)


@pytest.fixture
def openfda(cache: HttpCache) -> Callable[..., OpenFdaClient]:
    def make(handler: Callable[[httpx2.Request], httpx2.Response] | None = None) -> OpenFdaClient:
        http = SourceClient(
            cache,
            offline=False,
            transport=httpx2.MockTransport(handler or Replay()),
            sleep=lambda _: None,
        )
        return OpenFdaClient(http)

    return make


@pytest.fixture
def ingest(openfda, store: LabelStore) -> Callable[..., LabelsReport]:
    def run_ingest(
        compounds: list[CompoundRecord],
        handler: Callable[[httpx2.Request], httpx2.Response] | None = None,
    ) -> LabelsReport:
        return ingest_labels(compounds, openfda(handler), store)

    return run_ingest


def test_imatinib_gets_the_gleevec_label_and_no_otc_label(ingest, store: LabelStore) -> None:
    report = ingest([IMATINIB])

    assert report.failures == {}
    [gleevec] = store.get(5291)
    assert (gleevec.set_id, gleevec.brand, gleevec.substance) == (
        GLEEVEC,
        "Gleevec",
        "IMATINIB MESYLATE",
    )
    assert (gleevec.product_type, gleevec.effective_time) == ("rx", "20260713")
    assert gleevec.url == f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={GLEEVEC}"
    groups = {section.section: section.section_group for section in gleevec.sections}
    assert groups["mechanism_of_action"] == "pharmacology"
    assert groups["warnings_and_cautions"] == "warnings"
    assert groups["indications_and_usage"] == "indications"


def test_overdosage_and_table_fields_are_never_stored(ingest, conn: sqlite3.Connection) -> None:
    ingest([IMATINIB, IBUPROFEN, ACETAMINOPHEN])

    stored = {row[0] for row in conn.execute("SELECT DISTINCT section FROM label_section")}
    assert stored
    assert "overdosage" not in stored
    assert not [section for section in stored if section.endswith("_table")]


def test_only_dosing_is_marked_sensitive(ingest, store: LabelStore) -> None:
    ingest([IMATINIB])

    [gleevec] = store.get(5291)
    sensitive = {section.section for section in gleevec.sections if section.sensitive}
    assert sensitive == {"dosage_and_administration"}


def test_combination_products_are_excluded(ingest, store: LabelStore) -> None:
    ingest([ACETAMINOPHEN])

    # Apadaz (benzhydrocodone + acetaminophen) has a mechanism section and is a brand label, so
    # it would be chosen if combinations counted. Combinations are oral and single-ingredient
    # acetaminophen Rx labels are injections, so they would also have made oral the usual route.
    rx, otc = store.get(1983)
    assert (rx.set_id, rx.brand) == ("464e404a-1957-44a2-a53a-f2a9d3c15bde", "Acetaminophen")
    assert (otc.set_id, otc.brand) == (
        "3af22fc8-e4e0-4863-8696-6bc1257047cb",
        "Tylenol 8 HR Arthritis Pain",
    )
    assert {rx.substance, otc.substance} == {"ACETAMINOPHEN"}


def test_ibuprofen_mechanism_is_found_in_clinical_pharmacology(openfda) -> None:
    tablets = next(
        found
        for found in openfda().labels("ibuprofen")
        if found.set_id == "2144eff0-d7ab-486d-b116-a4ff3ae2afe2"
    )

    sections = {section.section: section for section in kept_sections(tablets)}

    assert "mechanism_of_action" not in sections
    pharmacology = sections["clinical_pharmacology"]
    assert pharmacology.section_group == "pharmacology"
    assert "prostaglandin synthetase inhibition" in pharmacology.text


def test_ibuprofen_rx_pick_is_oral_although_only_the_iv_label_has_a_mechanism_section(
    ingest, store: LabelStore
) -> None:
    ingest([IBUPROFEN])

    rx, _ = store.get(3672)
    # Three oral labels against Caldolor, the injection, which alone has `mechanism_of_action`.
    # Of the oral ones (none filed as a brand) the newest wins.
    assert (rx.brand, rx.set_id) == ("Ibuprofen", "2144eff0-d7ab-486d-b116-a4ff3ae2afe2")
    sections = {section.section: section for section in rx.sections}
    assert "mechanism_of_action" not in sections
    assert "prostaglandin synthetase inhibition" in sections["clinical_pharmacology"].text


def test_older_rx_precautions_map_to_warnings(ingest, store: LabelStore) -> None:
    ingest([IBUPROFEN])

    rx, _ = store.get(3672)
    groups = {section.section: section.section_group for section in rx.sections}
    assert groups["precautions"] == "warnings"
    assert groups["warnings"] == "warnings"


def test_otc_drug_facts_sections_map_to_otc_consumer(ingest, store: LabelStore) -> None:
    ingest([IBUPROFEN])

    _, otc = store.get(3672)
    assert (otc.brand, otc.substance) == ("Advil Menstrual Pain", "IBUPROFEN SODIUM")
    groups = {section.section: section.section_group for section in otc.sections}
    assert {section for section, group in groups.items() if group == "otc_consumer"} == {
        "active_ingredient",
        "purpose",
        "do_not_use",
        "ask_doctor",
        "ask_doctor_or_pharmacist",
        "when_using",
        "stop_use",
    }
    assert groups["warnings"] == "warnings"
    assert groups["indications_and_usage"] == "indications"
    assert groups["dosage_and_administration"] == "dosing"
    assert "keep_out_of_reach_of_children" not in groups
    assert "inactive_ingredient" not in groups


def test_drug_without_a_us_label_is_listed_and_stores_nothing(ingest, store: LabelStore) -> None:
    report = ingest([PARACETAMOL])

    assert report.failures == {}
    assert report.without_label == ["paracetamol"]
    assert store.get(1983) == ()


def test_openfda_disclaimer_is_stored_once(ingest, store: LabelStore, conn) -> None:
    ingest([IMATINIB, IBUPROFEN])

    disclaimer = store.disclaimer("openfda")
    assert disclaimer is not None
    assert disclaimer.startswith("Do not rely on openFDA to make decisions regarding medical care.")
    assert conn.execute("SELECT count(*) FROM source_disclaimer").fetchone() == (1,)


def test_rerun_is_served_from_the_cache_and_changes_nothing(
    ingest, conn: sqlite3.Connection
) -> None:
    ingest([IMATINIB, IBUPROFEN, ACETAMINOPHEN])
    rows_before = dump(conn)
    changes_before = conn.total_changes

    second_run = Replay()
    ingest([IMATINIB, IBUPROFEN, ACETAMINOPHEN], second_run)

    assert second_run.requests == []
    assert conn.total_changes == changes_before
    assert dump(conn) == rows_before


def test_a_failing_drug_is_reported_and_the_rest_stored(ingest, store: LabelStore) -> None:
    broken = Replay({("ibuprofen", PAGE_SIZE, 0): httpx2.Response(500)})

    report = ingest([IBUPROFEN, IMATINIB], broken)

    assert list(report.failures) == ["ibuprofen"]
    assert "HTTP 500" in report.failures["ibuprofen"]
    assert store.get(3672) == ()
    assert store.get(5291)


def test_run_stops_when_openfda_stops_answering(ingest, store: LabelStore) -> None:
    def throttled(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429)

    report = ingest([IBUPROFEN, IMATINIB], throttled)

    assert list(report.failures) == ["ibuprofen"]
    assert report.not_attempted == ["imatinib"]
    assert store.get(5291) == ()


def test_offline_run_on_an_empty_store_succeeds(tmp_path: Path) -> None:
    assert run(Settings(data_dir=tmp_path, offline=True)) == 0


def dump(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    return [
        *conn.execute("SELECT rowid, * FROM label ORDER BY rowid"),
        *conn.execute("SELECT rowid, * FROM label_section ORDER BY rowid"),
        *conn.execute("SELECT rowid, * FROM source_disclaimer ORDER BY rowid"),
    ]
