import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import pytest

from molecula.sources.http import SourceClient
from molecula.sources.pubchem import PubChemClient
from molecula.store.db import connect
from molecula.store.http_cache import HttpCache
from pubchem_replay import Replay


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_path / "molecula.db")
    yield conn
    conn.close()


@pytest.fixture
def cache(conn: sqlite3.Connection) -> HttpCache:
    return HttpCache(conn)


@pytest.fixture
def pubchem(cache: HttpCache) -> Callable[..., PubChemClient]:
    """Makes a PubChem client that replays recorded responses through the store's HTTP cache."""

    def make(handler: Replay | None = None) -> PubChemClient:
        http = SourceClient(
            cache,
            offline=False,
            transport=httpx2.MockTransport(handler or Replay()),
            sleep=lambda _: None,
        )
        return PubChemClient(http)

    return make
