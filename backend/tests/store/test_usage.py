from datetime import UTC, datetime
from pathlib import Path

from molecula.schemas.stats import RequestRecord
from molecula.store.usage import UsageStore, connect_usage

STARTED = datetime(2026, 10, 21, 9, 30, tzinfo=UTC)


def test_round_trips_a_request(usage_store: UsageStore) -> None:
    request = RequestRecord(
        id="a",
        started_at=STARTED,
        model="openai/gpt-oss-20b",
        outcome="answered",
        latency_ms=4200,
        input_tokens=1200,
        output_tokens=300,
        cost_usd=0.0,
        tools=["search_labels", "search_labels"],
        category="overdose_emergency",
        step_limit_reached=True,
    )

    usage_store.add(request)

    assert usage_store.since(STARTED) == [request]


def test_since_leaves_out_earlier_requests(usage_store: UsageStore) -> None:
    for id_, hour in (("early", 8), ("late", 10)):
        usage_store.add(
            RequestRecord(
                id=id_,
                started_at=STARTED.replace(hour=hour),
                model=None,
                outcome="limited",
                latency_ms=0,
            )
        )

    assert [r.id for r in usage_store.since(STARTED)] == ["late"]


def test_the_usage_log_has_none_of_the_stores_tables(tmp_path: Path) -> None:
    conn = connect_usage(tmp_path / "runtime" / "usage.db")

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()

    assert tables == {"request"}
    assert version == 0


def test_reopening_keeps_the_requests(tmp_path: Path) -> None:
    path = tmp_path / "usage.db"
    conn = connect_usage(path)
    UsageStore(conn).add(
        RequestRecord(id="a", started_at=STARTED, model=None, outcome="stopped", latency_ms=5)
    )
    conn.close()

    conn = connect_usage(path)
    assert [r.id for r in UsageStore(conn).since(STARTED)] == ["a"]
    conn.close()
