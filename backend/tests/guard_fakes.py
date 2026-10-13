"""An input check for tests: it sorts every message the same way, or fails."""

import asyncio
from collections.abc import Sequence

from molecula.guard.safety import Verdict
from molecula.schemas.chat import ChatMessage, Usage
from molecula.schemas.guard import InputCategory

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
