"""Measure how well a chat model extracts the label filter (#13) on the retrieval questions (#98).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=qwen/qwen3.8-27b \
        uv run python -m evals.chat_model.filters

Runs `FilterExtractor.extract` with the chat model the settings point at on every question in
`datasets/retrieval_questions.yaml`, then searches under the extracted filter. Reports how often
the model returns a valid filter, names the question's drug and picks its section group, the
recall of the filtered search next to the answer key's filters, and the time and output tokens
per question. Each extraction is cached in data/build/eval/filters/, keyed by model, prompt and
question, so a re-score or an interrupted run doesn't call the model again. The cached model
output is checked against the store by the current code on every run, so changes to name
resolution and the filter show in the scores.
"""

import hashlib
import json
import statistics
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from evals.chat_model.citations import model_label
from evals.retrieval.dataset import Question, load_questions
from evals.retrieval.filters import first_hit_rank, gold_filter, labels_by_drug, mrr, recall
from langchain_core.callbacks import get_usage_metadata_callback

from molecula import prompts
from molecula.agent.llm import chat_model_name, get_chat_model
from molecula.config import Settings, get_settings
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import LabelFilter
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import LabelIndex
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
    settings = get_settings()
    model_name = chat_model_name(settings)
    conn = connect(settings.db_path)
    compounds = CompoundStore(conn)
    extractor = FilterExtractor(
        get_chat_model(settings),
        CompoundService(
            compounds,
            ConformerFiles(settings.conformers_dir),
            suggestion_cutoff=settings.name_suggestion_cutoff,
        ),
        LabelService(LabelStore(conn), compounds),
    )
    index = LabelIndex(settings.index_dir)
    index.check_model(embedding_model_id(settings))
    retriever = LabelRetriever(
        index,
        get_embeddings(settings),
        top_k=TOP_K,
        min_score=-1.0,
        section_group_boost=settings.retrieval_section_group_boost,
    )
    questions = load_questions()

    extractions = extract_all(extractor, questions, cache_path(settings, model_name))
    scored = [
        score(question, extraction, extractor, retriever)
        for question, extraction in zip(questions, extractions, strict=True)
    ]
    gold = gold_ranks(questions, retriever, labels_by_drug(index.chunks()))
    print(report(model_name, scored, gold))
    save(settings, model_name, questions, extractions, scored)
    conn.close()
    return 0


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
            label_filter=LabelFilter.model_validate(entry["label_filter"]),
            seconds=entry["seconds"],
            output_tokens=entry["output_tokens"],
        )
    return extractions


def as_json(extraction: Extraction) -> dict[str, object]:
    return {**asdict(extraction), "label_filter": extraction.label_filter.model_dump(mode="json")}


def score(
    question: Question,
    extraction: Extraction,
    extractor: FilterExtractor,
    retriever: LabelRetriever,
) -> Scored:
    found = rechecked(extraction.label_filter, extractor)
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
        seconds=extraction.seconds,
        output_tokens=extraction.output_tokens,
    )


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
