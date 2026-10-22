from molecula.guard.validation import readable


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
