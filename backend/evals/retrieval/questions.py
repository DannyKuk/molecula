"""Grow and check the retrieval question set.

    uv run python -m evals.retrieval.questions sample --out chunks.json
    uv run python -m evals.retrieval.questions check

`sample` picks label chunks to write new questions from: every section group is filled up to
--per-group questions, counting the ones already in the dataset, from drugs the group doesn't
cover yet, with OTC labels mixed in. `check` fails on any question whose evidence no chunk of its
drug holds, that doesn't name the drug, or that copies its passage.
"""

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from evals.retrieval.compare_embeddings import label_chunks
from evals.retrieval.dataset import Question, is_hit, load_questions

from molecula.config import Settings, get_settings
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import Chunk

SEED = 88
MIN_CHUNK_CHARS = 400
OTC_SHARE = 1 / 3
# A question that repeats this many words of its passage in a row rewards lexical matching.
COPIED_WORDS = 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    sample_parser = commands.add_parser("sample")
    sample_parser.add_argument("--per-group", type=int, default=7)
    sample_parser.add_argument("--out", type=Path, required=True)
    commands.add_parser("check")
    args = parser.parse_args()

    settings = get_settings()
    chunks = label_chunks(settings)
    questions = load_questions()
    if args.command == "sample":
        sample(chunks, questions, args.per_group, drug_names(settings), args.out)
        return 0
    return check(chunks, questions)


def sample(
    chunks: list[Chunk], questions: list[Question], per_group: int, names: dict[int, str], out: Path
) -> None:
    picks = [
        {
            "chunk": chunk.id,
            "cid": chunk.cid,
            "drug": names[chunk.cid],
            "brands": brands(chunks, chunk.cid),
            "section": chunk.section,
            "section_group": chunk.section_group,
            "product_type": chunk.product_type,
            "text": chunk.text,
        }
        for chunk in pick_chunks(chunks, questions, per_group)
    ]
    out.write_text(json.dumps(picks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(picks)} chunks written to {out}")


def check(chunks: list[Chunk], questions: list[Question]) -> int:
    failures = [
        f"{question.id}: {problem}"
        for question in questions
        if (problem := problem_with(question, chunks))
    ]
    print("\n".join(failures) or f"All {len(questions)} questions pass.")
    return 1 if failures else 0


def problem_with(question: Question, chunks: list[Chunk]) -> str | None:
    answering = [chunk for chunk in chunks if is_hit(question, chunk)]
    if not answering:
        return "no chunk of the drug holds the evidence"
    # People say "Advil", not "Advil Menstrual Pain", and "Dilantin", not "Dilantin-125".
    names = [
        question.drug,
        *(re.split(r"[\s-]", brand)[0] for brand in brands(chunks, question.cid)),
    ]
    if not any(name.lower() in question.question.lower() for name in names):
        return f"the question names none of {names}"
    if any(copies(question.question, chunk.text) for chunk in answering):
        return f"the question repeats {COPIED_WORDS} words in a row from its passage"
    return None


def copies(question: str, text: str) -> bool:
    words = re.findall(r"[a-z0-9]+", text.lower())
    runs = {tuple(words[i : i + COPIED_WORDS]) for i in range(len(words) - COPIED_WORDS + 1)}
    asked = re.findall(r"[a-z0-9]+", question.lower())
    return any(
        tuple(asked[i : i + COPIED_WORDS]) in runs for i in range(len(asked) - COPIED_WORDS + 1)
    )


def pick_chunks(chunks: list[Chunk], questions: list[Question], per_group: int) -> list[Chunk]:
    rng = random.Random(SEED)
    covered: dict[str, set[int]] = defaultdict(set)
    for question in questions:
        covered[question.section_group].add(question.cid)
    by_group: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        if len(chunk.text) >= MIN_CHUNK_CHARS and chunk.cid not in covered[chunk.section_group]:
            by_group[chunk.section_group].append(chunk)

    picks = []
    for group, candidates in sorted(by_group.items()):
        needed = per_group - sum(q.section_group == group for q in questions)
        if needed <= 0:
            continue
        rng.shuffle(candidates)
        otc = one_per_drug([chunk for chunk in candidates if chunk.product_type == "otc"])
        otc = otc[: round(needed * OTC_SHARE)]
        otc_cids = {chunk.cid for chunk in otc}
        rx = one_per_drug(
            [c for c in candidates if c.product_type == "rx" and c.cid not in otc_cids]
        )
        picks.extend(otc + rx[: needed - len(otc)])
    return picks


def one_per_drug(chunks: list[Chunk]) -> list[Chunk]:
    seen: set[int] = set()
    unique = []
    for chunk in chunks:
        if chunk.cid not in seen:
            seen.add(chunk.cid)
            unique.append(chunk)
    return unique


def brands(chunks: list[Chunk], cid: int) -> list[str]:
    return sorted({chunk.brand for chunk in chunks if chunk.cid == cid and chunk.brand})


def drug_names(settings: Settings) -> dict[int, str]:
    conn = connect(settings.db_path)
    try:
        return {compound.cid: compound.name for compound in CompoundStore(conn).all()}
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
