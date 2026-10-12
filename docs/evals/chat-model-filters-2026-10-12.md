# Filter extraction with a local chat model, 2026-10-12

The first measurement for the chat-model choice (#98, step 2). #13 measured the label filter with the answer key's own filters: recall@5 0.85 within the right drug, 0.98 within the right drug and section group. That is the ceiling. This run lets a real chat model extract the filter, the way the app does, and searches under what it extracted.

## Setup

- **Model:** `openai/gpt-oss-20b` (MXFP4 GGUF, lmstudio-community) in LM Studio 0.4.25 with the llama.cpp ROCm runtime, on an RX 7900 XTX (24 GB). 32,768 tokens of context, one parallel slot, LM Studio's default reasoning effort. Temperature 0.2 (`LLM_TEMPERATURE`).
- **Extraction:** `FilterExtractor.extract` with `prompts/rag/extract_filters.md`, through `get_chat_model` and LangChain's default structured output (`json_schema`).
- **Search:** bge-m3 on the CPU, top 10 from the built index, no score threshold.
- **Questions:** the 94 in `backend/evals/datasets/retrieval_questions.yaml`. Each records its drug (`cid`) and the section group its evidence was taken from.

## Result

| Valid filter | Drug named | Only that drug | Group among picks | Group first | Seconds p50 / p95 | Output tokens mean |
|---|---|---|---|---|---|---|
| 1.00 (94) | 0.94 (88) | 0.90 (85) | 0.79 (74) | 0.67 (63) | 3.2 / 3.6 | 68 |

| Search | recall@1 | recall@5 | MRR@10 |
|---|---|---|---|
| answer key: whole index | 0.45 | 0.74 | 0.576 |
| answer key: drug | 0.50 | 0.85 | 0.643 |
| answer key: drug + section group | 0.82 | 0.98 | 0.890 |
| extracted by gpt-oss-20b | 0.59 | **0.78** | 0.669 |

| Questions | n | recall@5 |
|---|---|---|
| drug and group right | 68 | 0.97 |
| drug right, group wrong | 20 | 0.35 |
| drug wrong | 6 | 0.00 |

## What it shows

- **With a real model the filter gains 4 points, not 24.** Where the model names the right drug and group, the search is at the ceiling (0.97). All of the loss comes from the other 26 questions.
- **The six "wrong drug" questions are name resolution, not the model.** The model returned the name as written ("Doryx MPC", "Tirosint-SOL", "Xhance", "Effexor XR", "Fleqsuvy baclofen", "Seacall dexamethasone ointment"). None of them is a scope name or alias, so `check` marks them unsupported and the search finds nothing. They are brands from the openFDA labels, and two of them contain the generic name.
- **A wrong section group hides the answer.** The group is a hard filter, so when the model picks "warnings" for an answer in the patient leaflet, the search never sees the leaflet (0.35). Ten of the 20 are `patient_information` (7), `clinical_studies` (2) or `product` (1) questions, which the model sent to `warnings`, `indications` or another clinical section. Some of these may be answered in other words in the group the model picked; the answer key only counts the passage the question was written from, so 0.35 is a lower bound.
- **Speed and memory fit the local setup.** 3.2 s per extraction, 68 output tokens on average including reasoning. LM Studio held the model at a steady 18.4 GB of dedicated VRAM during the run (2.3 GB of it is Windows and other programs), with nothing spilled to shared memory, which leaves about 5.6 GB for the decision model (#102).

## Changes since this baseline

Every change to the filter, the name resolution or the search is measured on the same 94 questions with the extractions cached here, and gets a row: what changed, where, and the numbers before → after. A change that needs new extractions (a new prompt or model) says so.

| Change | Where | Drug named | Group among picks | recall@5 |
|---|---|---|---|---|
| Baseline: gpt-oss-20b extracts the filter as in #13 | this run | 0.94 | 0.79 | 0.78 |
| A label's brand counts as a name of its drug in `CompoundStore.find`, ignoring case and hyphens ("Doryx MPC", "Tirosint-SOL" for the label's "Tirosint SOL") | #14 | 0.98 | 0.79 | 0.82 |
| An unknown name that contains exactly one supported drug name is that drug (`FilterExtractor._drug_inside`: "Fleqsuvy baclofen", "Seacall dexamethasone ointment") | #14 | 1.00 | 0.79 | 0.84 |
| The section groups rank the search instead of filtering it: within the drug's labels, a chunk in an extracted group counts 0.15 higher (`RETRIEVAL_SECTION_GROUP_BOOST`) | #112 | 1.00 | 0.79 | **0.91** |

With the soft section groups, the 20 questions with a wrong group go from 0.35 to 0.70 and the 74 with the right group stay at 0.97. MRR@10 goes from 0.727 to 0.759. The answer key's ceiling (drug + section group) drops by one question, from 0.98 to 0.97 (MRR 0.890 → 0.877): the answer to imatinib-mechanism is the fifth pharmacology chunk, and closer chunks of other sections push it out of the top 10.

How the two searches (in the groups, and in every section of the drug's labels) are merged was decided on these questions. The boost rows are reproduced with `RETRIEVAL_SECTION_GROUP_BOOST`; the other merges were a one-off script on the same cache.

| Merge | Extracted recall@5 | Group wrong (20) | Ceiling recall@5 |
|---|---|---|---|
| Hard filter (before) | 0.84 | 0.35 | 0.98 |
| No groups (boost 0) | 0.85 | 0.85 | 0.85 |
| Boost +0.08 | 0.90 | 0.70 | 0.95 |
| Boost +0.12 | 0.91 | 0.70 | 0.96 |
| **Boost +0.15** | **0.91** | 0.70 | 0.97 |
| Boost +0.20 | 0.90 | 0.65 | 0.97 |
| Reciprocal rank fusion (k = 60) | 0.90 | 0.75 | 0.96 |
| Groups' top 2, then the rest | 0.90 | 0.85 | 0.95 |
| Reciprocal rank fusion, groups weighted 2:1 or 3:1 | 0.89 | 0.60 | 0.98 |

Above +0.08 the extracted score is flat (0.90–0.91); what the boost decides is the ceiling. +0.15 is the smallest boost that keeps the ceiling within one question of the hard filter, which #112 asked for. Weighted fusion keeps the ceiling but isn't a soft filter: with 10 results per list, every grouped chunk outranks every other chunk, so a wrong group still hides the answer whenever the group has 10 chunks of the drug.

Tried and not built:

- **Brand and alias names replaced by the generic name in the search text** ("How does Gleevec work" → "How does imatinib work"), with `CompoundService.find_mentions`. 47 of the 94 questions change. With the extracted filter recall@5 stays 0.84 (MRR 0.727 → 0.715); over the whole index it drops from 0.74 to 0.68, and within the answer key's drug from 0.85 to 0.81. bge-m3 matches the brand names in the label text better than the generic, so the question goes to the search as asked.

## Qwen3.8-27B does not fit next to a decision model

Measured before this run with `lmstudio-community/Qwen3.8-27B-GGUF` (Q4_K_M, 16.5 GiB of weights). LM Studio also loads the vision projector (`mmproj`, 0.9 GB) and, by default, four parallel slots and an MTP draft context for speculative decoding.

| Load | Dedicated VRAM | Spilled to shared memory |
|---|---|---|
| 32k context, 4 slots, MTP (LM Studio's defaults) | 22.8 GB (full) | 8.9 GB |
| 32k, 1 slot, MTP | 22.9 GB (full) | 6.8 GB |
| 16k, 1 slot, no MTP | 23.0 GB (full) | 2.2 GB |
| 8k (read off LM Studio by the owner) | 19.2 GB | none |

Anything spilled to shared memory runs from system RAM and is much slower. 8k fits the extraction (about 1.5k tokens) but leaves no room for a conversation or a second model, so Qwen3.8-27B was not run.

## Limits

- One model at temperature 0.2. A second run without the cache (2026-10-13, with the soft section groups) changed the extraction on a few questions but not the score: recall@5 0.91 both times, drug named 93 instead of 94, the right group 75 instead of 74. The tables above come from the first run, which is the cache they reproduce from.
- The questions are all English (German questions are part of #114 and #46).
- The boost is in bge-m3's cosine units and was chosen on these 94 questions. A new embedding model, hybrid search (#44) or a re-ranker (#96) needs it measured again.
- No brand per question in the answer key, so brand narrowing is not scored.

## Reproduce

Load the model in LM Studio, then in `backend/`:

```
lms load openai/gpt-oss-20b -c 32768 --parallel 1 --gpu max
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.filters
```

Extractions are cached in `data/build/eval/filters/` per model and prompt, so the scores above are reproduced from the cache without the model.
