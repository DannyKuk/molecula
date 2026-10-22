import json
from pathlib import Path

from evals.jsonl import append, jsonl_lines

LINE_BREAKS_SPLITLINES_SPLITS_AT = "\u2028\u2029\x0b\x0c\x1c\x1d\x1e\x85"


def test_an_entry_holding_unicode_line_separators_is_read_back_as_written(tmp_path: Path) -> None:
    cache = tmp_path / "answers.jsonl"
    first = {"id": "a", "text": "Line one\u2028line two\u2029paragraph two"}
    second = {"id": "b", "text": f"every break: {LINE_BREAKS_SPLITLINES_SPLITS_AT}, Ä é"}

    append(cache, first)
    append(cache, second)

    assert [json.loads(line) for line in jsonl_lines(cache)] == [first, second]


def test_a_missing_last_newline_and_blank_lines_give_no_empty_entries(tmp_path: Path) -> None:
    cache = tmp_path / "answers.jsonl"
    cache.write_text('{"id": "a"}\n\n{"id": "b"}', encoding="utf-8")

    assert jsonl_lines(cache) == ['{"id": "a"}', '{"id": "b"}']
