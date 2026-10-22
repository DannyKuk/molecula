import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from molecula.schemas.retrieval import Chunk
from molecula.services.knowledge_base import KnowledgeBase
from molecula.store.compounds import CompoundStore
from molecula.store.index import LabelIndex
from molecula.store.labels import LabelStore
from molecula.store.schema import SCHEMA_VERSION
from molecula.store.structures import ComplexFiles, ConformerFiles
from store_records import GLEEVEC, IMATINIB, MOTRIN, compound_record

GLEEVEC_FETCHED = datetime(2026, 10, 12, 8, 45, tzinfo=UTC)
MOTRIN_FETCHED = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


def chunk(id_: str) -> Chunk:
    return Chunk(
        id=id_,
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
        url=GLEEVEC.url,
    )


def knowledge_base(
    conn: sqlite3.Connection, tmp_path: Path, index: LabelIndex | None
) -> KnowledgeBase:
    return KnowledgeBase(
        conn,
        index,
        ConformerFiles(tmp_path / "structures" / "compounds"),
        ComplexFiles(tmp_path / "structures" / "complexes"),
    )


def test_counts_what_the_store_holds(conn: sqlite3.Connection, tmp_path: Path) -> None:
    CompoundStore(conn).save(IMATINIB, [], GLEEVEC_FETCHED)
    CompoundStore(conn).save(compound_record(3672, "ibuprofen"), [], MOTRIN_FETCHED)
    LabelStore(conn).save(5291, (GLEEVEC,), GLEEVEC_FETCHED)
    LabelStore(conn).save(3672, (MOTRIN,), MOTRIN_FETCHED)
    index = LabelIndex(tmp_path / "index")
    index.rebuild([chunk("a"), chunk("b"), chunk("c")], [[1.0, 0.0]] * 3, "fake-model")
    ConformerFiles(tmp_path / "structures" / "compounds").write(5291, "imatinib\n$$$$\n")
    ConformerFiles(tmp_path / "structures" / "compounds").write(3672, "ibuprofen\n$$$$\n")
    ComplexFiles(tmp_path / "structures" / "complexes").write(5291, "{}")

    stats = knowledge_base(conn, tmp_path, index).stats()

    assert stats.drugs == 2
    assert stats.labels == 2
    assert stats.label_sections == len(GLEEVEC.sections) + len(MOTRIN.sections)
    assert stats.chunks == 3
    assert stats.targets == 0
    assert (stats.conformers, stats.complexes) == (2, 1)
    assert stats.schema_version == SCHEMA_VERSION
    assert (stats.labels_fetched_from, stats.labels_fetched_to) == (GLEEVEC_FETCHED, MOTRIN_FETCHED)


def test_an_empty_store_without_an_index_gives_zeros(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    stats = knowledge_base(conn, tmp_path, None).stats()

    counts = (stats.drugs, stats.labels, stats.chunks, stats.conformers, stats.complexes)
    assert counts == (0, 0, 0, 0, 0)
    assert stats.labels_fetched_from is None and stats.labels_fetched_to is None
