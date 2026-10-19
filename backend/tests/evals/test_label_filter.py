from pathlib import Path

import pytest
from evals.chat_model.filters import typo_outcome
from evals.retrieval.dataset import Question, load_questions, load_typos

from molecula.schemas.compounds import Resolution, Suggestion
from molecula.schemas.retrieval import DrugFilter, LabelFilter, LabelQuery

GLEEVEC = Question(
    id="imatinib-mechanism",
    question="How does Gleevec work against leukemia?",
    cid=5291,
    drug="imatinib",
    section_group="pharmacology",
    evidence="inhibits the BCR-ABL tyrosine kinase",
    origin="hand",
)


def test_every_typo_question_is_a_retrieval_question_with_its_typo_in_it() -> None:
    questions = load_questions()
    typos = load_typos(questions)

    by_id = {question.id: question for question in questions}
    assert len(typos) == 18
    assert all(typo.question != by_id[typo.id].question for typo in typos)
    assert all(typo.evidence == by_id[typo.id].evidence for typo in typos)


@pytest.mark.parametrize(
    "entry",
    [
        '- id: unknown-question\n  question: "How does Gleevc work?"\n  typo: Gleevc\n',
        '- id: imatinib-mechanism\n  question: "How does Gleevec work?"\n  typo: Gleevc\n',
    ],
)
def test_a_typo_needs_a_known_id_and_its_typo_in_the_question(tmp_path: Path, entry: str) -> None:
    path = tmp_path / "typos.yaml"
    path.write_text(entry, encoding="utf-8")

    with pytest.raises(ValueError, match="needs a known id"):
        load_typos([GLEEVEC], path)


def suggesting(cid: int) -> LabelFilter:
    """The filter for "Gleevc", not supported, with a suggestion of the drug `cid`."""
    resolution = Resolution(
        query="Gleevc",
        status="not_supported",
        suggestions=[Suggestion(alias="Gleevec", cid=cid, name="imatinib")],
    )
    return LabelFilter(extracted=LabelQuery(substances=["Gleevc"]), unsupported=[resolution])


@pytest.mark.parametrize(
    ("found", "outcome"),
    [
        (
            LabelFilter(
                extracted=LabelQuery(substances=["Gleevec"]),
                drugs=[DrugFilter(name="Gleevec", cid=5291, generic="imatinib", set_ids=["a"])],
            ),
            "searched as the drug",
        ),
        (suggesting(5291), "not supported, the drug suggested"),
        (suggesting(1), "lost"),
        (LabelFilter(extracted=LabelQuery()), "lost"),
    ],
)
def test_typo_outcome(found: LabelFilter, outcome: str) -> None:
    assert typo_outcome(GLEEVEC, found) == outcome
