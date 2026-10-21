import json
from dataclasses import astuple, dataclass, fields
from datetime import datetime
from typing import Any, Literal

from molecula.store.db import StoreConnection
from molecula.store.sources import CHEMBL, RCSB, SourceName

type MatchedOn = Literal["inchikey", "connectivity"]

# Lists are stored as JSON arrays.
JSON_COLUMNS = frozenset({"accessions", "gene_symbols", "chains"})


@dataclass(frozen=True)
class TargetRecord:
    """A target the drug acts on and ChEMBL's mechanism for it. `molecule_chembl_id` is the
    parent molecule whose mechanisms list the target."""

    target_chembl_id: str
    molecule_chembl_id: str
    name: str
    target_type: str
    organism: str | None
    mechanism: str
    action_type: str | None
    accessions: tuple[str, ...]
    gene_symbols: tuple[str, ...]


@dataclass(frozen=True)
class LigandCode:
    """A PDB ligand code for the drug, found by its full InChIKey or only its connectivity."""

    code: str
    matched_on: MatchedOn


@dataclass(frozen=True)
class CandidateRecord:
    """A PDB entry with the drug's ligand bound to a protein of the target.

    `rank` orders one target's candidates, 1 being the best; `chains` are the target's chains.
    """

    target_chembl_id: str
    rank: int
    pdb_id: str
    ligand_code: str
    title: str | None
    resolution: float | None
    organism: str | None
    taxonomy_id: int | None
    chains: tuple[str, ...]


@dataclass(frozen=True)
class DrugTargets:
    targets: tuple[TargetRecord, ...] = ()
    ligand_codes: tuple[LigandCode, ...] = ()
    candidates: tuple[CandidateRecord, ...] = ()


TABLES: list[tuple[str, type[Any], SourceName]] = [
    ("target", TargetRecord, CHEMBL),
    ("ligand_code", LigandCode, RCSB),
    ("complex_candidate", CandidateRecord, RCSB),
]


class TargetStore:
    """The `target`, `ligand_code` and `complex_candidate` tables, per compound.

    A save that changes nothing leaves the rows untouched.
    """

    def __init__(self, conn: StoreConnection) -> None:
        self._conn = conn
        self._lock = conn.lock

    def get(self, cid: int) -> DrugTargets:
        with self._lock:
            rows = [self._rows(table, record_type, cid) for table, record_type, _ in TABLES]
        targets, ligand_codes, candidates = rows
        return DrugTargets(tuple(targets), tuple(ligand_codes), tuple(candidates))

    def save(self, cid: int, drug: DrugTargets, fetched_at: datetime) -> None:
        """Replace the compound's targets, ligand codes and candidates."""
        if self.get(cid) == drug:
            return
        records = [drug.targets, drug.ligand_codes, drug.candidates]
        with self._lock, self._conn:
            for table, _, _ in reversed(TABLES):
                self._conn.execute(f"DELETE FROM {table} WHERE cid = ?", (cid,))
            for (table, record_type, source), table_records in zip(TABLES, records, strict=True):
                columns = ["cid", *columns_of(record_type), "source", "fetched_at"]
                self._conn.executemany(
                    f"INSERT INTO {table} ({', '.join(columns)})"
                    f" VALUES ({', '.join('?' * len(columns))})",
                    [
                        (cid, *to_row(record), source, fetched_at.isoformat())
                        for record in table_records
                    ],
                )

    def _rows(self, table: str, record_type: type[Any], cid: int) -> list[Any]:
        columns = columns_of(record_type)
        rows = self._conn.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE cid = ? ORDER BY rowid", (cid,)
        ).fetchall()
        return [from_row(record_type, columns, row) for row in rows]


def columns_of(record_type: type[Any]) -> list[str]:
    return [field.name for field in fields(record_type)]


def to_row(record: Any) -> tuple[Any, ...]:
    return tuple(
        json.dumps(list(value)) if name in JSON_COLUMNS else value
        for name, value in zip(columns_of(type(record)), astuple(record), strict=True)
    )


def from_row[R](record_type: type[R], columns: list[str], row: tuple[Any, ...]) -> R:
    values = [
        tuple(json.loads(value)) if name in JSON_COLUMNS else value
        for name, value in zip(columns, row, strict=True)
    ]
    return record_type(*values)
