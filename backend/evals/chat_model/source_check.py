"""Score a source check on hand-labelled claims before the chat relies on it (#212).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.chat_model.source_check

`datasets/source_check_claims.yaml` holds answers from the from-memory and no-label evals, split
into claims by `guard/claims.py` and labelled by hand. Each answer's text and tool results come
from those evals' caches in `data/build/eval/`, so the run needs the owner's build directory. The
run stops when an answer no longer splits into its labelled claims: relabel after changing the
splitter.

`ChatModelSourceCheck` with the configured chat model checks each answer once. The report gives
the unsupported claims it catches (additions with and without a citation, and citation misses),
the supported claims and non-claims it wrongly rejects, who decided each rejection, and the
seconds per answer. Checks are cached per model, reasoning effort and prompt.
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
from evals.chat_model.citations import model_label
from evals.chat_model.no_label import read_verdicts
from pydantic import BaseModel, ConfigDict, model_validator

from molecula import prompts
from molecula.agent.llm import ChatModelError, get_chat_model
from molecula.config import Settings, get_settings
from molecula.guard.claims import split_claims
from molecula.guard.safety import fixed_answer
from molecula.guard.source_check import ChatModelSourceCheck
from molecula.schemas.chat import ToolResultEvent
from molecula.schemas.source_check import CheckedAnswer, CheckedClaim, ClaimLabel

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "source_check_claims.yaml"
VERDICTS = Path(__file__).resolve().parent
# The proposed go/no-go bar (#212); the owner sets the final one.
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
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    settings = get_settings()
    model_name = settings.local_llm_model or settings.llm_model or "unknown"
    labelled = load_dataset()
    answers = read_answers(settings, labelled)
    mismatched = [answer.key for answer in labelled if not splits_as_labelled(answer, answers)]
    if mismatched:
        raise SystemExit(f"These answers no longer split into their labelled claims: {mismatched}")
    checks = asyncio.run(check_all(settings, model_name, labelled, answers))
    print(report(model_label(settings, model_name), labelled, checks))
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
    source_check = ChatModelSourceCheck(get_chat_model(settings))
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
            except ChatModelError as error:
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
    """Keyed by the model, its reasoning effort and the checker's prompt."""
    name = model_label(settings, model_name)
    key = hashlib.sha256(f"{name}\n{prompts.load('guard/source_check')}".encode()).hexdigest()
    return (
        settings.build_dir / "eval" / "source_check" / f"{name.replace('/', '_')}-{key[:12]}.jsonl"
    )


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
    done = [(answer, checked) for answer in labelled if (checked := by_key[answer.key])]
    pairs = [
        pair for answer, checked in done for pair in zip(answer.claims, checked.claims, strict=True)
    ]
    unsupported = [(c, v) for c, v in pairs if c.label == "unsupported"]
    additions = [(c, v) for c, v in unsupported if c.addition]
    misses = [(c, v) for c, v in unsupported if not c.addition]
    supported = [(c, v) for c, v in pairs if c.label == "supported"]
    non_claims = [(c, v) for c, v in pairs if c.label == "not_a_claim"]
    caught = rate(unsupported)
    wrongly = rate(supported)
    seconds = [check.seconds for check in checks if check.checked is not None]
    clean = [
        checked for answer, checked in done if all(c.label != "unsupported" for c in answer.claims)
    ]
    with_addition = [checked for answer, checked in done if any(c.addition for c in answer.claims)]
    deciders = Counter(v.decided_by for _, v in pairs if v.label == "unsupported")
    go = caught >= MIN_CAUGHT and wrongly <= MAX_WRONGLY_REJECTED
    lines = [
        f"{name}: {len(done)} of {len(labelled)} answers checked, {len(pairs)} claims",
        "",
        "| Claims | Labelled | Rejected | Rate |",
        "|---|---|---|---|",
        row("Unsupported", unsupported),
        row("- additions, cited", [p for p in additions if p[0].refs]),
        row("- additions, uncited", [p for p in additions if not p[0].refs]),
        row("- citation misses (a returned result holds them)", misses),
        row("Supported", supported),
        row("Not a claim", non_claims),
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
        f"Bar (proposed): catch at least {MIN_CAUGHT:.0%} of the unsupported claims and wrongly "
        f"reject at most {MAX_WRONGLY_REJECTED:.0%} of the supported ones: "
        f"{'go' if go else 'no-go'} ({caught:.0%} caught, {wrongly:.0%} wrongly rejected).",
        "",
        "Unsupported claims let through:",
        *listed((c, v) for c, v in unsupported if v.label != "unsupported"),
        "",
        "Supported claims and non-claims rejected:",
        *listed((c, v) for c, v in supported + non_claims if v.label == "unsupported"),
    ]
    return "\n".join(lines)


type Pair = tuple[LabelledClaim, CheckedClaim]


def rejected(pairs: list[Pair]) -> int:
    return sum(verdict.label == "unsupported" for _, verdict in pairs)


def rate(pairs: list[Pair]) -> float:
    """The share of the claims the check rejected."""
    return rejected(pairs) / len(pairs) if pairs else 0.0


def row(name: str, pairs: list[Pair]) -> str:
    return f"| {name} | {len(pairs)} | {rejected(pairs)} | {rate(pairs):.0%} |"


def listed(pairs: Iterable[Pair]) -> list[str]:
    lines = [
        f"- {claim.text[:90]!r} (labelled {claim.label}, checked {verdict.label} by "
        f"{verdict.decided_by}): {verdict.reason or '-'}"
        for claim, verdict in pairs
    ]
    return lines or ["- none"]


if __name__ == "__main__":
    raise SystemExit(main())
