"""Probe whether the label search returns passages with an exact term the question names (#44).

    OFFLINE=1 uv run python -m evals.retrieval.exact_terms

Asks one question per term, filtered to the drug as the agent filters it, in each retrieval mode,
and counts the top 5 chunks that contain the term. Nothing here says whether a chunk answers the
question: it shows only whether the term-holding passages come up, which is what keyword search is
for and what the retrieval questions, written in other words than their passages, can't show.
"""

from dataclasses import dataclass

from molecula.config import get_settings
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.retrieval import DrugFilter, LabelFilter, LabelQuery, RetrievalMode
from molecula.store.index import Chunk, LabelIndex
from molecula.store.keywords import KeywordIndex

TOP_K = 5
MODES: list[RetrievalMode] = ["dense", "bm25", "hybrid"]


@dataclass(frozen=True)
class Probe:
    question: str
    term: str
    drug: str
    cid: int


PROBES = [
    Probe("Can I take simvastatin with strong CYP3A4 inhibitors?", "CYP3A4", "simvastatin", 54454),
    Probe("Does clopidogrel work in CYP2C19 poor metabolizers?", "CYP2C19", "clopidogrel", 60606),
    Probe("Can ondansetron cause QT prolongation?", "QT", "ondansetron", 4595),
    Probe("Does escitalopram prolong the QT interval?", "QT", "escitalopram", 146570),
    Probe("Can metformin be used when eGFR is below 30?", "eGFR", "metformin", 4091),
    Probe("Does imatinib work for CD117 positive GIST?", "CD117", "imatinib", 5291),
    Probe("Can methotrexate be taken with NSAIDs?", "NSAID", "methotrexate", 126941),
    Probe("How should INR be monitored on warfarin?", "INR", "warfarin", 54678486),
]


def main() -> int:
    settings = get_settings()
    index = LabelIndex(settings.index_dir)
    index.check_model(embedding_model_id(settings))
    embeddings = get_embeddings(settings)
    keywords = KeywordIndex(settings.keyword_index_path)
    chunks = index.chunks()
    retrievers = {
        mode: LabelRetriever(
            index,
            embeddings,
            top_k=TOP_K,
            min_score=-1.0,
            section_group_boost=settings.section_group_boost,
            mode=mode,
            keywords=keywords,
        )
        for mode in MODES
    }

    print(f"Top {TOP_K} chunks that contain the term, filtered to the drug\n")
    print(f"| Question | Term | Drug's chunks with it | {' | '.join(MODES)} |")
    print(f"|---|---|---|{'---|' * len(MODES)}")
    totals = dict.fromkeys(MODES, 0)
    for probe in PROBES:
        label_filter = drug_filter(probe, chunks)
        counts = []
        for mode in MODES:
            found = retrievers[mode].retrieve(probe.question, label_filter).chunks
            count = sum(holds(probe, chunk.text) for chunk in found)
            totals[mode] += count
            counts.append(f"{count}/{len(found)}")
        available = sum(chunk.cid == probe.cid and holds(probe, chunk.text) for chunk in chunks)
        print(f"| {probe.question} | {probe.term} | {available} | {' | '.join(counts)} |")
    print(f"| **All** | | | {' | '.join(f'{totals[m]}/{TOP_K * len(PROBES)}' for m in MODES)} |")
    return 0


def drug_filter(probe: Probe, chunks: list[Chunk]) -> LabelFilter:
    set_ids = sorted({chunk.set_id for chunk in chunks if chunk.cid == probe.cid})
    drug = DrugFilter(name=probe.drug, cid=probe.cid, generic=probe.drug, set_ids=set_ids)
    return LabelFilter(extracted=LabelQuery(substances=[probe.drug]), drugs=[drug])


def holds(probe: Probe, text: str) -> bool:
    return probe.term.casefold() in text.casefold()


if __name__ == "__main__":
    raise SystemExit(main())
