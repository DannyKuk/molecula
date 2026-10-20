# Hybrid search: does BM25 next to the embeddings find more?

> **Answer:** not with reciprocal rank fusion, so the label search stays dense (bge-m3 alone). Replaying the agent's 99 real label searches, hybrid search returns the answering passage in the top 5 for 76 of 94 questions, dense for 78. It gains 8 questions, all with the answer in a section the agent didn't ask for, and loses 10, mostly ones dense ranked first. Where it helps is exact terms: on 8 probe questions about terms such as CYP3A4, QT and eGFR, 29 of the top 40 chunks contain the term, against 26 for dense. The BM25 index is built and shipped anyway, and `RETRIEVAL_MODE=hybrid` turns it on.

## Question

#44 planned a BM25 keyword index next to the embeddings, so exact terms such as drug codes, "QT prolongation" or "CYP3A4" are found even when the embeddings miss them, merged with reciprocal rank fusion (RRF). Does it return the answering passage more often than bge-m3 alone, the way the app searches?

## What we tried

- **The keyword index:** SQLite FTS5 over the same 7,012 chunks as the vector index, with the same ids and metadata, in `data/build/index/bm25.db` (24 MB, 0.3 s to build). BM25 with FTS5's defaults, the Porter stemmer, every term of the question OR-ed. The drug, label and section filters apply to both searches (`store/keywords.py`).
- **Fusion:** each search takes its 20 best chunks under the filter, in the filter's section groups and in all sections, as the dense search does; RRF with k = 60 merges the two rankings (`rag/retriever.py`). Ties go to the higher cosine similarity.
- **Three measures, scored by script, no model called:**
  - the agent's own label searches from the citation eval's cache (`openai_gpt-oss-20b-answer-medium-clean-context-c9a1a2ddf098.jsonl`, the one the [RAG eval](../evals/rag-2026-10-19.md) used), replayed through `LabelRetriever` with their search texts and checked filters (`evals/rag/top_k.py`);
  - the 94 retrieval questions with the answer key's filters (`evals/retrieval/filters.py`);
  - a probe of 8 questions that name an exact term, counting the top 5 chunks that contain it (`evals/retrieval/exact_terms.py`). The questions are new and written for this; the score needs no judgement.
- **Variants**, on the answer key's filters with the first tokenizer: the keyword ranking with the filter's section groups first, a BM25 weight of 0.5 and 0.3 in the fusion, and 10 instead of 20 chunks per search.

## Result

**The agent's searches**, answer returned (99 searches, 94 questions):

| top_k | dense | hybrid | BM25 alone |
|---|---|---|---|
| 3 | **73** | 67 | 54 |
| 5 (the app's) | **78** | 76 | 63 |
| 10 | 85 | **86** | 72 |

**The answer key's filters**, recall@1 / recall@5 / MRR@10:

| Filter | dense | hybrid | BM25 alone |
|---|---|---|---|
| whole index | 0.45 / 0.74 / 0.576 | 0.43 / 0.74 / 0.547 | 0.33 / 0.56 / 0.422 |
| drug | 0.50 / **0.85** / 0.643 | 0.50 / 0.79 / 0.609 | 0.44 / 0.66 / 0.527 |
| drug + section group | 0.80 / **0.97** / 0.877 | 0.55 / 0.87 / 0.682 | 0.44 / 0.66 / 0.527 |

**Exact terms**, top 5 chunks that contain the term, filtered to the drug:

| Term (drug) | dense | hybrid | BM25 alone |
|---|---|---|---|
| CYP3A4 (simvastatin), CYP2C19 (clopidogrel), QT (ondansetron, escitalopram), eGFR (metformin), CD117 (imatinib), NSAID (methotrexate), INR (warfarin) | 26/40 | 29/40 | **31/40** |

**Variants:** putting the filter's section groups first in the keyword ranking brought the answer key's drug + section group search to 0.98 at recall@5 (dense 0.97), but on the agent's searches it returned 72 at top 5 against 75 without. Weights of 0.5 and 0.3 and 10 chunks per search changed nothing beyond a question or two. **Time:** a hybrid search takes 42 ms against 12 ms (median of the 99, embedding the question not counted).

## What it shows

- **RRF throws away how sure the embeddings are.** In 7 of the 10 questions hybrid loses, dense ranked the answer first or second and BM25 17th or lower, so its fused score fell behind chunks both searches ranked middling. The rank alone doesn't say that dense was sure.
- **BM25 rescues a wrong section group.** All 8 questions hybrid gains have their answer outside the section the agent asked for ("share my Ozempic pen" filtered to warnings, the answer in the instructions for use); dense, held back by the boost, ranked it 6th to 13th, and BM25 1st to 4th in 7 of them. The two searches miss different questions: either one finds 86 of 94 at top 5.
- **Paraphrased questions don't need keywords.** The retrieval questions were written in other words than their passages (`questions.py check` refuses copies), and BM25 alone finds 0.66 at recall@5 where bge-m3 finds 0.85. Only one of the 94 names an exact term.
- **Exact terms are where BM25 helps**, a little: 3 more term-holding chunks of 40 than dense.

## Decided along the way

- **Dense stays the default** (`RETRIEVAL_MODE=dense`); hybrid and BM25 alone are settings. The section-group boost (0.15) is unchanged, because the dense ranking didn't change (#112's note asks to re-measure it only then).
- **Hyphens split words, and a hyphenated question term is a phrase.** The labels write 5-HT3 as "5-HT3", "5-HT 3" and with the non-breaking hyphen (439 of them in the chunks); keeping "-" inside tokens would miss the last. "5-HT3" in a question matches "5-HT3" and "5‑HT3", not every "5".
- **The keyword index is part of the store.** `ingest index` builds both indexes from the same chunks, and the snapshot packs `index/`. Store releases before this one lack it, so `ingest fetch` builds it from the vector index when it is missing; without it, the app warns and searches dense.
- **No answer-level eval.** Retrieval that returns the answer less often can't make answers better, so the citation eval with gpt-oss-20b and the paid RAGAs judge were not run.

## Limits

- The answer key was pooled from the top 5 of the dense models compared in [embeddings](embeddings.md), so a passage only BM25 ranks high that answers in other words isn't counted. This favours dense.
- 94 questions tell apart differences of about 5 questions, not 2.
- The probe counts chunks containing the term, not chunks that answer; its 8 questions are new and unreviewed.
- Score fusion (weighting each search by its scores rather than ranks), or BM25 only for questions with code-like terms, may keep dense's sure hits and BM25's rescues. Neither was tried here; #44 asked for RRF.

## Reproduce

```
cd backend
OFFLINE=1 uv run python -m molecula.ingest fetch      # builds data/build/index/bm25.db if missing
for mode in dense hybrid bm25; do
  OFFLINE=1 RETRIEVAL_MODE=$mode uv run python -m evals.rag.top_k \
    ../data/build/eval/citations/openai_gpt-oss-20b-answer-medium-clean-context-c9a1a2ddf098.jsonl --top-k 3 5 10
  OFFLINE=1 RETRIEVAL_MODE=$mode uv run python -m evals.retrieval.filters
done
OFFLINE=1 uv run python -m evals.retrieval.exact_terms
```
