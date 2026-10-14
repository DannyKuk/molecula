from typing import Any

from langchain_core.tools import StructuredTool

from molecula.schemas.tools import CitedTarget, DrugArgs, DrugNotSupported, DrugTargetList
from molecula.services.compounds import CompoundService
from molecula.services.targets import TargetService
from molecula.tools.base import build_tool, not_supported


def get_targets_tool(compounds: CompoundService, targets: TargetService) -> StructuredTool:
    def get_targets(drug: str) -> DrugTargetList | DrugNotSupported:
        """Look up what a supported drug acts on: its target proteins and its mechanism of
        action, as ChEMBL records them.

        `drug` can be a generic name, a brand, a non-US or German name or a salt name; it is
        resolved to the stored drug first.

        Returns `status: "found"` with the drug's CID and generic `name`, and `targets`: for
        each target its name, type (single protein, complex, ...), organism, ChEMBL's
        `mechanism` text, `action_type` (INHIBITOR, AGONIST, ...), UniProt accessions, gene
        symbols, `source_url`, its ChEMBL page, and `ref`, the number to cite that target and
        its mechanism with in square brackets, like `[2]`. An empty `targets` list means
        ChEMBL records no mechanism for the drug; say that rather than guessing one. Returns
        `status: "not_supported"` with `suggestions` when the drug isn't in Molecula's data:
        say so and offer the suggestions, never pick one yourself.
        """
        resolution = compounds.resolve(drug)
        match = resolution.match
        if match is None:
            return not_supported(resolution)
        found = targets.targets_of(match.compound)
        return DrugTargetList(
            query=resolution.query,
            cid=match.compound.cid,
            name=match.compound.name,
            targets=[CitedTarget(**target.model_dump()) for target in found.targets],
        )

    return build_tool(get_targets, DrugArgs, finding_targets)


def finding_targets(args: dict[str, Any]) -> str:
    return f"Finding the targets of {args.get('drug', 'the drug')}"
