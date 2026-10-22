from threading import Thread

from molecula.store.db import StoreConnection
from molecula.store.summary import StoreCounts, count_store


def test_an_empty_store_counts_nothing(conn: StoreConnection) -> None:
    counts = count_store(conn)

    assert (counts.compounds, counts.labels, counts.label_sections, counts.targets) == (0, 0, 0, 0)
    assert counts.labels_fetched_from is None
    assert counts.labels_fetched_to is None


def test_counting_waits_for_the_connection_lock(conn: StoreConnection) -> None:
    counted: list[StoreCounts] = []
    counting = Thread(target=lambda: counted.append(count_store(conn)))

    with conn.lock:
        counting.start()
        counting.join(timeout=0.2)
        assert counting.is_alive()
        assert counted == []

    counting.join(timeout=5)
    assert len(counted) == 1
