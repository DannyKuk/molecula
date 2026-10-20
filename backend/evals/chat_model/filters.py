"""Measure how well a chat model extracts the label filter (#13) on the retrieval questions (#98).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=qwen/qwen3.8-27b \
        uv run python -m evals.chat_model.filters [--typos]

Runs `FilterExtractor.extract` with the chat model the settings point at on every question in
`datasets/retrieval_questions.yaml`, then searches under the extracted filter. Reports how often
the model returns a valid filter, names the question's drug and picks its section group, the
recall of the filtered search next to the answer key's filters, and the time and output tokens
per question. Each extraction is cached in data/build/eval/filters/, keyed by model, prompt and
question, so a re-score or an interrupted run doesn't call the model again. The cached model
output is checked against the store by the current code on every run, so changes to name
resolution and the filter show in the scores.

With --typos it runs the questions of `datasets/retrieval_questions_typos.yaml` instead, the same
questions with the drug name misspelled, and reports what became of each misspelling (#287).
"""

import argparse
import hashlib
import json
import sqlite3
import statistics
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from evals.chat_model.citations import model_label
from evals.retrieval.dataset import Question, load_questions, load_typos
from evals.retrieval.filters import first_hit_rank, gold_filter, labels_by_drug, mrr, recall
from langchain_core.callbacks import get_usage_metadata_callback

from molecula import prompts
from molecula.agent.llm import chat_model_name, get_chat_model
from molecula.config import Settings, get_settings
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import LabelFilter, LabelQuery
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.labels import LabelStore
from molecula.store.structures import ConformerFiles

TOP_K = 10
GOLD_SETUPS = ["whole index", "drug", "drug + section group"]


@dataclass(frozen=True)
class Extraction:
    question_id: str
    label_filter: LabelFilter
    seconds: float
    output_tokens: int | None


@dataclass(frozen=True)
class Scored:
    question_id: str
    valid: bool
    drug_found: bool
    only_that_drug: bool
    group_found: bool
    group_first: bool
    rank: int | None
    seconds: float
    output_tokens: int | None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--typos", action="store_true", help="run the misspelled questions")
    typos = parser.parse_args().typos
    settings = get_settings()
    model_name = chat_model_name(settings)
    conn = connect(settings.db_path)
    extractor = FilterExtractor(get_chat_model(settings), *services(settings, conn))
    index, retriever = search(settings)
    questions = load_typos(load_questions()) if typos else load_questions()

    cache = cache_path(settings, model_name)
    if typos:
        cache = cache.with_stem(f"{cache.stem}-typos")
    extractions = extract_all(extractor, questions, cache)
    scored = [
        score(question, extraction, extractor, retriever)
        for question, extraction in zip(questions, extractions, strict=True)
    ]
    gold = gold_ranks(questions, retriever, labels_by_drug(index.chunks()))
    print(report(model_name, scored, gold))
    if typos:
        found = [rechecked(extraction.label_filter, extractor) for extraction in extractions]
        print("\n" + typo_report(questions, found))
    save(settings, model_name, questions, extractions, scored)
    conn.close()
    return 0


def services(settings: Settings, conn: sqlite3.Connection) -> tuple[CompoundService, LabelService]:
    compounds = CompoundStore(conn)
    return (
        CompoundService(
            compounds,
            ConformerFiles(settings.conformers_dir),
            suggestion_cutoff=settings.name_suggestion_cutoff,
        ),
        LabelService(LabelStore(conn), compounds),
    )


def search(settings: Settings) -> tuple[LabelIndex, LabelRetriever]:
    """The built index and a search over it that keeps every result, for ranking."""
    index = LabelIndex(settings.index_dir)
    index.check_model(embedding_model_id(settings))
    retriever = LabelRetriever(
        index,
        get_embeddings(settings),
        top_k=TOP_K,
        min_score=-1.0,
        section_group_boost=settings.retrieval_section_group_boost,
        mode=settings.retrieval_mode,
        keywords=KeywordIndex(settings.keyword_index_path),
    )
    return index, retriever


def cache_path(settings: Settings, model_name: str) -> Path:
    name = model_label(settings, model_name)
    prompt = prompts.load("rag/extract_filters")
    key = hashlib.sha256(f"{name}\n{prompt}".encode()).hexdigest()[:12]
    slug = name.replace("/", "_")
    return settings.build_dir / "eval" / "filters" / f"{slug}-{key}.jsonl"


def extract_all(
    extractor: FilterExtractor, questions: list[Question], cache: Path
) -> list[Extraction]:
    """Every question's extraction, from the cache when this model and prompt already ran it."""
    cached = read_cache(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    extractions = []
    for number, question in enumerate(questions, start=1):
        if question.id not in cached:
            cached[question.id] = extract(extractor, question)
            with cache.open("a", encoding="utf-8") as file:
                file.write(json.dumps(as_json(cached[question.id])) + "\n")
            print(
                f"{number}/{len(questions)} {question.id}: {cached[question.id].seconds:.1f} s",
                flush=True,
            )
        extractions.append(cached[question.id])
    return extractions


def extract(extractor: FilterExtractor, question: Question) -> Extraction:
    with get_usage_metadata_callback() as usage:
        start = perf_counter()
        label_filter = extractor.extract(question.question)
        seconds = perf_counter() - start
    output_tokens = sum(call["output_tokens"] for call in usage.usage_metadata.values())
    return Extraction(question.id, label_filter, seconds, output_tokens or None)


def read_cache(cache: Path) -> dict[str, Extraction]:
    if not cache.exists():
        return {}
    extractions = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        extractions[entry["question_id"]] = Extraction(
            question_id=entry["question_id"],
            label_filter=cached_filter(entry["label_filter"]),
            seconds=entry["seconds"],
            output_tokens=entry["output_tokens"],
        )
    return extractions


def cached_filter(entry: dict[str, Any]) -> LabelFilter:
    """Only what the model gave: the rest is checked again on every run, and older caches hold
    the checked part in an earlier shape."""
    return LabelFilter(
        extracted=LabelQuery.model_validate(entry["extracted"]),
        extraction_error=entry["extraction_error"],
    )


def as_json(extraction: Extraction) -> dict[str, object]:
    return {**asdict(extraction), "label_filter": extraction.label_filter.model_dump(mode="json")}


def score(
    question: Question,
    extraction: Extraction,
    extractor: FilterExtractor,
    retriever: LabelRetriever,
) -> Scored:
    found = rechecked(extraction.label_filter, extractor)
    return score_filter(question, found, retriever, extraction.seconds, extraction.output_tokens)


def score_filter(
    question: Question,
    found: LabelFilter,
    retriever: LabelRetriever,
    seconds: float,
    output_tokens: int | None,
) -> Scored:
    cids = {drug.cid for drug in found.drugs}
    retrieval = retriever.retrieve(question.question, found)
    return Scored(
        question_id=question.id,
        valid=found.extraction_error is None,
        drug_found=question.cid in cids,
        only_that_drug=cids == {question.cid},
        group_found=question.section_group in found.section_groups,
        group_first=found.section_groups[:1] == [question.section_group],
        rank=first_hit_rank(question, retrieval.chunks),
        seconds=seconds,
        output_tokens=output_tokens,
    )


def typo_outcome(question: Question, found: LabelFilter) -> str:
    """What became of a misspelled drug name: searched as the drug, answered with the drug as a
    suggestion ("not supported, did you mean"), or lost."""
    if any(drug.cid == question.cid for drug in found.drugs):
        return "searched as the drug"
    suggested = {s.cid for resolution in found.unsupported for s in resolution.suggestions}
    if question.cid in suggested:
        return "not supported, the drug suggested"
    return "lost"


def typo_report(questions: list[Question], found: list[LabelFilter]) -> str:
    outcomes = [typo_outcome(q, f) for q, f in zip(questions, found, strict=True)]
    lines = ["| What became of the misspelling | Questions |", "|---|---|"]
    lines += [f"| {outcome} | {outcomes.count(outcome)} |" for outcome in dict.fromkeys(outcomes)]
    lines += ["", "Per question:"]
    lines += [
        f"- {q.id}: {outcome}; names {f.extracted.substances}"
        for q, f, outcome in zip(questions, found, outcomes, strict=True)
    ]
    return "\n".join(lines)


def rechecked(cached: LabelFilter, extractor: FilterExtractor) -> LabelFilter:
    """The cached model output checked against the store by the current code, so a change to
    name resolution or the filter is scored without calling the model again."""
    checked = extractor.check(cached.extracted)
    return checked.model_copy(update={"extraction_error": cached.extraction_error})


def gold_ranks(
    questions: list[Question], retriever: LabelRetriever, set_ids: dict[int, list[str]]
) -> dict[str, list[int | None]]:
    return {
        setup: [
            first_hit_rank(
                question,
                retriever.retrieve(question.question, gold_filter(question, setup, set_ids)).chunks,
            )
            for question in questions
        ]
        for setup in GOLD_SETUPS
    }


def report(model_name: str, scored: list[Scored], gold: dict[str, list[int | None]]) -> str:
    n = len(scored)

    def share(flag: str) -> str:
        count = sum(getattr(s, flag) for s in scored)
        return f"{count / n:.2f} ({count})"

    seconds = sorted(s.seconds for s in scored)
    tokens = [s.output_tokens for s in scored if s.output_tokens is not None]
    mean_tokens = f"{statistics.mean(tokens):.0f}" if tokens else "-"
    lines = [
        f"{model_name}, {n} questions, top {TOP_K}",
        "",
        "| Valid filter | Drug named | Only that drug | Group among picks | Group first "
        "| Seconds p50 / p95 | Output tokens mean |",
        "|---|---|---|---|---|---|---|",
        f"| {share('valid')} | {share('drug_found')} | {share('only_that_drug')} "
        f"| {share('group_found')} | {share('group_first')} "
        f"| {statistics.median(seconds):.1f} / {seconds[int(0.95 * (n - 1))]:.1f} "
        f"| {mean_tokens} |",
        "",
        "| Search | recall@1 | recall@5 | MRR@10 |",
        "|---|---|---|---|",
        *(row(f"answer key: {setup}", ranks) for setup, ranks in gold.items()),
        row(f"extracted by {model_name}", [s.rank for s in scored]),
        "",
        "recall@5 of the extracted filter, split by what the model got right:",
        "",
        "| Questions | n | recall@5 |",
        "|---|---|---|",
        split_row("drug and group right", [s for s in scored if s.drug_found and s.group_found]),
        split_row(
            "drug right, group wrong", [s for s in scored if s.drug_found and not s.group_found]
        ),
        split_row("drug wrong", [s for s in scored if not s.drug_found]),
        "",
        "Drug wrong: " + ids(s for s in scored if not s.drug_found),
        "Group wrong: " + ids(s for s in scored if s.drug_found and not s.group_found),
    ]
    return "\n".join(lines)


def split_row(name: str, part: list[Scored]) -> str:
    share = f"{recall([s.rank for s in part], 5):.2f}" if part else "-"
    return f"| {name} | {len(part)} | {share} |"


def ids(scored: Iterable[Scored]) -> str:
    return ", ".join(s.question_id for s in scored) or "-"


def row(setup: str, ranks: list[int | None]) -> str:
    return f"| {setup} | {recall(ranks, 1):.2f} | {recall(ranks, 5):.2f} | {mrr(ranks):.3f} |"


def save(
    settings: Settings,
    model_name: str,
    questions: list[Question],
    extractions: list[Extraction],
    scored: list[Scored],
) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = settings.build_dir / "eval" / f"filters-{model_name.replace('/', '_')}-{stamp}.json"
    payload = {
        "model": model_name,
        "prompt": prompts.load("rag/extract_filters"),
        "questions": [question.model_dump() for question in questions],
        "extractions": [as_json(extraction) for extraction in extractions],
        "scored": [asdict(s) for s in scored],
    }
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    raise SystemExit(main())
