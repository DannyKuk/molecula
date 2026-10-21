"""Ask the same questions in German and in English through the chat and compare the answers (#357).

    OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
        uv run python -m evals.multilang.run --times 3

Each of the `PAIRS` is a retrieval question (`datasets/retrieval_questions.yaml`) and its German
version (`retrieval_questions_de.yaml`), scored with the same answer key. Both are asked
`--times` times through `POST /chat` in-process, guard and source check included. Per language the
report gives: answers written in the question's language (by function words), questions the guard
answered with a fixed text, answers with an answering passage in a label search's top 5, and the
source check's verdicts on the answers' claims. Answers are cached in
`data/build/eval/multilang/`, keyed by the model, every prompt file and the tool descriptions.
"""

import argparse
import asyncio
import json
import re
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

import httpx
from evals.chat_model.citations import tool_descriptions
from evals.chat_model.search_language import GERMAN_WORDS, answered, search_questions
from evals.no_limits import for_evals
from evals.retrieval.dataset import Question, load_questions
from evals.retrieval.query_translation import load_german
from evals.safety.run import Answer, cache_path, post_chat, read_cache

from molecula.agent.llm import chat_model_name
from molecula.config import get_settings
from molecula.main import app, lifespan
from molecula.schemas.claims import ClaimLabel

type Language = Literal["de", "en"]
type Written = Literal["de", "en", "mixed", "none"]

LANGUAGES: tuple[Language, ...] = ("de", "en")
# One question per section group, plus one more where the German generic name differs from the
# English one (Paracetamol, Lamotrigin, Methylphenidat). Overdose and abuse questions are left out
# because the guard's emergency text would decide the language, and so are the questions #114 saw
# the guard answer as personal advice.
PAIRS = (
    "omeprazole-mechanism",
    "acetaminophen-pharmacology",
    "donepezil-indications",
    "lamotrigine-dosing",
    "ciprofloxacin-tizanidine",
    "montelukast-mood",
    "metformin-kidneys",
    "finasteride-contraindications",
    "pseudoephedrine-antidepressants",
    "imatinib-common-side-effects",
    "famotidine-clinical-studies",
    "valacyclovir-patient-information",
    "cetirizine-product",
    "methylphenidate-product",
    "ondansetron-specific-populations",
)
ANSWERED_BY_AGENT = ("ok", "overdose_emergency")
FUNCTION_WORDS: dict[Language, re.Pattern[str]] = {
    "de": re.compile(
        r"\b(?:der|die|das|den|dem|des|und|ist|sind|nicht|mit|bei|für|von|zu|zur|zum|auf|"
        r"wird|werden|kann|können|oder|auch|eine?[mnrs]?|wie|nach|sich|als|im|wenn|dass)\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(?:the|and|is|are|not|with|for|of|to|on|be|can|or|also|a|as|it|this|that|which|by|"
        r"from|may|should|have|has|when|if)\b",
        re.IGNORECASE,
    ),
}
CITATION = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
# A share of German function words at or above this is a German answer, at or below 1 - this
# an English one. Quoted label text leaves a German answer well above it.
CLEAR_SHARE = 0.7


@dataclass(frozen=True)
class Asked:
    """One asking of a question in one language."""

    question: Question
    language: Language
    answer: Answer

    @property
    def refused(self) -> bool:
        """The guard gave a fixed answer instead of the agent's."""
        return not self.failed and self.answer.category not in ANSWERED_BY_AGENT

    @property
    def failed(self) -> bool:
        return self.answer.error is not None

    @property
    def written(self) -> Written:
        return written_in(self.answer.text)

    @property
    def found(self) -> bool:
        return answered(self.question, self.answer)

    @property
    def verdicts(self) -> Counter[ClaimLabel] | None:
        """The source check's verdict on each claim, None when the check failed or didn't run."""
        return verdicts(self.answer)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--times", type=int, default=1, help="askings per question and language")
    args = parser.parse_args()
    questions = pair_questions()
    german = load_german(load_questions())
    model_name, asked = asyncio.run(ask_all(questions, german, args.times))
    print(f"{model_name}, {len(questions)} questions x {args.times} in German and English\n")
    print(report(asked))
    print("\n" + pair_lines(questions, asked))
    return 0


def pair_questions() -> list[Question]:
    by_id = {question.id: question for question in load_questions()}
    missing = [pair for pair in PAIRS if pair not in by_id]
    if missing:
        raise ValueError(f"Not retrieval questions: {missing}")
    return [by_id[pair] for pair in PAIRS]


async def ask_all(
    questions: list[Question], german: dict[str, str], times: int
) -> tuple[str, list[Asked]]:
    async with lifespan(app):
        if app.state.chat is None:
            raise SystemExit("The chat is off: build the index and set a chat model.")
        settings = get_settings()
        model_name = chat_model_name(settings)
        cache = cache_path(settings, model_name, tool_descriptions(app), "multilang")
        answers = read_cache(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        for_evals(app)
        asked = []
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
            for run in range(1, times + 1):
                for question in questions:
                    for language in LANGUAGES:
                        item_id = f"{question.id}-{language}-{run}"
                        if item_id not in answers:
                            text = german[question.id] if language == "de" else question.question
                            messages = [{"role": "user", "content": text}]
                            answers[item_id] = await post_chat(client, item_id, messages)
                            with cache.open("a", encoding="utf-8") as file:
                                file.write(json.dumps(asdict(answers[item_id])) + "\n")
                            print(f"{item_id}: {answers[item_id].seconds:.1f} s", flush=True)
                        asked.append(Asked(question, language, answers[item_id]))
    return model_name, asked


def german_share(text: str) -> float | None:
    """The share of German among the German and English function words in `text`, None when it
    has neither."""
    text = CITATION.sub(" ", text)
    german = len(FUNCTION_WORDS["de"].findall(text))
    english = len(FUNCTION_WORDS["en"].findall(text))
    return german / (german + english) if german + english else None


def written_in(text: str) -> Written:
    share = german_share(text)
    if share is None:
        return "none"
    if share >= CLEAR_SHARE:
        return "de"
    if share <= 1 - CLEAR_SHARE:
        return "en"
    return "mixed"


def verdicts(answer: Answer) -> Counter[ClaimLabel] | None:
    check = next((e for e in answer.events if e["type"] == "source_check"), None)
    if check is None or not check["checked"]:
        return None
    return Counter(claim["label"] for claim in check["claims"])


def report(asked: list[Asked]) -> str:
    rows = [
        "| | German | English |",
        "|---|---|---|",
    ]
    columns = {language: [a for a in asked if a.language == language] for language in LANGUAGES}

    def row(name: str, value: Callable[[list[Asked]], str]) -> None:
        rows.append(f"| {name} | {value(columns['de'])} | {value(columns['en'])} |")

    row("Answers", lambda a: str(len(a)))
    row("Failed", lambda a: str(sum(x.failed for x in a)))
    row("Fixed answer from the guard", lambda a: str(sum(x.refused for x in a)))
    row("Written in the question's language", lambda a: own_language(a))
    row("German function-word share, median", lambda a: median_share(a))
    row("Label searches written in German", lambda a: searches_in_german(a))
    row("Answering passage in a search's top 5", lambda a: share_of(a, lambda x: x.found))
    row("Source check ran", lambda a: share_of(a, lambda x: x.verdicts is not None))
    totals = {language: verdict_totals(column) for language, column in columns.items()}
    for label in ("supported", "held_elsewhere", "unsupported", "not_a_claim"):
        rows.append(
            f"| Claims {label.replace('_', ' ')} | {totals['de'][label]} | {totals['en'][label]} |"
        )
    row("Claims supported, of all claims", lambda a: supported_share(verdict_totals(a)))
    row("Seconds, median", lambda a: f"{statistics.median(x.answer.seconds for x in a):.1f}")
    return "\n".join(rows)


def own_language(asked: list[Asked]) -> str:
    agent = [a for a in asked if not a.refused and not a.failed]
    return f"{sum(a.written == a.language for a in agent)} of {len(agent)}"


def searches_in_german(asked: list[Asked]) -> str:
    searches = [text for a in asked for text in search_questions(a.answer)]
    return f"{sum(bool(GERMAN_WORDS.search(text)) for text in searches)} of {len(searches)}"


def median_share(asked: list[Asked]) -> str:
    shares = [s for a in asked if not a.refused and (s := german_share(a.answer.text)) is not None]
    return f"{statistics.median(shares):.2f}" if shares else "-"


def share_of(asked: list[Asked], test: Callable[[Asked], bool]) -> str:
    agent = [a for a in asked if not a.refused and not a.failed]
    return f"{sum(test(a) for a in agent)} of {len(agent)}"


def verdict_totals(asked: list[Asked]) -> Counter[ClaimLabel]:
    return sum((a.verdicts for a in asked if a.verdicts is not None), Counter())


def supported_share(totals: Counter[ClaimLabel]) -> str:
    claims = claim_count(totals)
    if not claims:
        return "-"
    return f"{totals['supported'] / claims:.2f} ({totals['supported']} of {claims})"


def claim_count(verdicts: Counter[ClaimLabel]) -> int:
    return verdicts.total() - verdicts["not_a_claim"]


def pair_lines(questions: list[Question], asked: list[Asked]) -> str:
    lines = []
    for question in questions:
        parts = []
        for language in LANGUAGES:
            runs = [a for a in asked if a.question.id == question.id and a.language == language]
            parts.append(f"{language} " + ", ".join(run_summary(a) for a in runs))
        lines.append(f"- {question.id}: " + "; ".join(parts))
    return "\n".join(lines)


def run_summary(asked: Asked) -> str:
    if asked.failed:
        return "failed"
    if asked.refused:
        return f"fixed answer ({asked.answer.category})"
    found = "hit" if asked.found else "miss"
    checked = asked.verdicts
    supported = f"{checked['supported']}/{claim_count(checked)}" if checked else "-"
    return f"{asked.written} {found} {supported}"


if __name__ == "__main__":
    raise SystemExit(main())
