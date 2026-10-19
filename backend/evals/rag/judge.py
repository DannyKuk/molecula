"""Judge exported answers with RAGAs faithfulness and answer relevancy, on a cloud model (#43).

    uv run --no-project --env-file ../.env --with ragas==0.4.3 \
        --with langchain-community==0.4.1 python evals/rag/judge.py \
        ../data/build/eval/rag/<cache name>.samples.jsonl [--limit N]

Runs in its own environment and imports nothing from the app: installing RAGAs in the project
would downgrade `openai` 3.29 → 3.3 and add langchain-community, datasets and pandas. Its own
prompts are part of the library, as LangChain's are. langchain-community is pinned because
ragas 0.4.3 imports `chat_models.vertexai`, which 0.4.2 dropped.

Faithfulness splits the answer into statements and asks the judge which of them the contexts
support (two calls); answer relevancy asks it for `STRICTNESS` questions the answer would fit and
compares them with the asked one by embedding (three calls and two embedding requests). The judge
and the embedding model are called through OpenRouter with OPENROUTER_API_KEY. Scores are saved
per sample next to the samples, keyed by their content, the judge model and the RAGAs version, so
an interrupted run goes on where it stopped, with each statement's verdict and the judge's reason;
the key's usage before and after gives the run's cost.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

OPENROUTER = "https://openrouter.ai/api/v1"
JUDGE = "anthropic/claude-haiku-5.5"
EMBEDDINGS = "openai/text-embedding-3-small"
RAGAS = "0.4.3"
STRICTNESS = 3
CONCURRENCY = 4
# RAGAs allows 1024 by default. claude-haiku-5.5 reasons first and gives a reason per statement,
# which took more than 4096 on an answer of 15 statements.
MAX_TOKENS = 16384
METRICS = ("faithfulness", "answer_relevancy")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("samples", type=Path, help="a .samples.jsonl file `export answers` wrote")
    parser.add_argument("--judge", default=JUDGE, help="the judge model on OpenRouter")
    parser.add_argument("--embeddings", default=EMBEDDINGS, help="for answer relevancy")
    parser.add_argument("--limit", type=int, help="judge only the first N samples")
    args = parser.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("Set OPENROUTER_API_KEY (pass --env-file ../.env to uv run).")
    samples = read_jsonl(args.samples)[: args.limit]
    output = scores_path(args.samples, args.judge)
    done = {score["id"]: score for score in read_jsonl(output)} if output.exists() else {}
    pending = [sample for sample in samples if sample["id"] not in done]

    spent_before = usage(key)
    asyncio.run(judge_all(pending, args.judge, args.embeddings, key, output))
    spent = usage(key) - spent_before

    scores = {score["id"]: score for score in read_jsonl(output)}
    judged = [scores[sample["id"]] | sample for sample in samples]
    print(report(judged, args.judge, args.embeddings))
    print(f"\nJudged {len(pending)} new samples for ${spent:.4f} (OpenRouter key usage).")
    return 0


async def judge_all(
    samples: list[dict[str, Any]], judge: str, embeddings: str, key: str, output: Path
) -> None:
    # RAGAs sends usage analytics unless this is set before it is imported.
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms.base import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness

    client = AsyncOpenAI(base_url=OPENROUTER, api_key=key)
    llm = llm_factory(judge, client=client, temperature=0, max_tokens=MAX_TOKENS)
    faithfulness = Faithfulness(llm=llm)
    relevancy = AnswerRelevancy(
        llm=llm,
        embeddings=embedding_factory("openai", model=embeddings, client=client),
        strictness=STRICTNESS,
    )
    slots = asyncio.Semaphore(CONCURRENCY)

    async def judge_one(sample: dict[str, Any]) -> None:
        async with slots:
            score: dict[str, Any] = {"id": sample["id"], "faithfulness": None, "statements": []}
            if sample["contexts"]:
                # The steps of `Faithfulness.ascore` (pinned version), which keeps only the score:
                # the judge's verdict and reason per statement are what a low score is checked by.
                statements = await faithfulness._create_statements(
                    sample["question"], sample["answer"]
                )
                if statements:
                    verdicts = await faithfulness._create_verdicts(
                        statements, "\n".join(sample["contexts"])
                    )
                    score["faithfulness"] = faithfulness._compute_score(verdicts)
                    score["statements"] = [v.model_dump() for v in verdicts.statements]
            result = await relevancy.ascore(
                user_input=sample["question"], response=sample["answer"]
            )
            score["answer_relevancy"] = result.value
        with output.open("a", encoding="utf-8") as file:
            file.write(json.dumps(score) + "\n")
        scores = {metric: score[metric] for metric in METRICS}
        print(f"{score['id']}: {scores}", flush=True)

    await asyncio.gather(*(judge_one(sample) for sample in samples))


def scores_path(samples: Path, judge: str) -> Path:
    """Next to the samples, keyed by their content too, so a new export is judged afresh."""
    name = samples.name.removesuffix(".samples.jsonl")
    key = hashlib.sha256(samples.read_bytes()).hexdigest()[:12]
    return samples.with_name(f"{name}.{judge.replace('/', '_')}.ragas-{RAGAS}-{key}.scores.jsonl")


def usage(key: str) -> float:
    """What the OpenRouter key has spent so far, in dollars."""
    request = urllib.request.Request(
        f"{OPENROUTER}/key", headers={"Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return float(json.load(response)["data"]["usage"])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def summary(values: list[float | None]) -> str:
    """The mean of the scores that exist, and how many are missing: an answer without contexts or
    without a statement has no faithfulness."""
    scored = [value for value in values if value is not None and not math.isnan(value)]
    if not scored:
        return "-"
    missing = len(values) - len(scored)
    return f"{statistics.fmean(scored):.2f}" + (f" ({missing} missing)" if missing else "")


def report(judged: list[dict[str, Any]], judge: str, embeddings: str) -> str:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in judged:
        by_group[sample["section_group"]].append(sample)
    lines = [
        f"RAGAs {RAGAS}, judge {judge}, embeddings {embeddings}, {len(judged)} answers",
        "",
        "| Section group | Answers | Faithfulness | Answer relevancy |",
        "|---|---|---|---|",
    ]
    rows = [*sorted(by_group.items()), ("**all**", judged)]
    for group, part in rows:
        cells = [summary([sample.get(metric) for sample in part]) for metric in METRICS]
        lines.append(f"| {group} | {len(part)} | {' | '.join(cells)} |")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
