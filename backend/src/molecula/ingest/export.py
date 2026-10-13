import hashlib
import logging
import shutil
import sqlite3
import tarfile
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from molecula.config import Settings
from molecula.schemas.store import StoreManifest
from molecula.store.index import LabelIndex
from molecula.store.schema import SCHEMA_VERSION, ensure_schema

logger = logging.getLogger(__name__)

ARCHIVE = "molecula-store.tar.gz"
MANIFEST = "manifest.json"
DB_FILE = "molecula.db"
# Only these go into the archive. The rest of data/build/ stays local: the model weights
# (fetched from Hugging Face instead), eval output and review notes.
FOLDERS = ("structures", "index")
RAW_CACHE_TABLE = "http_cache"
# GitHub's limit for one release asset.
ASSET_LIMIT_BYTES = 2 * 1024**3


class ExportError(Exception):
    """The store can't be exported as it is."""


def export_store(settings: Settings, out_dir: Path, built_at: datetime) -> StoreManifest:
    """Pack the store database without its raw HTTP cache, the conformers and the index into
    `out_dir`, with a manifest next to the archive. The store's database is opened read-only."""
    if not settings.db_path.exists():
        raise ExportError(f"There is no store at {settings.db_path}; run the ingest steps first.")
    embedding_model = index_model(settings.index_dir)
    with tempfile.TemporaryDirectory() as staging:
        db_copy = Path(staging) / DB_FILE
        copy_without_raw_cache(settings.db_path, db_copy)
        row_counts = count_rows(db_copy)
        last_run = oldest_label_fetch(db_copy)
        staged_archive = Path(staging) / ARCHIVE
        write_archive(staged_archive, db_copy, settings.build_dir)
        size = staged_archive.stat().st_size
        if size > ASSET_LIMIT_BYTES:
            raise ExportError(
                f"The archive is {size:,} bytes, above GitHub's limit of {ASSET_LIMIT_BYTES:,} "
                "bytes for a release asset."
            )
        with staged_archive.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(staged_archive, out_dir / ARCHIVE)
    manifest = StoreManifest(
        schema_version=SCHEMA_VERSION,
        built_at=built_at,
        last_run=last_run,
        embedding_model=embedding_model,
        row_counts=row_counts,
        archive=ARCHIVE,
        archive_bytes=size,
        sha256=sha256,
    )
    (out_dir / MANIFEST).write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def index_model(index_dir: Path) -> str:
    # Checked first because LabelIndex creates a missing folder. A snapshot without the index
    # couldn't answer a label question offline.
    model = LabelIndex(index_dir).model() if index_dir.exists() else None
    if model is None:
        raise ExportError(
            f"There is no label index in {index_dir}; run `python -m molecula.ingest index` first."
        )
    return model


def copy_without_raw_cache(source: Path, target: Path) -> None:
    """Copy every table of the store at `source` that the current schema has into a new store
    at `target`, except the rows of the raw HTTP cache. The empty table stays, so the copy is a
    complete store an ingest step can run on. A table the schema no longer creates, such as
    `source_disclaimer` (#180), is left behind."""
    with closing(sqlite3.connect(target.resolve().as_uri(), uri=True)) as conn:
        ensure_schema(conn)
        conn.execute("ATTACH DATABASE ? AS built", (f"{source.resolve().as_uri()}?mode=ro",))
        version = conn.execute("PRAGMA built.user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            raise ExportError(
                f"The store has schema version {version}, this code {SCHEMA_VERSION}. "
                "Export it with the code it was built with, or upgrade it with an ingest step."
            )
        with conn:
            for table in table_names(conn):
                if table == RAW_CACHE_TABLE:
                    continue
                columns = ", ".join(
                    row[1] for row in conn.execute(f'PRAGMA main.table_info("{table}")')
                )
                conn.execute(
                    f'INSERT INTO main."{table}" ({columns}) SELECT {columns} FROM built."{table}"'
                )
        conn.execute("DETACH DATABASE built")


def table_names(conn: sqlite3.Connection, schema: str = "main") -> list[str]:
    rows = conn.execute(
        f"SELECT name FROM {schema}.sqlite_master"
        " WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [name for (name,) in rows]


def count_rows(db_path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(db_path)) as conn:
        return {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in table_names(conn)
        }


def oldest_label_fetch(db_path: Path) -> datetime | None:
    # The oldest rather than the newest fetch: an update from the newest would miss a label
    # that changed after an earlier fetch of another one.
    with closing(sqlite3.connect(db_path)) as conn:
        oldest = conn.execute("SELECT MIN(fetched_at) FROM label").fetchone()[0]
    return datetime.fromisoformat(oldest) if oldest else None


def write_archive(path: Path, db_copy: Path, build_dir: Path) -> None:
    with tarfile.open(path, "w:gz") as archive:
        archive.add(db_copy, arcname=DB_FILE)
        for folder in FOLDERS:
            if (build_dir / folder).exists():
                archive.add(build_dir / folder, arcname=folder)


def run(settings: Settings) -> int:
    """`python -m molecula.ingest export`: pack the built store for a GitHub release. Run it
    with the backend stopped: Chroma writes to the index whenever it opens it."""
    try:
        manifest = export_store(settings, settings.export_dir, datetime.now(UTC))
    except ExportError as error:
        logger.error("%s", error)
        return 1
    logger.info(
        "%s: %.1f MB, sha256 %s, schema version %d, index built with %s",
        settings.export_dir / manifest.archive,
        manifest.archive_bytes / 1e6,
        manifest.sha256,
        manifest.schema_version,
        manifest.embedding_model,
    )
    for table, count in manifest.row_counts.items():
        logger.info("  %s: %d rows", table, count)
    return 0
