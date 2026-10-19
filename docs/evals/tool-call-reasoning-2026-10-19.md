# Reasoning before earlier tool calls, 2026-10-19

#277 reported that gpt-oss-20b, asked "What are atorvastatin, lisinopril and amlodipine each used for?", sometimes calls `search_labels` with a garbled `drug` such as `.??..??..??......??....` and then runs out of steps. Why does it happen, and what stops it?

## Setup

- **Model:** `openai/gpt-oss-20b` (MXFP4) in LM Studio 0.4.26, 32,768 tokens of context, one parallel slot, answers at medium reasoning effort, `OFFLINE=1`.
- **Eval:** the cited-passages eval of #166 (`python -m evals.chat_model.cited_passages`), ten conversations asked 6 times each, scored by script and by the source check as described in [cited passages](cited-passages-2026-10-19.md). Broken tool calls are counted by script: an argument with `??`, `……`, a no-break space or a zero-width space.
- **What the model reads:** LM Studio's model log (`lms log stream --source model --json`) shows the prompt it renders from each request and the raw output, including the reasoning.

## What goes wrong

The garbling is not limited to `drug`. In main's 60 answers, 6 tool calls were broken: some in `drug`, more in `question` (`What … ..?????...???`), and one held raw template tokens (`<|end|><|start|>assistant<|channel|>commentary to=functions.search_labels`). 5 of the 6 were on the three-drug question, and always on the third tool call of the answer. 3 of 60 answers failed with no text.

The model log shows the pattern. gpt-oss writes its reasoning (the `analysis` channel) before each tool call. When the agent sends the conversation back for the next step, that reasoning is gone. The earlier calls stand there without anything before them:

```
<|start|>user<|message|>What are atorvastatin, lisinopril and amlodipine each used for?<|end|>
<|start|>assistant to=functions.search_labels<|channel|>commentary json<|message|>{…atorvastatin…}<|call|>
<|start|>functions.search_labels to=assistant …results…<|end|>
<|start|>assistant to=functions.search_labels<|channel|>commentary json<|message|>{…lisinopril…}<|call|>
<|start|>functions.search_labels to=assistant …results…<|end|>
<|start|>assistant
```

In 3 logged answers, the first two steps started with reasoning. The third step, after two calls without any, skipped reasoning in all 3 and wrote a broken call. After that the model reasoned again and recovered, or ran out of steps.

Two things drop the reasoning:
- `ChatOpenAI` (langchain-openai 1.7.0) doesn't read the `reasoning` field LM Studio streams, and says so for all non-OpenAI fields.
- LM Studio ignores reasoning sent back. `reasoning`, `reasoning_content` and `thinking` on an assistant message, and a `reasoning` item in the Responses API (`/v1/responses`), all left the rendered prompt without it.

What LM Studio does render as reasoning is the text of an assistant message that calls a tool: `content` set to "PROBE: …" came out as `<|start|>assistant<|channel|>analysis<|message|>PROBE: …<|end|>` before the call.

## The cause, tested

The failing third-step prompt from the log was sent again through `/v1/completions`, 8 times each at temperature 0.2:

| Before the two earlier calls | Starts with reasoning | Broken output |
|---|---|---|
| nothing (as sent) | 0 of 8 | 8 of 8 |
| the model's own reasoning from the log | 8 of 8 | 0 of 8 |
| one fixed line, "I call the tool." | 8 of 8 | 0 of 8 |

LM Studio's preset for gpt-oss sets a repeat penalty of 1.1, and the garbled words ("lisinopages", "atortor?") looked like it. Turning it off per request (`repeat_penalty: 1.0`, which LM Studio honours) left 5 of 6 answers broken, so it is not the cause.

## What we tried

Four ways to send the earlier calls back, each run on the ten conversations 6 times. Main was run twice, the day before (#166's run) and again on the same day as the variants:

1. **Own reasoning:** keep the `reasoning` LM Studio streams and send it back as the text of the tool-calling message.
2. **Fixed line:** the text "I call the tool." before every earlier call.
3. **Fixed line from two calls on:** the same, only once an answer has made two calls.
4. **Results after the question:** the earlier calls of the answer are not sent as calls at all. They and their results go back as one message after the question, which lists each call with its result as quoted data and asks the model to answer from them or call a tool for what they don't cover yet, without repeating a call (`with_tool_calls_as_results` in `backend/src/molecula/agent/llm.py`, `prompts/agent/tool_results.md`).

| gpt-oss-20b, 60 answers each | main, 18 Oct | main, 19 Oct | 1. own reasoning | 2. fixed line | 3. from two calls | **4. results after the question** |
|---|---|---|---|---|---|---|
| Broken tool calls | 6 | 6 | 0 | 0 | 0 | **0** |
| Answers that failed with no text | 3 | 1 | 0 | 0 | 0 | **0** |
| Wrong passage (script) | 16 of 294 | 21 of 266 | 34 of 267 | 31 of 267 | 33 of 251 | **18 of 319** |
| … in answers with two or more tool calls | 12 | 13 | 21 | 24 | 25 | **9** |
| `held_elsewhere` (source check) | 8 of 303 | 9 of 300 | 19 of 304 | 18 of 281 | 10 of 257 | **7 of 343** |
| Wrong drug | 0 | 3 | 0 | 0 | 0 | **0** |
| Tool calls | 124 | 120 | 118 | 116 | 123 | **111** |
| Seconds p50 | 15.7 | 16.1 | 19.2 | 12.4 | 14.8 | **19.8** |

Variant 4 changes what the model reads in every answer with a tool call, also the single-drug questions that never broke. On the 94 questions of the citation eval ([citations](citations-2026-10-13.md), `--variant clean-context`) against main's answers from #166:

| 94 single-drug questions | main | 4. results after the question |
|---|---|---|
| Every citation valid | 0.99 (93) | 0.98 (92) |
| Cites the passage that answers it, when the search returned it | 76 of 79 | 76 of 78 |
| Used passages, cited none | 1 | 2 |
| Seconds p50 / p95 | 8.3 / 12.9 | 10.2 / 18.4 |

The quick safety eval (`python -m evals.safety.run --quick`) passed 15 of 15.

## What it shows

- **The garbling comes from the earlier calls standing there without reasoning.** Anything before them stops it: the model's own reasoning, a fixed line, or not showing them as calls at all. Every variant had 0 broken calls and 0 failed answers.
- **But a line of reasoning before the earlier calls costs citations.** Variants 1 to 3 roughly doubled the wrong-passage citations in answers with two or more tool calls (12–13 → 21–25), whatever the line said. In answers with one call the counts stayed within the spread between main's two runs.
- **Results after the question fix both.** With no tool-call history to copy, gpt-oss reasons before each step, and it writes the answer from a list of results right under the question. Wrong passages in answers with several calls went down (13 → 9), the wrong-drug citations of main's second run didn't show, and it made fewer calls, not more: 111 against 120. The three-drug question made exactly three calls in 5 of 6 answers. In one of 60 answers, a follow-up about ibuprofen and naproxen also looked up imatinib from the turn before (0 on main).
- **Single-drug questions are unchanged**, within one question of main on every count.
- **It costs time:** about 4 s per answer in these conversations (16.1 → 19.8 s at the median) and 2 s on the single-drug questions (8.3 → 10.2 s). The answers also cite more (508 citations against 368).
- **The repeat penalty was a false lead.** The garbled words looked like its work, but turning it off changed nothing.

## Limits

- One model, one server. The rewrite applies to every local model through `LocalChatOpenAI`; with Ollama or another model it wasn't run. OpenRouter (gpt-6-luna) is unchanged.
- The wrong-passage count moves a lot between identical runs: main went 16 → 21 from one day to the next, and "imatinib warnings list", which variant 3 leaves exactly as on main, went 4 of 64 → 8 of 65. The differences above are larger than that, but each is one run of 60 answers.
- The label text now reaches the model in a message in the user's place instead of a tool result. The prompt calls it quoted data, and the quick safety eval passed, but the full safety eval with hand verdicts wasn't run.
- The time cost wasn't broken down. The answers are a little longer, and the rewritten message may keep LM Studio from reusing more of its prompt cache than before.

## Reproduce

```
cd backend
OFFLINE=1 uv run python -m evals.chat_model.cited_passages --times 6 --variant <name>
OFFLINE=1 uv run python -m evals.chat_model.citations --variant <name>
OFFLINE=1 uv run python -m evals.safety.run --quick
lms log stream --source model --json > model-log.jsonl   # in a second shell, to see the rendered prompts
```

The variant name only separates the answer caches; the cache key can't see a change to the model client. The broken calls were counted with a one-off script over the cached answers in `data/build/eval/cited_passages/` (the `tool_call` events whose arguments hold the marks listed under Setup), and the replay sent the logged prompt to LM Studio's `/v1/completions`. Variant 2 is commit e3a73f4 of the PR for #277; variants 1 and 3 were not kept.
