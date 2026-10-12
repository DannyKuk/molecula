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

- One model, one run, at temperature 0.2. A second run may differ on a few questions.
- The questions are all English (German questions are part of #14 and #46).
- No brand per question in the answer key, so brand narrowing is not scored.

## Reproduce

Load the model in LM Studio, then in `backend/`:

```
lms load openai/gpt-oss-20b -c 32768 --parallel 1 --gpu max
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.filters
```

Extractions are cached in `data/build/eval/filters/` per model and prompt, so the scores above are reproduced from the cache without the model.
