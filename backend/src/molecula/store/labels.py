import sqlite3
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Literal

type ProductType = Literal["rx", "otc"]
type SectionGroup = Literal[
    "pharmacology",
    "indications",
    "dosing",
    "warnings",
    "contraindications",
    "interactions",
    "adverse_reactions",
    "otc_consumer",
    "specific_populations",
    "patient_information",
    "product",
    "abuse_dependence",
    "clinical_studies",
]

LABEL_COLUMNS = ["set_id", "substance", "brand", "product_type", "effective_time", "url"]


@dataclass(frozen=True)
class LabelSection:
    """One label section by its openFDA name. `sensitive` text may be cited but never turned
    into personal advice (dosing)."""

    section: str
    section_group: SectionGroup
    text: str
    sensitive: bool


@dataclass(frozen=True)
class LabelRecord:
    """A drug's canonical label for one product type and the sections the knowledge base uses."""

    set_id: str
    substance: str
    brand: str | None
    product_type: ProductType
    effective_time: str
    url: str
    sections: tuple[LabelSection, ...]

    @property
    def characters(self) -> int:
        return sum(len(section.text) for section in self.sections)


class LabelStore:
    """The `label` and `label_section` tables, per compound, and the sources' disclaimers.

    A save that changes nothing leaves the rows untouched.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = Lock()

    def get(self, cid: int) -> tuple[LabelRecord, ...]:
        """The compound's labels, prescription first."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {', '.join(LABEL_COLUMNS)} FROM label WHERE cid = ?"
                " ORDER BY product_type DESC",
                (cid,),
            ).fetchall()
            return tuple(LabelRecord(*row, sections=self._sections(row[0])) for row in rows)

    def save(self, cid: int, labels: tuple[LabelRecord, ...], fetched_at: datetime) -> None:
        """Replace the compound's labels and their sections."""
        if self.get(cid) == labels:
            return
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM label WHERE cid = ?", (cid,))
            for label in labels:
                self._conn.execute(
                    f"INSERT INTO label (cid, {', '.join(LABEL_COLUMNS)}, source, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, 'openfda', ?)",
                    (
                        cid,
                        label.set_id,
                        label.substance,
                        label.brand,
                        label.product_type,
                        label.effective_time,
                        label.url,
                        fetched_at.isoformat(),
                    ),
                )
                self._conn.executemany(
                    "INSERT INTO label_section (set_id, section, section_group, text, sensitive)"
                    " VALUES (?, ?, ?, ?, ?)",
                    [
                        (label.set_id, s.section, s.section_group, s.text, s.sensitive)
                        for s in label.sections
                    ],
                )

    def disclaimer(self, source: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT text FROM source_disclaimer WHERE source = ?", (source,)
            ).fetchone()
        return row[0] if row else None

    def save_disclaimer(self, source: str, text: str, fetched_at: datetime) -> None:
        """Store the text a source asks to be shown with its data, once per source."""
        if self.disclaimer(source) == text:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO source_disclaimer (source, text, fetched_at) VALUES (?, ?, ?)"
                " ON CONFLICT (source) DO UPDATE SET text = excluded.text,"
                " fetched_at = excluded.fetched_at",
                (source, text, fetched_at.isoformat()),
            )

    def _sections(self, set_id: str) -> tuple[LabelSection, ...]:
        rows = self._conn.execute(
            "SELECT section, section_group, text, sensitive FROM label_section"
            " WHERE set_id = ? ORDER BY rowid",
            (set_id,),
        ).fetchall()
        return tuple(
            LabelSection(section, group, text, bool(sensitive))
            for section, group, text, sensitive in rows
        )
