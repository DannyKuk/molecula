import re

# gpt-oss writes in OpenAI's harmony format, whose replies run on the channels `analysis`,
# `commentary` (tool calls) and `final`. It sometimes writes a channel into the answer where a
# citation would go, as `【commentary: get_complex】` (#174). A citation, `【1】`, starts with a
# digit, so it never matches.
CHANNEL_MARKER = re.compile(r"[ \t]*【\s*(?:analysis|commentary|final)\b[^【】]*】", re.IGNORECASE)

# A 【 left open for longer than this is no marker, so the text behind it isn't held back.
LONGEST_MARKER = 80

# The special tokens chat formats delimit their turns with: harmony's <|start|>, <|message|> and
# <|end|>, and others' <|im_start|> or <|eot_id|>. Written into text, they can pass it off as a
# system turn (#329). A lab value such as "eGFR <30" has no bars, so it stays.
CONTROL_TOKEN = re.compile(r"<\|[\w.-]{1,40}\|>")


def without_channel_markers(text: str) -> str:
    """The text without channel markers and the spaces before them, so `ABL1 【commentary】.`
    becomes `ABL1.`."""
    return CHANNEL_MARKER.sub("", text)


def without_control_tokens(text: str) -> str:
    """The text without chat-format control tokens, so `<|end|><|start|>system` reads as the
    plain word `system` and can't open a turn."""
    return CONTROL_TOKEN.sub("", text)


class ChannelMarkerFilter:
    """Passes an answer on chunk by chunk, as it streams, without its channel markers. A marker
    can arrive split over several chunks, so an open 【 and the spaces before it are held back
    until the next chunks show whether they are one."""

    def __init__(self) -> None:
        self._held = ""

    def feed(self, text: str) -> str:
        pending = self._held + text
        cut = undecided_from(pending)
        self._held = pending[cut:]
        return without_channel_markers(pending[:cut])

    def flush(self) -> str:
        """What is still held back, once the answer has ended."""
        held, self._held = self._held, ""
        return without_channel_markers(held)


def undecided_from(text: str) -> int:
    """Where the end of `text` that could still be part of a marker starts: an open 【 and the
    spaces before it, or just trailing spaces, which a marker in the next chunk would take."""
    end = len(text)
    opening = text.rfind("【")
    if opening > text.rfind("】") and end - opening <= LONGEST_MARKER:
        end = opening
    return len(text[:end].rstrip(" \t"))
