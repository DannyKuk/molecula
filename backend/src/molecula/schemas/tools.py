from collections.abc import Callable
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
)

from molecula.schemas.chat import Source
from molecula.schemas.compounds import Compound, DrugName, MatchKind, Suggestion
from molecula.schemas.labels import SectionGroup
from molecula.schemas.retrieval import Retrieval, RetrievedChunk
from molecula.schemas.targets import Target

MIN_COMPARED_DRUGS = 2
MAX_COMPARED_DRUGS = 4
MAX_SEARCH_QUESTION_LENGTH = 500


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
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_SEARCH_QUESTION_LENGTH
        ),
    ]
    drug: DrugName | None = None
    section: SectionGroup | None = None


class References:
    """The reference numbers of one answer's sources (or one MCP session's), from 1 in the
    order they were found. A label passage is keyed by its chunk id, any other source by its
    URL, so a passage or page that two tool calls find keeps its first number."""

    def __init__(self) -> None:
        self._refs: dict[str, int] = {}

    def ref_of(self, key: str) -> int:
        return self._refs.setdefault(key, len(self._refs) + 1)


class ToolResult(BaseModel):
    """What a tool returns. `sources` are where its facts come from, for the user to check.

    A result whose facts an answer can state carries a `ref` for each source, the number the
    answer cites it with as `[ref]`; `renumbered` sets them from one counter per answer.
    """

    model_config = ConfigDict(frozen=True)

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        """The same result with the reference numbers `ref_of` gives its sources' keys."""
        return self

    def sources(self) -> list[Source]:
        return []


class RefFirst(BaseModel):
    """Puts `ref` first in the JSON the model reads, next to what it numbers. Last, it sat after
    a passage's metadata and right before the next passage's text (#166)."""

    @model_serializer(mode="wrap")
    def _ref_first(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        return {"ref": data.pop("ref"), **data} if "ref" in data else data


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


class ResolvedDrug(RefFirst, ToolResult):
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
    ref: int | None = None

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        return self.model_copy(update={"ref": ref_of(self.source_url)})

    def sources(self) -> list[Source]:
        return [Source(kind=self.source, name=self.name, url=self.source_url, ref=self.ref)]


class DrugProperties(RefFirst, ToolResult):
    """A supported drug's PubChem properties; the compound carries the source."""

    status: Literal["found"] = "found"
    query: str
    compound: Compound
    ref: int | None = None

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        return self.model_copy(update={"ref": ref_of(self.compound.source_url)})

    def sources(self) -> list[Source]:
        compound = self.compound
        return [
            Source(kind=compound.source, name=compound.name, url=compound.source_url, ref=self.ref)
        ]


class CitedTarget(RefFirst, Target):
    """A target with `ref`, the number an answer cites its ChEMBL mechanism with as `[ref]`."""

    ref: int | None = None


class DrugTargetList(ToolResult):
    """A supported drug's targets with ChEMBL's mechanism and a source for each. An empty list
    means ChEMBL lists no mechanism for the drug."""

    status: Literal["found"] = "found"
    query: str
    cid: int
    name: str
    targets: list[CitedTarget]

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        targets = [
            target.model_copy(update={"ref": ref_of(target.source_url)}) for target in self.targets
        ]
        return self.model_copy(update={"targets": targets})

    def sources(self) -> list[Source]:
        return [
            Source(kind=target.source, name=target.name, url=target.source_url, ref=target.ref)
            for target in self.targets
        ]


class DrugComparison(ToolResult):
    """The drugs in the order asked, each with its properties or as not supported."""

    drugs: list[DrugProperties | DrugNotSupported]

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        return self.model_copy(update={"drugs": [drug.renumbered(ref_of) for drug in self.drugs]})

    def sources(self) -> list[Source]:
        return [source for drug in self.drugs for source in drug.sources()]


class HydrogenBond(BaseModel):
    """A hydrogen bond between a pocket residue's or cofactor's atom and a ligand atom, in Å."""

    model_config = ConfigDict(frozen=True)

    residue: str
    chain: str
    residue_atom: str
    ligand_atom: str
    distance: float


class ResidueContact(BaseModel):
    """A pocket residue, metal ion or cofactor and its closest heavy-atom distance to the ligand,
    in Å."""

    model_config = ConfigDict(frozen=True)

    residue: str
    chain: str
    distance: float


class DrugComplex(RefFirst, ToolResult):
    """A summary of a supported drug's reviewed complex: what it is bound to and how, without
    the coordinates the 3D view draws."""

    status: Literal["found"] = "found"
    query: str
    cid: int
    name: str
    pdb_id: str
    target: str | None
    organism: str | None
    ligand_code: str
    caption: str | None
    hydrogen_bonds: list[HydrogenBond]
    contacts: list[ResidueContact]
    source_url: str
    ref: int | None = None

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        return self.model_copy(update={"ref": ref_of(self.source_url)})

    def sources(self) -> list[Source]:
        return [Source(kind="rcsb", name=self.pdb_id, url=self.source_url, ref=self.ref)]


class NoComplex(ToolResult):
    """A supported drug without a reviewed complex: the 3D view shows the molecule alone."""

    status: Literal["no_complex"] = "no_complex"
    query: str
    cid: int
    name: str


class CitedPassage(RefFirst, RetrievedChunk):
    """A label passage and `ref`, the number an answer cites it with as `[ref]`."""

    ref: int


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
    passages: list[CitedPassage]
    retrieval: Retrieval = Field(exclude=True)

    def renumbered(self, ref_of: Callable[[str], int]) -> Self:
        """The same passages with the reference numbers `ref_of` gives their chunk ids."""
        passages = [
            passage.model_copy(update={"ref": ref_of(passage.id)}) for passage in self.passages
        ]
        return self.model_copy(update={"passages": passages})

    def sources(self) -> list[Source]:
        return [
            Source(
                kind="dailymed",
                name=passage.brand or passage.substance.lower(),
                url=passage.url,
                section=passage.section,
                effective_time=passage.effective_time,
                ref=passage.ref,
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
