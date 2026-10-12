from datetime import datetime

from molecula.schemas.labels import DrugLabels, Label, LabelSection
from molecula.store.compounds import CompoundStore
from molecula.store.labels import LabelRecord, LabelStore

# The labels ingest step writes every label row from openFDA.
LABEL_SOURCE = "openfda"


class LabelService:
    """The canonical labels of a supported drug, from the local store."""

    def __init__(self, labels: LabelStore, compounds: CompoundStore) -> None:
        self._labels = labels
        self._compounds = compounds

    def get_labels(self, cid: int) -> DrugLabels | None:
        """The drug's labels, an empty list if it has none, or None if the drug isn't stored."""
        if self._compounds.get(cid) is None:
            return None
        return DrugLabels(
            cid=cid,
            labels=[to_label(record) for record in self._labels.get(cid)],
            disclaimer=self._labels.disclaimer(LABEL_SOURCE),
        )


def to_label(record: LabelRecord) -> Label:
    return Label(
        set_id=record.set_id,
        substance=record.substance,
        brand=record.brand,
        product_type=record.product_type,
        effective_time=datetime.strptime(record.effective_time, "%Y%m%d").date(),
        sections=[
            LabelSection(
                section=section.section,
                section_group=section.section_group,
                text=section.text,
                sensitive=section.sensitive,
            )
            for section in record.sections
        ],
        source=LABEL_SOURCE,
        source_url=record.url,
    )
