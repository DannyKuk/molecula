"""Fake services, filter extractor and label retriever for the agent tool tests, and a tool
call helper."""

from datetime import date
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from molecula.schemas.complexes import Atom, Complex, Contact, Ligand, Residue
from molecula.schemas.compounds import Compound, Resolution, Suggestion
from molecula.schemas.labels import SectionGroup
from molecula.schemas.retrieval import (
    DrugFilter,
    LabelFilter,
    LabelQuery,
    Retrieval,
    RetrievedChunk,
    Widening,
)
from molecula.schemas.targets import DrugTargets, Target
from molecula.schemas.tools import CitedPassage

FLUTICASONE_CID = 5311101


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

    def targets_of(self, compound: Compound) -> DrugTargets:
        self.asked.append(compound.cid)
        return self.drugs.get(compound.cid, DrugTargets(cid=compound.cid, targets=[]))


MET318 = Residue(chain="A", number=318, name="MET")
THR315 = Residue(chain="A", number=315, name="THR")
IMATINIB_COMPLEX = Complex(
    pdb_id="1IEP",
    ligand=Ligand(
        code="STI",
        chain="A",
        number=201,
        atoms=[Atom(name="N3", element="N", xyz=(0.0, 0.0, 0.0))],
        bonds=[],
    ),
    trace=[],
    pocket=[],
    contacts=[
        Contact(kind="hbond", residue=MET318, residue_atom="N", ligand_atom=0, distance=3.0),
        Contact(kind="contact", residue=MET318, residue_atom="N", ligand_atom=0, distance=3.0),
        Contact(kind="contact", residue=THR315, residue_atom="OG1", ligand_atom=0, distance=2.9),
    ],
    target="ABL1",
    organism="Mus musculus",
)


class FakeComplexService:
    """Has imatinib's complex and no other; records the CIDs it was asked."""

    def __init__(self) -> None:
        self.complexes = {5291: IMATINIB_COMPLEX}
        self.asked: list[int] = []

    def get_complex(self, cid: int) -> Complex | None:
        self.asked.append(cid)
        return self.complexes.get(cid)


IMATINIB_SIDE_EFFECTS = RetrievedChunk(
    id="gleevec:adverse_reactions:0",
    text="Nausea, fluid retention and muscle cramps were the most common adverse reactions.",
    score=0.71,
    cid=5291,
    substance="IMATINIB MESYLATE",
    brand="Gleevec",
    product_type="rx",
    section="adverse_reactions",
    section_group="adverse_reactions",
    sensitive=False,
    set_id="gleevec",
    effective_time=date(2026, 7, 13),
    url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=gleevec",
    in_section_groups=True,
)
IMATINIB_LOW_SCORE = IMATINIB_SIDE_EFFECTS.model_copy(
    update={"id": "gleevec:storage:0", "text": "Store at room temperature.", "score": -0.1}
)


def cited(chunk: RetrievedChunk, ref: int) -> CitedPassage:
    return CitedPassage(**chunk.model_dump(), ref=ref)


def drug_filter(name: str, compound: Compound, set_ids: list[str]) -> DrugFilter:
    return DrugFilter(name=name, cid=compound.cid, generic=compound.name, set_ids=set_ids)


class FakeFilterExtractor:
    """Returns the filter set for a question (an empty one otherwise); records each request as
    (question, drug, section)."""

    def __init__(self) -> None:
        self.filters: dict[str, LabelFilter] = {}
        self.asked: list[tuple[str, str | None, SectionGroup | None]] = []

    def filter_for(
        self, question: str, *, drug: str | None = None, section: SectionGroup | None = None
    ) -> LabelFilter:
        self.asked.append((question, drug, section))
        return self.filters.get(question, LabelFilter(extracted=LabelQuery()))


class FakeLabelRetriever:
    """Finds `chunks` (or the question's own in `chunks_by_question`) and drops `dropped`
    unless the filter names drugs without labels, like the real retriever; records the filters
    it searched under."""

    def __init__(self) -> None:
        self.chunks = [IMATINIB_SIDE_EFFECTS]
        self.chunks_by_question: dict[str, list[RetrievedChunk]] = {}
        self.dropped = [IMATINIB_LOW_SCORE]
        self.widened: list[Widening] = []
        self.searched: list[LabelFilter | None] = []

    def retrieve(self, question: str, label_filter: LabelFilter | None = None) -> Retrieval:
        self.searched.append(label_filter)
        if label_filter is not None and label_filter.names_drugs and not label_filter.set_ids:
            return Retrieval(question=question, filter=label_filter, chunks=[], dropped=[])
        return Retrieval(
            question=question,
            filter=label_filter,
            chunks=self.chunks_by_question.get(question, self.chunks),
            dropped=self.dropped,
            widened=self.widened,
        )


def call_tool(tool: BaseTool, args: dict[str, Any]) -> ToolMessage:
    """Runs a tool the way the agent does: from a model's tool call, back as a ToolMessage."""
    message = tool.invoke({"type": "tool_call", "name": tool.name, "args": args, "id": "call_1"})
    assert isinstance(message, ToolMessage)
    return message
