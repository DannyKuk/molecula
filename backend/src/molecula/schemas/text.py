import unicodedata

ALLOWED_CONTROL_CHARACTERS = frozenset("\t\n\r")


def has_control_characters(text: str) -> bool:
    """Whether `text` holds a control character other than tab and line breaks: no keyboard
    types one, and they can hide text from a reader."""
    return any(
        unicodedata.category(char) == "Cc" and char not in ALLOWED_CONTROL_CHARACTERS
        for char in text
    )
