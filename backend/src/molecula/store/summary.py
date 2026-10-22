from dataclasses import dataclass
from datetime import datetime

from molecula.store.db import StoreConnection


@dataclass(frozen=True)
class StoreCounts:
    """Rows in the store's main tables, its schema version and the range of label fetches."""

    compounds: int
    labels: int
    label_sections: int
    targets: int
    schema_version: int
    labels_fetched_from: datetime | None
    labels_fetched_to: datetime | None


def count_store(conn: StoreConnection) -> StoreCounts:
    def rows(table: str) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    with conn.lock:
        oldest, newest = conn.execute(
            "SELECT MIN(fetched_at), MAX(fetched_at) FROM label"
        ).fetchone()
        return StoreCounts(
            compounds=rows("compound"),
            labels=rows("label"),
            label_sections=rows("label_section"),
            targets=rows("target"),
            schema_version=conn.execute("PRAGMA user_version").fetchone()[0],
            labels_fetched_from=datetime.fromisoformat(oldest) if oldest else None,
            labels_fetched_to=datetime.fromisoformat(newest) if newest else None,
        )
