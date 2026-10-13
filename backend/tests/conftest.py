import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest

from molecula.config import Settings
from molecula.sources.http import SourceClient
from molecula.sources.pubchem import PubChemClient
from molecula.store.db import connect
from molecula.store.http_cache import HttpCache
from pubchem_replay import Replay

type Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    """Makes settings for a store in `tmp_path`, offline and blind to the developer's `.env`;
    keyword arguments override any field."""

    def make(**overrides: Any) -> Settings:
        return Settings(_env_file=None, **({"data_dir": tmp_path, "offline": True} | overrides))

    return make


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_path / "molecula.db")
    yield conn
    conn.close()


@pytest.fixture
def cache(conn: sqlite3.Connection) -> HttpCache:
    return HttpCache(conn)


@pytest.fixture
def replaying_client(cache: HttpCache) -> Callable[..., SourceClient]:
    """Makes a source client that answers from `handler` through the store's HTTP cache and
    retries without waiting."""

    def make(handler: Handler, *, offline: bool = False) -> SourceClient:
        return SourceClient(
            cache,
            offline=offline,
            transport=httpx2.MockTransport(handler),
            sleep=lambda _: None,
        )

    return make


@pytest.fixture
def pubchem(replaying_client: Callable[..., SourceClient]) -> Callable[..., PubChemClient]:
    """Makes a PubChem client that replays recorded responses through the store's HTTP cache."""

    def make(handler: Replay | None = None) -> PubChemClient:
        return PubChemClient(replaying_client(handler or Replay()))

    return make
