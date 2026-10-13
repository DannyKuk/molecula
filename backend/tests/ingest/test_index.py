from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from molecula.config import Settings
from molecula.ingest.index import build_index, run
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import LabelIndex
from molecula.store.labels import LabelSection, LabelStore
from store_records import GLEEVEC, IMATINIB

FETCHED_AT = datetime(2026, 10, 12, tzinfo=UTC)
GLEEVEC_WITH_LONG_DOSING = replace(
    GLEEVEC,
    sections=(
        LabelSection("indications_and_usage", "indications", "1 INDICATIONS Ph+ CML.", False),
        LabelSection(
            "dosage_and_administration",
            "dosing",
            " ".join(f"Dose sentence {n} of the label." for n in range(300)),
            True,
        ),
    ),
)


def words(text: str) -> int:
    return len(text.split())


class FakeTokenizer:
    def tokenize(self, text: str) -> list[str]:
        return text.split()


def store_labels(settings: Settings) -> None:
    conn = connect(settings.db_path)
    CompoundStore(conn).save(IMATINIB, [], FETCHED_AT)
    LabelStore(conn).save(5291, (GLEEVEC_WITH_LONG_DOSING,), FETCHED_AT)
    conn.close()


def test_build_indexes_every_chunk_with_the_model_name(tmp_path: Path) -> None:
    index = LabelIndex(tmp_path / "chroma")

    chunks = build_index(
        [(5291, GLEEVEC_WITH_LONG_DOSING)], words, DeterministicFakeEmbedding(size=8), index, "fake"
    )

    assert len(chunks) > 2
    assert index.chunks() == sorted(chunks, key=lambda chunk: chunk.id)
    assert index.model() == "fake"


def test_rebuilding_gives_the_same_chunks(tmp_path: Path) -> None:
    index = LabelIndex(tmp_path / "chroma")
    embeddings = DeterministicFakeEmbedding(size=8)

    build_index([(5291, GLEEVEC_WITH_LONG_DOSING)], words, embeddings, index, "fake")
    first = index.chunks()
    build_index([(5291, GLEEVEC_WITH_LONG_DOSING)], words, embeddings, index, "fake")

    assert index.chunks() == first


def test_step_builds_the_index_from_the_store(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_labels(settings)
    monkeypatch.setattr("molecula.rag.embeddings.load_chunk_tokenizer", lambda _: FakeTokenizer())

    def fake_embeddings(current: Settings) -> Any:
        return DeterministicFakeEmbedding(size=8)

    monkeypatch.setattr("molecula.rag.embeddings.get_embeddings", fake_embeddings)

    assert run(settings) == 0

    index = LabelIndex(settings.index_dir)
    assert {chunk.section for chunk in index.chunks()} == {
        "indications_and_usage",
        "dosage_and_administration",
    }
    assert index.model() == "BAAI/bge-m3"


def test_step_without_labels_fails_with_a_hint(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    assert run(settings) == 1
    assert "run `python -m molecula.ingest labels` first" in caplog.text
