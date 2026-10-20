from molecula.agent.references import cited_refs


def test_citations_are_read_in_every_bracket_style_once_each() -> None:
    answer = "Nausea [2]. Edema [3][1]. Rash [1, 4]. Hepatotoxicity [2]."

    assert cited_refs(answer) == [2, 3, 1, 4]


def test_full_width_brackets_are_citations_too() -> None:
    answer = "Nausea【2】. Edema 【3, 1】."

    assert cited_refs(answer) == [2, 3, 1]


def test_links_footnotes_and_other_markers_are_not_citations() -> None:
    answer = (
        "See the [Gleevec label](https://dailymed.nlm.nih.gov/x) [label 2] 【4†source】 "
        "and the dose range [10-20]."
    )

    assert cited_refs(answer) == []
