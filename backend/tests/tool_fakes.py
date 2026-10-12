"""Fake compound and target services for the agent tool tests, and a tool call helper."""

from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from molecula.schemas.compounds import Compound, Resolution, Suggestion
from molecula.schemas.targets import DrugTargets, Target

FLUTICASONE_CID = 5311101
# A compound whose targets the fake target service has lost, to test a resolve/targets mismatch.
ORPHAN_CID = 999


def compound(cid: int, name: str) -> Compound:
    return Compound(
        cid=cid,
        name=name,
        inchikey=f"INCHIKEY-{cid}",
        smiles="C",
        formula="C",
        molecular_weight=100.0,
        xlogp=1.0,
        tpsa=None,
        hbond_donors=1,
        hbond_acceptors=1,
        rotatable_bonds=0,
        heavy_atoms=10,
        has_3d=True,
        conformer_source="pubchem",
        source="pubchem",
        source_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
    )


IMATINIB = compound(5291, "imatinib")
IBUPROFEN = compound(3672, "ibuprofen")
FLUTICASONE = compound(FLUTICASONE_CID, "fluticasone")
ORPHAN = compound(ORPHAN_CID, "orphan")
ABL1 = Target(
    target_chembl_id="CHEMBL1862",
    name="Tyrosine-protein kinase ABL1",
    target_type="SINGLE PROTEIN",
    organism="Homo sapiens",
    mechanism="Tyrosine-protein kinase ABL inhibitor",
    action_type="INHIBITOR",
    accessions=["P00519"],
    gene_symbols=["ABL1"],
    source="chembl",
    source_url="https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1862",
)
GLEEVEC_SUGGESTION = Suggestion(alias="Gleevec", cid=5291, name="imatinib")


class FakeCompoundService:
    """Resolves a few names the way the real service does; records the names it was asked."""

    def __init__(self) -> None:
        self.found = {
            "gleevec": (IMATINIB, "Gleevec", "alias"),
            "imatinib": (IMATINIB, "imatinib", "name"),
            "imatinib mesylate": (IMATINIB, "imatinib", "name"),
            "advil": (IBUPROFEN, "Advil", "alias"),
            "fluticasone": (FLUTICASONE, "fluticasone", "name"),
            "xhance": (FLUTICASONE, "Xhance", "brand"),
            "orphan": (ORPHAN, "orphan", "name"),
        }
        self.suggestions = {"gleevek": [GLEEVEC_SUGGESTION]}
        self.resolved: list[str] = []

    def resolve(self, name: str) -> Resolution:
        self.resolved.append(name)
        query = " ".join(name.split())
        key = query.casefold()
        if key in self.found:
            match, alias, kind = self.found[key]
            return Resolution(
                query=query, status="found", compound=match, matched_alias=alias, match_kind=kind
            )
        return Resolution(
            query=query, status="not_supported", suggestions=self.suggestions.get(key, [])
        )


class FakeTargetService:
    """Knows imatinib (one target) and fluticasone (none); records the CIDs it was asked."""

    def __init__(self) -> None:
        self.drugs = {
            5291: DrugTargets(cid=5291, targets=[ABL1]),
            FLUTICASONE_CID: DrugTargets(cid=FLUTICASONE_CID, targets=[]),
        }
        self.asked: list[int] = []

    def get_targets(self, cid: int) -> DrugTargets | None:
        self.asked.append(cid)
        return self.drugs.get(cid)


def call_tool(tool: BaseTool, args: dict[str, Any]) -> ToolMessage:
    """Runs a tool the way the agent does: from a model's tool call, back as a ToolMessage."""
    message = tool.invoke({"type": "tool_call", "name": tool.name, "args": args, "id": "call_1"})
    assert isinstance(message, ToolMessage)
    return message
