from dataclasses import replace

import pytest

from molecula.rag.chunking import CHUNK_TOKENS, MIN_REMAINDER_TOKENS, chunk_labels
from molecula.schemas.retrieval import Chunk
from molecula.store.labels import LabelRecord, LabelSection

IMATINIB_CID = 5291
IBUPROFEN_CID = 3672


def words(text: str) -> int:
    """A stand-in tokenizer: one token per word."""
    return len(text.split())


def sentences(prefix: str, count: int) -> str:
    """`count` ten-word sentences, each one distinct."""
    return " ".join(
        f"{prefix} sentence {n} says this about the drug label text." for n in range(count)
    )


MECHANISM = "12.1 Mechanism of Action Imatinib inhibits the BCR-ABL tyrosine kinase."
PHARMACOKINETICS = "12.3 Pharmacokinetics " + sentences("Absorption", 3)
GLEEVEC = LabelRecord(
    set_id="gleevec",
    substance="IMATINIB MESYLATE",
    brand="Gleevec",
    product_type="rx",
    effective_time="20260713",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    sections=(
        LabelSection("indications_and_usage", "indications", "1 INDICATIONS Ph+ CML.", False),
        LabelSection("dosage_and_administration", "dosing", sentences("Dose", 120), True),
        LabelSection(
            "clinical_pharmacology",
            "pharmacology",
            f"12 CLINICAL PHARMACOLOGY {MECHANISM} {PHARMACOKINETICS}",
            False,
        ),
        LabelSection("mechanism_of_action", "pharmacology", MECHANISM, False),
    ),
)
ADVIL = LabelRecord(
    set_id="advil",
    substance="IBUPROFEN",
    brand=None,
    product_type="otc",
    effective_time="20260820",
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=advil",
    sections=(
        LabelSection("do_not_use", "otc_consumer", "Do not use right before heart surgery.", False),
        LabelSection(
            "warnings",
            "warnings",
            "Warnings Allergy alert: ibuprofen may cause a severe allergic reaction. "
            "Do not use right before heart surgery.",
            False,
        ),
    ),
)


def by_section(chunks: list[Chunk], section: str) -> list[Chunk]:
    return [chunk for chunk in chunks if chunk.section == section]


@pytest.fixture
def chunks() -> list[Chunk]:
    return chunk_labels([(IMATINIB_CID, GLEEVEC), (IBUPROFEN_CID, ADVIL)], words)


def test_short_sections_stay_whole(chunks: list[Chunk]) -> None:
    assert [chunk.text for chunk in by_section(chunks, "indications_and_usage")] == [
        "1 INDICATIONS Ph+ CML."
    ]


def test_long_section_is_split_within_the_token_limit_with_overlap(chunks: list[Chunk]) -> None:
    dosing = by_section(chunks, "dosage_and_administration")

    assert len(dosing) == 3
    assert all(words(chunk.text) <= CHUNK_TOKENS for chunk in dosing)
    first_end = dosing[0].text.split(". ")[-2]
    assert first_end in dosing[1].text


def test_no_chunk_crosses_a_section_boundary(chunks: list[Chunk]) -> None:
    texts = {
        (label.set_id, section.section): " ".join(section.text.split())
        for label in (GLEEVEC, ADVIL)
        for section in label.sections
    }

    assert all(chunk.text in texts[chunk.set_id, chunk.section] for chunk in chunks)


def test_chunk_carries_the_label_metadata_and_the_sensitive_flag(chunks: list[Chunk]) -> None:
    dosing = by_section(chunks, "dosage_and_administration")[0]

    assert dosing == Chunk(
        id="gleevec:dosage_and_administration:0",
        text=dosing.text,
        cid=IMATINIB_CID,
        substance="IMATINIB MESYLATE",
        brand="Gleevec",
        product_type="rx",
        section="dosage_and_administration",
        section_group="dosing",
        sensitive=True,
        set_id="gleevec",
        effective_time="20260713",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    )
    assert all(getattr(chunk, field) != "" for chunk in chunks for field in Chunk.model_fields)
    assert {chunk.sensitive for chunk in chunks if chunk.section_group != "dosing"} == {False}


def test_ids_are_unique_and_stable(chunks: list[Chunk]) -> None:
    again = chunk_labels([(IMATINIB_CID, GLEEVEC), (IBUPROFEN_CID, ADVIL)], words)

    assert len({chunk.id for chunk in chunks}) == len(chunks)
    assert again == chunks


def test_repeated_text_is_indexed_once_under_the_more_specific_section(
    chunks: list[Chunk],
) -> None:
    pharmacology = by_section(chunks, "clinical_pharmacology")

    assert [chunk.text for chunk in by_section(chunks, "mechanism_of_action")] == [MECHANISM]
    assert [chunk.text for chunk in pharmacology] == [PHARMACOKINETICS]
    assert not any("BCR-ABL" in chunk.text for chunk in pharmacology)


def test_heading_left_after_cutting_out_a_repeat_is_dropped(chunks: list[Chunk]) -> None:
    assert words("12 CLINICAL PHARMACOLOGY") < MIN_REMAINDER_TOKENS
    assert not any(chunk.text == "12 CLINICAL PHARMACOLOGY" for chunk in chunks)


def test_repeats_across_section_groups_stay_in_both(chunks: list[Chunk]) -> None:
    # Retrieval filters on the group: an OTC question about warnings must still find the text.
    surgery = "Do not use right before heart surgery."

    assert any(surgery in chunk.text for chunk in by_section(chunks, "do_not_use"))
    assert any(surgery in chunk.text for chunk in by_section(chunks, "warnings"))


def test_of_two_identical_sections_the_first_keeps_the_text() -> None:
    twin = LabelSection("pharmacodynamics", "pharmacology", MECHANISM, False)
    label = replace(GLEEVEC, sections=(*GLEEVEC.sections, twin))

    chunks = chunk_labels([(IMATINIB_CID, label)], words)

    assert by_section(chunks, "pharmacodynamics") == []
    assert len(by_section(chunks, "mechanism_of_action")) == 1


def test_whitespace_is_collapsed() -> None:
    section = LabelSection("indications_and_usage", "indications", "1 INDICATIONS\n\n  CML ", False)
    label = replace(GLEEVEC, sections=(section,))

    assert [chunk.text for chunk in chunk_labels([(IMATINIB_CID, label)], words)] == [
        "1 INDICATIONS CML"
    ]
