import sqlite3

from molecula.schemas.stats import KnowledgeBaseStats
from molecula.store.index import LabelIndex
from molecula.store.structures import ComplexFiles, ConformerFiles
from molecula.store.summary import count_store


class KnowledgeBase:
    """What the built store holds: its tables, the label index and the structure files."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        index: LabelIndex | None,
        conformers: ConformerFiles,
        complexes: ComplexFiles,
    ) -> None:
        self._conn = conn
        self._index = index
        self._conformers = conformers
        self._complexes = complexes

    def stats(self) -> KnowledgeBaseStats:
        counts = count_store(self._conn)
        return KnowledgeBaseStats(
            drugs=counts.compounds,
            labels=counts.labels,
            label_sections=counts.label_sections,
            chunks=self._index.count() if self._index is not None else 0,
            targets=counts.targets,
            conformers=self._conformers.count(),
            complexes=self._complexes.count(),
            schema_version=counts.schema_version,
            labels_fetched_from=counts.labels_fetched_from,
            labels_fetched_to=counts.labels_fetched_to,
        )
