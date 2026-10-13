import unicodedata
from collections.abc import Sequence
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ALLOWED_CONTROL_CHARACTERS = frozenset("\t\n\r")


def has_control_characters(text: str) -> bool:
    """Whether `text` holds a control character other than tab and line breaks: no keyboard
    types one, and they can hide text from a reader."""
    return any(
        unicodedata.category(char) == "Cc" and char not in ALLOWED_CONTROL_CHARACTERS
        for char in text
    )


async def readable_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    """A 422 whose `detail` is one readable string the UI can show as it is, with the
    field-level list in `errors`."""
    errors = error.errors()
    return JSONResponse(
        status_code=422,
        content={"detail": readable(errors), "errors": jsonable_encoder(errors)},
    )


def readable(errors: Sequence[Any]) -> str:
    sentences = (sentence(error) for error in errors)
    return " ".join(dict.fromkeys(sentences))


def sentence(error: dict[str, Any]) -> str:
    """Our own rules raise plain sentences; pydantic's own messages get the field they are about."""
    if error["type"] == "value_error":
        return error["msg"].removeprefix("Value error, ")
    field = ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0])
    return f"{field}: {error['msg']}."
