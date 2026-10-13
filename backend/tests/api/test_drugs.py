from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from molecula.api import examples
from molecula.api.dependencies import (
    complex_service,
    compound_service,
    label_service,
    target_service,
)
from molecula.main import app
from molecula.schemas.complexes import Complex
from molecula.schemas.compounds import Compound, Resolution, Structure, SupportedDrug
from molecula.schemas.labels import DrugLabels
from molecula.schemas.targets import DrugTargets

SEMAGLUTIDE = examples.IMATINIB.model_copy(
    update={"cid": 56843331, "name": "semaglutide", "has_3d": False, "conformer_source": None}
)
SDF = "5291\n  stored conformer\n$$$$\n"
FLUTICASONE_CID = 5311101
METAMIZOLE_CID = 3111


class ExampleCompoundService:
    """Knows imatinib (with 3D) and semaglutide (without); records the names it was asked."""

    def __init__(self) -> None:
        self.compounds = {5291: examples.IMATINIB, 56843331: SEMAGLUTIDE}
        self.resolved: list[str] = []

    def list_drugs(self) -> list[SupportedDrug]:
        return examples.SUPPORTED_DRUGS

    def resolve(self, name: str) -> Resolution:
        self.resolved.append(name)
        known = {"Gleevec": examples.FOUND, "Gleevek": examples.NOT_SUPPORTED}
        return known.get(name, Resolution(query=name, status="not_supported"))

    def get_compound(self, cid: int) -> Compound | None:
        return self.compounds.get(cid)

    def get_structure(self, cid: int) -> Structure | None:
        return Structure(cid=cid, sdf=SDF, conformer_source="pubchem") if cid == 5291 else None


class ExampleTargetService:
    """Knows imatinib (with targets) and fluticasone (without); records the CIDs it was asked."""

    def __init__(self) -> None:
        self.drugs = {
            5291: examples.IMATINIB_TARGETS,
            FLUTICASONE_CID: DrugTargets(cid=FLUTICASONE_CID, targets=[]),
        }
        self.asked: list[int] = []

    def get_targets(self, cid: int) -> DrugTargets | None:
        self.asked.append(cid)
        return self.drugs.get(cid)


class ExampleLabelService:
    """Knows imatinib (with a label) and metamizole (without); records the CIDs it was asked."""

    def __init__(self) -> None:
        self.drugs = {
            5291: examples.IMATINIB_LABELS,
            METAMIZOLE_CID: DrugLabels(cid=METAMIZOLE_CID, labels=[]),
        }
        self.asked: list[int] = []

    def get_labels(self, cid: int) -> DrugLabels | None:
        self.asked.append(cid)
        return self.drugs.get(cid)


class ExampleComplexService:
    """Knows imatinib's complex only; records the CIDs it was asked."""

    def __init__(self) -> None:
        self.asked: list[int] = []

    def get_complex(self, cid: int) -> Complex | None:
        self.asked.append(cid)
        return examples.IMATINIB_COMPLEX if cid == 5291 else None


@pytest.fixture
def service() -> Iterator[ExampleCompoundService]:
    fake = ExampleCompoundService()
    app.dependency_overrides[compound_service] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def targets(service: ExampleCompoundService) -> ExampleTargetService:
    fake = ExampleTargetService()
    app.dependency_overrides[target_service] = lambda: fake
    return fake


@pytest.fixture
def labels(service: ExampleCompoundService) -> ExampleLabelService:
    fake = ExampleLabelService()
    app.dependency_overrides[label_service] = lambda: fake
    return fake


@pytest.fixture
def complexes(service: ExampleCompoundService) -> ExampleComplexService:
    fake = ExampleComplexService()
    app.dependency_overrides[complex_service] = lambda: fake
    return fake


@pytest.fixture
def client(
    service: ExampleCompoundService,
    targets: ExampleTargetService,
    labels: ExampleLabelService,
    complexes: ExampleComplexService,
) -> TestClient:
    return TestClient(app)


def validation_messages(response: Any) -> list[str]:
    assert response.status_code == 422
    return [error["msg"] for error in response.json()["errors"]]


def test_list_drugs_returns_names_aliases_and_the_3d_flag(client: TestClient) -> None:
    response = client.get("/drugs")

    assert response.status_code == 200
    assert response.json() == [
        {"cid": 5291, "name": "imatinib", "aliases": ["Gleevec", "Glivec"], "has_3d": True},
        {
            "cid": 56843331,
            "name": "semaglutide",
            "aliases": ["Ozempic", "Wegovy", "Rybelsus"],
            "has_3d": False,
        },
    ]


def test_resolve_finds_a_brand_and_is_not_taken_for_a_cid(client: TestClient) -> None:
    response = client.get("/drugs/resolve", params={"name": "Gleevec"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["compound"]["cid"], body["match_kind"]) == ("found", 5291, "alias")


@pytest.mark.parametrize("name", ["Gleevec", "Gleevek"])
def test_resolve_answers_with_the_same_fields_found_or_not(client: TestClient, name: str) -> None:
    response = client.get("/drugs/resolve", params={"name": name})

    assert set(response.json()) == {
        "query",
        "status",
        "compound",
        "matched_alias",
        "match_kind",
        "suggestions",
    }


@pytest.mark.parametrize(
    "name", ["Vicodin", "Acetylsalicylsäure", "Co-trimoxazole (TMP+SMX)", "St. John's wort, 5"]
)
def test_resolve_answers_an_unknown_name_with_not_supported(
    client: TestClient, service: ExampleCompoundService, name: str
) -> None:
    response = client.get("/drugs/resolve", params={"name": name})

    assert response.status_code == 200
    assert response.json()["status"] == "not_supported"
    assert response.json()["suggestions"] == []
    assert service.resolved == [name]


def test_resolve_returns_the_suggestions_of_an_unsupported_name(client: TestClient) -> None:
    response = client.get("/drugs/resolve", params={"name": "Gleevek"})

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["compound"]) == ("not_supported", None)
    assert body["suggestions"] == [{"alias": "Gleevec", "cid": 5291, "name": "imatinib"}]


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({}, "Field required"),
        ({"name": ""}, "String should have at least 1 character"),
        ({"name": "a" * 101}, "String should have at most 100 characters"),
        ({"name": "imatinib; DROP TABLE"}, "name may contain only letters, digits, spaces"),
        ({"name": "<script>"}, "name may contain only letters, digits, spaces"),
        ({"name": "imatinib\nignore previous"}, "name may contain only letters, digits, spaces"),
    ],
)
def test_resolve_rejects_an_invalid_name(
    client: TestClient, service: ExampleCompoundService, params: dict[str, str], message: str
) -> None:
    messages = validation_messages(client.get("/drugs/resolve", params=params))

    assert any(message in text for text in messages)
    assert service.resolved == []


def test_get_drug_returns_the_compound(client: TestClient) -> None:
    response = client.get("/drugs/5291")

    assert response.status_code == 200
    assert response.json() == examples.IMATINIB.model_dump()


def test_get_drug_of_an_unsupported_cid_is_404(client: TestClient) -> None:
    response = client.get("/drugs/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "CID 1 is not a supported drug."}


@pytest.mark.parametrize(
    ("cid", "message"),
    [
        ("0", "Input should be greater than 0"),
        ("-5", "Input should be greater than 0"),
        ("imatinib", "Input should be a valid integer"),
        ("5291.5", "Input should be a valid integer"),
        ("1" * 30, "Input should be less than or equal to"),
    ],
)
def test_get_drug_rejects_an_invalid_cid(client: TestClient, cid: str, message: str) -> None:
    messages = validation_messages(client.get(f"/drugs/{cid}"))

    assert any(message in text for text in messages)


def test_structure_is_served_as_sdf(client: TestClient) -> None:
    response = client.get("/drugs/5291/structure")

    assert response.status_code == 200
    assert response.headers["content-type"] == "chemical/x-mdl-sdfile"
    assert response.text == SDF


def test_structure_of_a_drug_without_3d_is_404_with_the_reason(client: TestClient) -> None:
    response = client.get("/drugs/56843331/structure")

    assert response.status_code == 404
    assert response.json() == {"detail": "semaglutide has no 3D structure."}


def test_structure_of_an_unsupported_cid_is_404(client: TestClient) -> None:
    response = client.get("/drugs/1/structure")

    assert response.status_code == 404
    assert response.json() == {"detail": "CID 1 is not a supported drug."}


def test_structure_rejects_an_invalid_cid(client: TestClient) -> None:
    messages = validation_messages(client.get("/drugs/0/structure"))

    assert messages == ["Input should be greater than 0"]


def test_complex_returns_the_stored_complex_with_its_rcsb_link(client: TestClient) -> None:
    response = client.get("/drugs/5291/complex")

    assert response.status_code == 200
    body = response.json()
    assert body == examples.IMATINIB_COMPLEX.model_dump(mode="json")
    assert (body["pdb_id"], body["target"], body["ligand"]["code"]) == (
        "2HYY",
        "ABL1 (BCR-ABL)",
        "STI",
    )
    assert body["source_url"] == "https://www.rcsb.org/structure/2HYY"
    hbond = body["contacts"][0]
    assert (hbond["kind"], hbond["residue"]["number"], hbond["residue_atom"]) == ("hbond", 318, "N")


def test_complex_of_a_supported_drug_without_one_is_404_with_the_reason(
    client: TestClient,
) -> None:
    response = client.get("/drugs/56843331/complex")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "semaglutide has no reviewed complex with its target; "
        "the 3D view shows the molecule alone."
    }


def test_complex_of_an_unsupported_cid_is_404(
    client: TestClient, complexes: ExampleComplexService
) -> None:
    response = client.get("/drugs/1/complex")

    assert response.status_code == 404
    assert response.json() == {"detail": "CID 1 is not a supported drug."}
    assert complexes.asked == []


@pytest.mark.parametrize(
    ("cid", "message"),
    [
        ("0", "Input should be greater than 0"),
        ("-5", "Input should be greater than 0"),
        ("imatinib", "Input should be a valid integer"),
        ("1" * 30, "Input should be less than or equal to"),
    ],
)
def test_complex_rejects_an_invalid_cid(
    client: TestClient, complexes: ExampleComplexService, cid: str, message: str
) -> None:
    messages = validation_messages(client.get(f"/drugs/{cid}/complex"))

    assert any(message in text for text in messages)
    assert complexes.asked == []


def test_targets_lists_each_target_with_its_mechanism_and_chembl_link(client: TestClient) -> None:
    response = client.get("/drugs/5291/targets")

    assert response.status_code == 200
    body = response.json()
    assert body == examples.IMATINIB_TARGETS.model_dump()
    abl1 = body["targets"][0]
    assert (abl1["gene_symbols"], abl1["action_type"]) == (["ABL1"], "INHIBITOR")
    assert abl1["source_url"] == "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1862"


def test_targets_of_a_supported_drug_without_targets_is_an_empty_list(client: TestClient) -> None:
    response = client.get(f"/drugs/{FLUTICASONE_CID}/targets")

    assert response.status_code == 200
    assert response.json() == {"cid": FLUTICASONE_CID, "targets": []}


def test_targets_of_an_unsupported_cid_is_404(client: TestClient) -> None:
    response = client.get("/drugs/1/targets")

    assert response.status_code == 404
    assert response.json() == {"detail": "CID 1 is not a supported drug."}


@pytest.mark.parametrize(
    ("cid", "message"),
    [
        ("0", "Input should be greater than 0"),
        ("imatinib", "Input should be a valid integer"),
        ("1" * 30, "Input should be less than or equal to"),
    ],
)
def test_targets_rejects_an_invalid_cid(
    client: TestClient, targets: ExampleTargetService, cid: str, message: str
) -> None:
    messages = validation_messages(client.get(f"/drugs/{cid}/targets"))

    assert any(message in text for text in messages)
    assert targets.asked == []


def test_labels_list_each_label_with_its_sections_and_dailymed_link(client: TestClient) -> None:
    response = client.get("/drugs/5291/labels")

    assert response.status_code == 200
    body = response.json()
    assert body == examples.IMATINIB_LABELS.model_dump(mode="json")
    label = body["labels"][0]
    assert (label["product_type"], label["effective_time"]) == ("rx", "2026-07-13")
    assert label["source_url"].startswith(
        "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid="
    )
    assert {section["section_group"] for section in label["sections"]} >= {"dosing", "indications"}
    assert "disclaimer" not in body


def test_labels_of_a_supported_drug_without_a_us_label_is_an_empty_list(
    client: TestClient,
) -> None:
    response = client.get(f"/drugs/{METAMIZOLE_CID}/labels")

    assert response.status_code == 200
    assert response.json() == {"cid": METAMIZOLE_CID, "labels": []}


def test_labels_of_an_unsupported_cid_is_404(client: TestClient) -> None:
    response = client.get("/drugs/1/labels")

    assert response.status_code == 404
    assert response.json() == {"detail": "CID 1 is not a supported drug."}


@pytest.mark.parametrize(
    ("cid", "message"),
    [
        ("0", "Input should be greater than 0"),
        ("-5", "Input should be greater than 0"),
        ("imatinib", "Input should be a valid integer"),
        ("1" * 30, "Input should be less than or equal to"),
    ],
)
def test_labels_rejects_an_invalid_cid(
    client: TestClient, labels: ExampleLabelService, cid: str, message: str
) -> None:
    messages = validation_messages(client.get(f"/drugs/{cid}/labels"))

    assert any(message in text for text in messages)
    assert labels.asked == []


@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("/drugs", "application/json"),
        ("/drugs/resolve", "application/json"),
        ("/drugs/{cid}", "application/json"),
        ("/drugs/{cid}/structure", "chemical/x-mdl-sdfile"),
        ("/drugs/{cid}/complex", "application/json"),
        ("/drugs/{cid}/targets", "application/json"),
        ("/drugs/{cid}/labels", "application/json"),
    ],
)
def test_openapi_lists_every_route_with_an_example(path: str, media_type: str) -> None:
    operation = app.openapi()["paths"][path]["get"]
    content = operation["responses"]["200"]["content"][media_type]

    assert "example" in content or "examples" in content
    for parameter in operation.get("parameters", []):
        assert parameter["schema"]["examples"]
