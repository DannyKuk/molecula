from collections.abc import Sequence
from typing import Any

from langchain_core.embeddings import Embeddings

from molecula.schemas.retrieval import LabelFilter, Retrieval, RetrievedChunk, Widening
from molecula.store.index import Chunk, LabelIndex
from molecula.store.labels import label_date


class LabelRetriever:
    """Similarity search over the label chunks, narrowed by a checked `LabelFilter`.

    The drugs, their labels and the product type narrow the search; the section groups only
    rank it. A chunk in one of the filter's groups counts `section_group_boost` higher, so a
    wrong group the chat model picks still leaves the drug's other sections in reach. The
    `top_k` best chunks are candidates; those whose own score is below `min_score` are dropped
    but still returned, so the retrieval trace can show them.

    A filter with several drugs searches each drug on its own and keeps its `top_k` best
    chunks, so a drug whose label matches the question better can't crowd out the others (#255).
    """

    def __init__(
        self,
        index: LabelIndex,
        embeddings: Embeddings,
        *,
        top_k: int,
        min_score: float,
        section_group_boost: float,
    ) -> None:
        self._index = index
        self._embeddings = embeddings
        self._top_k = top_k
        self._min_score = min_score
        self._section_group_boost = section_group_boost

    def retrieve(self, question: str, label_filter: LabelFilter | None = None) -> Retrieval:
        """The label chunks for `question`. A filter that names only drugs without searchable
        labels (unsupported, or no US label) finds nothing rather than other drugs' text.

        When none of the labels the filter narrows to has the section groups, the search widens
        to every label of the named drugs (or any product type). "Side effects of Advil"
        narrows to the OTC label, whose Drug Facts have no adverse reactions section, so it
        falls back to the prescription label's.
        """
        if label_filter is not None and label_filter.names_drugs and not label_filter.set_ids:
            return Retrieval(question=question, filter=label_filter, chunks=[], dropped=[])
        vector = self._embeddings.embed_query(question)
        candidates, widened = self._candidates(vector, label_filter)
        return Retrieval(
            question=question,
            filter=label_filter,
            chunks=[c for c in candidates if c.score >= self._min_score],
            dropped=[c for c in candidates if c.score < self._min_score],
            widened=widened,
        )

    def _candidates(
        self, vector: list[float], label_filter: LabelFilter | None
    ) -> tuple[list[RetrievedChunk], list[Widening]]:
        """The best chunks under the filter, or the best chunks of each drug it names."""
        searched = [drug for drug in label_filter.drugs if drug.set_ids] if label_filter else []
        if label_filter is None or len(searched) < 2:
            found, widened = self._search_widening(vector, label_filter)
            return self._ranked(found, label_filter, self._top_k), widened
        candidates: list[RetrievedChunk] = []
        widenings: set[Widening] = set()
        for drug in searched:
            one_drug = label_filter.model_copy(update={"drugs": [drug]})
            found, widened = self._search_widening(vector, one_drug)
            candidates += self._ranked(found, one_drug, self._top_k)
            widenings.update(widened)
        candidates.sort(key=self._ranking_score, reverse=True)
        return candidates, sorted(widenings)

    def _search_widening(
        self, vector: list[float], label_filter: LabelFilter | None
    ) -> tuple[list[tuple[Chunk, float]], list[Widening]]:
        """The search under the filter, or under every label of its drugs when that finds the
        section groups and the narrower labels don't. A brand's label with text in other
        sections is kept when no label of the drug has the groups either."""
        found = self._search(vector, label_filter, [])
        if label_filter is None or in_groups(found, label_filter):
            return found, []
        if where_clause(label_filter, ["labels"]) == where_clause(label_filter):
            return found, []
        wider = self._search(vector, label_filter, ["labels"])
        if in_groups(wider, label_filter) or not found:
            return wider, ["labels"]
        return found, []

    def _search(
        self, vector: list[float], label_filter: LabelFilter | None, widened: list[Widening]
    ) -> list[tuple[Chunk, float]]:
        """The closest chunks in the filter's section groups and in every section, together."""
        found = self._index.search(vector, self._top_k, where_clause(label_filter, widened))
        if label_filter is None or not label_filter.section_groups:
            return found
        grouped = self._index.search(
            vector, self._top_k, where_clause(label_filter, widened, section_groups=True)
        )
        return list({chunk.id: (chunk, score) for chunk, score in [*grouped, *found]}.values())

    def _ranked(
        self, found: list[tuple[Chunk, float]], label_filter: LabelFilter | None, limit: int
    ) -> list[RetrievedChunk]:
        groups = label_filter.section_groups if label_filter else []
        chunks = [retrieved(chunk, score, chunk.section_group in groups) for chunk, score in found]
        chunks.sort(key=self._ranking_score, reverse=True)
        return chunks[:limit]

    def _ranking_score(self, chunk: RetrievedChunk) -> float:
        return chunk.score + (self._section_group_boost if chunk.in_section_groups else 0.0)


def in_groups(found: list[tuple[Chunk, float]], label_filter: LabelFilter) -> bool:
    """Whether the search found a chunk in the filter's section groups; without groups, any."""
    if not label_filter.section_groups:
        return bool(found)
    return any(chunk.section_group in label_filter.section_groups for chunk, _ in found)


def where_clause(
    label_filter: LabelFilter | None,
    widened: Sequence[Widening] = (),
    *,
    section_groups: bool = False,
) -> dict[str, Any] | None:
    """The ChromaDB filter, with the `widened` parts given up; None searches the whole index.
    Named drugs are already narrowed to their labels of the product type, so the type only
    applies on its own. The section groups narrow only when `section_groups` is set."""
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
    if section_groups and label_filter.section_groups:
        conditions.append({"section_group": {"$in": label_filter.section_groups}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def retrieved(chunk: Chunk, score: float, in_section_groups: bool = False) -> RetrievedChunk:
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
        effective_time=label_date(chunk.effective_time),
        url=chunk.url,
        in_section_groups=in_section_groups,
    )
