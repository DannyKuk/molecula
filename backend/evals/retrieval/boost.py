"""Measure the section-group boost (#112) for the configured embedding model, with no chat model.

    EMBEDDING_MODEL=google/gemini-embedding-2 OFFLINE=0 uv run python -m evals.retrieval.boost \
        ../data/build/eval/filters/openai_gpt-oss-20b-<key>.jsonl 0 0.08 0.15

Scores the retrieval questions at each boost under the label filters a chat model extracted in
an earlier `evals.chat_model.filters` run (its cache file), checked against the store by the
current code, and under the answer key's filter (drug + section group), the ceiling. The boost is
in cosine units of one embedding model, so a new model needs it measured again (#96). Only the
questions are embedded, once each.
"""

import argparse
from pathlib import Path

from evals.chat_model.filters import read_cache, score_filter, services
from evals.retrieval.dataset import Question, load_questions
from evals.retrieval.filters import first_hit_rank, gold_filter, labels_by_drug, mrr, recall
from langchain_core.embeddings import Embeddings

from molecula.config import get_settings
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.filters import FilterCheck
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import LabelFilter
from molecula.store.db import connect
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex

TOP_K = 10
DEFAULT_BOOSTS = [0.0, 0.04, 0.08, 0.12, 0.15, 0.20]


class QueryCache(Embeddings):
    """Embeds each question once, however many boosts are scored."""

    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings
        self._vectors: dict[str, list[float]] = {}

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        if text not in self._vectors:
            self._vectors[text] = self._embeddings.embed_query(text)
        return self._vectors[text]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("extractions", type=Path, help="an evals.chat_model.filters cache file")
    parser.add_argument("boosts", type=float, nargs="*", default=DEFAULT_BOOSTS)
    args = parser.parse_args()
    settings = get_settings()
    conn = connect(settings.db_path)
    index = LabelIndex(settings.index_dir)
    index.check_model(embedding_model_id(settings))
    embeddings = QueryCache(get_embeddings(settings))
    questions = load_questions()
    filters = extracted_filters(questions, args.extractions, FilterCheck(*services(settings, conn)))
    set_ids = labels_by_drug(index.chunks())
    wrong_group = [
        position
        for position, (question, found) in enumerate(zip(questions, filters, strict=True))
        if question.section_group not in found.section_groups
    ]

    print(
        f"{embedding_model_id(settings)}, {len(questions)} questions, "
        f"{len(wrong_group)} with a wrong group, top {TOP_K}\n"
    )
    print("| Boost | Extracted recall@5 | MRR@10 | Group wrong recall@5 | Ceiling recall@5 |")
    print("|---|---|---|---|---|")
    for boost in args.boosts:
        retriever = LabelRetriever(
            index,
            embeddings,
            top_k=TOP_K,
            min_score=-1.0,
            section_group_boost=boost,
            mode="dense",
            keywords=KeywordIndex(settings.keyword_index_path),
        )
        ranks = [
            score_filter(question, found, retriever, 0.0, None).rank
            for question, found in zip(questions, filters, strict=True)
        ]
        ceiling = [
            first_hit_rank(
                question,
                retriever.retrieve(
                    question.question, gold_filter(question, "drug + section group", set_ids)
                ).chunks,
            )
            for question in questions
        ]
        wrong = [ranks[position] for position in wrong_group]
        print(
            f"| {boost:+.2f} | {recall(ranks, 5):.2f} | {mrr(ranks):.3f} "
            f"| {recall(wrong, 5):.2f} | {recall(ceiling, 5):.2f} |"
        )
    conn.close()
    return 0


def extracted_filters(
    questions: list[Question], cache: Path, check: FilterCheck
) -> list[LabelFilter]:
    cached = read_cache(cache)
    return [
        check.check(cached[question.id].label_filter.extracted).model_copy(
            update={"extraction_error": cached[question.id].label_filter.extraction_error}
        )
        for question in questions
    ]


if __name__ == "__main__":
    raise SystemExit(main())
