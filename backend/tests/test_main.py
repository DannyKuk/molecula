from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from molecula import main
from molecula.config import Settings
from molecula.main import app
from molecula.store.compounds import CompoundRecord, CompoundStore, Synonym
from molecula.store.db import connect
from molecula.store.structures import ConformerFiles

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
SDF = "5291\n  stored conformer\n$$$$\n"


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return settings


def test_frontend_origin_may_call_the_api() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_gets_no_cors_header() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_app_starts_without_a_store_and_supports_no_drug(settings: Settings) -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/drugs").json() == []
        resolution = client.get("/drugs/resolve", params={"name": "imatinib"}).json()
        targets = client.get("/drugs/5291/targets")
        labels = client.get("/drugs/5291/labels")

    assert resolution["status"] == "not_supported"
    assert targets.status_code == 404
    assert labels.status_code == 404
    assert not settings.db_path.exists()


def test_routes_serve_the_built_store(settings: Settings) -> None:
    conn = connect(settings.db_path)
    CompoundStore(conn).save(
        IMATINIB,
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias"), Synonym("STI571", "pubchem")],
        datetime(2026, 10, 11, tzinfo=UTC),
    )
    conn.close()
    ConformerFiles(settings.conformers_dir).write(5291, SDF)

    with TestClient(app) as client:
        drugs = client.get("/drugs").json()
        resolution = client.get("/drugs/resolve", params={"name": "imatinib mesylate"}).json()
        structure = client.get("/drugs/5291/structure")
        targets = client.get("/drugs/5291/targets").json()
        labels = client.get("/drugs/5291/labels").json()

    assert drugs == [{"cid": 5291, "name": "imatinib", "aliases": ["Gleevec"], "has_3d": True}]
    assert resolution["compound"]["cid"] == 5291
    assert structure.text == SDF
    assert targets == {"cid": 5291, "targets": []}
    assert labels == {"cid": 5291, "labels": [], "disclaimer": None}


@pytest.mark.parametrize(("cutoff", "suggested"), [(0.8, ["Gleevec"]), (0.9, [])])
def test_name_suggestion_cutoff_comes_from_the_settings(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, cutoff: float, suggested: list[str]
) -> None:
    monkeypatch.setattr(settings, "name_suggestion_cutoff", cutoff)
    conn = connect(settings.db_path)
    CompoundStore(conn).save(
        IMATINIB,
        [Synonym("imatinib", "name"), Synonym("Gleevec", "alias")],
        datetime(2026, 10, 11, tzinfo=UTC),
    )
    conn.close()

    with TestClient(app) as client:
        resolution = client.get("/drugs/resolve", params={"name": "Gleevek"}).json()

    assert resolution["status"] == "not_supported"
    assert [suggestion["alias"] for suggestion in resolution["suggestions"]] == suggested
