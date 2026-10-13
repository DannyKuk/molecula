import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from molecula.config import Settings
from molecula.ingest.runner import StepReport, log_failures, run_step, store_and_sources
from molecula.ingest.targets_report import write_report
from molecula.sources.chembl import ChemblClient, Mechanism, Molecule, Target
from molecula.sources.rcsb import ComplexCandidate, RcsbClient
from molecula.store.compounds import CompoundRecord, CompoundStore
from molecula.store.targets import (
    CandidateRecord,
    DrugTargets,
    LigandCode,
    TargetRecord,
    TargetStore,
)

logger = logging.getLogger(__name__)

HUMAN_TAXONOMY_ID = 9606
REPORT_NAME = "complex_candidates.md"

type Lookup = Literal["inchikey", "connectivity", "name"]


@dataclass(frozen=True)
class ChemblPick:
    """The ChEMBL molecule chosen for a compound, how it was found, and the other matches of
    that lookup, which were passed over."""

    molecule: Molecule
    matched_on: Lookup
    mechanisms: list[Mechanism]
    others: list[str]


@dataclass(frozen=True)
class DrugResult:
    compound: CompoundRecord
    pick: ChemblPick | None
    drug: DrugTargets


@dataclass
class TargetsReport(StepReport):
    results: list[DrugResult] = field(default_factory=list)


def ingest_targets(
    compounds: list[CompoundRecord], chembl: ChemblClient, rcsb: RcsbClient, store: TargetStore
) -> TargetsReport:
    """Store the targets, ligand codes and complex candidates of every compound.

    A compound that fails is reported and skipped. When a source stops answering, the run stops.
    """
    report = TargetsReport()
    report.results = run_step(
        compounds, lambda compound: ingest_targets_of(compound, chembl, rcsb, store), report
    )
    return report


def ingest_targets_of(
    compound: CompoundRecord, chembl: ChemblClient, rcsb: RcsbClient, store: TargetStore
) -> DrugResult:
    pick = pick_molecule(chembl, compound)
    mechanisms = unique_by_target(pick.mechanisms) if pick else []
    targets = [
        to_target(chembl.target(mechanism.target_chembl_id), mechanism)
        for mechanism in mechanisms
        if mechanism.target_chembl_id
    ]
    codes = ligand_codes(rcsb, compound)
    candidates = [
        candidate for target in targets for candidate in candidates_for(rcsb, target, codes)
    ]
    drug = DrugTargets(tuple(targets), tuple(codes), tuple(candidates))
    store.save(compound.cid, drug, fetched_at=datetime.now(UTC))
    return DrugResult(compound, pick, drug)


def pick_molecule(chembl: ChemblClient, compound: CompoundRecord) -> ChemblPick | None:
    """The named ChEMBL molecule for a compound, preferring one whose parent has mechanisms.

    Lookups go by exact InChIKey, then connectivity block, then name, and move on while no named
    molecule with mechanisms turns up: an exact match can be an unnamed record without any
    (glimepiride), and ChEMBL draws some drugs as another tautomer (doxycycline). Unnamed
    molecules are never picked. Without mechanisms anywhere, the first named molecule is kept.
    """
    lookups: list[tuple[Lookup, Callable[[], list[Molecule]]]] = [
        ("inchikey", lambda: chembl.molecules_for_inchikey(compound.inchikey)),
        ("connectivity", lambda: chembl.molecules_for_connectivity(compound.inchikey)),
        ("name", lambda: chembl.molecules_named(compound.name)),
    ]
    fallback = None
    for matched_on, lookup in lookups:
        molecules = lookup()
        for molecule in named_first(molecules, compound.name):
            others = [other.chembl_id for other in molecules if other != molecule]
            mechanisms = chembl.mechanisms(molecule.parent_chembl_id)
            pick = ChemblPick(molecule, matched_on, mechanisms, others)
            if mechanisms:
                return pick
            fallback = fallback or pick
    return fallback


def named_first(molecules: list[Molecule], name: str) -> list[Molecule]:
    """The named molecules, the one named like the drug first."""
    named = [molecule for molecule in molecules if molecule.pref_name]
    return sorted(
        named, key=lambda molecule: (molecule.pref_name or "").casefold() != name.casefold()
    )


def unique_by_target(mechanisms: list[Mechanism]) -> list[Mechanism]:
    """The first mechanism for each target: ChEMBL repeats them across records and salts."""
    first: dict[str | None, Mechanism] = {}
    for mechanism in mechanisms:
        first.setdefault(mechanism.target_chembl_id, mechanism)
    return list(first.values())


def to_target(target: Target, mechanism: Mechanism) -> TargetRecord:
    return TargetRecord(
        target_chembl_id=target.chembl_id,
        molecule_chembl_id=mechanism.molecule_chembl_id,
        name=target.pref_name,
        target_type=target.target_type,
        organism=target.organism,
        mechanism=mechanism.mechanism_of_action,
        action_type=mechanism.action_type,
        accessions=tuple(c.accession for c in target.components if c.accession),
        gene_symbols=tuple(c.gene_symbol for c in target.components if c.gene_symbol),
    )


def ligand_codes(rcsb: RcsbClient, compound: CompoundRecord) -> list[LigandCode]:
    if codes := rcsb.ligand_codes(compound.inchikey):
        return [LigandCode(code, "inchikey") for code in codes]
    return [
        LigandCode(code, "connectivity")
        for code in rcsb.ligand_codes_by_connectivity(compound.smiles, compound.inchikey)
    ]


def candidates_for(
    rcsb: RcsbClient, target: TargetRecord, codes: list[LigandCode]
) -> list[CandidateRecord]:
    """Entries with one of the ligand codes bound to a protein of the target, best first."""
    if not target.gene_symbols:
        return []
    species = virus_species(target.organism)
    found = [
        (code.code, complex_)
        for code in codes
        for complex_ in rcsb.complexes(code.code, list(target.gene_symbols), taxon=species)
    ]
    found.sort(key=lambda pair: (rank_key(pair[1]), pair[0]))
    return [
        CandidateRecord(
            target_chembl_id=target.target_chembl_id,
            rank=rank,
            pdb_id=complex_.pdb_id,
            ligand_code=code,
            title=complex_.title,
            resolution=complex_.resolution,
            organism=complex_.organism,
            taxonomy_id=complex_.taxonomy_id,
            chains=tuple(complex_.chains),
        )
        for rank, (code, complex_) in enumerate(found, start=1)
    ]


def virus_species(organism: str | None) -> str | None:
    """The species a viral target's complexes must come from; None for any other target.

    Cellular targets match across species (mouse ABL1 in 1IEP), but viral gene names are generic:
    HIV-1 integrase and foamy virus integrase are both `pol`. ChEMBL names a strain after its
    species, "Influenza A virus (A/Puerto Rico/8/1934(H1N1))", and the species is what counts,
    since the neuraminidase structures come from many strains. A type in the parentheses is part
    of the species: "Herpes simplex virus (type 1 / strain 17)" is "Herpes simplex virus 1".
    """
    if organism is None or "virus" not in organism.casefold():
        return None
    species, _, strain = organism.partition(" (")
    if virus_type := re.match(r"type (\w+)", strain):
        return f"{species} {virus_type.group(1)}"
    return species


def rank_key(complex_: ComplexCandidate) -> tuple[bool, bool, float, str]:
    """Human proteins first, then the best (lowest) resolution, entries without one last."""
    return (
        complex_.taxonomy_id != HUMAN_TAXONOMY_ID,
        complex_.resolution is None,
        complex_.resolution or 0.0,
        complex_.pdb_id,
    )


def run(settings: Settings) -> int:
    """`python -m molecula.ingest targets`: targets and complex candidates for every compound."""
    with store_and_sources(settings) as (conn, http):
        report = ingest_targets(
            CompoundStore(conn).all(), ChemblClient(http), RcsbClient(http), TargetStore(conn)
        )
    path = settings.build_dir / REPORT_NAME
    write_report(report, path)
    log_summary(report, path)
    return 0 if report.complete else 1


def log_summary(report: TargetsReport, path: Path) -> None:
    with_targets = [r for r in report.results if r.drug.targets]
    with_candidates = [r for r in report.results if r.drug.candidates]
    logger.info(
        "%d compounds: %d with targets, %d with complex candidates; report in %s",
        len(report.results),
        len(with_targets),
        len(with_candidates),
        path,
    )
    log_failures(report, "a source")
