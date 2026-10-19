from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from molecula.schemas.compounds import Resolution
from molecula.schemas.labels import ProductType, SectionGroup
from molecula.schemas.usage import Usage


class LabelQuery(BaseModel):
    # No docstring: pydantic would send it to the model as the schema's description, and the
    # instructions for these fields live in prompts/rag/extract_filters.md.
    model_config = ConfigDict(frozen=True)

    substances: list[str] = []
    section_groups: list[str] = []
    product_type: ProductType | None = None


type Widening = Literal["labels"]


class DrugFilter(BaseModel):
    """A drug the question names, as it names it, and the labels of that drug to search.
    `narrowed` means a brand or the product type left out some of the drug's labels."""

    model_config = ConfigDict(frozen=True)

    name: str
    cid: int
    generic: str
    set_ids: list[str]
    narrowed: bool = False


class LabelFilter(BaseModel):
    """What a label search is narrowed to, after checking the extracted query against the store.

    `unsupported` holds the resolutions of named drugs that aren't in the store, with their
    suggestions, and `ignored_section_groups` the extracted groups that don't exist; both are
    left out of the search. `extraction_error` says why the model gave no usable query, and
    `extraction_usage` is what that model call used; it is None when no model was asked.
    """

    model_config = ConfigDict(frozen=True)

    extracted: LabelQuery
    drugs: list[DrugFilter] = []
    unsupported: list[Resolution] = []
    section_groups: list[SectionGroup] = []
    ignored_section_groups: list[str] = []
    product_type: ProductType | None = None
    extraction_error: str | None = None
    extraction_usage: Usage | None = None

    @property
    def names_drugs(self) -> bool:
        return bool(self.drugs or self.unsupported)

    @property
    def set_ids(self) -> list[str]:
        return [set_id for drug in self.drugs for set_id in drug.set_ids]


class RetrievedChunk(BaseModel):
    """A label chunk a search found, with its cosine similarity to the query and what to cite.
    `in_section_groups` means it is in one of the filter's section groups and ranked higher."""

    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    score: float
    cid: int
    substance: str
    brand: str | None
    product_type: ProductType
    section: str
    section_group: SectionGroup
    sensitive: bool
    set_id: str
    effective_time: date
    url: str
    in_section_groups: bool = False


class Retrieval(BaseModel):
    """The chunks a label search kept, best first, and the candidates it dropped for scoring
    below the threshold, with the filter it searched under (None: the whole index).

    `widened` lists the parts of the filter given up because the labels it narrowed to have
    none of its section groups: "labels" searched every label of the named drugs (or any
    product type).
    """

    model_config = ConfigDict(frozen=True)

    question: str
    filter: LabelFilter | None
    chunks: list[RetrievedChunk]
    dropped: list[RetrievedChunk]
    widened: list[Widening] = []
