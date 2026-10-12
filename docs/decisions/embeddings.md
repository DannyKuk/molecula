# Embeddings: which model finds the right label passage

> **Answer:** `BAAI/bge-m3`, run locally on the CPU. It finds the passage that answers a question in the top 5 for 85% of 94 test questions (today's bge-small: 80%), in 37 ms per question on a CPU, and it is multilingual, so German questions (#46) won't need another model. The CPU-sized models bge-large, Qwen3-Embedding-0.6B and modernbert-embed score the same within what 94 questions can tell apart. The large models (Qwen3-Embedding-8B, text-embedding-3-large, gemini-embedding-2) find 97–98%, a real step up, but need a GPU or the cloud. A cloud setup with text-embedding-3-large is the candidate for later, decided together with the chat model and after a re-ranker and hybrid search (#44) have been measured on bge-m3. The price of bge-m3 is its size: 2.3 GB of weights to download and hold in RAM, against 133 MB for bge-small.

## Question

Which embedding model should index the label chunks and embed the user's question? The index ships prebuilt in the snapshot (#35) and the app embeds each question on the CPU in Docker, so the default has to run on a CPU. How much retrieval quality does that cost compared with large local models and cloud models, and how much does the model weigh?

## What we tried

- **94 retrieval questions** in `backend/evals/datasets/retrieval_questions.yaml`, over 61 drugs and all 14 section groups, Rx and OTC labels: 23 on topics chosen by hand, 71 written for label chunks that `python -m evals.retrieval.questions sample` picked at random (seed 88), filling every section group to 7 (the OTC-only group has 3). Each question names its drug and carries `evidence`, an exact passage of that drug's label. `python -m evals.retrieval.questions check` makes sure every passage is in a chunk of its drug, that the question names the drug or a brand, and that it doesn't repeat five words in a row from the chunk it was written from.
- **A hit** is a retrieved chunk of the question's drug that contains one of the question's passages, whatever section it comes from: labels repeat facts, and #92 moved text between sections (comment on #88).
- **The runner**, `python -m evals.retrieval.compare_embeddings`, embeds all 7,012 chunks the app's index holds (same chunker, same store) and each question on its own, and reports recall@1, recall@5 and MRR@10 searched within the question's drug (as the retriever in #13 will filter) and over the whole index, plus embedding time, peak GPU memory, index size and the time to embed one question. It saves every question's top 10 chunks per model, so a run can be scored again (`python -m evals.retrieval.rescore`) and shown on a results page without embedding anything.
- **Local candidates**, with sentence-transformers: bge-small-en-v1.5 (the default until now) and bge-large-en-v1.5, each with and without the BGE query instruction; MedEmbed-small-v0.1 (bge-small tuned on medical text); nomic's modernbert-embed-base; bge-m3; Qwen3-Embedding 0.6B, 4B and 8B. Chunks were embedded on an AMD RX 7900 XTX (24 GB, ROCm 10, fp16, batch size 8, each model in its own process); questions on the GPU and, for the CPU-sized models, again on an Intel Core Ultra 7 265K.
- **Cloud candidates** through OpenRouter, with the app's own `get_embeddings`: openai/text-embedding-3-small, openai/text-embedding-3-large, google/gemini-embedding-2, qwen/qwen3-embedding-8b. All four cost about $1 in total for the 2.8M tokens of chunks.
- **The answer key completed by pooling.** The first scores counted a chunk only if it held the one passage the question was written from. To find answers in other words, every chunk a model ranked in its top 5 above its first hit (532 chunks for 79 questions, pooled over all 14 models) was judged against a strict rule: a chunk counts only if a patient reading just that chunk gets the same specific fact; related or partial facts don't. Four helper agents judged a quarter each and quoted the passage for every "yes"; a script checked that every quote is in its chunk; all 49 "yes" verdicts and a sample of 20 "partial" and 12 "no" were reviewed by hand (one "yes" overruled: a bare table row that doesn't say which reactions are the most common). The 43 distinct passages went into the dataset as `pooled_evidence` of 25 questions.

## Result

**Retrieval with the completed answer key** (searched within the question's drug unless noted; query time is the median for one question, CPU for the CPU-sized models, otherwise as noted):

| Model | Dims | R@1 | R@5 | MRR@10 | R@5 whole index | Query (ms) | Index (MB) | Weights |
|---|---|---|---|---|---|---|---|---|
| bge-small | 384 | 0.56 | 0.80 | 0.666 | 0.74 | 8 | 106.8 | 133 MB |
| bge-small + instruction | 384 | 0.59 | 0.78 | 0.672 | 0.73 | 8 | 106.9 | 133 MB |
| MedEmbed-small | 384 | 0.51 | 0.79 | 0.640 | 0.73 | 8 | 106.9 | 133 MB |
| modernbert-embed | 768 | 0.53 | 0.83 | 0.658 | 0.74 | 18 | 120.3 | 596 MB |
| Qwen3-Embedding-0.6B | 1024 | 0.59 | 0.83 | 0.686 | 0.73 | 67 | 135.2 | 1.19 GB |
| **bge-m3** | 1024 | 0.50 | **0.85** | 0.644 | 0.76 | **37** | 135.1 | **2.27 GB** |
| bge-large | 1024 | 0.59 | 0.87 | 0.694 | 0.78 | 36 | 135.1 | 1.34 GB |
| bge-large + instruction | 1024 | 0.57 | 0.88 | 0.691 | 0.80 | 39 | 135.1 | 1.34 GB |
| Qwen3-Embedding-4B | 2560 | 0.70 | 0.94 | 0.797 | 0.88 | 29 (GPU) | 210.4 | 8.0 GB |
| Qwen3-Embedding-8B | 4096 | 0.70 | 0.97 | 0.818 | 0.91 | 39 (GPU) | 288.5 | 15.1 GB |
| text-embedding-3-small | 1536 | 0.60 | 0.86 | 0.720 | 0.83 | 441 (cloud) | 159.4 | – |
| text-embedding-3-large | 3072 | 0.68 | 0.97 | 0.796 | 0.93 | 577 (cloud) | 237.4 | – |
| gemini-embedding-2 | 3072 | 0.71 | 0.98 | 0.829 | 0.98 | 314 (cloud) | 237.4 | – |
| qwen3-embedding-8b (cloud) | 4096 | 0.69 | 0.97 | 0.813 | 0.93 | 489 (cloud) | 288.5 | – |

Cloud query times include the round trip to OpenRouter (cloud Qwen3-8B had a p95 of 5.7 s). Weights are the published file sizes; a model needs about as much RAM on a CPU.

**Recall@5 with the first and the completed answer key:**

| Model | First key | Completed key |
|---|---|---|
| bge-small | 0.72 | 0.80 |
| bge-m3 | 0.79 | 0.85 |
| bge-large + instruction | 0.82 | 0.88 |
| Qwen3-Embedding-8B | 0.89 | 0.97 |
| text-embedding-3-large | 0.91 | 0.97 |
| gemini-embedding-2 | 0.93 | 0.98 |

**Pairwise on the same questions** (questions in the top 5 for one model and not the other; p from an exact McNemar test):

| A | B | Only A | Only B | p |
|---|---|---|---|---|
| bge-large + instruction | bge-small | 10 | 2 | 0.039 |
| bge-m3 | bge-small | 10 | 5 | 0.30 |
| bge-large | bge-m3 | 7 | 5 | 0.77 |
| bge-m3 | Qwen3-Embedding-0.6B | 6 | 4 | 0.75 |
| bge-large + instruction | bge-large | 2 | 1 | 1.0 |
| MedEmbed-small | bge-small | 1 | 2 | 1.0 |
| Qwen3-Embedding-8B | bge-large | 10 | 1 | 0.012 |
| gemini-embedding-2 | bge-large | 11 | 1 | 0.006 |
| gemini-embedding-2 | Qwen3-Embedding-8B | 1 | 0 | 1.0 |

**Recall@5 by section group** (7 questions each, OTC consumer 3, so one question is 0.14; a direction, not a measurement):

| Section group | bge-small | bge-m3 | bge-large + instr. | Qwen3-0.6B | Qwen3-8B | 3-large | Gemini |
|---|---|---|---|---|---|---|---|
| abuse_dependence | 0.86 | 0.71 | 0.71 | 0.86 | 1.00 | 1.00 | 1.00 |
| adverse_reactions | 0.71 | 0.86 | 0.86 | 0.86 | 1.00 | 0.86 | 1.00 |
| clinical_studies | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| contraindications | 0.86 | 0.86 | 0.86 | 0.86 | 1.00 | 1.00 | 1.00 |
| dosing | 0.71 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| indications | 0.86 | 0.86 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 |
| interactions | 1.00 | 0.86 | 1.00 | 0.57 | 1.00 | 1.00 | 1.00 |
| otc_consumer | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| overdosage | 0.57 | 1.00 | 0.86 | 0.86 | 0.86 | 1.00 | 1.00 |
| patient_information | 0.86 | 0.86 | 0.71 | 1.00 | 1.00 | 1.00 | 1.00 |
| pharmacology | 0.43 | 0.57 | 0.57 | 0.57 | 1.00 | 0.86 | 1.00 |
| product | 0.86 | 0.86 | 0.86 | 0.57 | 0.86 | 0.86 | 0.86 |
| specific_populations | 0.71 | 0.71 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 |
| warnings | 1.00 | 1.00 | 1.00 | 0.86 | 0.86 | 1.00 | 0.86 |

**Embedding the 7,012 chunks** on the RX 7900 XTX at batch size 8, each model in a fresh process:

| Model | Time | Peak VRAM |
|---|---|---|
| bge-small, MedEmbed-small | 10 s | 0.2 GB |
| modernbert-embed | 23 s | 0.7 GB |
| bge-large | 35 s | 0.9 GB |
| bge-m3 | 37 s | 1.7 GB |
| Qwen3-Embedding-0.6B | 80 s | 2.7 GB |
| Qwen3-Embedding-4B | 359 s | 11.4 GB |
| Qwen3-Embedding-8B | 624 s | 18.8 GB |

The app's index, rebuilt with bge-m3 by `python -m molecula.ingest index` (GPU, 2026-10-12): 7,012 chunks from 156 labels in 92 s including the download, 135.1 MB.

## What it shows

- **There are three tiers, and only the steps between them are real.** bge-small at 0.80; the CPU-sized models bge-m3, bge-large, Qwen3-0.6B and modernbert at 0.83–0.88; the GPU and cloud models at 0.97–0.98. Within a tier the pairwise counts are close to even (bge-large against bge-m3: 7 to 5), so 94 questions can't rank them. Between tiers they are lopsided (Qwen3-8B against bge-large: 10 to 1).
- **Speed and index size don't decide among CPU-sized models.** Every one embeds a question in under 70 ms on a CPU, small next to the seconds a chat model takes, and every index is 107–135 MB. What differs is the weight file: 133 MB to 2.3 GB.
- **bge-m3 wins on what's left: languages.** It ties bge-large on English and is multilingual; bge-large, bge-small and modernbert are English-only, and Qwen3-0.6B is multilingual but a little weaker here and twice as slow.
- **Medical tuning didn't help.** MedEmbed-small, bge-small trained further on medical text, scored the same as bge-small (1 to 2 pairwise) and worse at rank 1.
- **The query instruction didn't matter.** bge-large with and without it: 2 to 1; bge-small: 0.78 against 0.80.
- **Small models need the drug filter more.** Over the whole index, bge-small drops from 0.80 to 0.74 and bge-m3 from 0.85 to 0.76; Gemini doesn't drop at all. The filter in #13 matters most for the small models.
- **A strict answer key undercounts, unevenly.** Completing the key raised every model by 5 to 8 points, the large models the most: they more often found the same fact in the patient leaflet's words. Comparing models on a single-passage key would have made the gap between tiers look smaller than it is.
- **Local and cloud Qwen3-8B agree** (0.97 both, 2 to 2 pairwise against text-embedding-3-large), so the local fp16 run on the GPU measures the model, not the setup. Recall was also the same whether questions were embedded on the GPU in fp16 or on the CPU in fp32 (one question moved, at rank 1, for Qwen3-0.6B).

## Decided along the way

- **bge-m3 is the default local model** (Danny, 2026-10-12): multilingual for #46, tied with the best CPU-sized model, and the 2.3 GB are acceptable for an app that should work offline. `LOCAL_EMBEDDING_MODEL` still selects another one; the index has to be rebuilt after a change.
- **A cloud setup is a later decision** (Danny, 2026-10-12). Once the chat model runs in the cloud, offline use and privacy no longer argue against cloud embeddings, so a cloud setup would pair the cloud chat model with text-embedding-3-large (0.97 here; gemini-embedding-2's 0.98 is a tie). It is decided with the chat model, after a re-ranker and hybrid search (#44) have been measured on bge-m3 with these 94 questions, since they may close part of the gap locally. It needs one index per embedding model; today there is one.
- **No second copy of the weights.** bge-m3 publishes only `pytorch_model.bin`. transformers 5 loads it and also downloads a `model.safetensors` converted in a pull request on the model's page, "for next time": the first build left 4.4 GB in `data/build/models`. `load_local_model` sets transformers' `DISABLE_SAFETENSORS_CONVERSION`; an online load afterwards kept the folder at 2.3 GB, and bge-m3 loads offline from the `.bin` alone.
- **One local model per process, batch size 8, peak GPU memory recorded.** On Windows a model that no longer fits in VRAM doesn't fail: the driver moves the rest into shared system memory and the model keeps running many times slower, with no error. Measured with Qwen3-Embedding-8B (15.1 GB of weights) on the 24 GB card:

  | Run | Time per batch | What happened |
  |---|---|---|
  | After five other models in the same process, batch 16 | ~27 s (3 h estimated) | the earlier models' GPU memory was never released; the process held 17.4 GB of system RAM |
  | Alone in a fresh process, batch 16 | ~1.9 s | fits |
  | Same run, later batches | ~4.3 s | ~1 GB in shared GPU memory as PyTorch's memory pool grew |
  | Alone, batch 8 | ~0.7 s for half as many chunks (624 s in all) | peak 18.8 GB, no spill |

  Only the speed changes, never the vectors; the embedding times are what a spill ruins, so the runner frees GPU memory after each model, each local model builds its vectors in its own process, all use batch size 8, and the cache keeps each build's peak GPU memory so a spill shows in the results.
- **nomic-embed-text-v1.5 replaced by nomic-ai/modernbert-embed-base.** nomic-embed-text-v1.5 needs `trust_remote_code`, and its code calls `get_extended_attention_mask`, which transformers 5.x no longer has; it fails to load with transformers 5.19.0. modernbert-embed-base is nomic's successor with the same `search_query:` / `search_document:` prefixes.
- **Each model gets the input its model card documents.** BGE with and without its query instruction; modernbert-embed with its prefixes; Qwen3-Embedding with the query instruction it ships for sentence-transformers, which the cloud run prepends too because OpenRouter doesn't add it. The OpenAI models take no instruction.
- **The questions were written in the session, not generated by a local model.** A first attempt with Gemma 4 31B in LM Studio hung on the first call (it doesn't fit in 24 GB); the generator and its prompt were removed.
- **A drug's products can disagree, so #13 should filter by product type too.** Diclofenac has Voltaren gel (OTC) and Zipsor capsules (Rx) under one drug: the gel's label says it isn't known whether it is safe under 18, Zipsor's says from 12. Filtering by drug alone can hand the chat model the wrong product's answer.

## Limits

- **94 questions.** Around a recall of 0.85 the 95% interval is about ±0.07; differences within a tier are not real. The pairwise counts say more than the table.
- **Only the top 5 were judged.** Recall@1 and recall@5 use a complete key; MRR@10 can still miss an answering chunk at ranks 6–10, so it is a lower bound.
- **One reviewer.** The pooled judgments were made by helper agents under one rule and checked by one person, not by independent annotators. The rule was strict: borderline chunks count as misses.
- **Hard questions remain.** "Does Nexium 24HR contain sugar?" (the label says sucrose) is missed by every model; its top chunks describe prescription Nexium.
- **Gemini's task type is not passed.** OpenRouter's OpenAI-style endpoint has no field for it, so gemini-embedding-2 runs below its best.
- **English questions only.** bge-m3's multilingual strength is the model card's claim, not measured here; German questions come with #46.
- **One machine.** Build times and GPU memory are for the RX 7900 XTX on Windows; CPU query times for the Core Ultra 7 265K.

## Reproduce

In `backend/` (local runs need the models once without `OFFLINE=1`; cloud runs need `OPENROUTER_API_KEY`):

```
uv run python -m evals.retrieval.questions check
uv run python -m evals.retrieval.compare_embeddings --only bge-m3          # one model per process
uv run python -m evals.retrieval.compare_embeddings                        # all, vectors from the cache
uv run python -m evals.retrieval.compare_embeddings --device cpu --only bge-small bge-m3 bge-large qwen3-0.6b
uv run python -m evals.retrieval.rescore ../data/build/eval/embeddings-<stamp>.json
uv run python -m molecula.ingest index                                     # the app's index
```

Runs are saved in `data/build/eval/` and chunk vectors cached in `data/build/eval/vectors/` (not in git). The GPU runs used a separate environment with AMD's ROCm 10 PyTorch build (#90).
