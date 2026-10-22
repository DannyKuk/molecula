import re
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from molecula.schemas.retrieval import Chunk

TABLE = "label_chunks"
COLUMNS = list(Chunk.model_fields)
# Porter stemming, so "effects" finds "effect". unicode61 splits words at every hyphen, also the
# non-breaking one (U+2011) the labels often use; a hyphenated query term is matched as a
# phrase of its parts instead, so 5-HT3 finds "5-HT3" and not each "5".
TOKENIZER = "porter unicode61"
TERM = re.compile(r"[^\W_]+(?:[-\u2010\u2011][^\W_]+)*")
FILTER_COLUMNS = {"cid", "set_id", "product_type", "section_group"}


class KeywordIndex:
    """A BM25 index of the label chunks (SQLite FTS5), with the same ids and metadata as the
    vector index, so a search narrows by the same filter."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def exists(self) -> bool:
        return self._path.exists()

    def rebuild(self, chunks: Sequence[Chunk]) -> None:
        """Replace the index with `chunks`. Written next to it and moved into place, so a
        search never sees a half-built index."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        building = self._path.with_name(self._path.name + ".building")
        building.unlink(missing_ok=True)
        unindexed = ", ".join(f"{column} UNINDEXED" for column in COLUMNS if column != "text")
        with closing(sqlite3.connect(building)) as conn, conn:
            conn.execute(
                f"CREATE VIRTUAL TABLE {TABLE} USING fts5(text, {unindexed}, "
                f'tokenize="{TOKENIZER}")'
            )
            placeholders = ", ".join("?" for _ in COLUMNS)
            conn.executemany(
                f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) VALUES ({placeholders})",
                (to_row(chunk) for chunk in sorted(chunks, key=lambda chunk: chunk.id)),
            )
            conn.execute(f"INSERT INTO {TABLE} ({TABLE}) VALUES ('optimize')")
        building.replace(self._path)

    def replace_drug(self, cid: int, chunks: Sequence[Chunk]) -> None:
        """Replace the compound's chunks with `chunks` in one transaction; a search sees either
        the old or the new ones."""
        placeholders = ", ".join("?" for _ in COLUMNS)
        with closing(sqlite3.connect(self._path)) as conn, conn:
            conn.execute(f"DELETE FROM {TABLE} WHERE cid = ?", (cid,))
            conn.executemany(
                f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) VALUES ({placeholders})",
                (to_row(chunk) for chunk in chunks),
            )

    def search(
        self, question: str, n: int, where: dict[str, Any] | None = None
    ) -> list[tuple[Chunk, float]]:
        """Up to `n` chunks that share a term with `question` and match the ChromaDB `where`
        filter, best first, with their BM25 score (higher is better); empty before the first
        build."""
        query = match_query(question)
        if not query or not self.exists():
            return []
        condition, parameters = sql_condition(where)
        # bm25() is lower for a better match; ties are broken by id so the order is stable.
        sql = (
            f"SELECT {', '.join(COLUMNS)}, bm25({TABLE}) FROM {TABLE} WHERE {TABLE} MATCH ?"
            f"{f' AND {condition}' if condition else ''} ORDER BY bm25({TABLE}), id LIMIT ?"
        )
        with closing(sqlite3.connect(f"{self._path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
            rows = conn.execute(sql, [query, *parameters, n]).fetchall()
        return [(to_chunk(row[:-1]), -row[-1]) for row in rows]


def match_query(question: str) -> str:
    """An FTS5 query that matches any term of `question`. Each term is quoted, which makes a
    hyphenated term a phrase and keeps words such as NOT and characters such as * and ' in a
    question from being query syntax."""
    terms = dict.fromkeys(term.casefold() for term in TERM.findall(question))
    return " OR ".join(f'"{term}"' for term in terms)


def sql_condition(where: dict[str, Any] | None) -> tuple[str, list[Any]]:
    """The SQL for the parts of ChromaDB's filter syntax that `where_clause` writes: a field
    equal to a value or `$in` a list, and `$and` of those."""
    if not where:
        return "", []
    if "$and" in where:
        parts = [sql_condition(part) for part in where["$and"]]
        return " AND ".join(sql for sql, _ in parts), [
            value for _, values in parts for value in values
        ]
    ((column, test),) = where.items()
    if column not in FILTER_COLUMNS:
        raise ValueError(f"The keyword index can't filter on {column}")
    if isinstance(test, dict):
        values = list(test["$in"])
        return f"{column} IN ({', '.join('?' for _ in values)})", values
    return f"{column} = ?", [test]


def to_row(chunk: Chunk) -> tuple[Any, ...]:
    return tuple(getattr(chunk, column) for column in COLUMNS)


def to_chunk(row: Sequence[Any]) -> Chunk:
    return Chunk.model_validate(dict(zip(COLUMNS, row, strict=True)))
