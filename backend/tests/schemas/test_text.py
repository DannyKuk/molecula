import pytest

from molecula.schemas.text import has_control_characters


@pytest.mark.parametrize(
    "text",
    ["What is imatinib?\r\n\tAnd why?", "Wie wirkt Ibuprofen?", "Was ist 【1】?", "no break"],
)
def test_ordinary_text_has_no_control_characters(text: str) -> None:
    assert not has_control_characters(text)


@pytest.mark.parametrize("text", ["a\x00b", "\x1b[31mred", "a\x7fb", "a\x85b", "back\x08space"])
def test_null_escape_delete_and_c1_characters_are_control_characters(text: str) -> None:
    assert has_control_characters(text)
