from typing import Any

from evals.multilang.run import (
    PAIRS,
    Asked,
    german_share,
    pair_questions,
    report,
    searches_in_german,
    verdict_totals,
    written_in,
)
from evals.retrieval.dataset import load_questions
from evals.retrieval.query_translation import load_german
from evals.safety.run import Answer

from molecula.schemas.claims import ClaimLabel

GERMAN = (
    "Omeprazol hemmt die Protonenpumpe in den Belegzellen des Magens, sodass weniger Säure "
    "gebildet wird [1]. Die Wirkung hält auch nach dem Absetzen noch einige Tage an [1]."
)
ENGLISH = (
    "Omeprazole blocks the proton pump of the stomach's parietal cells, which lowers the amount "
    "of acid that is made [1]. The effect can last for days after the last dose [1]."
)


def answer(*events: dict[str, Any], category: str | None = "ok") -> Answer:
    done = [{"type": "done", "category": category, "step_limit_reached": False}]
    return Answer("omeprazole-mechanism-de-1", 200, [*events, *done], 12.0)


def token(text: str) -> dict[str, Any]:
    return {"type": "token", "text": text}


def source_check(*labels: ClaimLabel, checked: bool = True) -> dict[str, Any]:
    claims = [{"text": "x", "refs": [1], "label": label, "decided_by": "model"} for label in labels]
    return {"type": "source_check", "checked": checked, "claims": claims}


def asked(language: str, answer: Answer) -> Asked:
    return Asked(pair_questions()[0], language, answer)  # type: ignore[arg-type]


def test_every_pair_has_an_english_and_a_german_question() -> None:
    german = load_german(load_questions())

    assert len(PAIRS) == len(set(PAIRS)) == 15
    assert all(question.id in german for question in pair_questions())


def test_a_german_answer_is_german_and_an_english_one_english() -> None:
    assert written_in(GERMAN) == "de"
    assert written_in(ENGLISH) == "en"


def test_a_german_answer_quoting_an_english_label_sentence_stays_german() -> None:
    quoted = GERMAN + ' Die Fachinformation sagt: "Omeprazole is a proton pump inhibitor." [2]'

    assert written_in(quoted) == "de"


def test_an_answer_that_switches_language_halfway_is_mixed() -> None:
    assert written_in(GERMAN + " " + ENGLISH) == "mixed"


def test_text_without_function_words_has_no_language() -> None:
    assert german_share("Omeprazol [1]") is None
    assert written_in("Omeprazol [1]") == "none"


def test_citation_numbers_are_not_counted_as_words() -> None:
    assert german_share("[1] [2, 3]") is None


def test_the_source_check_verdicts_are_counted_per_label() -> None:
    answers = [
        asked("de", answer(token(GERMAN), source_check("supported", "supported", "unsupported"))),
        asked("de", answer(token(GERMAN), source_check("not_a_claim", "held_elsewhere"))),
        asked("de", answer(token(GERMAN), source_check(checked=False))),
    ]

    totals = verdict_totals(answers)

    assert totals == {"supported": 2, "unsupported": 1, "not_a_claim": 1, "held_elsewhere": 1}
    assert answers[2].verdicts is None


def test_a_fixed_answer_from_the_guard_is_refused_but_not_failed() -> None:
    refused = asked("de", answer(token("Dazu kann ich nichts sagen."), category="off_topic"))
    failed = Asked(
        refused.question,
        "de",
        Answer("x", 200, [{"type": "error", "kind": "timeout", "message": "Zu langsam."}], 1.0),
    )

    assert refused.refused and not refused.failed
    assert failed.failed and not failed.refused


def test_the_report_leaves_fixed_answers_out_of_the_language_count() -> None:
    answers = [
        asked("de", answer(token(GERMAN), source_check("supported"))),
        asked("de", answer(token(ENGLISH), source_check("unsupported"))),
        asked("de", answer(token("Dazu kann ich nichts sagen."), category="off_topic")),
        asked("en", answer(token(ENGLISH), source_check("supported"))),
    ]

    lines = report(answers).splitlines()

    assert "| Fixed answer from the guard | 1 | 0 |" in lines
    assert "| Written in the question's language | 1 of 2 | 1 of 1 |" in lines
    assert "| Claims supported, of all claims | 0.50 (1 of 2) | 1.00 (1 of 1) |" in lines


def test_label_searches_are_counted_by_the_language_they_were_written_in() -> None:
    def search(question: str) -> dict[str, Any]:
        return {
            "type": "tool_call",
            "id": "1",
            "name": "search_labels",
            "args": {"question": question},
        }

    answers = [
        asked("de", answer(search("Wie wirkt Omeprazol?"), search("How does omeprazole work?"))),
        asked("de", answer(search("Omeprazole mechanism"))),
    ]

    assert searches_in_german(answers) == "1 of 3"
