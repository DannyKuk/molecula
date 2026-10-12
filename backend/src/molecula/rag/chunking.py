import re
from collections.abc import Callable, Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

from molecula.store.index import Chunk
from molecula.store.labels import LabelRecord, LabelSection

type CountTokens = Callable[[str], int]

# Measured with the bge tokenizer: 500 tokens plus [CLS], [SEP] and a short prefix such as
# nomic's "search_document: " stay within the 512 tokens BERT-sized models read.
CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50
# What is left of a section once the sections it repeats are cut out is often only its heading
# ("12 CLINICAL PHARMACOLOGY"); such scraps are not worth a chunk.
MIN_REMAINDER_TOKENS = 10


def chunk_labels(
    labels: Sequence[tuple[int, LabelRecord]], count_tokens: CountTokens
) -> list[Chunk]:
    """Every label's sections as chunks, in label and section order."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_TOKENS,
        chunk_overlap=OVERLAP_TOKENS,
        length_function=count_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator="end",
    )
    return [
        chunk
        for cid, label in labels
        for chunk in chunk_label(cid, label, splitter.split_text, count_tokens)
    ]


def chunk_label(
    cid: int,
    label: LabelRecord,
    split: Callable[[str], list[str]],
    count_tokens: CountTokens,
) -> list[Chunk]:
    """Split each section on its own, so no chunk mixes two sections.

    Text one section repeats from another of the same group is indexed once, under the more
    specific section: clinical_pharmacology repeats mechanism_of_action and pharmacodynamics.
    """
    texts = [normalize(section.text) for section in label.sections]
    chunks = []
    for position, section in enumerate(label.sections):
        repeated = [
            other_text
            for other_position, (other, other_text) in enumerate(
                zip(label.sections, texts, strict=True)
            )
            if other.section_group == section.section_group
            and repeats(texts[position], other_text, other_comes_first=other_position < position)
        ]
        parts = cut_out(texts[position], repeated)
        if repeated:
            parts = [part for part in parts if count_tokens(part) >= MIN_REMAINDER_TOKENS]
        pieces = [piece for part in parts for piece in split(part)]
        chunks.extend(
            to_chunk(cid, label, section, number, text) for number, text in enumerate(pieces)
        )
    return chunks


def repeats(text: str, other_text: str, other_comes_first: bool) -> bool:
    """Whether `text` contains the other section's text, which is then indexed under the other.

    Of two identical sections, the first one keeps the text; a section never repeats itself.
    """
    if not other_text or other_text not in text:
        return False
    return len(other_text) < len(text) or other_comes_first


def cut_out(text: str, repeated: list[str]) -> list[str]:
    if not repeated:
        return [text]
    longest_first = sorted(repeated, key=len, reverse=True)
    pattern = "|".join(re.escape(part) for part in longest_first)
    return [part.strip() for part in re.split(pattern, text) if part.strip()]


def normalize(text: str) -> str:
    return " ".join(text.split())


def to_chunk(cid: int, label: LabelRecord, section: LabelSection, number: int, text: str) -> Chunk:
    return Chunk(
        id=f"{label.set_id}:{section.section}:{number}",
        text=text,
        cid=cid,
        substance=label.substance,
        brand=label.brand,
        product_type=label.product_type,
        section=section.section,
        section_group=section.section_group,
        sensitive=section.sensitive,
        set_id=label.set_id,
        effective_time=label.effective_time,
        url=label.url,
    )
