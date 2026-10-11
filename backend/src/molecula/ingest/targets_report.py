from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from molecula.store.targets import CandidateRecord, TargetRecord

if TYPE_CHECKING:
    from molecula.ingest.targets import DrugResult, TargetsReport

SHOWN_GENES = 6
INTRO = (
    "Written by `python -m molecula.ingest targets`. For each drug: the ChEMBL molecule, its "
    "targets, its PDB ligand codes and the entries showing a ligand bound to a protein of the "
    "target, human first, then by resolution. "
    "The hero set is chosen from these by hand (`docs/data-plan.md` §5.3)."
)


def write_report(report: TargetsReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(report), encoding="utf-8")


def render(report: TargetsReport) -> str:
    lines = ["# Complex candidates", "", INTRO, "", *summary(report)]
    for result in report.results:
        lines += drug_section(result)
    return "\n".join(lines) + "\n"


def summary(report: TargetsReport) -> list[str]:
    results = report.results
    lines = [
        "## Summary",
        "",
        f"- {len(results)} compounds stored: "
        f"{sum(1 for r in results if r.drug.targets)} with targets, "
        f"{sum(1 for r in results if r.drug.candidates)} with complex candidates.",
        f"- No ChEMBL molecule: {names(r for r in results if r.pick is None)}",
        f"- No target in ChEMBL: {names(r for r in results if r.pick and not r.drug.targets)}",
        f"- No ligand code in the PDB: {names(r for r in results if not r.drug.ligand_codes)}",
    ]
    lines += [f"- Failed: {name}: {reason}" for name, reason in report.failures.items()]
    if report.not_attempted:
        lines.append(
            f"- Not attempted (a source stopped answering): {', '.join(report.not_attempted)}"
        )
    return [*lines, ""]


def names(results: Iterable[DrugResult]) -> str:
    return ", ".join(result.compound.name for result in results) or "none"


def drug_section(result: DrugResult) -> list[str]:
    lines = [f"## {result.compound.name} (CID {result.compound.cid})", ""]
    if pick := result.pick:
        molecule = pick.molecule
        line = f"- ChEMBL: {molecule.chembl_id} {molecule.pref_name}, matched on {pick.matched_on}"
        if molecule.parent_chembl_id != molecule.chembl_id:
            line += f", parent {molecule.parent_chembl_id}"
        if pick.others:
            line += f"; passed over {', '.join(pick.others)}"
        lines.append(line)
    else:
        lines.append("- ChEMBL: no molecule")
    codes = [f"{code.code} ({code.matched_on})" for code in result.drug.ligand_codes]
    lines += [f"- Ligand codes: {', '.join(codes) or 'none'}", ""]
    for target in result.drug.targets:
        candidates = [
            c for c in result.drug.candidates if c.target_chembl_id == target.target_chembl_id
        ]
        lines += target_section(target, candidates)
    return lines


def target_section(target: TargetRecord, candidates: list[CandidateRecord]) -> list[str]:
    genes = list(target.gene_symbols[:SHOWN_GENES])
    if len(target.gene_symbols) > SHOWN_GENES:
        genes.append(f"+{len(target.gene_symbols) - SHOWN_GENES} more")
    lines = [
        f"### {target.name} ({target.target_chembl_id})",
        "",
        f"{target.mechanism} ({target.action_type}); {target.target_type}, {target.organism}; "
        f"genes: {', '.join(genes) or 'none'}. {len(candidates)} candidates.",
        "",
    ]
    if not candidates:
        return lines
    lines += [
        "| Rank | PDB | Ligand | Resolution (Å) | Organism | Chains | Title |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {c.rank} | {c.pdb_id} | {c.ligand_code} | {c.resolution or '-'} | {c.organism or '-'}"
        f" | {','.join(c.chains)} | {(c.title or '').replace('|', '/')} |"
        for c in candidates
    ]
    return [*lines, ""]
