import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock


@dataclass(frozen=True)
class CachedResponse:
    status: int
    content_type: str | None
    body: bytes


class HttpCache:
    """Raw source responses by request, so re-running an ingest step doesn't download again."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = Lock()

    def get(self, key: str) -> CachedResponse | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT status, content_type, body FROM http_cache WHERE key = ?", (key,)
            ).fetchone()
        return CachedResponse(*row) if row else None

    def put(self, key: str, url: str, response: CachedResponse) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO http_cache"
                " (key, url, status, content_type, body, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    url,
                    response.status,
                    response.content_type,
                    response.body,
                    datetime.now(UTC).isoformat(),
                ),
            )
