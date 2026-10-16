import pytest

from molecula.agent.channel_markers import ChannelMarkerFilter, without_channel_markers

MARKED = "Imatinib binds through van der Waals interactions【commentary: get_complex】."
UNMARKED = "Imatinib binds through van der Waals interactions."


def streamed(chunks: list[str]) -> str:
    markers = ChannelMarkerFilter()
    return "".join(markers.feed(chunk) for chunk in chunks) + markers.flush()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (MARKED, UNMARKED),
        ("It binds ABL1 【commentary: get_complex】.", "It binds ABL1."),
        ("It binds ABL1 【commentary: get_complex】 and KIT.", "It binds ABL1 and KIT."),
        (
            "It binds ABL1【commentary】, KIT【analysis】 and PDGFR【final】.",
            "It binds ABL1, KIT and PDGFR.",
        ),
        ("It binds ABL1【commentary to=functions.get_complex】.", "It binds ABL1."),
        ("It binds ABL1【 Commentary: get_complex 】.", "It binds ABL1."),
    ],
    ids=[
        "before a full stop",
        "after a space",
        "mid-sentence",
        "every channel",
        "harmony recipient",
        "spaced, capitalised",
    ],
)
def test_a_channel_marker_is_removed_with_the_space_before_it(text: str, expected: str) -> None:
    assert without_channel_markers(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Nausea is common【1】.",
        "Nausea【1, 2】 and edema [3].",
        "Nausea [1, 4] and edema [2][3].",
        "A note in 【brackets】 stays.",
        "Unclosed 【commentary: get_complex",
    ],
)
def test_citations_and_other_brackets_are_left_alone(text: str) -> None:
    assert without_channel_markers(text) == text
    assert streamed(list(text)) == text


def test_a_marker_in_one_chunk_is_removed() -> None:
    assert streamed(["It binds ABL1 ", "【commentary: get_complex】", "."]) == "It binds ABL1."


@pytest.mark.parametrize(
    "text",
    [
        MARKED,
        "Nausea【1】 and edema [2]. It binds ABL1 【commentary: get_complex】 and KIT【1, 2】.",
        "It binds ABL1【analysis】【commentary: get_complex】.\n\nNext paragraph【final】.",
    ],
)
def test_text_split_anywhere_streams_out_as_the_whole_text_would(text: str) -> None:
    whole = without_channel_markers(text)

    for cut in range(len(text) + 1):
        assert streamed([text[:cut], text[cut:]]) == whole
    assert streamed(list(text)) == whole


def test_text_with_no_marker_comes_out_as_it_went_in() -> None:
    text = "Imatinib blocks ABL1 [1].\n\n- It is a tablet【2】.  "

    assert streamed(list(text)) == text


def test_text_waits_only_while_a_marker_could_still_be_forming() -> None:
    markers = ChannelMarkerFilter()

    assert markers.feed("It binds ABL1 ") == "It binds ABL1"
    assert markers.feed("【commen") == ""
    assert markers.feed("tary: get_complex】") == ""
    assert markers.feed(" and KIT") == " and KIT"


def test_a_long_bracket_that_never_closes_is_let_through() -> None:
    markers = ChannelMarkerFilter()
    text = "【" + "x" * 200

    assert markers.feed(text) == text
