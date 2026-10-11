import sqlite3
from dataclasses import astuple, dataclass, fields
from datetime import datetime
from threading import Lock
from typing import Literal

type ConformerSource = Literal["pubchem", "rdkit"]
type SynonymKind = Literal["name", "alias", "pubchem"]


@dataclass(frozen=True)
class CompoundRecord:
    """A parent compound as stored. `name` is the scope name, never PubChem's title."""

    cid: int
    name: str
    inchikey: str
    smiles: str
    formula: str
    mw: float
    xlogp: float | None
    tpsa: float | None
    hbd: int
    hba: int
    rotb: int
    heavy_atoms: int
    conformer_source: ConformerSource | None
    source: str

    @property
    def has_3d(self) -> bool:
        return self.conformer_source is not None


@dataclass(frozen=True)
class Synonym:
    alias: str
    kind: SynonymKind


COLUMNS = [field.name for field in fields(CompoundRecord)]


class CompoundStore:
    """The `compound` and `synonym` tables. Writes that change nothing leave the rows untouched."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = Lock()

    def get(self, cid: int) -> CompoundRecord | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {', '.join(COLUMNS)} FROM compound WHERE cid = ?", (cid,)
            ).fetchone()
        return CompoundRecord(*row) if row else None

    def synonyms(self, cid: int) -> list[Synonym]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT alias, kind FROM synonym WHERE cid = ? ORDER BY rowid", (cid,)
            ).fetchall()
        return [Synonym(*row) for row in rows]

    def save(self, compound: CompoundRecord, synonyms: list[Synonym], fetched_at: datetime) -> None:
        """Store a compound and replace its synonyms. The first spelling of an alias wins."""
        wanted = unique_aliases(synonyms)
        compound_changed = self.get(compound.cid) != compound
        synonyms_changed = self.synonyms(compound.cid) != wanted
        if not (compound_changed or synonyms_changed):
            return
        with self._lock, self._conn:
            if compound_changed:
                # A scope name that PubChem now maps to another CID would clash on `name`.
                self._conn.execute(
                    "DELETE FROM compound WHERE name = ? AND cid != ?",
                    (compound.name, compound.cid),
                )
                self._upsert(compound, fetched_at)
            if synonyms_changed:
                self._conn.execute("DELETE FROM synonym WHERE cid = ?", (compound.cid,))
                self._conn.executemany(
                    "INSERT INTO synonym (alias, cid, kind) VALUES (?, ?, ?)",
                    [(synonym.alias, compound.cid, synonym.kind) for synonym in wanted],
                )

    def _upsert(self, compound: CompoundRecord, fetched_at: datetime) -> None:
        columns = [*COLUMNS, "has_3d", "fetched_at"]
        updates = ", ".join(f"{column} = excluded.{column}" for column in columns[1:])
        self._conn.execute(
            f"INSERT INTO compound ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})"
            f" ON CONFLICT (cid) DO UPDATE SET {updates}",
            (*astuple(compound), compound.has_3d, fetched_at.isoformat()),
        )


def unique_aliases(synonyms: list[Synonym]) -> list[Synonym]:
    seen: set[str] = set()
    unique = []
    for synonym in synonyms:
        key = synonym.alias.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(synonym)
    return unique
