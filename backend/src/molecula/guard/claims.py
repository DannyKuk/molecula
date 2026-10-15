"""Split an answer into the claims a source check judges one by one.

A claim is a sentence, except that a list or table whose items cite one source, or none, is one
claim, and a lead-in ending in ":" (or a heading) belongs to the list after it.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from molecula.schemas.claims import Claim

CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]|【(\d+(?:\s*,\s*\d+)*)】")
ITEM = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
ROW = re.compile(r"^\s*\|")
TABLE_RULE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-*:?\s*$")
RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
HEADING = re.compile(r"^\s*(?:#{1,6}\s+\S.*|\*\*[^*]+\*\*:?|__[^_]+__:?)\s*$")
_CITATIONS = r"(?:\s*(?:\[\d+(?:\s*,\s*\d+)*\]|【\d+(?:\s*,\s*\d+)*】))*"
# A sentence ends at . ! or ?, after any closing quote, bracket or bold marker and the citations
# that follow it, where the next sentence starts with a capital.
SENTENCE_END = re.compile(r"[.!?][\"”\u2019')*_]*" + _CITATIONS + r"(?=\s+[\"“„*_(]*[A-ZÄÖÜ])")
WORD_BEFORE = re.compile(r"([\w.]+)\.[^\w]*$")
# Words a period follows inside a sentence. Single letters ("z. B.", "d. h.") are caught apart.
ABBREVIATIONS = frozenset(
    {"e.g", "i.e", "vs", "approx", "ca", "cf", "dr", "nr", "no", "fig", "bzw", "ggf", "evtl"}
    | {"inkl", "max", "min", "mind", "usw", "z.b", "d.h", "u.a", "st", "u.s"}
)


@dataclass
class _Block:
    kind: Literal["text", "list", "heading"]
    lines: list[str] = field(default_factory=list)


def split_claims(answer: str, *, leave_out: Sequence[str] = ()) -> list[Claim]:
    """The answer's claims in order. Text in `leave_out` (the guard's emergency line) is
    dropped first."""
    for text in leave_out:
        answer = answer.replace(text.strip(), "")
    claims: list[Claim] = []
    blocks = _blocks(answer)
    for position, block in enumerate(blocks):
        before_list = position + 1 < len(blocks) and blocks[position + 1].kind == "list"
        if block.kind == "heading":
            continue
        if block.kind == "list":
            claims += _list_claims(block.lines, _lead_in(blocks, position))
            continue
        sentences = split_sentences(" ".join(line.strip() for line in block.lines))
        if before_list and sentences and _strip_citations(sentences[-1]).endswith(":"):
            sentences = sentences[:-1]
        for sentence in sentences:
            _add(claims, sentence)
    return claims


def split_sentences(text: str) -> list[str]:
    sentences, start = [], 0
    for end in SENTENCE_END.finditer(text):
        if _is_abbreviation(text[: end.start() + 1]):
            continue
        sentences.append(text[start : end.end()].strip())
        start = end.end()
    sentences.append(text[start:].strip())
    return [sentence for sentence in sentences if sentence]


def refs(text: str) -> tuple[int, ...]:
    """The reference numbers cited in the text, `[n]`, `[n, m]` and `【n】` alike."""
    found = {
        int(number)
        for match in CITATION.finditer(text)
        for number in (match[1] or match[2]).split(",")
    }
    return tuple(sorted(found))


def _blocks(answer: str) -> list[_Block]:
    blocks: list[_Block] = []
    blank = True
    for line in answer.splitlines():
        if not line.strip() or RULE.match(line):
            blank = True
            continue
        current = blocks[-1] if blocks else None
        if HEADING.match(line):
            blocks.append(_Block("heading", [line.strip()]))
        elif ITEM.match(line) or ROW.match(line):
            if current is None or current.kind != "list":
                blocks.append(_Block("list"))
            if not TABLE_RULE.match(line):
                blocks[-1].lines.append(line.strip())
        elif current is not None and current.kind == "list" and line[:1].isspace() and not blank:
            current.lines[-1] += " " + line.strip()
        elif current is not None and current.kind == "text" and not blank:
            current.lines.append(line)
        else:
            blocks.append(_Block("text", [line]))
        blank = False
    return blocks


def _lead_in(blocks: list[_Block], position: int) -> str:
    """The heading or the sentence ending in ":" right before the list at `position`."""
    if position == 0:
        return ""
    previous = blocks[position - 1]
    if previous.kind == "heading":
        return previous.lines[0]
    if previous.kind == "text":
        last = split_sentences(" ".join(line.strip() for line in previous.lines))[-1]
        if _strip_citations(last).endswith(":"):
            return last
    return ""


def _list_claims(items: list[str], lead_in: str) -> list[Claim]:
    cited = {refs(item) for item in items if refs(item)}
    if len(cited) <= 1:
        text = "\n".join([lead_in, *items] if lead_in else items)
        return [Claim(text=text, refs=refs(text))]
    texts = (f"{lead_in}\n{item}" if lead_in else item for item in items)
    return [Claim(text=text, refs=refs(text)) for text in texts]


def _add(claims: list[Claim], sentence: str) -> None:
    """A sentence of citations alone ("[1][2]") cites the claim before it."""
    if claims and not re.search(r"\w", _strip_citations(sentence)):
        merged = f"{claims[-1].text} {sentence}"
        claims[-1] = Claim(text=merged, refs=refs(merged))
    else:
        claims.append(Claim(text=sentence, refs=refs(sentence)))


def _is_abbreviation(text: str) -> bool:
    if not text.endswith("."):
        return False
    word = WORD_BEFORE.search(text)
    if word is None:
        return False
    token = word[1].rsplit(" ", 1)[-1].casefold()
    return (len(token) == 1 and token.isalpha()) or token in ABBREVIATIONS


def _strip_citations(text: str) -> str:
    return CITATION.sub("", text).strip()
