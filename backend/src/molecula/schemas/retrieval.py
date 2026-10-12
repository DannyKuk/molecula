from datetime import date

from pydantic import BaseModel, ConfigDict

from molecula.schemas.labels import ProductType, SectionGroup


class LabelQuery(BaseModel):
    # No docstring: pydantic would send it to the model as the schema's description, and the
    # instructions for these fields live in prompts/rag/extract_filters.md.
    model_config = ConfigDict(frozen=True)

    substances: list[str] = []
    section_groups: list[str] = []
    product_type: ProductType | None = None


class DrugFilter(BaseModel):
    """A drug the question names, as it names it, and the labels of that drug to search."""

    model_config = ConfigDict(frozen=True)

    name: str
    cid: int
    generic: str
    set_ids: list[str]


class LabelFilter(BaseModel):
    """What a label search is narrowed to, after checking the extracted query against the store.

    `unsupported` holds named drugs that aren't in the store and `ignored_section_groups` the
    extracted groups that don't exist; both are left out of the search. `extraction_error` says
    why the model gave no usable query.
    """

    model_config = ConfigDict(frozen=True)

    extracted: LabelQuery
    drugs: list[DrugFilter] = []
    unsupported: list[str] = []
    section_groups: list[SectionGroup] = []
    ignored_section_groups: list[str] = []
    product_type: ProductType | None = None
    extraction_error: str | None = None

    @property
    def names_drugs(self) -> bool:
        return bool(self.drugs or self.unsupported)

    @property
    def set_ids(self) -> list[str]:
        return [set_id for drug in self.drugs for set_id in drug.set_ids]


class RetrievedChunk(BaseModel):
    """A label chunk a search found, with its cosine similarity to the query and what to cite."""

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


class Retrieval(BaseModel):
    """The chunks a label search kept, best first, and the candidates it dropped for scoring
    below the threshold, with the filter it searched under (None: the whole index)."""

    model_config = ConfigDict(frozen=True)

    question: str
    filter: LabelFilter | None
    chunks: list[RetrievedChunk]
    dropped: list[RetrievedChunk]
