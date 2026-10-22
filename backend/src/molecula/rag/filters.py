from collections.abc import Callable, Iterable, Mapping
from typing import Protocol, get_args

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from molecula import prompts
from molecula.schemas.compounds import Resolution
from molecula.schemas.decisions import (
    DecisionResponse,
    NoulQuestion,
    Question,
    StateMessage,
)
from molecula.schemas.labels import Label, ProductType, SectionGroup
from molecula.schemas.retrieval import DrugFilter, LabelFilter, LabelQuery
from molecula.schemas.usage import usage_of
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService

SECTION_GROUP_ORDER: tuple[str, ...] = get_args(SectionGroup.__value__)
SECTION_GROUPS: frozenset[str] = frozenset(SECTION_GROUP_ORDER)
MAX_SECTION_GROUPS = 3
SECTION_THRESHOLD = 0.5


class FilterExtractor:
    """Turns a question into the filter its label search runs under: the model extracts a
    `LabelQuery`, and `check` keeps only what the store knows."""

    def __init__(
        self, model: BaseChatModel, compounds: CompoundService, labels: LabelService
    ) -> None:
        self._model = model
        self._check = FilterCheck(compounds, labels)

    def extract(self, question: str) -> LabelFilter:
        """The checked filter for `question`. When the model gives no usable query, the filter
        is empty (a search of the whole index) and says why in `extraction_error`."""
        structured = self._model.with_structured_output(LabelQuery, include_raw=True)
        # The question goes in its own message, never into the prompt: it is untrusted text.
        result = structured.invoke(
            [SystemMessage(prompts.load("rag/extract_filters")), HumanMessage(question)]
        )
        query = result["parsed"]
        usage = usage_of(result["raw"])
        if isinstance(query, LabelQuery):
            return self.check(query).model_copy(update={"extraction_usage": usage})
        error = result["parsing_error"] or "the model returned no filter"
        return LabelFilter(
            extracted=LabelQuery(), extraction_error=str(error), extraction_usage=usage
        )

    def filter_for(
        self, question: str, *, drug: str | None = None, section: SectionGroup | None = None
    ) -> LabelFilter:
        """The filter for a search the agent asks for. A `drug` the agent names is searched
        as it is, without asking the model, which saves a model call per search; otherwise the
        filter is extracted from `question`. `section` joins the section groups either way."""
        sections: list[str] = [section] if section else []
        if drug is not None:
            return self.check(LabelQuery(substances=[drug], section_groups=sections))
        label_filter = self.extract(question)
        if section is None or section in label_filter.section_groups:
            return label_filter
        return label_filter.model_copy(
            update={"section_groups": [*label_filter.section_groups, section]}
        )

    def check(self, query: LabelQuery) -> LabelFilter:
        return self._check.check(query)


class Decider(Protocol):
    async def decide(
        self, state: str | list[StateMessage], questions: Mapping[str, Question]
    ) -> DecisionResponse: ...


class DecisionFilterExtractor:
    """Fills the filter with a decision model in one call, a yes/no question per section group.
    A decision model answers only what it is asked, so the drug names are found in the question
    by `CompoundService.find_names`. It isn't asked for the product type: Jev set one on 68 of
    94 questions that didn't say one, which hides a drug's other labels (#287)."""

    def __init__(
        self,
        model: Decider,
        compounds: CompoundService,
        labels: LabelService,
        *,
        threshold: float = SECTION_THRESHOLD,
    ) -> None:
        self._model = model
        self._compounds = compounds
        self._check = FilterCheck(compounds, labels)
        self._threshold = threshold
        self.questions = filter_questions()

    async def extract(self, question: str) -> LabelFilter:
        """The checked filter for `question`. Raises the model's errors as they come."""
        # The question goes as its own message, never into the questions: it is untrusted text.
        state = [StateMessage(role="user", content=question)]
        return self.filter_from(question, await self._model.decide(state, self.questions))

    def filter_from(self, question: str, response: DecisionResponse) -> LabelFilter:
        """The checked filter for `question` from the model's answers to `questions`."""
        probabilities = {group: response.noul(group).noul for group in SECTION_GROUP_ORDER}
        query = LabelQuery(
            substances=self._compounds.find_names(question),
            section_groups=picked_groups(probabilities, self._threshold),
        )
        return self._check.check(query).model_copy(
            update={"extraction_usage": response.usage.as_usage()}
        )


def filter_questions() -> dict[str, Question]:
    """A yes/no question per section group, keyed by the group."""
    return {
        group: NoulQuestion(instructions=section_question(group)) for group in SECTION_GROUP_ORDER
    }


def section_question(group: str) -> str:
    part = prompts.load(f"rag/label_filter/sections/{group}").strip()
    return prompts.load("rag/label_filter/section", part=part).strip()


def picked_groups(probabilities: Mapping[str, float], threshold: float) -> list[str]:
    """The groups whose probability reaches `threshold`, likeliest first, at most three, as many
    as the chat model may pick."""
    likeliest = sorted(probabilities, key=lambda group: probabilities[group], reverse=True)
    return [group for group in likeliest if probabilities[group] >= threshold][:MAX_SECTION_GROUPS]


class FilterCheck:
    """Checks a `LabelQuery` against the store, whichever model filled it."""

    def __init__(self, compounds: CompoundService, labels: LabelService) -> None:
        self._compounds = compounds
        self._labels = labels

    def check(self, query: LabelQuery) -> LabelFilter:
        """`query` checked against the store: drug names resolved to supported drugs and their
        labels, unknown section groups set aside."""
        drugs: dict[int, DrugFilter] = {}
        unsupported: list[Resolution] = []
        for name in query.substances:
            if not name.strip():
                continue
            resolution = self._compounds.resolve(name)
            drug = self._drug_filter(name, resolution, query.product_type)
            if drug is None:
                unsupported.append(resolution)
            elif drug.cid in drugs:
                drugs[drug.cid] = merged(drugs[drug.cid], drug)
            else:
                drugs[drug.cid] = drug
        groups = unique(group.strip().casefold() for group in query.section_groups)
        return LabelFilter(
            extracted=query,
            drugs=list(drugs.values()),
            unsupported=unsupported,
            section_groups=[group for group in groups if group in SECTION_GROUPS],
            ignored_section_groups=[group for group in groups if group not in SECTION_GROUPS],
            product_type=query.product_type,
        )

    def _drug_filter(
        self, name: str, resolution: Resolution, product_type: ProductType | None
    ) -> DrugFilter | None:
        match = resolution.match
        if match is None:
            return None
        compound = match.compound
        drug_labels = self._labels.get_labels(compound.cid)
        all_labels = drug_labels.labels if drug_labels else []
        labels = all_labels
        if match.kind != "name":
            labels = narrowed(labels, lambda label: is_brand_of(name, label, compound.name))
        if product_type:
            labels = narrowed(labels, lambda label: label.product_type == product_type)
        return DrugFilter(
            name=name,
            cid=compound.cid,
            generic=compound.name,
            set_ids=[label.set_id for label in labels],
            narrowed=len(labels) < len(all_labels),
        )


def narrowed[T](items: list[T], keep: Callable[[T], bool]) -> list[T]:
    """The items to keep, or all of them when none would be left: a brand or product type the
    drug has no label for doesn't hide the labels it has."""
    kept = [item for item in items if keep(item)]
    return kept or items


def is_brand_of(name: str, label: Label, generic: str) -> bool:
    """Whether `name` is the label's brand: "Voltaren" for "Voltaren Arthritis Pain". Brands
    that carry the generic name ("good now omeprazole") don't count, so a generic or salt name
    never narrows a search to one label."""
    if label.brand is None or generic.casefold() in label.brand.casefold():
        return False
    words = name.casefold().split()
    return label.brand.casefold().split()[: len(words)] == words


def merged(first: DrugFilter, second: DrugFilter) -> DrugFilter:
    return first.model_copy(
        update={
            "set_ids": unique([*first.set_ids, *second.set_ids]),
            "narrowed": first.narrowed and second.narrowed,
        }
    )


def unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))
