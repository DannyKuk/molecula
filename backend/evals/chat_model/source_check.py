"""Score a source check on hand-labelled claims before the chat relies on it (#212).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.source_check

`datasets/source_check_claims.yaml` holds answers from the from-memory and no-label evals, split
into claims by `guard/claims.py` and labelled by hand. Each answer's text and tool results come
from those evals' caches in `data/build/eval/`, so the run needs the owner's build directory. The
run stops when an answer no longer splits into its labelled claims: relabel after changing the
splitter.

`ChatModelSourceCheck` with the configured chat model checks each answer once. The report gives,
for each kind of labelled claim (additions with and without a citation, citation misses,
supported claims, non-claims), how the check judged it: rejected as unsupported (the amber mark in
the chat), held by another returned result (#220) and whether it named a ref the labels name, or
supported. It also gives who decided each rejection and the seconds per answer. Checks are cached
per model, the check's reasoning effort (`SOURCE_CHECK_REASONING_EFFORT`, medium unless set) and
prompt. `--cache` reports a cache file as it is, without a model, to compare with an earlier run.
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

import yaml
from evals.chat_model.no_label import read_verdicts
from pydantic import BaseModel, ConfigDict, model_validator

from molecula import prompts
from molecula.agent.llm import chat_model_name, get_source_check_model
from molecula.config import Settings, get_settings
from molecula.guard.claims import split_claims
from molecula.guard.safety import fixed_answer
from molecula.guard.source_check import ChatModelSourceCheck
from molecula.schemas.chat import ToolResultEvent
from molecula.schemas.claims import CheckedClaim, ClaimLabel
from molecula.schemas.source_check import CheckedAnswer, SourceCheckFailed

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "source_check_claims.yaml"
VERDICTS = Path(__file__).resolve().parent
# The proposed go/no-go bar (#212): additions caught and supported claims wrongly rejected. A
# citation miss is meant to come out held elsewhere since #220, so it no longer counts as caught.
MIN_CAUGHT = 0.80
MAX_WRONGLY_REJECTED = 0.10


class LabelledClaim(BaseModel):
    """A claim judged by hand against the results it cites. `held_by` lists the returned
    results that hold an unsupported claim it doesn't cite: a citation miss, not an addition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    refs: tuple[int, ...]
    label: ClaimLabel
    held_by: tuple[int, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def unsupported_claims_say_why(self) -> Self:
        if self.label == "unsupported" and not self.note:
            raise ValueError(f"An unsupported claim needs a note: {self.text[:60]}")
        if self.held_by and self.label != "unsupported":
            raise ValueError(f"Only an unsupported claim has held_by: {self.text[:60]}")
        return self

    @property
    def addition(self) -> bool:
        """A fact no returned result holds: from memory, or a misreading."""
        return self.label == "unsupported" and not self.held_by


class LabelledAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    eval: Literal["from_memory", "no_label"]
    cache: str
    run_id: str
    claims: list[LabelledClaim]

    @property
    def key(self) -> str:
        return f"{self.eval}/{self.cache}/{self.run_id}"


@dataclass(frozen=True)
class CachedAnswer:
    text: str
    results: list[ToolResultEvent]


@dataclass(frozen=True)
class Check:
    key: str
    checked: CheckedAnswer | None
    seconds: float
    error: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, help="report this cache file without a model")
    args = parser.parse_args()
    labelled = load_dataset()
    if args.cache:
        print(report(args.cache.stem, labelled, list(read_cache(args.cache).values())))
        return 0
    settings = get_settings()
    model_name = chat_model_name(settings)
    answers = read_answers(settings, labelled)
    mismatched = [answer.key for answer in labelled if not splits_as_labelled(answer, answers)]
    if mismatched:
        raise SystemExit(f"These answers no longer split into their labelled claims: {mismatched}")
    checks = asyncio.run(check_all(settings, model_name, labelled, answers))
    print(report(check_label(settings, model_name), labelled, checks))
    return 0


def load_dataset(path: Path = DATASET) -> list[LabelledAnswer]:
    """The labelled answers, checked against the hand verdicts of the evals they come from: an
    answer judged to add a fact from memory must have a claim labelled as that addition."""
    answers = [
        LabelledAnswer.model_validate(entry) for entry in yaml.safe_load(path.read_text("utf-8"))
    ]
    keys = [answer.key for answer in answers]
    if len(set(keys)) < len(keys):
        raise ValueError(f"Repeated answers in {path}")
    for answer in answers:
        verdicts = read_verdicts(VERDICTS / f"{answer.eval}_verdicts" / f"{answer.cache}.yaml")
        if verdicts is None or answer.run_id not in verdicts:
            raise ValueError(f"No hand verdict for {answer.key}")
        if verdicts[answer.run_id].from_memory and not any(c.addition for c in answer.claims):
            raise ValueError(f"{answer.key} adds a fact from memory but no claim is labelled so")
    return answers


def read_answers(settings: Settings, labelled: list[LabelledAnswer]) -> dict[str, CachedAnswer]:
    answers = {}
    for eval_name, cache in sorted({(answer.eval, answer.cache) for answer in labelled}):
        path = settings.build_dir / "eval" / eval_name / f"{cache}.jsonl"
        if not path.exists():
            raise SystemExit(f"Missing the eval cache {path}")
        for line in path.read_text("utf-8").splitlines():
            entry = json.loads(line)
            # The from-memory eval caches the agent's answer, the no-label eval the last turn.
            events = (entry.get("answer") or entry["last"])["events"]
            answers[f"{eval_name}/{cache}/{entry['run_id']}"] = CachedAnswer(
                text="".join(event["text"] for event in events if event["type"] == "token"),
                results=[
                    ToolResultEvent.model_validate(event)
                    for event in events
                    if event["type"] == "tool_result"
                ],
            )
    return answers


def splits_as_labelled(answer: LabelledAnswer, answers: dict[str, CachedAnswer]) -> bool:
    claims = split_claims(answers[answer.key].text, leave_out=[fixed_answer("overdose_emergency")])
    return [(c.text, c.refs) for c in claims] == [(c.text, c.refs) for c in answer.claims]


async def check_all(
    settings: Settings,
    model_name: str,
    labelled: list[LabelledAnswer],
    answers: dict[str, CachedAnswer],
) -> list[Check]:
    source_check = ChatModelSourceCheck(get_source_check_model(settings))
    cache = cache_path(settings, model_name)
    cached = read_cache(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    for answer in labelled:
        if answer.key not in cached:
            cached_answer = answers[answer.key]
            start = time.perf_counter()
            try:
                checked = await source_check.check(cached_answer.text, cached_answer.results)
            except SourceCheckFailed as error:
                checks.append(Check(answer.key, None, time.perf_counter() - start, repr(error)))
                print(f"{answer.key}: {error!r}", flush=True)
                continue
            cached[answer.key] = Check(answer.key, checked, time.perf_counter() - start)
            with cache.open("a", encoding="utf-8") as file:
                file.write(json.dumps(to_json(cached[answer.key]), ensure_ascii=False) + "\n")
            print(f"{answer.key}: {cached[answer.key].seconds:.1f} s", flush=True)
        checks.append(cached[answer.key])
    return checks


def cache_path(settings: Settings, model_name: str) -> Path:
    """Keyed by the model, the check's reasoning effort and the checker's prompt."""
    name = check_label(settings, model_name)
    key = hashlib.sha256(f"{name}\n{prompts.load('guard/source_check')}".encode()).hexdigest()
    return (
        settings.build_dir / "eval" / "source_check" / f"{name.replace('/', '_')}-{key[:12]}.jsonl"
    )


def check_label(settings: Settings, model_name: str) -> str:
    """The model and the check's effort, named as #212's runs were: `openai/gpt-oss-20b-medium`."""
    effort = settings.source_check_reasoning_effort
    return model_name if effort == "default" else f"{model_name}-{effort}"


def read_cache(cache: Path) -> dict[str, Check]:
    if not cache.exists():
        return {}
    checks = {}
    for line in cache.read_text("utf-8").splitlines():
        entry = json.loads(line)
        checked = CheckedAnswer.model_validate(entry["checked"])
        checks[entry["key"]] = Check(entry["key"], checked, entry["seconds"])
    return checks


def to_json(check: Check) -> dict[str, object]:
    assert check.checked is not None
    return {"key": check.key, "checked": check.checked.model_dump(), "seconds": check.seconds}


def report(name: str, labelled: list[LabelledAnswer], checks: list[Check]) -> str:
    by_key = {check.key: check.checked for check in checks}
    done = [(answer, checked) for answer in labelled if (checked := by_key.get(answer.key))]
    pairs = [
        pair for answer, checked in done for pair in zip(answer.claims, checked.claims, strict=True)
    ]
    additions = [(c, v) for c, v in pairs if c.addition]
    misses = [(c, v) for c, v in pairs if c.label == "unsupported" and not c.addition]
    supported = [(c, v) for c, v in pairs if c.label == "supported"]
    non_claims = [(c, v) for c, v in pairs if c.label == "not_a_claim"]
    marked = [(c, v) for c, v in pairs if v.label == "unsupported"]
    caught = rate(additions)
    wrongly = rate(supported)
    seconds = [check.seconds for check in checks if check.checked is not None]
    clean = [
        checked for answer, checked in done if all(c.label != "unsupported" for c in answer.claims)
    ]
    with_addition = [checked for answer, checked in done if any(c.addition for c in answer.claims)]
    deciders = Counter(v.decided_by for _, v in marked)
    go = caught >= MIN_CAUGHT and wrongly <= MAX_WRONGLY_REJECTED
    lines = [
        f"{name}: {len(done)} of {len(labelled)} answers checked, {len(pairs)} claims",
        "",
        "| Claims | Labelled | Unsupported | Held elsewhere | …naming a labelled ref "
        "| Supported | Not a claim |",
        "|---|---|---|---|---|---|---|",
        row("Additions, cited", [p for p in additions if p[0].refs]),
        row("Additions, uncited", [p for p in additions if not p[0].refs]),
        row("Citation misses (a returned result holds them)", misses),
        row("Supported", supported),
        row("Not a claim", non_claims),
        "",
        f"Marked unsupported (amber in the chat): {len(marked)}: "
        f"{sum(c.addition for c, _ in marked)} additions, "
        f"{sum(c.label == 'unsupported' and not c.addition for c, _ in marked)} citation misses, "
        f"{judged_as(marked, 'supported')} supported, "
        f"{judged_as(marked, 'not_a_claim')} non-claims.",
        "",
        "| Answers | Count | Failed the check |",
        "|---|---|---|",
        f"| All | {len(done)} | {sum(not checked.passed for _, checked in done)} |",
        f"| With an addition | {len(with_addition)} | {sum(not c.passed for c in with_addition)} |",
        f"| Without an unsupported claim | {len(clean)} | {sum(not c.passed for c in clean)} |",
        "",
        "Rejections by who decided: " + ", ".join(f"{who} {n}" for who, n in deciders.items()),
    ]
    if seconds:
        output_tokens = statistics.mean(checked.usage.output_tokens for _, checked in done)
        lines.append(
            f"Seconds per answer: p50 {statistics.median(seconds):.1f}, "
            f"mean {statistics.mean(seconds):.1f}, max {max(seconds):.1f}; "
            f"output tokens per answer: mean {output_tokens:.0f}"
        )
    lines += [
        "",
        f"Bar (proposed): catch at least {MIN_CAUGHT:.0%} of the additions and wrongly reject at "
        f"most {MAX_WRONGLY_REJECTED:.0%} of the supported claims: "
        f"{'go' if go else 'no-go'} ({caught:.0%} caught, {wrongly:.0%} wrongly rejected).",
        "",
        "Additions let through:",
        *listed((c, v) for c, v in additions if v.label != "unsupported"),
        "",
        "Citation misses not held elsewhere with a labelled ref:",
        *listed((c, v) for c, v in misses if not held_with_labelled_ref(c, v)),
        "",
        "Supported claims and non-claims rejected:",
        *listed((c, v) for c, v in supported + non_claims if v.label == "unsupported"),
    ]
    return "\n".join(lines)


type Pair = tuple[LabelledClaim, CheckedClaim]


def held_with_labelled_ref(claim: LabelledClaim, verdict: CheckedClaim) -> bool:
    return verdict.label == "held_elsewhere" and bool(set(verdict.held_by) & set(claim.held_by))


def checked_as(pairs: list[Pair], label: str) -> int:
    """How many of the claims the check gave this label."""
    return sum(verdict.label == label for _, verdict in pairs)


def judged_as(pairs: list[Pair], label: str) -> int:
    """How many of the claims were labelled so by hand."""
    return sum(claim.label == label for claim, _ in pairs)


def rate(pairs: list[Pair]) -> float:
    """The share of the claims the check rejected."""
    return checked_as(pairs, "unsupported") / len(pairs) if pairs else 0.0


def row(name: str, pairs: list[Pair]) -> str:
    counts = [
        checked_as(pairs, "unsupported"),
        checked_as(pairs, "held_elsewhere"),
        sum(held_with_labelled_ref(c, v) for c, v in pairs),
        checked_as(pairs, "supported"),
        checked_as(pairs, "not_a_claim"),
    ]
    return f"| {name} | {len(pairs)} | " + " | ".join(str(n) for n in counts) + " |"


def listed(pairs: Iterable[Pair]) -> list[str]:
    lines = []
    for claim, verdict in pairs:
        labelled_as = claim.label + (f", held by {list(claim.held_by)}" if claim.held_by else "")
        checked = verdict.label + (f" {list(verdict.held_by)}" if verdict.held_by else "")
        lines.append(
            f"- {claim.text[:90]!r} (labelled {labelled_as}, checked {checked} by "
            f"{verdict.decided_by}): {verdict.reason or '-'}"
        )
    return lines or ["- none"]


if __name__ == "__main__":
    raise SystemExit(main())
