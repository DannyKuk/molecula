import pytest

from molecula.guard.validation import has_control_characters, readable


@pytest.mark.parametrize(
    "text",
    ["What is imatinib?\r\n\tAnd why?", "Wie wirkt Ibuprofen?", "Was ist 【1】?", "no\u00a0break"],
)
def test_ordinary_text_has_no_control_characters(text: str) -> None:
    assert not has_control_characters(text)


@pytest.mark.parametrize("text", ["a\x00b", "\x1b[31mred", "a\x7fb", "a\x85b", "back\x08space"])
def test_null_escape_delete_and_c1_characters_are_control_characters(text: str) -> None:
    assert has_control_characters(text)


def test_our_own_sentences_are_kept_and_pydantic_messages_name_their_field() -> None:
    errors = [
        {"type": "value_error", "loc": ("body", "messages"), "msg": "Value error, Too long."},
        {"type": "literal_error", "loc": ("body", "messages", 0, "role"), "msg": "Input wrong"},
        {"type": "greater_than", "loc": ("path", "cid"), "msg": "Input should be greater than 0"},
    ]

    assert readable(errors) == (
        "Too long. messages.0.role: Input wrong. cid: Input should be greater than 0."
    )


def test_the_same_sentence_is_said_once() -> None:
    error = {"type": "value_error", "loc": ("body",), "msg": "Value error, Too long."}

    assert readable([error, error]) == "Too long."
