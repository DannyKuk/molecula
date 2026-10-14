"""An input check and a source check for tests: they give the same verdict every time, or
fail."""

import asyncio
from collections.abc import Sequence

from molecula.guard.safety import Verdict
from molecula.schemas.chat import ChatMessage, ToolResultEvent, Usage
from molecula.schemas.claims import CheckedClaim
from molecula.schemas.guard import InputCategory
from molecula.schemas.source_check import CheckedAnswer

CHECK_USAGE = Usage(input_tokens=300, output_tokens=5, total_tokens=305)


class FakeCheck:
    """Sorts every message into `category`, or raises `error`, after `delay` seconds."""

    def __init__(
        self,
        category: InputCategory = "ok",
        *,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.category = category
        self.error = error
        self.delay = delay
        self.checked: list[Sequence[ChatMessage]] = []

    async def check(self, conversation: Sequence[ChatMessage]) -> Verdict:
        self.checked.append(conversation)
        await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return Verdict(self.category, CHECK_USAGE)


SOURCE_CHECK_USAGE = Usage(input_tokens=500, output_tokens=40, total_tokens=540)


class FakeSourceCheck:
    """Judges every answer as one supported claim, or with `claims`, or raises `error`, after
    `delay` seconds. `checked` holds each answer and the results it was checked against."""

    def __init__(
        self,
        claims: list[CheckedClaim] | None = None,
        *,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.claims = claims
        self.error = error
        self.delay = delay
        self.checked: list[tuple[str, list[ToolResultEvent]]] = []

    async def check(self, answer: str, results: Sequence[ToolResultEvent]) -> CheckedAnswer:
        self.checked.append((answer, list(results)))
        await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        claims = self.claims or [
            CheckedClaim(text=answer, label="supported", decided_by="model", reason="Held.")
        ]
        return CheckedAnswer(claims=claims, usage=SOURCE_CHECK_USAGE)
