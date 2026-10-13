from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from molecula.schemas.chat import Source
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


class ToolResult(BaseModel):
    """What a tool returns. `sources` are where its facts come from, for the user to check."""

    model_config = ConfigDict(frozen=True)

    def sources(self) -> list[Source]:
        return []


class DrugNotSupported(ToolResult):
    """A name that isn't a supported drug, with the closest supported names, best first.

    The suggestions are only offered to the user: they are never the answer.
    """

    status: Literal["not_supported"] = "not_supported"
    query: str
    suggestions: list[Suggestion]


class InvalidArguments(BaseModel):
    """A tool call whose arguments failed validation, with one readable line per problem."""

    model_config = ConfigDict(frozen=True)

    status: Literal["invalid_arguments"] = "invalid_arguments"
    errors: list[str]


class ResolvedDrug(ToolResult):
    """The supported drug a name refers to, the stored name or alias it matched, and its
    PubChem page."""

    status: Literal["found"] = "found"
    query: str
    cid: int
    name: str
    matched_alias: str
    match_kind: MatchKind
    source: str
    source_url: str

    def sources(self) -> list[Source]:
        return [Source(kind=self.source, name=self.name, url=self.source_url)]


class DrugProperties(ToolResult):
    """A supported drug's PubChem properties; the compound carries the source."""

    status: Literal["found"] = "found"
    query: str
    compound: Compound

    def sources(self) -> list[Source]:
        compound = self.compound
        return [Source(kind=compound.source, name=compound.name, url=compound.source_url)]


class DrugTargetList(ToolResult):
    """A supported drug's targets with ChEMBL's mechanism and a source for each. An empty list
    means ChEMBL lists no mechanism for the drug."""

    status: Literal["found"] = "found"
    query: str
    cid: int
    name: str
    targets: list[Target]

    def sources(self) -> list[Source]:
        return [
            Source(kind=target.source, name=target.name, url=target.source_url)
            for target in self.targets
        ]


class DrugComparison(ToolResult):
    """The drugs in the order asked, each with its properties or as not supported."""

    drugs: list[DrugProperties | DrugNotSupported]

    def sources(self) -> list[Source]:
        return [source for drug in self.drugs for source in drug.sources()]


class LabelPassages(ToolResult):
    """The label passages a search found, best first, each with what to cite.

    `drugs` are the generic names searched, `drugs_without_label` the supported drugs that have
    no US label, and `unsupported` the named drugs outside the store. `retrieval` is the whole
    search (filter, widening, dropped candidates) for the retrieval trace; it is left out of the
    JSON the model reads.
    """

    status: Literal["found"] = "found"
    question: str
    drugs: list[str]
    drugs_without_label: list[str]
    unsupported: list[DrugNotSupported]
    passages: list[RetrievedChunk]
    retrieval: Retrieval = Field(exclude=True)

    def sources(self) -> list[Source]:
        return [
            Source(
                kind="dailymed",
                name=passage.brand or passage.substance.lower(),
                url=passage.url,
                section=passage.section,
                effective_time=passage.effective_time,
            )
            for passage in self.passages
        ]


class LabelDrugsNotSupported(ToolResult):
    """A label search that named only drugs outside the store, so it searched nothing rather
    than another drug's label. `retrieval` is left out of the JSON the model reads."""

    status: Literal["not_supported"] = "not_supported"
    question: str
    drugs: list[DrugNotSupported]
    retrieval: Retrieval = Field(exclude=True)
