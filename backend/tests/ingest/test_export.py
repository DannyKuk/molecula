import hashlib
import sqlite3
import tarfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from molecula.config import Settings
from molecula.ingest import export
from molecula.ingest.export import ARCHIVE, MANIFEST, ExportError, export_store, run
from molecula.schemas.store import StoreManifest
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.db import connect
from molecula.store.http_cache import CachedResponse, HttpCache
from molecula.store.index import Chunk, LabelIndex
from molecula.store.labels import LabelRecord, LabelSection, LabelStore
from molecula.store.schema import SCHEMA_VERSION
from molecula.store.structures import ConformerFiles

LABELS_FETCHED = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
LATER_LABEL_FETCHED = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
BUILT_AT = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
MODEL = "fake-model"
CACHED_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/imatinib/cids/JSON"
IMATINIB = CompoundRecord(
    cid=5291,
    name="imatinib",
    inchikey="KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    smiles="C",
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
IBUPROFEN = CompoundRecord(
    cid=3672,
    name="ibuprofen",
    inchikey="HEFNNWSXXWATRW-UHFFFAOYSA-N",
    smiles="C",
    formula="C13H18O2",
    mw=206.28,
    xlogp=3.5,
    tpsa=37.3,
    hbd=1,
    hba=2,
    rotb=4,
    heavy_atoms=15,
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
ADVIL = LabelRecord(
    set_id="advil",
    substance="IBUPROFEN",
    brand="Advil",
    product_type="otc",
    effective_time="20260101",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=advil",
    sections=(LabelSection("purpose", "otc_consumer", "Pain reliever", False),),
)
CHUNK = Chunk(
    id="gleevec:mechanism_of_action:0",
    text="Inhibits BCR-ABL.",
    cid=5291,
    substance="IMATINIB MESYLATE",
    brand="Gleevec",
    product_type="rx",
    section="mechanism_of_action",
    section_group="pharmacology",
    sensitive=False,
    set_id="gleevec",
    effective_time="20260713",
    url=GLEEVEC.url,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path / "data", offline=True)


def build_store(settings: Settings, *, with_index: bool = True) -> None:
    """A small store in `tmp_path` with every part a real build has, and files that must stay
    local: model weights, runtime data, eval output and review notes."""
    with closing(connect(settings.db_path)) as conn:
        CompoundStore(conn).save(IMATINIB, [], LATER_LABEL_FETCHED)
        CompoundStore(conn).save(IBUPROFEN, [], LATER_LABEL_FETCHED)
        LabelStore(conn).save(5291, (GLEEVEC,), LATER_LABEL_FETCHED)
        LabelStore(conn).save(3672, (ADVIL,), LABELS_FETCHED)
        HttpCache(conn).put(
            "pubchem:name:imatinib", CACHED_URL, CachedResponse(200, "application/json", b"{}")
        )
    ConformerFiles(settings.conformers_dir).write(5291, "imatinib\n$$$$\n")
    if with_index:
        LabelIndex(settings.index_dir).rebuild([CHUNK], [[1.0, 0.0]], MODEL)
    for local_only in (
        settings.models_dir / "models--BAAI--bge-m3" / "weights.bin",
        settings.build_dir / "eval" / "run.json",
        settings.build_dir / "complex_candidates.md",
        settings.data_dir / "runtime" / "usage.db",
    ):
        local_only.parent.mkdir(parents=True, exist_ok=True)
        local_only.write_bytes(b"local only")


def archive_names(path: Path) -> list[str]:
    with tarfile.open(path) as archive:
        return archive.getnames()


def unpack(settings: Settings, into: Path) -> Path:
    with tarfile.open(settings.export_dir / ARCHIVE) as archive:
        archive.extractall(into, filter="data")
    return into


def test_archive_holds_only_the_database_the_conformers_and_the_index(
    settings: Settings,
) -> None:
    build_store(settings)

    assert run(settings) == 0

    names = archive_names(settings.export_dir / ARCHIVE)
    assert "molecula.db" in names
    assert "structures/compounds/5291.sdf" in names
    assert "index/chroma/chroma.sqlite3" in names
    assert {name.split("/")[0] for name in names} == {"molecula.db", "structures", "index"}
    assert not any("\\" in name for name in names)


def test_leaves_out_the_models_runtime_data_and_other_local_files(settings: Settings) -> None:
    build_store(settings)

    run(settings)

    names = archive_names(settings.export_dir / ARCHIVE)
    for local_only in ("models", "runtime", "usage.db", "eval", "complex_candidates.md", "export"):
        assert not any(local_only in name.split("/") for name in names)


def test_exported_database_has_an_empty_http_cache_and_all_other_rows(
    settings: Settings, tmp_path: Path
) -> None:
    build_store(settings)

    run(settings)

    with closing(connect(unpack(settings, tmp_path / "fresh") / "molecula.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0
        assert HttpCache(conn).get("pubchem:name:imatinib") is None
        assert [row[0] for row in conn.execute("SELECT name FROM compound ORDER BY cid")] == [
            "ibuprofen",
            "imatinib",
        ]
        assert LabelStore(conn).get(5291) == (GLEEVEC,)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_built_store_is_not_changed(settings: Settings) -> None:
    build_store(settings)
    before = settings.db_path.read_bytes()

    run(settings)

    assert settings.db_path.read_bytes() == before
    with closing(connect(settings.db_path)) as conn:
        assert HttpCache(conn).get("pubchem:name:imatinib") is not None


def test_manifest_matches_the_archive(settings: Settings, tmp_path: Path) -> None:
    build_store(settings)

    returned = export_store(settings, settings.export_dir, BUILT_AT)

    manifest = StoreManifest.model_validate_json(
        (settings.export_dir / MANIFEST).read_text(encoding="utf-8")
    )
    archive = settings.export_dir / ARCHIVE
    assert manifest == returned
    assert manifest.sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert manifest.archive == ARCHIVE
    assert manifest.archive_bytes == archive.stat().st_size
    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.built_at == BUILT_AT
    assert manifest.embedding_model == MODEL
    with closing(sqlite3.connect(unpack(settings, tmp_path / "fresh") / "molecula.db")) as conn:
        for table, count in manifest.row_counts.items():
            assert conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == count
    assert manifest.row_counts["compound"] == 2
    assert manifest.row_counts["label"] == 2
    assert manifest.row_counts["label_section"] == 3
    assert manifest.row_counts["http_cache"] == 0


def test_last_run_is_the_oldest_label_fetch(settings: Settings) -> None:
    build_store(settings)

    manifest = export_store(settings, settings.export_dir, BUILT_AT)

    assert manifest.last_run == LABELS_FETCHED


def test_store_without_labels_has_no_last_run(settings: Settings) -> None:
    with closing(connect(settings.db_path)):
        pass
    LabelIndex(settings.index_dir).rebuild([], [], MODEL)

    manifest = export_store(settings, settings.export_dir, BUILT_AT)

    assert manifest.last_run is None


def test_a_second_export_replaces_the_first(settings: Settings) -> None:
    build_store(settings)
    export_store(settings, settings.export_dir, BUILT_AT)
    with closing(connect(settings.db_path)) as conn:
        CompoundStore(conn).prune(keep={5291})

    manifest = export_store(settings, settings.export_dir, BUILT_AT)

    archive = settings.export_dir / ARCHIVE
    assert manifest.row_counts["compound"] == 1
    assert manifest.sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_store_without_an_index_is_refused(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    build_store(settings, with_index=False)

    assert run(settings) == 1

    assert "python -m molecula.ingest index" in caplog.text
    assert not settings.index_dir.exists()
    assert not (settings.export_dir / ARCHIVE).exists()


def test_missing_store_is_refused(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    assert run(settings) == 1

    assert "There is no store" in caplog.text


def test_store_with_another_schema_version_is_refused(settings: Settings) -> None:
    build_store(settings)
    with closing(sqlite3.connect(settings.db_path)) as conn:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION - 1}")

    with pytest.raises(ExportError, match=f"schema version {SCHEMA_VERSION - 1}"):
        export_store(settings, settings.export_dir, BUILT_AT)


def test_archive_above_the_release_asset_limit_is_refused(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_store(settings)
    monkeypatch.setattr(export, "ASSET_LIMIT_BYTES", 100)

    with pytest.raises(ExportError, match="GitHub's limit"):
        export_store(settings, settings.export_dir, BUILT_AT)

    assert not (settings.export_dir / ARCHIVE).exists()
    assert not (settings.export_dir / MANIFEST).exists()
