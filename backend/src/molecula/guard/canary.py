from molecula.schemas.chat import ChatEvent, DoneEvent, ErrorEvent, SourcesEvent, TokenEvent


class PromptLeaked(Exception):
    """An event held the system prompt's canary, so the answer is repeating the prompt. The
    message names the event's type, never its text."""


class CanaryWatch:
    """Passes the agent's events on and raises PromptLeaked before the canary would go out.
    The canary can arrive split over several tokens, so the answer's last `len(canary) - 1`
    characters are held back until more text shows they don't start it, and sent before the
    `sources`, `done` or `error` that ends the answer. Every other event is checked whole: a
    status or a tool call shows the tool's arguments."""

    def __init__(self, canary: str) -> None:
        self._canary = canary
        self._held = ""

    def passed(self, event: ChatEvent) -> list[ChatEvent]:
        """What can be sent for `event`, in order."""
        if isinstance(event, TokenEvent):
            return tokens(self._sendable(event.text))
        if self._canary in event.model_dump_json():
            raise PromptLeaked(event.type)
        if isinstance(event, SourcesEvent | DoneEvent | ErrorEvent):
            held, self._held = self._held, ""
            return [*tokens(held), event]
        return [event]

    def _sendable(self, text: str) -> str:
        pending = self._held + text
        if self._canary in pending:
            raise PromptLeaked("token")
        cut = max(len(pending) - len(self._canary) + 1, 0)
        self._held = pending[cut:]
        return pending[:cut]


def tokens(text: str) -> list[ChatEvent]:
    return [TokenEvent(text=text)] if text else []
