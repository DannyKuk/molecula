import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from molecula.config import Settings
from molecula.ingest.runner import StepReport, log_failures, run_step, store_and_sources
from molecula.services.compounds import name_candidates
from molecula.sources.errors import SourceNotFound
from molecula.sources.openfda import Label, OpenFdaClient
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.labels import LabelRecord, LabelSection, LabelStore, ProductType, SectionGroup

logger = logging.getLogger(__name__)

SOURCE = "openfda"
DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
PRODUCT_TYPES: dict[ProductType, str] = {
    "rx": "HUMAN PRESCRIPTION DRUG",
    "otc": "HUMAN OTC DRUG",
}
# The sections the knowledge base uses, from PLR prescription labels, older prescription labels
# and OTC Drug Facts. Left out: the preclinical sections (animal and carcinogenicity studies),
# references, change notes, and the `*_table` HTML copies of sections already kept as text.
# `overdosage` is kept: its symptoms, treatment and toxic amounts matter when someone has taken
# too much, and the app runs offline.
SECTION_GROUPS: dict[str, SectionGroup] = {
    "mechanism_of_action": "pharmacology",
    "clinical_pharmacology": "pharmacology",
    "pharmacodynamics": "pharmacology",
    "pharmacokinetics": "pharmacology",
    "pharmacogenomics": "pharmacology",
    "microbiology": "pharmacology",
    "indications_and_usage": "indications",
    "dosage_and_administration": "dosing",
    "boxed_warning": "warnings",
    "warnings_and_cautions": "warnings",
    "warnings": "warnings",
    "precautions": "warnings",
    "general_precautions": "warnings",
    "laboratory_tests": "warnings",
    "contraindications": "contraindications",
    "drug_interactions": "interactions",
    "drug_and_or_laboratory_test_interactions": "interactions",
    "adverse_reactions": "adverse_reactions",
    "use_in_specific_populations": "specific_populations",
    "pregnancy": "specific_populations",
    "teratogenic_effects": "specific_populations",
    "nonteratogenic_effects": "specific_populations",
    "labor_and_delivery": "specific_populations",
    "nursing_mothers": "specific_populations",
    "pediatric_use": "specific_populations",
    "geriatric_use": "specific_populations",
    "pregnancy_or_breast_feeding": "specific_populations",
    "information_for_patients": "patient_information",
    "spl_medguide": "patient_information",
    "spl_patient_package_insert": "patient_information",
    "patient_medication_information": "patient_information",
    "instructions_for_use": "patient_information",
    "description": "product",
    "dosage_forms_and_strengths": "product",
    "how_supplied": "product",
    "storage_and_handling": "product",
    "inactive_ingredient": "product",
    "drug_abuse_and_dependence": "abuse_dependence",
    "abuse": "abuse_dependence",
    "dependence": "abuse_dependence",
    "controlled_substance": "abuse_dependence",
    "clinical_studies": "clinical_studies",
    "overdosage": "overdosage",
    "do_not_use": "otc_consumer",
    "stop_use": "otc_consumer",
    "ask_doctor": "otc_consumer",
    "ask_doctor_or_pharmacist": "otc_consumer",
    "when_using": "otc_consumer",
    "purpose": "otc_consumer",
    "active_ingredient": "otc_consumer",
    "keep_out_of_reach_of_children": "otc_consumer",
    "other_safety_information": "otc_consumer",
}
# Text that may be quoted but never turned into personal advice: doses, use in pregnancy, children
# and older people, the patient leaflets' "how to take" passages, how a drug is misused, and
# toxic and lethal amounts.
SENSITIVE_GROUPS: frozenset[SectionGroup] = frozenset(
    {"dosing", "specific_populations", "patient_information", "abuse_dependence", "overdosage"}
)
REFERENCE_APPLICATIONS = ("NDA", "BLA")


@dataclass(frozen=True)
class DrugLabels:
    """The canonical labels chosen for a compound out of the `found` labels its search returned."""

    compound: CompoundRecord
    found: int
    labels: tuple[LabelRecord, ...]


@dataclass
class LabelsReport(StepReport):
    results: list[DrugLabels] = field(default_factory=list)

    @property
    def without_label(self) -> list[str]:
        return [result.compound.name for result in self.results if not result.labels]


def ingest_labels(
    compounds: list[CompoundRecord], openfda: OpenFdaClient, store: LabelStore
) -> LabelsReport:
    """Store the canonical prescription and OTC label of every compound.

    A compound that fails is reported and skipped. When openFDA stops answering, the run stops.
    """
    report = LabelsReport()
    report.results = run_step(
        compounds, lambda compound: ingest_labels_of(compound, openfda, store), report
    )
    return report


def ingest_labels_of(
    compound: CompoundRecord, openfda: OpenFdaClient, store: LabelStore
) -> DrugLabels:
    """Search openFDA by the compound's name, which `data/scope.yaml` keeps as the US generic."""
    fetched_at = datetime.now(UTC)
    try:
        search = openfda.search(compound.name)
    except SourceNotFound:
        found: list[Label] = []
    else:
        found = search.labels
        if search.disclaimer:
            store.save_disclaimer(SOURCE, search.disclaimer, fetched_at)
    labels = canonical_labels(compound.name, found)
    store.save(compound.cid, labels, fetched_at)
    return DrugLabels(compound, len(found), labels)


def canonical_labels(name: str, labels: list[Label]) -> tuple[LabelRecord, ...]:
    """At most one prescription and one OTC label: the best single-ingredient label of the drug.

    A label of the parent itself or one of its salts is taken over another form of it (an ester
    such as fluticasone propionate); other forms count only when a product type has no such label.
    """
    canonical = []
    for product_type, openfda_type in PRODUCT_TYPES.items():
        single = [
            label
            for label in labels
            if openfda_type in label.openfda.product_type and len(label.openfda.substance_name) == 1
        ]
        parent = name.casefold()
        parents = [label for label in single if substance_parent(label) == parent]
        forms = [label for label in single if substance_parent(label).startswith(f"{parent} ")]
        if candidates := parents or forms:
            on_route = most_common_route(candidates)
            canonical.append(to_record(min(on_route, key=preference), product_type))
    return tuple(canonical)


def route(label: Label) -> str:
    """The label's routes as one value, e.g. "INTRAMUSCULAR,INTRAVENOUS"; empty without any."""
    return ",".join(sorted(label.openfda.route))


def most_common_route(labels: list[Label]) -> list[Label]:
    """The labels on the route most of them share, so the canonical label is the drug's usual
    form (ibuprofen tablets, not the IV injection that happens to have a mechanism section).

    Equally common routes go by name; labels without a route form a group of their own, which
    loses a tie.
    """
    counts = Counter(route(label) for label in labels)
    usual = min(counts, key=lambda value: (-counts[value], value == "", value))
    return [label for label in labels if route(label) == usual]


def substance_parent(label: Label) -> str:
    """The label's one substance without salt and hydrate words, in lower case."""
    return name_candidates(label.openfda.substance_name[0])[-1].casefold()


def preference(label: Label) -> tuple[bool, bool, int, int, str]:
    """Sorts the better label first: a mechanism section, the brand's own label, the newest, the
    one with the most sections the knowledge base uses, then by set_id so the choice is stable."""
    return (
        "mechanism_of_action" not in label.sections,
        not is_reference_label(label),
        -int(label.effective_time),
        -len(kept_sections(label)),
        label.set_id,
    )


def is_reference_label(label: Label) -> bool:
    """The brand's own label: filed under a new drug or biologics application (NDA or BLA, not a
    generic's ANDA or an OTC monograph) and sold under a name other than its generic name.

    The name check leaves out authorized generics and biosimilars, which are filed the same way.
    """
    fields = label.openfda
    filed_as_original = any(
        number.startswith(REFERENCE_APPLICATIONS) for number in fields.application_number
    )
    generic = {name.casefold() for name in fields.generic_name}
    branded = any(brand.casefold() not in generic for brand in fields.brand_name)
    return filed_as_original and branded


def kept_sections(label: Label) -> tuple[LabelSection, ...]:
    sections = []
    for section, texts in label.sections.items():
        group = SECTION_GROUPS.get(section)
        text = "\n\n".join(part.strip() for part in texts if part.strip())
        if group and text:
            sections.append(LabelSection(section, group, text, group in SENSITIVE_GROUPS))
    return tuple(sections)


def to_record(label: Label, product_type: ProductType) -> LabelRecord:
    return LabelRecord(
        set_id=label.set_id,
        substance=label.openfda.substance_name[0],
        brand=label.openfda.brand_name[0] if label.openfda.brand_name else None,
        product_type=product_type,
        effective_time=label.effective_time,
        url=DAILYMED_URL.format(set_id=label.set_id),
        sections=kept_sections(label),
    )


def run(settings: Settings) -> int:
    """`python -m molecula.ingest labels`: canonical labels for every compound."""
    with store_and_sources(settings) as (conn, http):
        report = ingest_labels(
            CompoundStore(conn).all(),
            OpenFdaClient(http, api_key=settings.openfda_api_key),
            LabelStore(conn),
        )
    log_summary(report)
    return 0 if report.complete else 1


def log_summary(report: LabelsReport) -> None:
    labels = [label for result in report.results for label in result.labels]
    logger.info(
        "%d compounds: %d with a prescription label, %d with an OTC label; %d characters stored",
        len(report.results),
        sum(1 for label in labels if label.product_type == "rx"),
        sum(1 for label in labels if label.product_type == "otc"),
        sum(label.characters for label in labels),
    )
    for result in report.results:
        chosen = ", ".join(
            f"{label.product_type} {label.brand or label.substance} {label.set_id}"
            f" ({label.characters} characters)"
            for label in result.labels
        )
        logger.info("  %s: %d found; %s", result.compound.name, result.found, chosen or "none")
    if report.without_label:
        logger.info("no US label: %s", ", ".join(report.without_label))
    log_failures(report, "openFDA")
