"""Fail on broken relative links and on stale "not built" phrases in docs/ and the README.

Run from anywhere: uv run --project backend python scripts/check_docs.py
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE = re.compile(r"^\s*(```|~~~)")
STALE = re.compile(
    r"not built yet|decided, not built|planned to build|will be added", re.IGNORECASE
)
EXTERNAL = ("http://", "https://", "mailto:", "#")


def markdown_files() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """The file's lines outside fenced code blocks, numbered from 1."""
    lines = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            lines.append((number, line))
    return lines


def broken_link(path: Path, target: str) -> bool:
    if target.startswith(EXTERNAL):
        return False
    file_part = unquote(target.split("#", 1)[0].split("?", 1)[0])
    return not (path.parent / file_part).exists()


def problems(path: Path) -> list[str]:
    where = path.relative_to(ROOT).as_posix()
    found = []
    for number, line in prose_lines(path):
        for target in LINK.findall(line):
            if broken_link(path, target):
                found.append(f"{where}:{number}: broken link {target}")
        if match := STALE.search(line):
            found.append(f"{where}:{number}: stale phrase '{match.group(0)}'")
    return found


def main() -> int:
    found = [problem for path in markdown_files() for problem in problems(path)]
    for problem in found:
        print(problem.encode("ascii", "backslashreplace").decode("ascii"))
    if found:
        print(f"check_docs: {len(found)} problem(s)")
        return 1
    print("check_docs: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
