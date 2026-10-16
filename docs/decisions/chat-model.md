# Chat model: which model answers, locally and in the cloud

> **Answer:** locally, `openai/gpt-oss-20b` in LM Studio. Every eval in this repo was run on it, and it fits next to the embedding model on a 24 GB GPU. In the cloud, `openai/gpt-6-luna` on OpenRouter, now the default `LLM_MODEL`. On the 28 questions of the from-memory eval it passed 27, adding a fact from memory in 1 answer against 4 for gpt-oss-20b. It was safe on all 49 messages of the safety eval, and it is the cheapest of the measured cloud models that stick to their sources ($0.10 in, $0.50 out per million tokens). claude-haiku-5.5, at the same price, added nothing from memory but told the reader three times that Molecula has no data on drugs it never looked up. Online, Jev sorts the messages for either chat model ([decision model as the input check](../evals/input-check-decision-2026-10-16.md)).

## Question

Which model should write the answers, call the tools and check the answers against their sources, in the local setup and in the cloud setup (#98)? The weakness that matters most is adding facts that no tool returned, which gpt-oss-20b does in about one answer in seven, also with a citation ([from memory](../evals/from-memory-2026-10-14.md)). The source check marks those afterwards but can't stop them ([answer check](answer-check.md)). A cloud model doesn't have to be the strongest, only better than the local one where the local one is weak, and cheap.

## What we tried

- **Local:** gpt-oss-20b throughout. Qwen3.8-27B didn't fit next to a decision model on the RX 7900 XTX ([filter eval](../evals/chat-model-filters-2026-10-12.md)), and the decision model is no longer local, but every prompt was tuned and measured on gpt-oss-20b.
- **Cloud, on the no-label questions (#193):** gpt-5-mini and deepseek-v4-flash, with main's prompt and tools unchanged ([no-label eval](../evals/no-label-2026-10-14.md)).
- **Cloud, on the from-memory questions (this issue):** gpt-6-luna and claude-haiku-5.5, picked by the owner from the models his OpenRouter key allows. Both are newer than gpt-5-mini and cost less. Each answered the 28 questions once at its default reasoning effort; the answers were judged by hand against the same rules as gpt-oss-20b's, every flag and every question gpt-oss-20b had got wrong re-read with the full passages.
- **The safety eval on the winner:** gpt-6-luna answering, Jev sorting the messages, as the cloud setup runs.

## Result

From-memory questions, 28 per model, main's prompt and tools:

| Model | Pass | From memory | Denies data | Right passage returned | Seconds p50 | Output tokens mean |
|---|---|---|---|---|---|---|
| gpt-oss-20b, LM Studio (#208's run) | 24 | 4 | 0 | 22 | 7.2 | - |
| **gpt-6-luna** | **27** | 1 | 0 | 26 | 5.8 | 217 |
| claude-haiku-5.5 | 25 | 0 | 3 | 27 | 4.7 | 741 |

No-label questions (#193), 24 metamizole askings and 9 controls:

| Model | Metamizole: pass | From memory | Controls pass | Cost per run | Seconds p50 |
|---|---|---|---|---|---|
| gpt-oss-20b, low | 27 of 48 | 6 | 9 of 18 | local | 7 |
| deepseek-v4-flash | 11 of 24 | 13 | 7 of 9 | $0.04 | 21 |
| gpt-5-mini | 21 of 24 | 3 | 9 of 9 | $0.26 | 27 |

Safety eval, 49 messages, Jev sorting ([safety eval](../evals/safety.md)):

| Answering model | Safe | Other phone numbers | Label's hospital treatment passed on (#149) |
|---|---|---|---|
| gpt-oss-20b | 49 of 49 | 0 | 2 answers |
| gpt-6-luna | 49 of 49 | 0 | 0 |

OpenRouter prices per million tokens on 2026-10-16, in / out: gpt-6-luna $0.10 / $0.50, claude-haiku-5.5 $0.10 / $0.50, gpt-5-mini $0.25 / $2.00, deepseek-v4-flash $0.09 / $0.18, gpt-oss-20b $0.02 / $0.09.

## What it shows

- **gpt-6-luna is better than gpt-oss-20b where gpt-oss-20b is weak, and costs little.** It kept to the passages on the questions gpt-oss-20b keeps getting wrong: no MAOI names the label doesn't give, the celecoxib ulcer rates read right, omeprazole's age bands right. Its one addition is the spironolactone overdose answer, which lists low sodium as an overdose sign where the label says it is unlikely in overdose; gpt-oss-20b made the same misreading. Its answers are short (217 output tokens on average), and it was faster than gpt-oss-20b on the owner's GPU.
- **claude-haiku-5.5 adds nothing from memory but denies data instead.** Its answers are three times as long and give the label's rates exactly, but in three of them it tells the reader that Molecula has no data on other blood thinners, antidepressants or acid reducers, which are stored and were never searched. A reader can't tell that sentence is wrong, which is why it counts against it.
- **deepseek-v4-flash, the cheapest, fails the way that matters.** It called metamizole a painkiller from memory in 13 of 24 answers.
- **gpt-6-luna's safety answers are calmer than gpt-oss-20b's.** Every overdose answer opens with the guard's emergency line and then stays short, without passing on the label's hospital treatment as if it were for the reader. Two things are wrong without being unsafe: it put an emergency line of its own in front of a plain maximum-dose question, and it told the reader twice that it can't show a 3D model, while the chat shows one under the answer (#228).

## Decided along the way

- **No filter-extraction or tool-calling set of its own.** #98 planned both for every candidate. The from-memory and safety evals run the whole agent, tools included, and gpt-6-luna called a tool and cited it in every answer of the safety eval that reached the agent; the owner decided the screen was enough (2026-10-16).
- **The default reasoning effort.** Both cloud models ran with `LLM_REASONING_EFFORT` empty, as the app ships.
- **The source check runs on the same model.** In the cloud setup gpt-6-luna also checks the answers; that was not measured on the 181 labelled claims ([source check eval](../evals/source-check-2026-10-14.md)).

## Limits

- One run of 28 questions per cloud model. gpt-oss-20b's identical runs differed by two to four additions, so 1 against 4 is a direction, not a measured gap; the 95% intervals overlap.
- The answers were judged by subagents and checked by me where they flagged something and on the questions known to be hard, not every sentence of every answer.
- The source check on gpt-6-luna, its filter extraction on the 94 retrieval questions, and the phone-number check over 70 overdose askings (#168) were not run.
- Prices are OpenRouter's list prices on one day; the cost per answer was not measured.

## Reproduce

The cloud runs need `OPENROUTER_API_KEY` and `OFFLINE=0`, which picks the cloud chat model even with the local settings in `.env` (#230).

```
cd backend
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna uv run python -m evals.chat_model.from_memory --times 1
OFFLINE=0 LLM_MODEL=anthropic/claude-haiku-5.5 uv run python -m evals.chat_model.from_memory --times 1
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna uv run python -m evals.safety.run
```

Answers are cached in `data/build/eval/`, and the hand verdicts are in `backend/evals/chat_model/from_memory_verdicts/` and `backend/evals/safety/verdicts/`, named like the caches, so a re-run asks nothing.
