import hashlib
import logging
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

import httpx2
from pydantic import ValidationError

from molecula.config import Settings
from molecula.ingest.export import ARCHIVE, DB_FILE, FOLDERS, MANIFEST
from molecula.rag.embeddings import (
    LOCAL,
    ModelDownloadError,
    download_local_model,
    embedding_model_id,
    has_local_model,
)
from molecula.schemas.store import StoreManifest
from molecula.sources.http import USER_AGENT
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.schema import SCHEMA_VERSION

logger = logging.getLogger(__name__)

STORE_PARTS = (DB_FILE, *FOLDERS)
# SQLite would apply a journal left by the replaced database to the downloaded one.
DB_SIDE_FILES = ("-journal", "-wal", "-shm")
TIMEOUT = httpx2.Timeout(60.0, connect=10.0)
CHUNK_BYTES = 1024 * 1024


class FetchError(Exception):
    """The store release can't be downloaded, or doesn't fit this code."""


def fetch_store(settings: Settings, client: httpx2.Client) -> StoreManifest:
    """Download the pinned store release, check it and unpack it into `build_dir`, replacing
    the database, the structures and the index there. A failed check leaves `build_dir` as it
    was."""
    manifest = download_manifest(client, f"{settings.store_release_url}/{MANIFEST}")
    check_manifest(manifest, settings)
    settings.build_dir.mkdir(parents=True, exist_ok=True)
    # Staged inside build_dir, so the unpacked store moves into place without a copy, also when
    # data/ is a mounted volume.
    with tempfile.TemporaryDirectory(dir=settings.build_dir, prefix=".fetch-") as staging:
        archive = Path(staging) / ARCHIVE
        logger.info(
            "Downloading %s of %s (%.1f MB)",
            ARCHIVE,
            settings.store_release,
            manifest.archive_bytes / 1e6,
        )
        download(client, f"{settings.store_release_url}/{manifest.archive}", archive, manifest)
        check_archive(archive, manifest)
        unpacked = Path(staging) / "store"
        unpack(archive, unpacked)
        replace_store(unpacked, settings.build_dir)
    return manifest


def download_manifest(client: httpx2.Client, url: str) -> StoreManifest:
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx2.HTTPError as error:
        raise FetchError(f"{url} could not be downloaded: {error}") from error
    try:
        return StoreManifest.model_validate_json(response.content)
    except ValidationError as error:
        raise FetchError(f"{url} is not a store manifest: {error}") from error


def check_manifest(manifest: StoreManifest, settings: Settings) -> None:
    if manifest.schema_version != SCHEMA_VERSION:
        raise FetchError(
            f"{settings.store_release} has schema version {manifest.schema_version}, this code "
            f"{SCHEMA_VERSION}. Set STORE_RELEASE to a release made with this code."
        )
    model = embedding_model_id(settings)
    if manifest.embedding_model != model:
        raise FetchError(
            f"The index in {settings.store_release} was built with {manifest.embedding_model}, "
            f"but the settings name {model}, and the index refuses another model's queries. "
            "Use that model, or build the index with `python -m molecula.ingest index`."
        )


def download(client: httpx2.Client, url: str, target: Path, manifest: StoreManifest) -> None:
    """Stream `url` into `target`, stopping once it is larger than the manifest says."""
    received = 0
    try:
        with client.stream("GET", url) as response, target.open("wb") as file:
            response.raise_for_status()
            for chunk in response.iter_bytes(CHUNK_BYTES):
                received += len(chunk)
                if received > manifest.archive_bytes:
                    raise FetchError(
                        f"{url} is larger than the {manifest.archive_bytes:,} bytes "
                        "the manifest gives."
                    )
                file.write(chunk)
    except httpx2.HTTPError as error:
        raise FetchError(f"{url} could not be downloaded: {error}") from error


def check_archive(archive: Path, manifest: StoreManifest) -> None:
    size = archive.stat().st_size
    if size != manifest.archive_bytes:
        raise FetchError(
            f"The archive has {size:,} bytes, the manifest {manifest.archive_bytes:,}."
        )
    with archive.open("rb") as file:
        sha256 = hashlib.file_digest(file, "sha256").hexdigest()
    if sha256 != manifest.sha256:
        raise FetchError(f"The archive's SHA-256 is {sha256}, the manifest's {manifest.sha256}.")


def unpack(archive: Path, target: Path) -> None:
    """Unpack the store parts, refusing any member that is a link or lands outside them."""
    try:
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                check_member(member)
            tar.extractall(target, filter="data")
    except tarfile.TarError as error:
        raise FetchError(f"The archive could not be unpacked: {error}") from error


def check_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if not (member.isfile() or member.isdir()):
        raise FetchError(f"The archive holds {member.name}, which is not a file or folder.")
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise FetchError(f"The archive holds {member.name}, outside the store.")
    if path.parts[0] not in STORE_PARTS:
        raise FetchError(f"The archive holds {member.name}, outside the store.")


def replace_store(unpacked: Path, build_dir: Path) -> None:
    for part in STORE_PARTS:
        remove(build_dir / part)
    for suffix in DB_SIDE_FILES:
        (build_dir / f"{DB_FILE}{suffix}").unlink(missing_ok=True)
    for part in STORE_PARTS:
        if (unpacked / part).exists():
            (unpacked / part).replace(build_dir / part)


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def store_step(settings: Settings, *, force: bool, transport: httpx2.BaseTransport | None) -> bool:
    if settings.db_path.exists() and not force:
        logger.info(
            "The store at %s is already there; `fetch --force` replaces it", settings.db_path
        )
        return True
    if settings.db_path.exists():
        logger.warning(
            "--force: replacing the store at %s; local updates to it (#25) are lost",
            settings.db_path,
        )
    with httpx2.Client(
        transport=transport,
        timeout=TIMEOUT,
        # GitHub redirects release downloads to its file host.
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        try:
            manifest = fetch_store(settings, client)
        except FetchError as error:
            logger.error("The store was not fetched: %s", error)
            return False
    logger.info(
        "Unpacked %s into %s: schema version %d, built %s, %d compounds, %d labels",
        settings.store_release,
        settings.build_dir,
        manifest.schema_version,
        manifest.built_at.date(),
        manifest.row_counts.get("compound", 0),
        manifest.row_counts.get("label", 0),
    )
    return True


def model_step(settings: Settings) -> bool:
    if settings.embedding_model != LOCAL:
        logger.info(
            "EMBEDDING_MODEL=%s is a cloud model; no local model is needed",
            settings.embedding_model,
        )
        return True
    if has_local_model(settings):
        logger.info(
            "%s at %s is already in %s",
            settings.local_embedding_model,
            settings.local_embedding_model_revision[:7],
            settings.models_dir,
        )
        return True
    logger.info(
        "Downloading %s at %s into %s (about 2.3 GB)",
        settings.local_embedding_model,
        settings.local_embedding_model_revision[:7],
        settings.models_dir,
    )
    try:
        download_local_model(settings)
    except ModelDownloadError as error:
        logger.error("The model was not fetched: %s", error)
        return False
    logger.info("%s downloaded and its weights checked", settings.local_embedding_model)
    return True


def keyword_step(settings: Settings) -> None:
    """Build the keyword index from the label index when it is missing: store releases made
    before #44 don't hold it. It takes about a second and no network."""
    keywords = KeywordIndex(settings.keyword_index_path)
    if keywords.exists() or not settings.index_dir.exists():
        return
    chunks = LabelIndex(settings.index_dir).chunks()
    keywords.rebuild(chunks)
    logger.info(
        "Built the keyword index of %d chunks at %s", len(chunks), settings.keyword_index_path
    )


def run(
    settings: Settings, *, force: bool = False, transport: httpx2.BaseTransport | None = None
) -> int:
    """`python -m molecula.ingest fetch`: download the pinned store release and the embedding
    model when they are missing, and build the keyword index the release lacks. It needs the
    internet once and ignores OFFLINE, which only decides whether the app calls cloud models."""
    store_ready = store_step(settings, force=force, transport=transport)
    if store_ready:
        keyword_step(settings)
    model_ready = model_step(settings)
    return 0 if store_ready and model_ready else 1
