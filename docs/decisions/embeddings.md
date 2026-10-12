# Embeddings: which model finds the right label passage

> **Answer:** not decided yet. The clean run of the local models is still to come (#88).

## Question

Which embedding model should index the label chunks and embed the user's question? The index ships prebuilt in the snapshot (#35) and the app embeds each question on the CPU in Docker, so the default has to be small and fast on a CPU. How much retrieval quality does that cost compared with large local models and cloud models?

## What we tried

- **94 retrieval questions** in `backend/evals/datasets/retrieval_questions.yaml`, over 61 drugs and all 14 section groups: 23 on topics chosen by hand, 71 written for label chunks that `python -m evals.retrieval.questions sample` picked at random (seed 88), at most 7 per section group, with OTC labels mixed in. Each question names its drug and carries `evidence`, an exact passage of that drug's label. `python -m evals.retrieval.questions check` makes sure every evidence passage is in a chunk of its drug, that the question names the drug or a brand, and that it doesn't repeat five words in a row from its passage.
- **A hit** is a retrieved chunk of the question's drug that contains the evidence. It doesn't matter which section the chunk comes from: labels repeat facts, and #92 moved text between sections (comment on #88).
- **The runner**, `python -m evals.retrieval.compare_embeddings`, embeds all 7,012 chunks the app's index holds (same chunker, same store) and each question on its own, and reports recall@1, recall@5 and MRR@10 searched within the question's drug (as the retriever in #13 filters) and over the whole index, plus embedding time, peak GPU memory, index size and query time. It saves each question's top 10 chunks per model for a results page.
- **Local candidates**, run with sentence-transformers on an RX 7900 XTX (ROCm 10, fp16): bge-small-en-v1.5 (the current default) and bge-large-en-v1.5, each with and without the BGE query instruction; MedEmbed-small-v0.1 (bge-small tuned on medical text); nomic's modernbert-embed-base; bge-m3; Qwen3-Embedding 0.6B, 4B and 8B.
- **Cloud candidates** through OpenRouter, with the app's own `get_embeddings`: openai/text-embedding-3-small, openai/text-embedding-3-large, google/gemini-embedding-2, qwen/qwen3-embedding-8b.

## Result

The cloud run (2026-10-12):

| Model | Dims | R@1 in drug | R@5 in drug | MRR@10 in drug | R@5 whole index | Index (MB) | Query p50 (ms) |
|---|---|---|---|---|---|---|---|
| text-embedding-3-small | 1536 | 0.51 | 0.81 | 0.647 | 0.78 | 159.3 | 407 |
| text-embedding-3-large | 3072 | 0.56 | 0.91 | 0.704 | 0.87 | 237.4 | 558 |
| gemini-embedding-2 | 3072 | 0.62 | 0.93 | 0.745 | 0.93 | 237.3 | 298 |
| qwen3-embedding-8b | 4096 | 0.52 | 0.90 | 0.688 | 0.86 | 288.5 | 843 |

Query times include the round trip to OpenRouter. The local models follow after the clean run.

## What it shows

To be written with the local results.

## Decided along the way

- **One local model per process, batch size 8, peak GPU memory recorded** (2026-10-12). On Windows a model that no longer fits in VRAM doesn't fail: the driver moves the rest into shared system memory over PCIe and the model keeps running, many times slower, with no error. Measured with Qwen3-Embedding-8B (about 16 GB of weights in fp16) on the 24 GB RX 7900 XTX:

  | Run | Time per batch | What happened |
  |---|---|---|
  | After five other models in the same process, batch 16 | ~27 s (3 h estimated) | the earlier models' GPU memory was never released; the process held 17.4 GB of system RAM |
  | Alone in a fresh process, batch 16 | ~1.9 s | fits |
  | Same run, later batches | ~4.3 s | ~1 GB in shared GPU memory (Task Manager) as PyTorch's memory pool grew |

  Only the speed changes, never the vectors, so recall isn't affected; the embedding times are, and so are any times measured after an earlier model in the same process (Qwen3-4B's 408 s was thrown away). The runner now frees GPU memory after each model, each local model builds its vectors in its own process, every local model uses batch size 8 so their times compare, and the cache stores the peak GPU memory of each build, so a spill shows in the results instead of only in Task Manager.
- **nomic-embed-text-v1.5 replaced by nomic-ai/modernbert-embed-base.** nomic-embed-text-v1.5 needs `trust_remote_code`, and its code calls `get_extended_attention_mask`, which transformers 5.x no longer has; it fails to load with transformers 5.19.0. modernbert-embed-base is nomic's successor with the same `search_query:` / `search_document:` prefixes and runs on transformers' own ModernBERT code.
- **Each model gets the input its model card documents.** BGE is run with and without its query instruction; modernbert-embed with its prefixes; Qwen3-Embedding with the query instruction it ships for sentence-transformers, which the cloud run prepends too, because OpenRouter's endpoint doesn't add it. The OpenAI models take no instruction.
- **The questions were written in this session, not generated by a local model.** A first attempt with Gemma 4 31B in LM Studio hung on the first call (the model doesn't fit in 24 GB); the question generator and its prompt were removed.

## Limits

- **94 questions.** Around a recall of 0.9 the 95% interval is about ±0.06, around 0.55 about ±0.10: differences of a few points between models are not real. Every model answers the same questions, so pairwise counts (found by A and missed by B) say more.
- **A hit needs the exact evidence passage.** A chunk that answers in other words counts as a miss, so recall is a lower bound.
- **Gemini's task type is not passed.** Gemini embeds queries and documents differently when told which is which; OpenRouter's OpenAI-style endpoint has no field for it, so gemini-embedding-2 runs below its best.
- **English questions only.** German questions (#46) need their own check; bge-small is English-only.

## Reproduce

To be written with the final runs.
