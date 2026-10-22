from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
type RetrievalMode = Literal["dense", "bm25", "hybrid"]
type QueryTranslationMode = Literal["off", "translate", "multi_query"]


class Rewrites(BaseModel):
    # No docstring, as for LabelQuery: the instructions live in prompts/rag/rewrite_query.md.
    model_config = ConfigDict(extra="forbid")

    rewrites: list[str] = Field(min_length=1)


class TranslationStep(BaseModel):
    """One query translation step and the query it produced (#114, #446)."""

    model_config = ConfigDict(frozen=True)

    step: str
    output: str


class QueryTranslation(BaseModel):
    """What a label search searched for its question: `queries`, the question first unless it
    was translated, and the `steps` that wrote them. `error` says why the model gave no usable
    query, so the question was searched as written, and `usage` is what the model call used;
    it is None when no model was asked."""

    model_config = ConfigDict(frozen=True)

    queries: list[str]
    steps: list[TranslationStep] = []
    error: str | None = None
    usage: Usage | None = None


class EmbeddingSetup(BaseModel):
    """The model this instance embeds the labels and questions with, by its id, whether it runs
    in-process, and the bonus a passage from the guessed section group gets (#350)."""

    model_config = ConfigDict(frozen=True)

    embedding_model: str
    local: bool
    section_group_boost: float


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


class Chunk(BaseModel):
    """A piece of one label section, with what retrieval filters on and the source to cite, as
    the label indexes store it: `effective_time` is the label's date as openFDA writes it
    (YYYYMMDD)."""

    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    cid: int
    substance: str
    brand: str | None
    product_type: ProductType
    section: str
    section_group: SectionGroup
    sensitive: bool
    set_id: str
    effective_time: str
    url: str


class RetrievedChunk(Chunk):
    """A label chunk a search found, with its cosine similarity to the query and what to cite.
    `effective_time` is the stored YYYYMMDD read as a date. `in_section_groups` means it is in one
    of the filter's section groups and ranked higher.

    `dense_rank` and `bm25_rank` are its places in the embedding and keyword rankings of the
    search that found it (None: not in that ranking), and `fused_score` its reciprocal rank
    fusion score, which orders the chunks in the "bm25" and "hybrid" modes (#44)."""

    effective_time: date
    score: float
    in_section_groups: bool = False
    dense_rank: int | None = None
    bm25_rank: int | None = None
    fused_score: float | None = None


class Retrieval(BaseModel):
    """The chunks a label search kept, best first, and the candidates it dropped for scoring
    below the threshold, with the filter it searched under (None: the whole index).

    `widened` lists the parts of the filter given up because the labels it narrowed to have
    none of its section groups: "labels" searched every label of the named drugs (or any
    product type). `mode` is the ranking the search used, `min_score` the similarity a candidate
    needed to be kept and `section_group_boost` what a chunk in the filter's section groups
    counted higher in the ranking. `translation` is what QUERY_TRANSLATION searched in place of
    `question`; None when it is off.
    """

    model_config = ConfigDict(frozen=True)

    question: str
    filter: LabelFilter | None
    chunks: list[RetrievedChunk]
    dropped: list[RetrievedChunk]
    widened: list[Widening] = []
    mode: RetrievalMode
    min_score: float
    section_group_boost: float
    translation: QueryTranslation | None = None
