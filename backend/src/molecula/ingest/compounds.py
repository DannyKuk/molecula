import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from molecula.config import Settings
from molecula.ingest.conformers import embed_conformer
from molecula.ingest.runner import StepReport, log_failures, run_step, store_and_sources
from molecula.ingest.scope import Scope, ScopeEntry, load_scope
from molecula.schemas.compounds import ConformerSource
from molecula.sources.errors import SourceError
from molecula.sources.pubchem import CompoundProperties, PubChemClient
from molecula.store.compounds import CompoundRecord, CompoundStore, Synonym
from molecula.store.sources import PUBCHEM
from molecula.store.structures import ConformerFiles

logger = logging.getLogger(__name__)

SYNONYM_LIMIT = 30
# PubChem has no conformer for peptides and proteins, and an RDKit one would be meaningless.
# Small molecules PubChem skips (too flexible, e.g. ritonavir with 50 heavy atoms) stay far below.
MAX_EMBED_HEAVY_ATOMS = 100


class IngestError(Exception):
    """A scope drug that can't be stored as one compound of its own."""


class AmbiguousParent(IngestError):
    """A name whose compound has no single parent, such as a mixture of two drugs."""


class DuplicateCompound(IngestError):
    """Two scope names for the same parent compound; storing both would rename the first."""


@dataclass
class IngestReport(StepReport):
    stored: list[CompoundRecord] = field(default_factory=list)
    pruned: list[CompoundRecord] = field(default_factory=list)
    pruned_conformers: list[int] = field(default_factory=list)


def ingest_compounds(
    scope: Scope, pubchem: PubChemClient, store: CompoundStore, conformers: ConformerFiles
) -> IngestReport:
    """Store the parent compound, its properties, a conformer and synonyms for every scope drug.

    A drug that fails is reported and skipped; the others are still stored. When PubChem stops
    answering, the run stops too: more requests would only prolong a block.

    Only a complete run prunes: compounds it didn't store have left the scope, and are deleted
    with their synonyms, targets and conformer files. A conformer file without a compound goes too.
    """
    report = IngestReport()
    claimed: dict[int, str] = {}

    def ingest_and_claim(entry: ScopeEntry) -> CompoundRecord:
        compound = ingest_entry(entry, pubchem, store, conformers, claimed)
        claimed[compound.cid] = compound.name
        return compound

    report.stored = run_step(
        scope.drugs, ingest_and_claim, report, catch=(SourceError, IngestError)
    )
    if report.complete:
        report.pruned = store.prune(claimed)
        report.pruned_conformers = conformers.prune(claimed)
    return report


def ingest_entry(
    entry: ScopeEntry,
    pubchem: PubChemClient,
    store: CompoundStore,
    conformers: ConformerFiles,
    claimed: Mapping[int, str],
) -> CompoundRecord:
    """Fetch and store one scope drug. `claimed` maps CIDs already stored in this run to names."""
    cid = parent_cid(pubchem, entry.name)
    if cid in claimed:
        raise DuplicateCompound(f"CID {cid} is already stored as {claimed[cid]}")
    properties = pubchem.properties(cid)
    sdf, conformer_source = conformer(pubchem, properties)
    compound = to_record(entry.name, properties, conformer_source)
    store.save(compound, synonyms(entry, pubchem.synonyms(cid)), fetched_at=datetime.now(UTC))
    if sdf is None:
        conformers.remove(cid)
    else:
        conformers.write(cid, sdf)
    return compound


def synonyms(entry: ScopeEntry, pubchem_synonyms: list[str]) -> list[Synonym]:
    """The scope name and aliases, then the top PubChem synonyms that aren't among them."""
    scope_terms = [entry.name, *entry.aliases]
    taken = {term.casefold() for term in scope_terms}
    extra = [alias for alias in pubchem_synonyms if alias.casefold() not in taken]
    return [
        Synonym(entry.name, "name"),
        *(Synonym(alias, "alias") for alias in entry.aliases),
        *(Synonym(alias, "pubchem") for alias in extra[:SYNONYM_LIMIT]),
    ]


def parent_cid(pubchem: PubChemClient, name: str) -> int:
    """The parent compound for a name, so a salt or hydrate resolves to the active molecule."""
    cid = pubchem.cids_for_name(name)[0]
    parents = pubchem.parent_cids(cid)
    if len(parents) != 1:
        raise AmbiguousParent(f"CID {cid} has {len(parents)} parent compounds: {parents}")
    return parents[0]


def conformer(
    pubchem: PubChemClient, properties: CompoundProperties
) -> tuple[str | None, ConformerSource | None]:
    """The conformer SDF and where it came from: PubChem, else RDKit, else (None, None)."""
    if sdf := pubchem.conformer_sdf(properties.cid):
        return sdf, "pubchem"
    if properties.heavy_atoms > MAX_EMBED_HEAVY_ATOMS:
        return None, None
    if sdf := embed_conformer(properties.cid, properties.smiles):
        return sdf, "rdkit"
    return None, None


def to_record(
    name: str, properties: CompoundProperties, conformer_source: ConformerSource | None
) -> CompoundRecord:
    return CompoundRecord(
        cid=properties.cid,
        name=name,
        inchikey=properties.inchikey,
        smiles=properties.smiles,
        formula=properties.formula,
        mw=properties.molecular_weight,
        xlogp=properties.xlogp,
        tpsa=properties.tpsa,
        hbd=properties.hbd,
        hba=properties.hba,
        rotb=properties.rotatable_bonds,
        heavy_atoms=properties.heavy_atoms,
        conformer_source=conformer_source,
        source=PUBCHEM,
    )


def run(settings: Settings) -> int:
    """`python -m molecula.ingest compounds`: fill the store for the whole scope."""
    scope = load_scope(settings.scope_path)
    with store_and_sources(settings) as (conn, http):
        report = ingest_compounds(
            scope, PubChemClient(http), CompoundStore(conn), ConformerFiles(settings.conformers_dir)
        )
    log_summary(report)
    return 0 if report.complete else 1


def log_summary(report: IngestReport) -> None:
    sources = Counter(compound.conformer_source or "none" for compound in report.stored)
    logger.info(
        "stored %d compounds; conformers: %d PubChem, %d RDKit, %d none",
        len(report.stored),
        sources["pubchem"],
        sources["rdkit"],
        sources["none"],
    )
    for compound in report.stored:
        if compound.conformer_source != "pubchem":
            logger.info(
                "  %s (CID %d): conformer from %s",
                compound.name,
                compound.cid,
                compound.conformer_source or "nowhere",
            )
    if report.pruned:
        logger.info("pruned %d compounds that left the scope", len(report.pruned))
    for compound in report.pruned:
        logger.info("  pruned: %s (CID %d)", compound.name, compound.cid)
    if report.pruned_conformers:
        logger.info(
            "removed %d conformer files: %s",
            len(report.pruned_conformers),
            ", ".join(f"{cid}.sdf" for cid in report.pruned_conformers),
        )
    log_failures(report, "PubChem")
