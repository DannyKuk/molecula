import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from molecula.api import dependencies
from molecula.main import app
from molecula.schemas.stats import RequestRecord
from molecula.services.knowledge_base import KnowledgeBase
from molecula.services.usage import UsageLog
from molecula.store.compounds import CompoundStore
from molecula.store.structures import ComplexFiles, ConformerFiles
from molecula.store.usage import UsageStore
from store_records import IMATINIB

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def client(
    conn: sqlite3.Connection, usage_store: UsageStore, tmp_path: Path
) -> Iterator[TestClient]:
    knowledge_base = KnowledgeBase(
        conn, None, ConformerFiles(tmp_path / "compounds"), ComplexFiles(tmp_path / "complexes")
    )
    usage_log = UsageLog(usage_store, "openai/gpt-oss-20b", now=lambda: NOW)
    app.dependency_overrides[dependencies.knowledge_base] = lambda: knowledge_base
    app.dependency_overrides[dependencies.usage_log] = lambda: usage_log
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_stats_hold_the_knowledge_base_and_the_usage(
    client: TestClient, conn: sqlite3.Connection, usage_store: UsageStore
) -> None:
    CompoundStore(conn).save(IMATINIB, [], NOW)
    usage_store.add(
        RequestRecord(
            id="a",
            started_at=NOW,
            model="openai/gpt-oss-20b",
            outcome="answered",
            latency_ms=4000,
            input_tokens=900,
            output_tokens=100,
            cost_usd=0.0,
            tools=["search_labels"],
            category="ok",
            step_limit_reached=False,
        )
    )

    stats = client.get("/stats", params={"days": 2}).json()

    assert stats["knowledge_base"]["drugs"] == 1
    assert [day["date"] for day in stats["usage"]["days"]] == ["2026-10-20", "2026-10-21"]
    assert stats["usage"]["days"][1]["outcomes"] == {"answered": 1}
    assert stats["usage"]["days"][1]["latency_p95_ms"] == 4000
    assert stats["usage"]["tool_calls"] == {"search_labels": 1}
    assert stats["usage"]["categories"] == {"ok": 1}


def test_an_empty_usage_log_gives_zeros(client: TestClient) -> None:
    stats = client.get("/stats").json()

    assert len(stats["usage"]["days"]) == 30
    assert {day["requests"] for day in stats["usage"]["days"]} == {0}
    assert stats["usage"]["errors"] == {}
    assert stats["knowledge_base"]["drugs"] == 0


@pytest.mark.parametrize("days", [0, 366])
def test_days_outside_one_to_a_year_are_refused(client: TestClient, days: int) -> None:
    assert client.get("/stats", params={"days": days}).status_code == 422
