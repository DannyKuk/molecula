"""Measure query translation and multi-query on the label search before building them (#114).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.retrieval.query_translation

Runs every retrieval question through `LabelRetriever` on the built index, in English, in German
as written (`datasets/retrieval_questions_de.yaml`), in German translated to English by the chat
model (`prompts/rag/translate_query.md`), and as multi-query: the question plus 3 rewrites the
chat model is asked to write in English (`prompts/rag/rewrite_query.md`), the results of the
four searches merged with reciprocal rank fusion. Each search runs over the whole index and
filtered to the question's drug, the filter the agent sets for a question about one drug. The
model's outputs are cached in `data/build/eval/query_translation/`, keyed by the model and
both prompts.
"""

import hashlib
import statistics
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import yaml
from evals.retrieval.dataset import Question, load_questions
from evals.retrieval.filters import first_hit_rank, gold_filter, labels_by_drug, mrr, recall
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from molecula import prompts
from molecula.agent.llm import chat_model_name, get_chat_model
from molecula.config import Settings, get_settings
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.fusion import reciprocal_rank_fusion
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import LabelFilter, RetrievedChunk
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex

GERMAN = Path(__file__).resolve().parents[1] / "datasets" / "retrieval_questions_de.yaml"
TOP_K = 10
FILTERS = ["whole index", "drug"]


class Rewrites(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewrites: list[str] = Field(min_length=1)


class ModelOutputs(BaseModel):
    """What the chat model wrote for one question, and how long each call took."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    translation: str
    translate_seconds: float
    rewrites_en: list[str]
    rewrites_de: list[str]
    rewrite_seconds: float


def main() -> int:
    settings = get_settings()
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
    set_ids = labels_by_drug(index.chunks())
    questions = load_questions()
    german = load_german(questions)
    model_name = chat_model_name(settings)
    outputs = ask_all(get_chat_model(settings), questions, german, cache_path(settings, model_name))

    setups: dict[str, Callable[[Question], list[str]]] = {
        "English": lambda q: [q.question],
        "German as written": lambda q: [german[q.id]],
        "German translated": lambda q: [outputs[q.id].translation],
        "English + 3 rewrites": lambda q: [q.question, *outputs[q.id].rewrites_en],
        "German + 3 rewrites": lambda q: [german[q.id], *outputs[q.id].rewrites_de],
    }
    ranks: dict[tuple[str, str], list[int | None]] = defaultdict(list)
    for question in questions:
        for where in FILTERS:
            label_filter = gold_filter(question, where, set_ids)
            for setup, queries in setups.items():
                found = search(retriever, queries(question), label_filter)
                ranks[setup, where].append(first_hit_rank(question, found))

    print(f"{len(questions)} questions, {model_name}, {embedding_model_id(settings)}\n")
    print("| Queries | Search | recall@1 | recall@5 | MRR@10 |")
    print("|---|---|---|---|---|")
    for where in FILTERS:
        for setup in setups:
            found = ranks[setup, where]
            print(
                f"| {setup} | {where} | {recall(found, 1):.2f} | {recall(found, 5):.2f} "
                f"| {mrr(found):.3f} |"
            )
    translating = statistics.median(o.translate_seconds for o in outputs.values())
    rewriting = statistics.median(o.rewrite_seconds for o in outputs.values())
    print(
        f"\nModel time per question, median: translation {translating:.1f} s, "
        f"rewrites {rewriting:.1f} s"
    )
    print_changes(questions, ranks)
    return 0


def load_german(questions: list[Question]) -> dict[str, str]:
    entries = yaml.safe_load(GERMAN.read_text("utf-8"))
    german = {entry["id"]: entry["question"] for entry in entries}
    missing = {q.id for q in questions} - german.keys()
    if missing or len(german) != len(entries):
        raise ValueError(f"{GERMAN} must hold each English id once; missing: {sorted(missing)}")
    return german


def cache_path(settings: Settings, model_name: str) -> Path:
    setup = (
        f"{model_name}\n{prompts.load('rag/translate_query')}\n{prompts.load('rag/rewrite_query')}"
    )
    key = hashlib.sha256(setup.encode()).hexdigest()[:12]
    return (
        settings.build_dir
        / "eval"
        / "query_translation"
        / f"{model_name.replace('/', '_')}-{key}.jsonl"
    )


def ask_all(
    model: BaseChatModel, questions: list[Question], german: dict[str, str], cache: Path
) -> dict[str, ModelOutputs]:
    outputs = {}
    if cache.exists():
        for line in cache.read_text("utf-8").splitlines():
            output = ModelOutputs.model_validate_json(line)
            outputs[output.id] = output
    cache.parent.mkdir(parents=True, exist_ok=True)
    for number, question in enumerate(questions, start=1):
        if question.id in outputs:
            continue
        outputs[question.id] = ask(model, question, german[question.id])
        with cache.open("a", encoding="utf-8") as file:
            file.write(outputs[question.id].model_dump_json() + "\n")
        print(f"{number}/{len(questions)} {question.id}", flush=True)
    return outputs


def ask(model: BaseChatModel, question: Question, german: str) -> ModelOutputs:
    started = time.perf_counter()
    translation = model.invoke(
        [SystemMessage(prompts.load("rag/translate_query")), HumanMessage(german)]
    )
    translated = time.perf_counter()
    rewrites_en = rewrite(model, question.question)
    rewrites_de = rewrite(model, german)
    finished = time.perf_counter()
    return ModelOutputs(
        id=question.id,
        translation=" ".join(str(translation.content).split()),
        translate_seconds=translated - started,
        rewrites_en=rewrites_en,
        rewrites_de=rewrites_de,
        rewrite_seconds=(finished - translated) / 2,
    )


def rewrite(model: BaseChatModel, text: str) -> list[str]:
    structured = model.with_structured_output(Rewrites)
    result = structured.invoke(
        [SystemMessage(prompts.load("rag/rewrite_query")), HumanMessage(text)]
    )
    return result.rewrites[:3] if isinstance(result, Rewrites) else []


def search(
    retriever: LabelRetriever, queries: list[str], label_filter: LabelFilter | None
) -> list[RetrievedChunk]:
    """One search per query, merged with reciprocal rank fusion; a chunk found twice counts once
    with the sum of its fused scores."""
    results = [retriever.retrieve(query, label_filter).chunks for query in queries]
    if len(results) == 1:
        return results[0]
    chunks = {chunk.id: chunk for chunks_found in reversed(results) for chunk in chunks_found}
    fused = reciprocal_rank_fusion([[chunk.id for chunk in found] for found in results])
    return [chunks[chunk_id] for chunk_id in list(fused)[:TOP_K]]


def print_changes(
    questions: list[Question], ranks: dict[tuple[str, str], list[int | None]]
) -> None:
    """The questions whose first hit moved in or out of the top 5, under the drug filter."""
    comparisons = [
        ("German as written", "German translated"),
        ("English", "English + 3 rewrites"),
        ("German as written", "German + 3 rewrites"),
    ]
    for before, after in comparisons:
        print(f"\n{before} → {after}, drug filter, top 5:")
        lines = []
        for question, old, new in zip(
            questions, ranks[before, "drug"], ranks[after, "drug"], strict=True
        ):
            was, now = old is not None and old <= 5, new is not None and new <= 5
            if was != now:
                lines.append(f"- {'gained' if now else 'lost'} {question.id}: rank {old} → {new}")
        print("\n".join(lines) or "- no change")


if __name__ == "__main__":
    raise SystemExit(main())
