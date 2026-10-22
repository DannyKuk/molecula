# Chat model: which model answers, locally and in the cloud

> **Answer:** locally, `openai/gpt-oss-20b` in LM Studio. Every eval in this repo was run on it, and it fits next to the embedding model on a 24 GB GPU. In the cloud, `openai/gpt-6-luna` on OpenRouter, now the default `LLM_MODEL`. On the 28 questions of the from-memory eval it passed 27, adding a fact from memory in 1 answer against 4 for gpt-oss-20b. It was safe on all 49 messages of the safety eval, and it is the cheapest of the measured cloud models that stick to their sources ($0.10 in, $0.50 out per million tokens). claude-haiku-5.5, at the same price, added nothing from memory but told the reader three times that Molecula has no data on drugs it never looked up. Online, Jev sorts the messages for either chat model ([decision model as the input check](../evals/input-check-decision-2026-10-16.md)). gpt-6-luna answers at medium reasoning effort, like gpt-oss-20b: against its own default effort, medium made no difference beyond the spread of one run, at the same cost (#256). On the same evals at medium, claude-haiku-5.5 and deepseek-v4.1-flash looked up both drugs in every plain comparison but flagged more answers: 11 and 4 of 24 comparison answers added a fact from memory or denied data, against none for gpt-6-luna, at 3.7 and 2.3 times its cost (#386). On today's prompts gpt-oss-20b passed 25 of the 28 from-memory questions. glm-4.7-flash, the only other downloaded model that fits the GPU, passed 24, but its answers took 2.7 times as long and 3 of its 24 comparisons ran past the app's time limits, so gpt-oss-20b stays the local model (#387).

## Question

Which model should write the answers, call the tools and check the answers against their sources, in the local setup and in the cloud setup (#98)? The weakness that matters most is adding facts that no tool returned, which gpt-oss-20b does in about one answer in seven, also with a citation ([from memory](../evals/from-memory-2026-10-14.md)). The source check marks those afterwards but can't stop them ([answer check](answer-check.md)). A cloud model doesn't have to be the strongest, only better than the local one where the local one is weak, and cheap.

## What we tried

- **Local:** gpt-oss-20b throughout. Qwen3.8-27B didn't fit next to a decision model on the RX 7900 XTX ([filter eval](../evals/chat-model-filters-2026-10-12.md)), and the decision model is no longer local, but every prompt was tuned and measured on gpt-oss-20b.
- **Cloud, on the no-label questions (#193):** gpt-5-mini and deepseek-v4-flash, with main's prompt and tools unchanged ([no-label eval](../evals/no-label-2026-10-14.md)).
- **Cloud, on the from-memory questions (this issue):** gpt-6-luna and claude-haiku-5.5, picked by the owner from the models his OpenRouter key allows. Both are newer than gpt-5-mini and cost less. Each answered the 28 questions once at its default reasoning effort; the answers were judged by hand against the same rules as gpt-oss-20b's, every flag and every question gpt-oss-20b had got wrong re-read with the full passages.
- **The safety eval on the winner:** gpt-6-luna answering, Jev sorting the messages, as the cloud setup runs.
- **gpt-6-luna at both answer efforts (#256):** since #254 every answering model reasons at medium (`ANSWER_REASONING_EFFORT`), which was measured only on gpt-oss-20b. gpt-6-luna answered the from-memory eval (28 questions) and the comparisons eval (8 questions × 3, [comparisons](../evals/comparisons-2026-10-17.md)) once at `default` (no effort sent, the model's own) and once at `medium`, on main at 774776c with today's prompts, so these runs are not comparable with the from-memory table above, which used the prompts of 2026-10-16. Every answer was judged by hand against the from-memory rules.
- **claude-haiku-5.5 and deepseek-v4.1-flash at medium (#386):** the same two evals, the same commit and the same judging, so the other cloud models a user can pick are measured next to gpt-6-luna. deepseek-v4.1-flash is the newer flash on OpenRouter; #193's deepseek-v4-flash was measured on the no-label eval only.
- **The local models at medium (#387):** the same two evals and the same judging on gpt-oss-20b, as the baseline on today's prompts, and on glm-4.7-flash (30B mixture of experts, 3B active). glm is the only other downloaded model that fits the 24 GB GPU at 32,768 tokens and one slot (`lms load --estimate-only`: 18.3 GB; qwen3.6-27b 21.8 GB, gemma-4-31b 28.1 GB). Each ran alone in LM Studio on the RX 7900 XTX with `OFFLINE=1`, on main at 2ce1626, whose prompts, tools and agent are those of 774776c. Offline the label filter runs on the chat model itself. glm was asked one question first: it called `search_labels` through LM Studio and took the reasoning-effort field without an error.

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

gpt-6-luna at both answer efforts (#256), from-memory questions, 28 each:

| Answer effort | Pass | From memory | Denies data | Right passage returned | Seconds p50 | Output tokens mean | Cost of the run |
|---|---|---|---|---|---|---|---|
| default | 27 | 1 | 0 | 25 | 3.9 | 222 | $0.016 |
| **medium** | 26 | 1 | 1 | 25 | 4.0 | 220 | $0.016 |

The same on the comparisons eval, 24 answers each; "evidence" counts the answers that searched the label or looked up the targets of both drugs:

| Answer effort | Evidence, comparisons | Evidence, 3D + compare | From memory | Denies data | Seconds p50, comparisons | Cost of the run |
|---|---|---|---|---|---|---|
| default | 11 of 12 | 0 of 6 | 1 | 1 | 13.4 | $0.019 |
| **medium** | 10 of 12 | 0 of 6 | 0 | 0 | 7.5 | $0.019 |

The cloud models (#386) and the local models (#387) at medium, with the same prompts and tools; the local seconds are on the RX 7900 XTX. From-memory questions, 28 each:

| Model | Pass | From memory | Denies data | Right passage returned | Seconds p50 | Output tokens mean | Cost of the run |
|---|---|---|---|---|---|---|---|
| **gpt-6-luna** | 26 | 1 | 1 | 25 | 4.0 | 220 | $0.016 |
| claude-haiku-5.5 | 26 | 0 | 2 | 27 | 5.9 | 777 | $0.060 |
| deepseek-v4.1-flash | 27 | 1 | 0 | 27 | 3.9 | 455 | $0.037 |
| **gpt-oss-20b**, LM Studio | 25 | 3 | 0 | 23 | 8.6 | 555 | local |
| glm-4.7-flash, LM Studio | 24 | 4 | 0 | 22 | 22.8 | 847 | local |

Comparisons, 24 answers each:

| Model | Evidence, comparisons | Evidence, 3D + compare | Answers without a flag | From memory | Denies data | Seconds p50, comparisons | Cost of the run |
|---|---|---|---|---|---|---|---|
| **gpt-6-luna** | 10 of 12 | 0 of 6 | 24 | 0 | 0 | 7.5 | $0.019 |
| claude-haiku-5.5 | 12 of 12 | 1 of 6 | 13 | 6 | 7 | 10.0 | $0.071 |
| deepseek-v4.1-flash | 12 of 12 | 0 of 6 | 20 | 4 | 0 | 5.7 | $0.043 |
| **gpt-oss-20b**, LM Studio | 10 of 12 | 0 of 6 | 18 | 4 | 2 | 15.6 | local |
| glm-4.7-flash, LM Studio | 8 of 12 | 0 of 6 | 15, and 3 failed | 6 | 2 | 71.1 | local |

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
- **Medium neither helps nor costs gpt-6-luna.** Both efforts make the same one addition on the 28 questions, the spironolactone overdose misreading, and medium's one denial ("Molecula's data don't answer those details" about Tylenol and other blood thinners, where the store holds the INR passage) is a difference of one answer. On the comparisons, the 3D answers at both efforts compare the two structures without a label search, and stay with what the structures hold, as gpt-oss-20b's did at medium. At the default one answer called metformin's lactic acidosis "rare", a word no result used, and a German answer said after `compare_drugs` alone that Molecula's data don't cover effects and side effects. Each run cost the same; the median comparison took 7.5 s at medium against 13.4 s at the default.
- **claude-haiku-5.5 looks up the most and still denies the most.** It searched both labels in every plain comparison and was the only model to look up both drugs in a 3D answer, but 7 of its 24 comparison answers say Molecula has no data it never looked for: twice that there is no 3D structure of aspirin without asking for it (the store has 3N8Y), and once that the passages cover no interactions while they listed four. Its additions are mostly what the target does ("a protein that helps make inflammation signals") and one wrong count, two hydrogen bonds to Tyr356 where the structure has one. On the 28 label questions it added nothing from memory, as on 2026-10-16, with two denials. Its answers are three and a half times as long as gpt-6-luna's and cost 3.7 times as much.
- **deepseek-v4.1-flash keeps to the labels but explains the targets from memory.** It is the fastest of the three (5.7 s per comparison at the median), looked up both drugs in every plain comparison and denied nothing. On the label questions its one addition is bupropion's seizure risk rising with "the amount that reaches the body quickly". Its four comparison additions are what the target does: all three typo answers call PTGS2 the enzyme behind pain or inflammation, which no result says, and one calls TRPV1 a channel for pain perception. It costs 2.3 times as much as gpt-6-luna.
- **gpt-6-luna stays the cloud default.** Its comparison answers at medium had no flag, its 3D answers said only what the structures hold, and it is the cheapest of the three. What it does worse is look up both drugs in every comparison (10 of 12).
- **gpt-oss-20b on today's prompts keeps to the labels about as before, and misreads more in comparisons than gpt-6-luna.** 3 of its 28 label answers add something, against 4 in #208's run. Two are the misreadings it made before: MAOI names (phenelzine, tranylcypromine) where the pseudoephedrine label says only "a prescription MAOI", and low sodium as a spironolactone overdose sign, which gpt-6-luna gets wrong too. The third is a lisinopril warning about earlier ACE-inhibitor swelling, from a passage the search didn't return. In the comparisons it looked up both drugs as often as gpt-6-luna (10 of 12), but 6 of its 24 answers have a flag. Two say there is no reviewed aspirin structure without asking for one. Four misread or add: naproxen's 1,500 mg as the daily maximum where the label allows it only for a limited period, metformin "without changing insulin levels", omeprazole "irreversibly" inhibiting the pump, and paracetamol acting through "central pathways". Its median comparison took 15.6 s, twice gpt-6-luna's.
- **glm-4.7-flash is no better than gpt-oss-20b and much slower.** On the labels it adds about as much (4 of 28). It says acetazolamide is contraindicated with a sulfa allergy, where the label says cross-sensitivity "is possible". It raises lamotrigine's dose by 50% after a footnote for patients under 30 kg. It makes the spironolactone misreading and swaps levothyroxine's box and pouch counts. Its median answer took 22.8 s against 8.6 s. In the comparisons 3 of 24 answers failed on the app's time limits, 60 s per model call and 180 s per answer; the two failed omeprazole answers had already searched both labels, which the evidence count includes. 6 of the 21 that arrived have a flag. They call ibuprofen a reversible COX-2 inhibitor, tie COX-1 to inflammation, pain and fever, call both of glimepiride's metabolites inactive where the label says one keeps a third of its activity, and miscount paracetamol's hydrogen-bond donors. Two denials say Molecula doesn't cover how the drugs work, after only `compare_drugs`: one English answer, one German. It reasons at length (2,340 output tokens on the first test question). A short prompt sent with and without `reasoning_effort=medium` spent all 800 allowed tokens on reasoning both times, so the test can't tell whether LM Studio passes the effort on for it. It often writes a sentence before calling a tool, and in 16 of its 52 answers the chat shows that sentence run into the answer without a space ("…labels.Ambien (zolpidem)…"). deepseek-v4.1-flash's answers show the same; gpt-oss-20b writes nothing before its tool calls (#399).
- **gpt-oss-20b stays the local model.** glm-4.7-flash adds as much from memory, answers two to five times slower and fails on the time limits; nothing it does is better.
- **gpt-6-luna's safety answers are calmer than gpt-oss-20b's.** Every overdose answer opens with the guard's emergency line and then stays short, without passing on the label's hospital treatment as if it were for the reader. Two things are wrong without being unsafe: it put an emergency line of its own in front of a plain maximum-dose question, and it told the reader twice that it can't show a 3D model, while the chat shows one under the answer (#228).

## Decided along the way

- **No filter-extraction or tool-calling set of its own.** #98 planned both for every candidate. The from-memory and safety evals run the whole agent, tools included, and gpt-6-luna called a tool and cited it in every answer of the safety eval that reached the agent; the owner decided the screen was enough (2026-10-16).
- **The default reasoning effort.** Both cloud models first ran with `LLM_REASONING_EFFORT` empty, as the app shipped then. Since #254 the answers reason at medium (`ANSWER_REASONING_EFFORT`) because that stopped gpt-oss-20b from answering comparisons from memory ([comparisons](../evals/comparisons-2026-10-17.md)). Measured on gpt-6-luna in #256, medium is as good as its own default at the same cost, so the cloud answers keep medium and get no default of their own.
- **The source check runs on the same model.** In the cloud setup gpt-6-luna also checks the answers; that was not measured on the 181 labelled claims ([source check eval](../evals/source-check-2026-10-14.md)).

## Limits

- One run of 28 questions per cloud model. gpt-oss-20b's identical runs differed by two to four additions, so 1 against 4 is a direction, not a measured gap; the 95% intervals overlap.
- The answers were judged by subagents and checked by me where they flagged something and on the questions known to be hard, not every sentence of every answer.
- The source check on gpt-6-luna, its filter extraction on the 94 retrieval questions, and the phone-number check over 70 overdose askings (#168) were not run.
- Prices are OpenRouter's list prices on one day. The cost of #256's runs is the sum of OpenRouter's cost for each answer, recorded in the eval caches; it includes Jev's label-filter calls.
- #256's effort comparison is one run per effort. Repeated identical runs of gpt-oss-20b differed by two to four additions, so differences of one answer (1 against 0 denials, 10 against 11 comparisons with evidence for both drugs) say nothing; seconds also depend on OpenRouter's load at the time. The medium comparisons run hung on its 8th answer and was resumed from its cache once #389 was fixed; the fix changes no prompt or tool.
- #386 is one run per model too. Tying cyclooxygenase to pain or inflammation counts as an addition when no result of that answer says it, and that rule alone decides 6 of the 10 comparison additions. Read leniently, deepseek-v4.1-flash's comparisons would have one flag (TRPV1) or none, as clean as gpt-6-luna's, and claude-haiku-5.5 would keep its 7 denials. The safety eval wasn't run on claude-haiku-5.5 or deepseek-v4.1-flash: a user who picks them gets checks measured on the tested models only.
- #387 is one run per model as well, so 25 against 24 label passes and 18 against 15 clean comparisons say nothing on their own. What separates the two local models is time and failures. The local seconds include the label-filter call on the same model, where the cloud runs had Jev extract the filter, so they don't compare one to one with the cloud seconds; they also depend on the GPU. Whether glm-4.7-flash reasons less at medium wasn't measured. Both local models looked up "Voltaren arthritis gel" with `resolve_drug` only, which doesn't know the brand, and told the reader it isn't covered; this passes the rules, as no passage was returned (#400). No safety eval on glm-4.7-flash: only the tested models get one.

## Reproduce

The cloud runs need `OPENROUTER_API_KEY` and `OFFLINE=0`, which picks the cloud chat model even with the local settings in `.env` (#230).

```
cd backend
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna uv run python -m evals.chat_model.from_memory --times 1
OFFLINE=0 LLM_MODEL=anthropic/claude-haiku-5.5 uv run python -m evals.chat_model.from_memory --times 1
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna uv run python -m evals.safety.run
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna ANSWER_REASONING_EFFORT=default uv run python -m evals.chat_model.from_memory
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna ANSWER_REASONING_EFFORT=medium uv run python -m evals.chat_model.from_memory
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna ANSWER_REASONING_EFFORT=default uv run python -m evals.chat_model.comparisons
OFFLINE=0 LLM_MODEL=openai/gpt-6-luna ANSWER_REASONING_EFFORT=medium uv run python -m evals.chat_model.comparisons
OFFLINE=0 LLM_MODEL=anthropic/claude-haiku-5.5 uv run python -m evals.chat_model.from_memory
OFFLINE=0 LLM_MODEL=anthropic/claude-haiku-5.5 uv run python -m evals.chat_model.comparisons
OFFLINE=0 LLM_MODEL=deepseek/deepseek-v4.1-flash uv run python -m evals.chat_model.from_memory
OFFLINE=0 LLM_MODEL=deepseek/deepseek-v4.1-flash uv run python -m evals.chat_model.comparisons
```

The local runs need the model loaded alone in LM Studio, `lms load <model> -c 32768 --parallel 1`, with `OFFLINE=1` and `LOCAL_LLM_BASE_URL` from `.env`:

```
cd backend
OFFLINE=1 LOCAL_LLM_MODEL=openai/gpt-oss-20b uv run python -m evals.chat_model.from_memory
OFFLINE=1 LOCAL_LLM_MODEL=openai/gpt-oss-20b uv run python -m evals.chat_model.comparisons
OFFLINE=1 LOCAL_LLM_MODEL=zai-org/glm-4.7-flash uv run python -m evals.chat_model.from_memory
OFFLINE=1 LOCAL_LLM_MODEL=zai-org/glm-4.7-flash uv run python -m evals.chat_model.comparisons
```

Answers are cached in `data/build/eval/`, and the hand verdicts are in `backend/evals/chat_model/from_memory_verdicts/` and `backend/evals/safety/verdicts/`, named like the caches, so a re-run asks nothing. The comparisons eval only counts tool calls; its hand verdicts for #256, #386 and #387 are in `backend/evals/chat_model/comparisons_verdicts/`.
