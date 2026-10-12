from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from molecula.schemas.compounds import Compound, DrugName, MatchKind, Suggestion
from molecula.schemas.labels import SectionGroup
from molecula.schemas.retrieval import Retrieval, RetrievedChunk
from molecula.schemas.targets import Target

MIN_COMPARED_DRUGS = 2
MAX_COMPARED_DRUGS = 4
MAX_QUESTION_LENGTH = 500


class ResolveDrugArgs(BaseModel):
    name: DrugName


class DrugArgs(BaseModel):
    drug: DrugName


class CompareDrugsArgs(BaseModel):
    drugs: Annotated[
        list[DrugName], Field(min_length=MIN_COMPARED_DRUGS, max_length=MAX_COMPARED_DRUGS)
    ]


class SearchLabelsArgs(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH)
    ]
    drug: DrugName | None = None
    section: SectionGroup | None = None


class DrugNotSupported(BaseModel):
    """A name that isn't a supported drug, with the closest supported names, best first.

    The suggestions are only offered to the user: they are never the answer.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["not_supported"] = "not_supported"
    query: str
    suggestions: list[Suggestion]


class InvalidArguments(BaseModel):
    """A tool call whose arguments failed validation, with one readable line per problem."""

    model_config = ConfigDict(frozen=True)

    status: Literal["invalid_arguments"] = "invalid_arguments"
    errors: list[str]


class ResolvedDrug(BaseModel):
    """The supported drug a name refers to, the stored name or alias it matched, and its
    PubChem page."""

    model_config = ConfigDict(frozen=True)

    status: Literal["found"] = "found"
    query: str
    cid: int
    name: str
    matched_alias: str
    match_kind: MatchKind
    source: str
    source_url: str


class DrugProperties(BaseModel):
    """A supported drug's PubChem properties; the compound carries the source."""

    model_config = ConfigDict(frozen=True)

    status: Literal["found"] = "found"
    query: str
    compound: Compound


class DrugTargetList(BaseModel):
    """A supported drug's targets with ChEMBL's mechanism and a source for each. An empty list
    means ChEMBL lists no mechanism for the drug."""

    model_config = ConfigDict(frozen=True)

    status: Literal["found"] = "found"
    query: str
    cid: int
    name: str
    targets: list[Target]


class DrugComparison(BaseModel):
    """The drugs in the order asked, each with its properties or as not supported."""

    model_config = ConfigDict(frozen=True)

    drugs: list[DrugProperties | DrugNotSupported]


class LabelPassages(BaseModel):
    """The label passages a search found, best first, each with what to cite.

    `drugs` are the generic names searched, `drugs_without_label` the supported drugs that have
    no US label, and `unsupported` the named drugs outside the store. `retrieval` is the whole
    search (filter, widening, dropped candidates) for the retrieval trace; it is left out of the
    JSON the model reads.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["found"] = "found"
    question: str
    drugs: list[str]
    drugs_without_label: list[str]
    unsupported: list[DrugNotSupported]
    passages: list[RetrievedChunk]
    retrieval: Retrieval = Field(exclude=True)


class LabelDrugsNotSupported(BaseModel):
    """A label search that named only drugs outside the store, so it searched nothing rather
    than another drug's label. `retrieval` is left out of the JSON the model reads."""

    model_config = ConfigDict(frozen=True)

    status: Literal["not_supported"] = "not_supported"
    question: str
    drugs: list[DrugNotSupported]
    retrieval: Retrieval = Field(exclude=True)
