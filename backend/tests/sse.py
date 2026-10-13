"""Reads a server-sent event stream, as the chat endpoint sends it, for the tests."""

import json
from typing import Any


def server_sent_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """The (event name, data) pairs of a stream, in order."""
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events
