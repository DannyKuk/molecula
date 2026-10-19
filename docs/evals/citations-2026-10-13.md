# Citations with local chat models, 2026-10-13

Does the agent cite the label passages it uses in a form the chat can link (#129)? Before #129 the system prompt asked for a Markdown link to DailyMed after each sentence. In the #125 manual run gpt-oss-20b did that in only 1 of 4 answers. Since #129 every passage has a reference number, the prompt asks for `[n]`, and the `sources` event carries the same numbers.

## Setup

- **Agent:** `ChatAgent.stream` wired as in `main.py`, `OFFLINE=1`, the built store and bge-m3 index, one single-turn conversation per question (`python -m evals.chat_model.citations`). The "before" runs are the same runner on `main` at 9032876, with its `src` first on `PYTHONPATH`.
- **Models:** in LM Studio with the llama.cpp ROCm runtime on an RX 7900 XTX (24 GB), 32,768 tokens of context, one parallel slot, temperature 0.2. `openai/gpt-oss-20b` (MXFP4) and `qwen/qwen3.8-27b` (Q4_K_M).
- **Questions:** the 94 in `backend/evals/datasets/retrieval_questions.yaml`. Each names one drug and records the label passage that answers it.
- **Scoring**, counted from the chat events: a citation is valid when it points at a passage `search_labels` returned for that answer. That means `[n]` or `【n】` with the passage's `ref`, or (before #129) a Markdown link to the passage's DailyMed page. "Cites the evidence" means a cited passage holds the answer-key passage. It is counted only for answers whose search returned that passage. A link names a whole label, so for links this is checked per label.

## Result

Shares are of the answers that used label passages. gpt-oss-20b answered all 94 questions with passages, and none failed. qwen3.8-27b was stopped after 39 questions (see below); the two answers cut off when it was stopped are left out.

| Model | Prompt | Cite a passage: `[n]` or link | also `【n】` | Every citation valid | Use `【n】` | Other markers | Cite the evidence (when returned) | Seconds p50 / p95 |
|---|---|---|---|---|---|---|---|---|
| gpt-oss-20b | link (before) | 0.38 (36) | 0.38 (36) | 0.38 (36) | 0.01 (1) | 0.53 (50) | 0.42 (31 of 74) | 6.2 / 10.9 |
| gpt-oss-20b | `[n]` (#129) | 0.74 (70) | **0.96 (90)** | 0.96 (90) | 0.21 (20) | 0.00 | **0.96 (75 of 78)** | 5.7 / 7.2 |
| qwen3.8-27b, first 39 | `[n]` (#129) | 0.95 (37) | 0.95 (37) | 0.95 (37) | 0.00 | 0.00 | 0.95 (35 of 37) | 62.6 / 117.7 |

## What it shows

- **Numbered references fix citing for gpt-oss-20b.** Asked for links, it wrote one that resolves in 38% of answers. In 53% it used its own `【4†source】` marker instead, which points at nothing in Molecula. Asked for `[n]`, every answer that used the labels cites a passage. The 4 without a citation say that the labels don't answer the question. Not one citation pointed at a number no passage has.
- **gpt-oss writes `【n】` in about one answer in five, even when asked for `[n]`.** Those are its own full-width brackets around the right reference number. For example, "…lowers the chance of needing surgery such as TURP or prostatectomy【1】", where passage 1 is the Proscar label's indications. So `cited_refs` accepts both bracket styles, and the chat UI must too (#20). That takes gpt-oss from 0.74 to 0.96. **This is a gpt-oss special case.** qwen3.8-27b wrote `[n]` in every answer that cited, here and in the five conversations of the #129 PR, and never `【n】`. So another model needs no special handling: accepting `【n】` costs one character class in `CITATION` and changes nothing for a model that writes `[n]`.
- **The citations point at the right text.** Where the search returned the passage that answers the question, gpt-oss cites it in 75 of 78 answers. With links that was 31 of 74, and only per label.
- **qwen3.8-27b cites well but is slow, and was stopped early.** Its 39 answers cite a passage 37 times, about 4 citations per answer, with no invalid number. The other 2 ran into the 60 s limit per model call (`LLM_TIMEOUT_SECONDS`): qwen thinks for over a minute before some answers (p50 62.6 s per question). At that pace the full set takes over an hour and a half per prompt. Once it was clear that qwen writes `[n]`, the run was stopped, and qwen was not run on the link prompt. The time limit belongs to the chat-model choice (#98).
- **The five-conversation check in the #129 PR was too small to show the problem.** It found 4 of 4 for gpt-oss; over 94 questions the strict `[n]` count is 0.74.

## Changes since this baseline

Each change to the citation prompt, the tool description or the citation parsing gets a row, measured on the same 94 questions. Parsing changes re-score the cached answers; prompt changes ask again.

| Change | Where | gpt-oss-20b: cite a passage |
|---|---|---|
| Baseline: the prompt asks for a Markdown DailyMed link | `main` before #129 | 0.38 |
| Passages carry `ref`, the prompt and the tool description ask for `[n]` | #129 | 0.74 |
| `cited_refs` and the chat also read `【n】` (cached answers re-scored) | #129 | **0.96** |
| main's prompt on main a4823ae (the guard's prompts, the emergency numbers and every tool's `ref` since #129) | main a4823ae | 0.96 |
| The owner's citation-first prompt: a sentence about a drug needs a `ref` from any tool or is deleted | #208 | 0.96 |
| main's agent on main 5de6556 (answers at medium reasoning effort since #254) | main 5de6556 | 0.99 |
| Every result the model can cite starts with its `ref` | #166 | 0.99 |

- **#208 changes nothing measurable here.** Main → #208: every citation valid 0.96 → 0.96, no invalid number in either run, the passage that answers the question cited in 72 of 76 → 75 of 77 answers where it was returned, 1.9 → 1.5 citations per answer, 8.9 → 8.5 s at the median. Strict `[n]` fell from 0.83 to 0.74 because more answers used `【n】` (13 → 20), which `cited_refs` and the chat read. Both runs leave 4 answers uncited, each one saying the labels don't answer. The main run used a worktree at a4823ae with its `src` first on `PYTHONPATH`.

- **#166 changes nothing measurable here either.** Main → `ref` first: every citation valid 0.99 → 0.99, the passage that answers cited in 75 of 79 → 76 of 79 answers where it was returned, `【n】` in 14 → 21 answers. What it fixes is in answers this eval doesn't ask: several drugs, follow-ups and long lists ([cited passages](cited-passages-2026-10-19.md)). Run with `--variant ref-first`, since the change is in code the cache key doesn't see.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.citations
```

Answers are cached in `data/build/eval/citations/`, keyed by model, system prompt and tool descriptions, and a run re-scores them with the current scorer without asking again. For the "before" rows, check out `main` at 9032876 in a worktree, set `DATA_DIR` to this checkout's `data/`, and put the worktree's `backend/src` first on `PYTHONPATH`.
