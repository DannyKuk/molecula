import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from molecula.config import Settings
from molecula.ingest.conformers import embed_conformer
from molecula.ingest.scope import Scope, ScopeEntry, load_scope
from molecula.sources.errors import SourceError, SourceUnavailable
from molecula.sources.http import SourceClient
from molecula.sources.pubchem import CompoundProperties, PubChemClient
from molecula.store.compounds import CompoundRecord, CompoundStore, ConformerSource, Synonym
from molecula.store.db import connect
from molecula.store.http_cache import HttpCache
from molecula.store.structures import ConformerFiles

logger = logging.getLogger(__name__)

SYNONYM_LIMIT = 30
# PubChem has no conformer for peptides and proteins, and an RDKit one would be meaningless.
# Small molecules PubChem skips (too flexible, e.g. ritonavir with 50 heavy atoms) stay far below.
MAX_EMBED_HEAVY_ATOMS = 100


class AmbiguousParent(Exception):
    """A name whose compound has no single parent, such as a mixture of two drugs."""


@dataclass
class IngestReport:
    stored: list[CompoundRecord] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)
    not_attempted: list[str] = field(default_factory=list)


def ingest_compounds(
    scope: Scope, pubchem: PubChemClient, store: CompoundStore, conformers: ConformerFiles
) -> IngestReport:
    """Store the parent compound, its properties, a conformer and synonyms for every scope drug.

    A drug that fails is reported and skipped; the others are still stored. When PubChem stops
    answering, the run stops too: more requests would only prolong a block.
    """
    report = IngestReport()
    for position, entry in enumerate(scope.drugs):
        try:
            report.stored.append(ingest_entry(entry, pubchem, store, conformers))
        except (SourceError, AmbiguousParent) as error:
            logger.warning("%s: %s", entry.name, error)
            report.failures[entry.name] = str(error)
            if isinstance(error, SourceUnavailable):
                report.not_attempted = [drug.name for drug in scope.drugs[position + 1 :]]
                break
    return report


def ingest_entry(
    entry: ScopeEntry, pubchem: PubChemClient, store: CompoundStore, conformers: ConformerFiles
) -> CompoundRecord:
    cid = parent_cid(pubchem, entry.name)
    properties = pubchem.properties(cid)
    sdf, conformer_source = conformer(pubchem, properties)
    compound = to_record(entry.name, properties, conformer_source)
    synonyms = [
        Synonym(entry.name, "name"),
        *(Synonym(alias, "alias") for alias in entry.aliases),
        *(Synonym(alias, "pubchem") for alias in pubchem.synonyms(cid)[:SYNONYM_LIMIT]),
    ]
    if sdf is None:
        conformers.remove(cid)
    else:
        conformers.write(cid, sdf)
    store.save(compound, synonyms, fetched_at=datetime.now(UTC))
    return compound


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
        source="pubchem",
    )


def run(settings: Settings) -> int:
    """`python -m molecula.ingest compounds`: fill the store for the whole scope."""
    scope = load_scope(settings.scope_path)
    conn = connect(settings.db_path)
    http = SourceClient(HttpCache(conn), offline=settings.offline)
    try:
        report = ingest_compounds(
            scope, PubChemClient(http), CompoundStore(conn), ConformerFiles(settings.conformers_dir)
        )
    finally:
        http.close()
        conn.close()
    log_summary(report)
    return 1 if report.failures or report.not_attempted else 0


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
    for name, reason in report.failures.items():
        logger.error("  failed: %s: %s", name, reason)
    if report.not_attempted:
        logger.error(
            "stopped because PubChem stopped answering; %d drugs not attempted. "
            "Re-run later: what is stored so far is served from the cache.",
            len(report.not_attempted),
        )
