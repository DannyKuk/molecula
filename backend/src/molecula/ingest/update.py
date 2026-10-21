import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from molecula.config import Settings
from molecula.ingest.index import DrugIndexer
from molecula.ingest.labels import canonical_labels
from molecula.ingest.runner import StepReport, log_failures, run_step, store_and_sources
from molecula.sources.errors import SourceError, SourceNotFound
from molecula.sources.openfda import OpenFdaClient
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.label_updates import (
    LabelChange,
    LabelUpdateRun,
    LabelUpdateStore,
    UpdateOutcome,
)
from molecula.store.labels import LabelRecord, LabelStore

logger = logging.getLogger(__name__)

type Reindex = Callable[[int, Sequence[LabelRecord]], None]


@dataclass(frozen=True)
class Drug:
    """A compound and the canonical labels the store holds for it."""

    compound: CompoundRecord
    labels: tuple[LabelRecord, ...]

    @property
    def name(self) -> str:
        return self.compound.name


def update_labels(
    compounds: Sequence[CompoundRecord],
    openfda: OpenFdaClient,
    labels: LabelStore,
    updates: LabelUpdateStore,
    reindex: Reindex,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> LabelUpdateRun:
    """Bring the canonical labels up to date and record the run.

    Follows the label chosen for each drug: a few count queries find the chosen labels that
    openFDA withdrew or published a new version of, and only those drugs are fetched again,
    selected again and re-indexed. Ends after one request when openFDA has published nothing
    since the last run.
    """
    started = now()
    last = updates.last_finished()
    drugs = [Drug(compound, labels.get(compound.cid)) for compound in compounds]
    effective_times = {
        label.set_id: label.effective_time for drug in drugs for label in drug.labels
    }
    run = LabelUpdateRun(
        started_at=started,
        finished_at=started,
        outcome="failed",
        source_updated=None,
        drugs_checked=len(drugs),
        drugs_rechecked=0,
    )
    try:
        # Any one of our labels will do to read openFDA's publication date off a count.
        source_updated = openfda.last_updated(min(effective_times)) if effective_times else None
        run = replace(run, source_updated=source_updated)
        if last and source_updated and source_updated == last.source_updated:
            return finish(run, updates, now, outcome="nothing_new")
        listed = openfda.listed(sorted(effective_times))
        newer = openfda.newer(dict(sorted(effective_times.items())))
    except SourceError as error:
        logger.error("openFDA check failed: %s", error)
        return finish(run, updates, now, error=str(error))
    marked = [drug for drug in drugs if was_changed(drug, listed, newer)]
    report = StepReport()
    changes = run_step(marked, lambda drug: recheck(drug, openfda, labels, reindex, now()), report)
    log_failures(report, "openFDA")
    return finish(
        replace(
            run,
            drugs_rechecked=len(marked),
            changes=tuple(change for drug_changes in changes for change in drug_changes),
        ),
        updates,
        now,
        outcome="complete" if report.complete else "incomplete",
        error="; ".join(f"{name}: {reason}" for name, reason in report.failures.items()) or None,
    )


def was_changed(drug: Drug, listed: set[str], newer: set[str]) -> bool:
    """Whether openFDA withdrew one of the drug's chosen labels or has a new version of it."""
    return any(label.set_id not in listed or label.set_id in newer for label in drug.labels)


def recheck(
    drug: Drug,
    openfda: OpenFdaClient,
    labels: LabelStore,
    reindex: Reindex,
    fetched_at: datetime,
) -> list[LabelChange]:
    """Select the drug's canonical labels again from all its labels as openFDA lists them now.
    A changed drug is re-indexed before its label rows are replaced: should the run stop in
    between, the next run still sees the stored label as old and repeats both."""
    try:
        found = openfda.labels(drug.name, refresh=True)
    except SourceNotFound:
        found = []
    chosen = canonical_labels(drug.name, found)
    if chosen == drug.labels:
        return []
    reindex(drug.compound.cid, chosen)
    labels.save(drug.compound.cid, chosen, fetched_at)
    return label_changes(drug.compound.cid, drug.labels, chosen)


def label_changes(
    cid: int, old: Sequence[LabelRecord], new: Sequence[LabelRecord]
) -> list[LabelChange]:
    before = {label.product_type: label for label in old}
    after = {label.product_type: label for label in new}
    return [
        LabelChange(
            cid=cid,
            product_type=product_type,
            old_set_id=old_label.set_id if old_label else None,
            old_effective_time=old_label.effective_time if old_label else None,
            new_set_id=new_label.set_id if new_label else None,
            new_effective_time=new_label.effective_time if new_label else None,
        )
        for product_type in sorted(before.keys() | after.keys())
        if (old_label := before.get(product_type)) != (new_label := after.get(product_type))
    ]


def finish(
    run: LabelUpdateRun,
    updates: LabelUpdateStore,
    now: Callable[[], datetime],
    *,
    outcome: UpdateOutcome = "failed",
    error: str | None = None,
) -> LabelUpdateRun:
    finished = replace(run, finished_at=now(), outcome=outcome, error=error)
    updates.add(finished)
    return finished


def run(settings: Settings) -> int:
    """`python -m molecula.ingest update`: bring the labels up to date. Run it with the backend
    stopped: the backend keeps the label index open, and only one process may write to it."""
    if settings.offline:
        logger.error("OFFLINE=1: a label update needs openFDA, so nothing was checked or changed")
        return 1
    with store_and_sources(settings) as (conn, http):
        compounds = CompoundStore(conn).all()
        result = update_labels(
            compounds,
            OpenFdaClient(http, api_key=settings.openfda_api_key),
            LabelStore(conn),
            LabelUpdateStore(conn),
            DrugIndexer(settings),
        )
    log_summary(result, {compound.cid: compound.name for compound in compounds})
    return 0 if result.outcome in ("complete", "nothing_new") else 1


def log_summary(run: LabelUpdateRun, names: dict[int, str]) -> None:
    if run.outcome == "nothing_new":
        logger.info(
            "openFDA has published nothing since the last update (data of %s)",
            run.source_updated,
        )
        return
    logger.info(
        "%s: %d drugs checked (openFDA data of %s), %d fetched again, %d labels changed, in %.0f s",
        run.outcome,
        run.drugs_checked,
        run.source_updated,
        run.drugs_rechecked,
        len(run.changes),
        (run.finished_at - run.started_at).total_seconds(),
    )
    for change in run.changes:
        logger.info(
            "  %s %s: %s %s -> %s %s",
            names.get(change.cid, change.cid),
            change.product_type,
            change.old_set_id or "none",
            change.old_effective_time or "",
            change.new_set_id or "none",
            change.new_effective_time or "",
        )
    if run.error:
        logger.error("  %s", run.error)
