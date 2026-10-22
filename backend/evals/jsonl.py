"""The JSON Lines caches the eval runners append answers to and read back."""

import json
from pathlib import Path
from typing import Any


def append(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def jsonl_lines(path: Path) -> list[str]:
    """The file's lines, split only at newlines: an answer may hold a Unicode line separator,
    which `splitlines` would split at."""
    return [line for line in path.read_text("utf-8").split("\n") if line]
