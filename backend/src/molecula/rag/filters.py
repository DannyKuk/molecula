from collections.abc import Callable, Iterable
from typing import get_args

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from molecula import prompts
from molecula.schemas.compounds import Compound, Resolution
from molecula.schemas.labels import Label, ProductType, SectionGroup
from molecula.schemas.retrieval import DrugFilter, LabelFilter, LabelQuery
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService

SECTION_GROUPS: frozenset[str] = frozenset(get_args(SectionGroup.__value__))


class FilterExtractor:
    """Turns a question into the filter its label search runs under: the model extracts a
    `LabelQuery`, and `check` keeps only what the store knows."""

    def __init__(
        self, model: BaseChatModel, compounds: CompoundService, labels: LabelService
    ) -> None:
        self._model = model
        self._compounds = compounds
        self._labels = labels

    def extract(self, question: str) -> LabelFilter:
        """The checked filter for `question`. When the model gives no usable query, the filter
        is empty (a search of the whole index) and says why in `extraction_error`."""
        structured = self._model.with_structured_output(LabelQuery, include_raw=True)
        # The question goes in its own message, never into the prompt: it is untrusted text.
        result = structured.invoke(
            [SystemMessage(prompts.load("rag/extract_filters")), HumanMessage(question)]
        )
        query = result["parsed"]
        if isinstance(query, LabelQuery):
            return self.check(query)
        error = result["parsing_error"] or "the model returned no filter"
        return LabelFilter(extracted=LabelQuery(), extraction_error=str(error))

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
        compound = match.compound if match else self._drug_inside(name)
        if compound is None:
            return None
        drug_labels = self._labels.get_labels(compound.cid)
        all_labels = drug_labels.labels if drug_labels else []
        labels = all_labels
        if match is None or match.kind != "name":
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

    def _drug_inside(self, name: str) -> Compound | None:
        """The one supported drug an unknown product name contains: "Fleqsuvy baclofen" is
        baclofen. A name with two drugs in it stays unknown rather than picking one."""
        cids = {mention.cid for mention in self._compounds.find_mentions(name)}
        if len(cids) != 1:
            return None
        return self._compounds.get_compound(cids.pop())


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
