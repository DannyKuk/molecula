"""Export the 2026-10-12 embedding comparison as the small JSON the benchmark page reads.

    OFFLINE=1 uv run python -m evals.retrieval.benchmark_export [--run RUN] [--cpu-run CPU_RUN]

Scores the saved run again against the current answer key, as `rescore` does, so the store must
hold the same chunks as when the run was made. Keeps per model and question the rank of the first
hit within the drug and over the whole index, and the chunk ranked first within the drug; recall@k,
the hit grid and MRR follow from the ranks on the page. CPU query times come from the CPU pass.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evals.retrieval.compare_embeddings import Result, label_chunks, recall
from evals.retrieval.dataset import Question, load_questions
from evals.retrieval.rescore import rescored_run

from molecula.config import get_settings
from molecula.schemas.retrieval import Chunk

RUN = "embeddings-20261012T122048Z.json"
CPU_RUN = "embeddings-20261012T122456Z.json"
OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "lib"
    / "benchmarks"
    / "embeddings-2026-10-12.json"
)
SOURCE = "docs/decisions/embeddings.md"

# Published weight file sizes, as in the table of docs/decisions/embeddings.md; the run doesn't
# record them. Cloud models have none.
WEIGHTS_MB: dict[str, int | None] = {
    "bge-small": 133,
    "bge-small+instruction": 133,
    "medembed-small": 133,
    "bge-large": 1340,
    "bge-large+instruction": 1340,
    "modernbert-embed": 596,
    "bge-m3": 2270,
    "qwen3-0.6b": 1190,
    "qwen3-4b": 8000,
    "qwen3-8b": 15100,
    "cloud:text-embedding-3-small": None,
    "cloud:text-embedding-3-large": None,
    "cloud:gemini-embedding-2": None,
    "cloud:qwen3-8b": None,
}


def main() -> int:
    eval_dir = get_settings().build_dir / "eval"
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=eval_dir / RUN, help="the comparison run")
    parser.add_argument(
        "--cpu-run", type=Path, default=eval_dir / CPU_RUN, help="its CPU pass, for query times"
    )
    parser.add_argument("--out", type=Path, default=OUTPUT, help="where the JSON is written")
    args = parser.parse_args()

    run = json.loads(args.run.read_text(encoding="utf-8"))
    cpu_run = json.loads(args.cpu_run.read_text(encoding="utf-8"))
    chunks = {chunk.id: chunk for chunk in label_chunks(get_settings())}
    try:
        data = page_data(args.run.stem, run, cpu_run, load_questions(), chunks)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{args.out}: {args.out.stat().st_size / 1e3:.0f} kB")
    print(summary(data))
    return 0


def page_data(
    name: str,
    run: dict[str, Any],
    cpu_run: dict[str, Any],
    questions: list[Question],
    chunks: dict[str, Chunk],
) -> dict[str, Any]:
    """The page's JSON: `ranks` and `top_chunk` hold one entry per question, in the order of
    `questions`. Raises ValueError when the run doesn't fit the answer key or the store."""
    results = rescored_run(run, questions, chunks)
    cpu_query_ms = {row["label"]: row["query_ms_p50"] for row in cpu_run["results"]}
    top_chunk = {r.label: [q.top_in_drug[0].chunk for q in r.questions] for r in results}
    shown = sorted({chunk for ids in top_chunk.values() for chunk in ids})
    return {
        "meta": {
            "run": name,
            "date": run["run"]["date"],
            "questions": len(questions),
            "chunks": run["run"]["chunks"],
            "top_k": run["run"]["top_k"],
            "hit": "a retrieved chunk of the question's drug that contains its evidence "
            "or one of its pooled_evidence passages",
            "source": SOURCE,
        },
        "models": [model(result, cpu_query_ms.get(result.label)) for result in results],
        "questions": [
            question.model_dump(
                include={
                    "id",
                    "question",
                    "drug",
                    "section_group",
                    "evidence",
                    "pooled_evidence",
                }
            )
            for question in questions
        ],
        "ranks": {
            r.label: {
                "in_drug": [q.rank_in_drug for q in r.questions],
                "whole_index": [q.rank_whole_index for q in r.questions],
            }
            for r in results
        },
        "top_chunk": top_chunk,
        "chunks": {
            chunk_id: {
                "section": chunks[chunk_id].section,
                "brand": chunks[chunk_id].brand,
                "text": chunks[chunk_id].text,
            }
            for chunk_id in shown
        },
    }


def model(result: Result, cpu_query_ms: float | None) -> dict[str, Any]:
    return {
        "label": result.label,
        "model": result.model,
        "dimensions": result.dimensions,
        "index_mb": round(result.index_mb, 1),
        "weights_mb": WEIGHTS_MB[result.label],
        "query_ms": round(result.query_ms_p50),
        "query_device": query_device(result.query_device),
        "cpu_query_ms": None if cpu_query_ms is None else round(cpu_query_ms),
        "recall_at_5": {
            "in_drug": round(result.in_drug.recall_at_5, 4),
            "whole_index": round(result.whole_index.recall_at_5, 4),
        },
    }


def query_device(device: str) -> str:
    if device.startswith("cuda"):
        return "gpu"
    if device == "openrouter":
        return "cloud"
    return device


def summary(data: dict[str, Any]) -> str:
    """Recall@5 recomputed from the written ranks, to set beside the decision doc's table."""
    lines = ["| Model | R@5 in drug | R@5 whole index | CPU query (ms) |", "|---|---|---|---|"]
    for entry in data["models"]:
        ranks = data["ranks"][entry["label"]]
        cpu = "-" if entry["cpu_query_ms"] is None else str(entry["cpu_query_ms"])
        lines.append(
            f"| {entry['label']} | {recall(ranks['in_drug'], 5):.2f} "
            f"| {recall(ranks['whole_index'], 5):.2f} | {cpu} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
