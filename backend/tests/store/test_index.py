import re
from pathlib import Path

import pytest

from molecula.schemas.retrieval import Chunk
from molecula.store.index import IndexModelMismatch, LabelIndex, to_metadata

MODEL = "BAAI/bge-small-en-v1.5"
MECHANISM = Chunk(
    id="gleevec:mechanism_of_action:0",
    text="Imatinib inhibits the BCR-ABL tyrosine kinase.",
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
PURPOSE = MECHANISM.model_copy(
    update={
        "id": "advil:purpose:0",
        "text": "Pain reliever/fever reducer",
        "cid": 3672,
        "substance": "IBUPROFEN",
        "brand": None,
        "product_type": "otc",
        "section": "purpose",
        "section_group": "otc_consumer",
        "set_id": "advil",
    }
)


@pytest.fixture
def index(tmp_path: Path) -> LabelIndex:
    return LabelIndex(tmp_path / "chroma")


def test_round_trips_chunks_with_their_metadata(index: LabelIndex) -> None:
    index.rebuild([PURPOSE, MECHANISM], [[0.0, 1.0], [1.0, 0.0]], MODEL)

    assert index.chunks() == [PURPOSE, MECHANISM]


def test_label_without_a_brand_keeps_none(index: LabelIndex) -> None:
    index.rebuild([PURPOSE], [[0.0, 1.0]], MODEL)

    assert index.chunks()[0].brand is None


def test_rebuild_replaces_the_whole_index(index: LabelIndex) -> None:
    index.rebuild([PURPOSE, MECHANISM], [[0.0, 1.0], [1.0, 0.0]], MODEL)
    index.rebuild([MECHANISM], [[1.0, 0.0]], MODEL)

    assert index.chunks() == [MECHANISM]


def test_index_persists_on_disk(tmp_path: Path) -> None:
    LabelIndex(tmp_path / "chroma").rebuild([MECHANISM], [[1.0, 0.0]], MODEL)

    assert LabelIndex(tmp_path / "chroma").chunks() == [MECHANISM]


def test_empty_before_the_first_build(index: LabelIndex) -> None:
    assert index.chunks() == []
    assert index.model() is None


def test_records_the_model_it_was_built_with(index: LabelIndex) -> None:
    index.rebuild([MECHANISM], [[1.0, 0.0]], MODEL)

    assert index.model() == MODEL
    index.check_model(MODEL)


def test_another_model_is_refused(index: LabelIndex) -> None:
    index.rebuild([MECHANISM], [[1.0, 0.0]], MODEL)

    with pytest.raises(IndexModelMismatch, match=re.escape("built with BAAI/bge-small-en-v1.5")):
        index.check_model("nomic-ai/nomic-embed-text-v1.5")


def test_chunks_and_vectors_must_match_in_number(index: LabelIndex) -> None:
    with pytest.raises(ValueError, match="2 chunks but 1 vectors"):
        index.rebuild([PURPOSE, MECHANISM], [[1.0, 0.0]], MODEL)


def test_empty_index_leaves_nothing_of_the_previous_build(tmp_path: Path) -> None:
    leftover = tmp_path / "chroma" / "old-segment" / "data_level0.bin"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"old vectors")

    index = LabelIndex.empty(tmp_path / "chroma")

    assert not leftover.parent.exists()
    assert index.chunks() == []


def test_search_ranks_by_cosine_similarity(index: LabelIndex) -> None:
    index.rebuild([PURPOSE, MECHANISM], [[0.0, 1.0], [1.0, 0.0]], MODEL)

    found = index.search([1.0, 0.0], n=2)

    assert [chunk for chunk, _ in found] == [MECHANISM, PURPOSE]
    assert [round(score, 6) for _, score in found] == [1.0, 0.0]


def test_search_keeps_only_chunks_matching_the_filter(index: LabelIndex) -> None:
    index.rebuild([PURPOSE, MECHANISM], [[0.0, 1.0], [1.0, 0.0]], MODEL)

    found = index.search([1.0, 0.0], n=2, where={"product_type": "otc"})

    assert [chunk for chunk, _ in found] == [PURPOSE]


def test_search_before_the_first_build_finds_nothing(index: LabelIndex) -> None:
    assert index.search([1.0, 0.0], n=5) == []


def test_replace_drug_swaps_one_compounds_chunks_and_keeps_the_others(index: LabelIndex) -> None:
    old_extra = MECHANISM.model_copy(
        update={"id": "gleevec:mechanism_of_action:1", "text": "Old second chunk."}
    )
    index.rebuild([MECHANISM, old_extra, PURPOSE], [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], MODEL)
    newer = MECHANISM.model_copy(
        update={"text": "Imatinib also inhibits KIT.", "effective_time": "20261101"}
    )

    index.replace_drug(5291, [newer], [[0.9, 0.1]])

    assert index.chunks() == [PURPOSE, newer]
    assert index.vectors([newer.id]) == {newer.id: pytest.approx([0.9, 0.1])}


def test_replace_drug_without_chunks_removes_the_compound(index: LabelIndex) -> None:
    index.rebuild([MECHANISM, PURPOSE], [[1.0, 0.0], [0.0, 1.0]], MODEL)

    index.replace_drug(5291, [], [])

    assert index.chunks() == [PURPOSE]


def test_the_metadata_is_every_field_but_the_id_and_text_and_leaves_out_a_missing_brand() -> None:
    assert to_metadata(PURPOSE) == {
        "cid": 3672,
        "substance": "IBUPROFEN",
        "product_type": "otc",
        "section": "purpose",
        "section_group": "otc_consumer",
        "sensitive": False,
        "set_id": "advil",
        "effective_time": "20260713",
        "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    }
