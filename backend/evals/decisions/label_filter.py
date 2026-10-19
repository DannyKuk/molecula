"""Score a decision model as the label filter, next to the chat model's extraction (#287).

    OFFLINE=0 DECISION_MODEL=jev-1.13 uv run python -m evals.decisions.label_filter [--typos]

Jev runs on OpenRouter, so its run needs the network and no `LOCAL_DECISION_BASE_URL`. Nothing
else goes out: the search runs on the built index.

Each question of `datasets/retrieval_questions.yaml` (with --typos, the misspelled ones) goes to
`DecisionFilterExtractor`, the way the chat would ask it: one call with a yes/no question per
section group and a choice for the product type, while the drug names come from the question by
code. A second call asks one choice over the section groups, for comparison. Both answers are
cached with their probabilities per model and prompts, so a re-score or the threshold table
doesn't call the model again; a failed call stops the run, and the next run goes on from the
cache. The report has the same tables as `evals.chat_model.filters`, then recall@5 per threshold,
the one-choice variant, the product types picked, and seconds and cost per question.
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from evals.chat_model.filters import (
    Scored,
    gold_ranks,
    report,
    score_filter,
    search,
    services,
    typo_report,
)
from evals.retrieval.dataset import Question, load_questions, load_typos
from evals.retrieval.filters import labels_by_drug, mrr, recall

from molecula import prompts
from molecula.agent.decisions import get_decision_model
from molecula.config import Settings, get_settings
from molecula.rag.filters import (
    SECTION_GROUP_ORDER,
    SECTION_THRESHOLD,
    Decider,
    DecisionFilterExtractor,
    filter_questions,
)
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.decisions import (
    ChoiceQuestion,
    DecisionResponse,
    StateMessage,
)
from molecula.schemas.decisions import (
    Question as DecisionQuestion,
)
from molecula.schemas.retrieval import LabelFilter
from molecula.store.db import connect

THRESHOLDS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
CHOICE = "section"
WARM_UP = [StateMessage(role="user", content="How does ibuprofen work?")]


@dataclass(frozen=True)
class Decided:
    id: str
    question: str
    answers: DecisionResponse
    choice: DecisionResponse
    seconds: float


class CacheOnly:
    """Stands in for the model when every answer is cached, so a re-score needs no model
    settings."""

    async def decide(
        self, state: str | list[StateMessage], questions: Mapping[str, DecisionQuestion]
    ) -> DecisionResponse:
        raise RuntimeError("every answer should be cached")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--typos", action="store_true", help="run the misspelled questions")
    typos = parser.parse_args().typos
    settings = get_settings()
    name = (settings.decision_model or "unknown").replace("/", "_")
    questions = load_typos(load_questions()) if typos else load_questions()
    conn = connect(settings.db_path)
    compounds, labels = services(settings, conn)
    cache = cache_path(settings, name, typos=typos)
    cached = read_cache(cache)
    model: Decider = (
        CacheOnly() if all(q.id in cached for q in questions) else get_decision_model(settings)
    )

    def extractor_at(threshold: float) -> DecisionFilterExtractor:
        return DecisionFilterExtractor(model, compounds, labels, threshold=threshold)

    decided = asyncio.run(decide_all(model, questions, cached, cache))
    index, retriever = search(settings)
    found = [extractor_at(SECTION_THRESHOLD).filter_from(d.question, d.answers) for d in decided]
    scored = [
        score_filter(question, label_filter, retriever, d.seconds, None)
        for question, label_filter, d in zip(questions, found, decided, strict=True)
    ]
    gold = gold_ranks(questions, retriever, labels_by_drug(index.chunks()))
    print(report(f"{name}, section groups at {SECTION_THRESHOLD}", scored, gold))
    print("\n" + threshold_table(questions, decided, extractor_at, retriever))
    print("\n" + choice_table(questions, found, decided, retriever))
    print("\n" + product_types(found))
    print("\n" + speed(decided))
    if typos:
        print("\n" + typo_report(questions, found))
    conn.close()
    return 0


def section_choice() -> ChoiceQuestion:
    return ChoiceQuestion(
        instructions=prompts.load("rag/label_filter/section_choice").strip(),
        criteria={
            group: prompts.load(f"rag/label_filter/sections/{group}").strip()
            for group in SECTION_GROUP_ORDER
        },
    )


def cache_path(settings: Settings, name: str, *, typos: bool) -> Path:
    """Keyed by the model and every question it is asked, prompts included."""
    asked = [q.model_dump(mode="json") for q in [*filter_questions().values(), section_choice()]]
    key = hashlib.sha256(json.dumps([name, asked], sort_keys=True).encode()).hexdigest()[:12]
    file = f"{name}-{key}{'-typos' if typos else ''}.jsonl"
    return settings.build_dir / "eval" / "decisions" / "label_filter" / file


async def decide_all(
    model: Decider, questions: list[Question], cached: dict[str, Decided], cache: Path
) -> list[Decided]:
    """Every question's answers, from the cache when this model and these prompts already ran
    it. One call before the first new question loads the model, so the times are warm."""
    asked = filter_questions()
    choice = {CHOICE: section_choice()}
    if any(question.id not in cached for question in questions):
        await model.decide(WARM_UP, asked)
    cache.parent.mkdir(parents=True, exist_ok=True)
    for number, question in enumerate(questions, start=1):
        if question.id in cached:
            continue
        # The question goes as its own message, never into the questions: it is untrusted text.
        state = [StateMessage(role="user", content=question.question)]
        start = time.perf_counter()
        answers = await model.decide(state, asked)
        seconds = time.perf_counter() - start
        decided = Decided(
            question.id, question.question, answers, await model.decide(state, choice), seconds
        )
        cached[question.id] = decided
        with cache.open("a", encoding="utf-8") as file:
            file.write(json.dumps(to_json(decided), ensure_ascii=False) + "\n")
        print(f"{number}/{len(questions)} {question.id}: {seconds:.2f} s", flush=True)
    return [cached[question.id] for question in questions]


def read_cache(cache: Path) -> dict[str, Decided]:
    if not cache.exists():
        return {}
    decided = {}
    for line in cache.read_text("utf-8").splitlines():
        entry = json.loads(line)
        decided[entry["id"]] = Decided(
            id=entry["id"],
            question=entry["question"],
            answers=DecisionResponse.model_validate(entry["answers"]),
            choice=DecisionResponse.model_validate(entry["choice"]),
            seconds=entry["seconds"],
        )
    return decided


def to_json(decided: Decided) -> dict[str, object]:
    return {
        "id": decided.id,
        "question": decided.question,
        "answers": decided.answers.model_dump(mode="json"),
        "choice": decided.choice.model_dump(mode="json"),
        "seconds": decided.seconds,
    }


def threshold_table(
    questions: list[Question],
    decided: list[Decided],
    extractor_at: Callable[[float], DecisionFilterExtractor],
    retriever: LabelRetriever,
) -> str:
    """How the threshold for a section group's yes trades groups per question against recall.
    Chosen on these same questions, so the best row flatters the model."""
    lines = [
        "| Threshold | Groups per question | No group | Group among picks | recall@5 | MRR@10 |",
        "|---|---|---|---|---|---|",
    ]
    for threshold in THRESHOLDS:
        extractor = extractor_at(threshold)
        found = [extractor.filter_from(d.question, d.answers) for d in decided]
        scored = [
            score_filter(q, f, retriever, d.seconds, None)
            for q, f, d in zip(questions, found, decided, strict=True)
        ]
        ranks = [s.rank for s in scored]
        groups = statistics.mean(len(f.section_groups) for f in found)
        lines.append(
            f"| {threshold} | {groups:.1f} | {sum(not f.section_groups for f in found)} "
            f"| {sum(s.group_found for s in scored)} | {recall(ranks, 5):.2f} | {mrr(ranks):.3f} |"
        )
    return "\n".join(lines)


def choice_table(
    questions: list[Question],
    found: list[LabelFilter],
    decided: list[Decided],
    retriever: LabelRetriever,
) -> str:
    """The same filter with the one section group a single choice picks."""
    scored: list[Scored] = []
    for question, label_filter, d in zip(questions, found, decided, strict=True):
        picked = d.choice.choice(CHOICE).choice
        one_group = label_filter.model_copy(update={"section_groups": [picked]})
        scored.append(score_filter(question, one_group, retriever, d.seconds, None))
    ranks = [s.rank for s in scored]
    return "\n".join(
        [
            "One choice over the section groups instead of a yes/no per group:",
            "",
            "| Group right | recall@5 | MRR@10 |",
            "|---|---|---|",
            f"| {sum(s.group_found for s in scored)} | {recall(ranks, 5):.2f} | {mrr(ranks):.3f} |",
        ]
    )


def product_types(found: list[LabelFilter]) -> str:
    counts = Counter(label_filter.product_type or "either" for label_filter in found)
    narrowed = sum(any(drug.narrowed for drug in f.drugs) for f in found if f.product_type)
    return (
        f"Product type picked: {dict(counts)}; "
        f"a picked type left out some of the drug's labels in {narrowed} questions"
    )


def speed(decided: list[Decided]) -> str:
    seconds = sorted(d.seconds for d in decided)
    tokens = statistics.mean(d.answers.usage.input_tokens for d in decided)
    costs = [d.answers.usage.cost for d in decided]
    cost = "unknown" if None in costs else f"${sum(c for c in costs if c is not None):.5f}"
    return (
        f"Seconds per question (the filter call): p50 {statistics.median(seconds):.2f}, "
        f"p95 {seconds[int(0.95 * (len(seconds) - 1))]:.2f}, max {seconds[-1]:.2f}; "
        f"input tokens per question: mean {tokens:.0f}; cost of the filter calls: {cost}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
