from collections.abc import Sequence
from datetime import datetime
from typing import Any

from langchain_core.embeddings import Embeddings

from molecula.schemas.retrieval import LabelFilter, Retrieval, RetrievedChunk, Widening
from molecula.store.index import Chunk, LabelIndex

# The labels go first: the section groups say what the question asks, a brand only which
# product the user has, and another label of the same drug can still answer it.
WIDENINGS: tuple[Widening, ...] = ("labels", "section_groups")


class LabelRetriever:
    """Similarity search over the label chunks, narrowed by a checked `LabelFilter`.

    The `top_k` closest chunks are candidates; those scoring below `min_score` are dropped but
    still returned, so the retrieval trace can show them.
    """

    def __init__(
        self, index: LabelIndex, embeddings: Embeddings, *, top_k: int, min_score: float
    ) -> None:
        self._index = index
        self._embeddings = embeddings
        self._top_k = top_k
        self._min_score = min_score

    def retrieve(self, question: str, label_filter: LabelFilter | None = None) -> Retrieval:
        """The label chunks for `question`. A filter that names only drugs without searchable
        labels (unsupported, or no US label) finds nothing rather than other drugs' text.

        When the full filter finds nothing, the search widens: first to every label of the
        named drugs, then to every section. "Side effects of Advil" narrows to the OTC label,
        whose Drug Facts have no adverse reactions section, so it falls back to the
        prescription label's.
        """
        if label_filter is not None and label_filter.names_drugs and not label_filter.set_ids:
            return Retrieval(question=question, filter=label_filter, chunks=[], dropped=[])
        vector = self._embeddings.embed_query(question)
        widened: list[Widening] = []
        found = self._index.search(vector, self._top_k, where_clause(label_filter))
        for step in WIDENINGS:
            if found or label_filter is None:
                break
            if where_clause(label_filter, [*widened, step]) == where_clause(label_filter, widened):
                continue
            widened.append(step)
            found = self._index.search(vector, self._top_k, where_clause(label_filter, widened))
        candidates = [retrieved(chunk, score) for chunk, score in found]
        return Retrieval(
            question=question,
            filter=label_filter,
            chunks=[c for c in candidates if c.score >= self._min_score],
            dropped=[c for c in candidates if c.score < self._min_score],
            widened=widened,
        )


def where_clause(
    label_filter: LabelFilter | None, widened: Sequence[Widening] = ()
) -> dict[str, Any] | None:
    """The ChromaDB filter, with the `widened` parts given up; None searches the whole index.
    Named drugs are already narrowed to their labels of the product type, so the type only
    applies on its own."""
    if label_filter is None:
        return None
    conditions: list[dict[str, Any]] = []
    if label_filter.drugs:
        if "labels" in widened and any(drug.narrowed for drug in label_filter.drugs):
            conditions.append({"cid": {"$in": [drug.cid for drug in label_filter.drugs]}})
        else:
            conditions.append({"set_id": {"$in": label_filter.set_ids}})
    elif label_filter.product_type and "labels" not in widened:
        conditions.append({"product_type": label_filter.product_type})
    if label_filter.section_groups and "section_groups" not in widened:
        conditions.append({"section_group": {"$in": label_filter.section_groups}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def retrieved(chunk: Chunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk.id,
        text=chunk.text,
        score=score,
        cid=chunk.cid,
        substance=chunk.substance,
        brand=chunk.brand,
        product_type=chunk.product_type,
        section=chunk.section,
        section_group=chunk.section_group,
        sensitive=chunk.sensitive,
        set_id=chunk.set_id,
        effective_time=datetime.strptime(chunk.effective_time, "%Y%m%d").date(),
        url=chunk.url,
    )
