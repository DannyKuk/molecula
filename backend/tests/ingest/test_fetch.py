import hashlib
import io
import sqlite3
import tarfile
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from fake_hub import FakeHub, install_fake_hub
from molecula.config import Settings
from molecula.ingest.export import ARCHIVE, MANIFEST, export_store
from molecula.ingest.fetch import run
from molecula.rag.embeddings import has_local_model
from molecula.schemas.store import StoreManifest
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import Chunk, LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.schema import SCHEMA_VERSION
from molecula.store.structures import ConformerFiles
from store_records import IMATINIB

MODEL = "BAAI/bge-m3"
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
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
)


@dataclass(frozen=True)
class Release:
    manifest: StoreManifest
    archive: bytes


@dataclass
class FakeGitHub:
    """Serves one release's manifest and archive at their download URLs, and records the paths
    asked for."""

    release: Release
    tag: str
    requested: list[str] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requested.append(request.url.path)
        prefix = f"/DannyKuk/molecula/releases/download/{self.tag}/"
        if request.url.host != "github.com" or not request.url.path.startswith(prefix):
            return httpx2.Response(404)
        name = request.url.path.removeprefix(prefix)
        if name == MANIFEST:
            return httpx2.Response(200, content=self.release.manifest.model_dump_json())
        if name == ARCHIVE:
            return httpx2.Response(200, content=self.release.archive)
        return httpx2.Response(404)

    @property
    def archive_requests(self) -> list[str]:
        return [path for path in self.requested if path.endswith(ARCHIVE)]


@pytest.fixture(scope="module")
def release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """A store with one compound, its conformer and both indexes, exported as a release would
    be."""
    return built_release(tmp_path_factory, with_keywords=True)


@pytest.fixture(scope="module")
def release_before_44(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """A release made before the keyword index (#44), as store-2026-10-16 is."""
    return built_release(tmp_path_factory, with_keywords=False)


def built_release(tmp_path_factory: pytest.TempPathFactory, *, with_keywords: bool) -> Release:
    built = Settings(_env_file=None, data_dir=tmp_path_factory.mktemp("built"), offline=True)
    with closing(connect(built.db_path)) as conn:
        CompoundStore(conn).save(IMATINIB, [], datetime(2026, 10, 12, tzinfo=UTC))
    ConformerFiles(built.conformers_dir).write(5291, "imatinib\n$$$$\n")
    LabelIndex(built.index_dir).rebuild([CHUNK], [[1.0, 0.0]], MODEL)
    if with_keywords:
        KeywordIndex(built.keyword_index_path).rebuild([CHUNK])
    manifest = export_store(built, built.export_dir, datetime(2026, 10, 13, tzinfo=UTC))
    return Release(manifest, (built.export_dir / ARCHIVE).read_bytes())


@pytest.fixture(autouse=True)
def hub(monkeypatch: pytest.MonkeyPatch) -> FakeHub:
    return install_fake_hub(monkeypatch)


@pytest.fixture
def settings(make_settings: Callable[..., Settings], tmp_path: Path) -> Settings:
    return make_settings(data_dir=tmp_path / "data", offline=False)


def serve(release: Release, settings: Settings) -> FakeGitHub:
    return FakeGitHub(release, settings.store_release)


def fetch(settings: Settings, github: FakeGitHub, *, force: bool = False) -> int:
    return run(settings, force=force, transport=httpx2.MockTransport(github))


def with_archive(archive: bytes, manifest: StoreManifest) -> Release:
    return Release(
        manifest.model_copy(
            update={
                "archive_bytes": len(archive),
                "sha256": hashlib.sha256(archive).hexdigest(),
            }
        ),
        archive,
    )


def stored_compounds(settings: Settings) -> list[str]:
    with closing(sqlite3.connect(settings.db_path)) as conn:
        return [name for (name,) in conn.execute("SELECT name FROM compound")]


def leftovers(settings: Settings) -> list[str]:
    if not settings.build_dir.exists():
        return []
    return [path.name for path in settings.build_dir.iterdir() if path.name != "models"]


def test_fresh_clone_gets_the_store_and_the_model(
    release: Release, settings: Settings, hub: FakeHub
) -> None:
    github = serve(release, settings)

    assert fetch(settings, github) == 0

    assert stored_compounds(settings) == ["imatinib"]
    assert (settings.conformers_dir / "5291.sdf").exists()
    assert LabelIndex(settings.index_dir).model() == MODEL
    assert has_local_model(settings)
    assert [call["revision"] for call in hub.calls] == [settings.local_embedding_model_revision]
    assert sorted(leftovers(settings)) == ["index", "molecula.db", "structures"]


def test_release_keyword_index_is_unpacked(release: Release, settings: Settings) -> None:
    assert fetch(settings, serve(release, settings)) == 0

    found = KeywordIndex(settings.keyword_index_path).search("BCR-ABL", 5)
    assert [chunk.id for chunk, _ in found] == [CHUNK.id]


def test_keyword_index_missing_from_an_older_release_is_built_from_the_label_index(
    release_before_44: Release, settings: Settings
) -> None:
    assert fetch(settings, serve(release_before_44, settings)) == 0

    found = KeywordIndex(settings.keyword_index_path).search("BCR-ABL", 5)
    assert [chunk for chunk, _ in found] == [CHUNK]


def test_offline_setting_does_not_stop_the_download(
    release: Release, make_settings: Callable[..., Settings], tmp_path: Path, hub: FakeHub
) -> None:
    # OFFLINE only switches between local and cloud model calls; the data has to come once.
    offline = make_settings(data_dir=tmp_path / "data", offline=True)
    github = serve(release, offline)

    assert fetch(offline, github) == 0

    assert stored_compounds(offline) == ["imatinib"]
    assert github.archive_requests
    assert len(hub.calls) == 1
    assert has_local_model(offline)


def test_wrong_checksum_is_rejected_and_leaves_no_store(
    release: Release, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    tampered = Release(release.manifest.model_copy(update={"sha256": "0" * 64}), release.archive)

    assert fetch(settings, serve(tampered, settings)) == 1

    assert "SHA-256" in caplog.text
    assert not settings.db_path.exists()
    assert leftovers(settings) == []


def test_archive_larger_than_the_manifest_says_is_rejected(
    release: Release, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    short = release.manifest.model_copy(update={"archive_bytes": 100})

    assert fetch(settings, serve(Release(short, release.archive), settings)) == 1

    assert "larger than the 100 bytes" in caplog.text
    assert leftovers(settings) == []


def test_other_schema_version_is_rejected_before_the_download(
    release: Release, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    newer = release.manifest.model_copy(update={"schema_version": SCHEMA_VERSION + 1})
    github = serve(Release(newer, release.archive), settings)

    assert fetch(settings, github) == 1

    assert f"schema version {SCHEMA_VERSION + 1}" in caplog.text
    assert github.archive_requests == []
    assert not settings.db_path.exists()


def test_index_of_another_embedding_model_is_refused(
    release: Release, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    other = release.manifest.model_copy(update={"embedding_model": "BAAI/bge-small-en-v1.5"})
    github = serve(Release(other, release.archive), settings)

    assert fetch(settings, github) == 1

    assert "built with BAAI/bge-small-en-v1.5" in caplog.text
    assert github.archive_requests == []


def test_missing_release_says_which_url_failed(
    release: Release,
    make_settings: Callable[..., Settings],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    current = make_settings(
        data_dir=tmp_path / "data", offline=False, store_release="store-2000-01-01"
    )
    github = FakeGitHub(release, "store-2026-10-17")

    assert fetch(current, github) == 1

    assert "store-2000-01-01/manifest.json could not be downloaded" in caplog.text
    assert not current.db_path.exists()


def test_existing_store_is_left_alone_without_force(
    release: Release, settings: Settings, hub: FakeHub
) -> None:
    with closing(connect(settings.db_path)):
        pass
    before = settings.db_path.read_bytes()
    github = serve(release, settings)

    assert fetch(settings, github) == 0

    assert github.requested == []
    assert settings.db_path.read_bytes() == before
    assert len(hub.calls) == 1


def test_force_replaces_the_store_and_says_local_updates_are_lost(
    release: Release, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with closing(connect(settings.db_path)):
        pass
    stale_index_file = settings.index_dir / "stale.bin"
    stale_index_file.parent.mkdir(parents=True)
    stale_index_file.write_bytes(b"old")
    journal = settings.build_dir / "molecula.db-journal"
    journal.write_bytes(b"old")

    assert fetch(settings, serve(release, settings), force=True) == 0

    assert "local updates" in caplog.text
    assert stored_compounds(settings) == ["imatinib"]
    assert not stale_index_file.exists()
    assert not journal.exists()


def test_present_model_is_not_downloaded_again(
    release: Release, settings: Settings, hub: FakeHub
) -> None:
    fetch(settings, serve(release, settings))
    settings.db_path.unlink()
    github = serve(release, settings)

    assert fetch(settings, github) == 0

    assert github.archive_requests
    assert len(hub.calls) == 1


def test_failed_model_download_fails_the_step(
    release: Release,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    install_fake_hub(monkeypatch, weights=b"tampered weights")

    assert fetch(settings, serve(release, settings)) == 1

    assert "The model was not fetched" in caplog.text
    assert stored_compounds(settings) == ["imatinib"]
    assert not has_local_model(settings)


def tar_with(member: tarfile.TarInfo, content: bytes = b"") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content) if member.isfile() else None)
    return buffer.getvalue()


def file_member(name: str) -> tarfile.TarInfo:
    return tarfile.TarInfo(name)


def link_member(name: str, kind: bytes, target: str) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.type = kind
    member.linkname = target
    return member


@pytest.mark.parametrize(
    "member",
    [
        file_member("../evil.txt"),
        file_member("structures/../../evil.txt"),
        file_member("/evil.txt"),
        file_member("."),
        file_member("models/evil.bin"),
        link_member("structures/link", tarfile.SYMTYPE, "../../evil.txt"),
        link_member("index/link", tarfile.LNKTYPE, "molecula.db"),
    ],
    ids=[
        "parent",
        "nested parent",
        "absolute",
        "current folder",
        "outside the store",
        "symlink",
        "hard link",
    ],
)
def test_unsafe_archive_member_is_rejected(
    release: Release,
    settings: Settings,
    tmp_path: Path,
    member: tarfile.TarInfo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    unsafe = with_archive(tar_with(member, b"evil"), release.manifest)

    assert fetch(settings, serve(unsafe, settings)) == 1

    assert "The archive holds" in caplog.text
    assert leftovers(settings) == []
    assert not (tmp_path / "evil.txt").exists()
    assert not (settings.data_dir / "evil.txt").exists()
    assert not (settings.models_dir / "evil.bin").exists()
