from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
    "overdosage",
]


class LabelSection(BaseModel):
    """One label section by its openFDA name. `sensitive` text may be cited but never turned
    into personal advice."""

    model_config = ConfigDict(frozen=True)

    section: str
    section_group: SectionGroup
    text: str
    sensitive: bool


class Label(BaseModel):
    """A drug's canonical US label for one product type, linked to its DailyMed page."""

    model_config = ConfigDict(frozen=True)

    set_id: str
    substance: str
    brand: str | None
    product_type: ProductType
    effective_time: date
    sections: list[LabelSection]
    source: str
    source_url: str


class DrugLabels(BaseModel):
    """The labels of a supported drug, prescription first. An empty list means the drug has no
    US label."""

    model_config = ConfigDict(frozen=True)

    cid: int
    labels: list[Label]
