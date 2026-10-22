from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Any

from langchain_core.embeddings import Embeddings

from molecula.rag.fusion import reciprocal_rank_fusion
from molecula.schemas.retrieval import (
    Chunk,
    LabelFilter,
    Retrieval,
    RetrievalMode,
    RetrievedChunk,
    Widening,
)
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.labels import label_date

# Chunks each search keeps before fusion, so one the other search ranks high can still make top_k.
FUSION_DEPTH = 20


@dataclass(frozen=True)
class Query:
    text: str
    vector: list[float]


class LabelRetriever:
    """Search over the label chunks, narrowed by a checked `LabelFilter`.

    The drugs, their labels and the product type narrow the search; the section groups only
    rank it. A chunk in one of the filter's groups counts `section_group_boost` higher, so a
    wrong group the chat model picks still leaves the drug's other sections in reach. The
    `top_k` best chunks are candidates; those whose own score is below `min_score` are dropped
    but still returned, so the retrieval trace can show them.

    `mode` picks the ranking: "dense" by embedding similarity, "bm25" by the keyword index, and
    "hybrid" both, each searched `FUSION_DEPTH` deep and merged by reciprocal rank fusion (#44).

    A filter with several drugs searches each drug on its own and keeps its `top_k` best
    chunks, so a drug whose label matches the question better can't crowd out the others (#255).

    Several `queries` (a question and its rewrites, #446) are each searched under the filter,
    and their rankings merged by reciprocal rank fusion, still `top_k` per drug.
    """

    def __init__(
        self,
        index: LabelIndex,
        embeddings: Embeddings,
        *,
        top_k: int,
        min_score: float,
        section_group_boost: float,
        mode: RetrievalMode = "dense",
        keywords: KeywordIndex | None = None,
    ) -> None:
        if mode != "dense" and keywords is None:
            raise ValueError(f"Retrieval mode {mode} needs the keyword index")
        self._index = index
        self._embeddings = embeddings
        self._top_k = top_k
        self._min_score = min_score
        self._section_group_boost = section_group_boost
        self._mode = mode
        self._keywords = keywords

    def retrieve(
        self,
        question: str,
        label_filter: LabelFilter | None = None,
        *,
        queries: Sequence[str] = (),
    ) -> Retrieval:
        """The label chunks for `question`, or for `queries` when they are given. A filter that
        names only drugs without searchable labels (unsupported, or no US label) finds nothing
        rather than other drugs' text.

        When none of the labels the filter narrows to has the section groups, the search widens
        to every label of the named drugs (or any product type). "Side effects of Advil"
        narrows to the OTC label, whose Drug Facts have no adverse reactions section, so it
        falls back to the prescription label's.
        """
        if label_filter is not None and label_filter.names_drugs and not label_filter.set_ids:
            return Retrieval(
                question=question,
                filter=label_filter,
                chunks=[],
                dropped=[],
                mode=self._mode,
                min_score=self._min_score,
                section_group_boost=self._section_group_boost,
            )
        texts = queries or [question]
        searched = [Query(text, self._embeddings.embed_query(text)) for text in texts]
        candidates, widened = self._candidates(searched, label_filter)
        return Retrieval(
            question=question,
            filter=label_filter,
            chunks=[c for c in candidates if c.score >= self._min_score],
            dropped=[c for c in candidates if c.score < self._min_score],
            widened=widened,
            mode=self._mode,
            min_score=self._min_score,
            section_group_boost=self._section_group_boost,
        )

    def _candidates(
        self, queries: Sequence[Query], label_filter: LabelFilter | None
    ) -> tuple[list[RetrievedChunk], list[Widening]]:
        """The best chunks under the filter, or the best chunks of each drug it names."""
        searched = [drug for drug in label_filter.drugs if drug.set_ids] if label_filter else []
        if label_filter is None or len(searched) < 2:
            found, widened = self._search_widening(queries, label_filter)
            return found[: self._top_k], widened
        candidates: list[RetrievedChunk] = []
        widenings: set[Widening] = set()
        for drug in searched:
            one_drug = label_filter.model_copy(update={"drugs": [drug]})
            found, widened = self._search_widening(queries, one_drug)
            candidates += found[: self._top_k]
            widenings.update(widened)
        candidates.sort(key=self._ranking_score, reverse=True)
        return candidates, sorted(widenings)

    def _search_widening(
        self, queries: Sequence[Query], label_filter: LabelFilter | None
    ) -> tuple[list[RetrievedChunk], list[Widening]]:
        """The search under the filter, or under every label of its drugs when that finds the
        section groups and the narrower labels don't. A brand's label with text in other
        sections is kept when no label of the drug has the groups either."""
        found = self._search(queries, label_filter, [])
        if label_filter is None or in_groups(found, label_filter):
            return found, []
        if where_clause(label_filter, ["labels"]) == where_clause(label_filter):
            return found, []
        wider = self._search(queries, label_filter, ["labels"])
        if in_groups(wider, label_filter) or not found:
            return wider, ["labels"]
        return found, []

    def _search(
        self, queries: Sequence[Query], label_filter: LabelFilter | None, widened: list[Widening]
    ) -> list[RetrievedChunk]:
        """The chunks in the filter's section groups and in every section together, ranked
        for each query, and the rankings of several queries merged."""
        wheres = [where_clause(label_filter, widened)]
        if label_filter is not None and label_filter.section_groups:
            wheres.insert(0, where_clause(label_filter, widened, section_groups=True))
        groups = label_filter.section_groups if label_filter else []
        if len(queries) == 1:
            return self._search_one(queries[0], wheres, groups, self._depth)
        depth = max(self._top_k, FUSION_DEPTH)
        return merged([self._search_one(query, wheres, groups, depth) for query in queries])

    def _search_one(
        self,
        query: Query,
        wheres: list[dict[str, Any] | None],
        groups: Sequence[str],
        depth: int,
    ) -> list[RetrievedChunk]:
        dense = self._dense(query.vector, wheres, groups, depth) if self._mode != "bm25" else []
        if self._mode == "dense":
            return dense
        return self._fused(query, dense, self._keyword(query.text, wheres, depth), groups)

    def _dense(
        self,
        vector: list[float],
        wheres: list[dict[str, Any] | None],
        groups: Sequence[str],
        depth: int,
    ) -> list[RetrievedChunk]:
        found = [hit for where in wheres for hit in self._index.search(vector, depth, where)]
        unique = {chunk.id: (chunk, score) for chunk, score in found}
        chunks = [
            retrieved(chunk, score, chunk.section_group in groups)
            for chunk, score in unique.values()
        ]
        chunks.sort(key=self._boosted_score, reverse=True)
        return [
            chunk.model_copy(update={"dense_rank": rank}) for rank, chunk in enumerate(chunks, 1)
        ]

    def _keyword(self, text: str, wheres: list[dict[str, Any] | None], depth: int) -> list[Chunk]:
        assert self._keywords is not None
        found = [hit for where in wheres for hit in self._keywords.search(text, depth, where)]
        unique = {chunk.id: (chunk, score) for chunk, score in found}
        return [chunk for chunk, _ in sorted(unique.values(), key=lambda hit: hit[1], reverse=True)]

    def _fused(
        self, query: Query, dense: list[RetrievedChunk], keyword: list[Chunk], groups: Sequence[str]
    ) -> list[RetrievedChunk]:
        """The dense and keyword rankings merged by reciprocal rank fusion. Chunks only the
        keyword search found get their cosine similarity too, which `min_score` applies to."""
        chunks = {chunk.id: chunk for chunk in dense}
        keyword_only = [chunk for chunk in keyword if chunk.id not in chunks]
        vectors = self._index.vectors([chunk.id for chunk in keyword_only])
        for chunk in keyword_only:
            similarity = cosine(query.vector, vectors[chunk.id])
            chunks[chunk.id] = retrieved(chunk, similarity, chunk.section_group in groups)
        bm25_ranks = {chunk.id: rank for rank, chunk in enumerate(keyword, 1)}
        fused = reciprocal_rank_fusion([[chunk.id for chunk in dense], list(bm25_ranks)])
        ranked = [
            chunks[id_].model_copy(update={"bm25_rank": bm25_ranks.get(id_), "fused_score": score})
            for id_, score in fused.items()
        ]
        ranked.sort(key=lambda chunk: (self._ranking_score(chunk), chunk.score), reverse=True)
        return ranked

    @property
    def _depth(self) -> int:
        return self._top_k if self._mode == "dense" else max(self._top_k, FUSION_DEPTH)

    def _ranking_score(self, chunk: RetrievedChunk) -> float:
        if chunk.fused_score is not None:
            return chunk.fused_score
        return self._boosted_score(chunk)

    def _boosted_score(self, chunk: RetrievedChunk) -> float:
        return chunk.score + (self._section_group_boost if chunk.in_section_groups else 0.0)


def merged(rankings: Sequence[Sequence[RetrievedChunk]]) -> list[RetrievedChunk]:
    """The rankings of several queries merged by reciprocal rank fusion, the fused score in
    `fused_score`. A chunk keeps the similarity and ranks of the first query that found it."""
    chunks: dict[str, RetrievedChunk] = {}
    for ranking in rankings:
        for chunk in ranking:
            chunks.setdefault(chunk.id, chunk)
    fused = reciprocal_rank_fusion([[chunk.id for chunk in ranking] for ranking in rankings])
    return [chunks[id_].model_copy(update={"fused_score": score}) for id_, score in fused.items()]


def in_groups(found: Sequence[RetrievedChunk], label_filter: LabelFilter) -> bool:
    """Whether the search found a chunk in the filter's section groups; without groups, any."""
    if not label_filter.section_groups:
        return bool(found)
    return any(chunk.section_group in label_filter.section_groups for chunk in found)


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
        **chunk.model_dump(exclude={"effective_time"}),
        effective_time=label_date(chunk.effective_time),
        score=score,
        in_section_groups=in_section_groups,
    )


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b)))
