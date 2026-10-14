# Answers from memory about drugs with a label, 2026-10-14

Does the chat add facts from memory to answers about drugs that do have a label, and does gpt-oss-20b's reasoning effort change that (#197)? The no-label eval saw it in its control questions: dosing intervals for ibuprofen and naproxen, metformin as "a biguanide" ([no-label eval](no-label-2026-10-14.md)). Those controls compare two drugs; this eval asks single-drug questions across every part of a label.

## Setup

- **Chat:** `ChatAgent.stream` as `main.py` builds it, with `OFFLINE=1`, the built store and the bge-m3 index (`python -m evals.chat_model.from_memory`). The guard is left out: it would refuse some of the questions (snorting bupropion) before the agent answers, and what is measured is what the agent adds to its tool results.
- **Model:** `openai/gpt-oss-20b` (MXFP4) in LM Studio, llama.cpp ROCm runtime on an RX 7900 XTX, 32,768 tokens of context, one parallel slot, temperature 0.2. Asked once with no `LLM_REASONING_EFFORT` (which reasons about as briefly as "low", #198) and once with `medium`. Main at 5c8027f.
- **Questions:** 28 of the 94 retrieval questions, two from each of the 14 label section groups, drawn with a fixed seed and listed in `backend/evals/datasets/from_memory_sample.yaml`. Each asked once per effort.
- **Scoring:** each answer is judged by hand against the no-label eval's two rules (`RULES` in `backend/evals/chat_model/no_label.py`). *From memory*: it states a drug's class, use, effect, side effect, warning, dosing or structure that no returned label passage or tool result holds. *Denies data*: it says Molecula doesn't cover something a tool returned. Restating or simplifying a passage, drawing a conclusion from it, or explaining what a technical term means is not from memory; a fact no passage holds is, also when it misreads one. The verdicts, with a note on each answer, are in `backend/evals/chat_model/from_memory_verdicts/`.
- **Not used:** the issue asked to judge the cached citations-eval answers first. They were asked on 2026-10-13 before four commits that changed the prompt or the tools (the guard, `get_complex`, the 3D sorting, the emergency numbers), so both efforts were asked again on main.

## Result

| Effort | Answers | Pass | From memory | Denies data | Seconds p50 | Output tokens mean |
|---|---|---|---|---|---|---|
| none (about low) | 28 | 23 | **4** | 1 | 9.3 | 193 |
| medium | 28 | 22 | **6** | 0 | 13.3 | 394 |

No errors and no empty answers in either run.

## What it shows

- **About one answer in five adds something from memory: 10 of 56 over both runs.** Most answers follow their passages closely, down to doses, percentages and storage temperatures. The additions are claims in prose, never numbers: a list of MAOI antidepressants (phenelzine, tranylcypromine, isocarboxazid, selegiline) "listed in the label" when the passages only say "a prescription MAOI", in both runs; clopidogrel "prevents heart attacks or strokes", in both runs, with rabeprazole as an alternative the label doesn't name; an angiotensin-receptor blocker as the alternative to lisinopril; serotonin syndrome as the reason for Delsym's MAOI warning; ibuprofen's cyclooxygenase and arachidonic acid where the label says the mechanism "is not completely understood". Several of these are things a reader would act on, so this is common enough to need a check (#205). Because they are prose, a word or number check can't find them; the check has to judge each sentence against the tool results.
- **Medium doesn't reduce it.** 6 against 4 here; on the no-label eval's controls it went the other way, 2 of 9 against 8 of 18. Both gaps are within the spread of two or three answers between identical runs, so neither eval shows an effect on memory. What medium measurably costs is time and length: 4 seconds more at the median and twice the output tokens. Its longer answers carry more explanation, and that is where its additions sit (valacyclovir: "the virus remains in the body").
- **Recommendation: leave `LLM_REASONING_EFFORT` empty for gpt-oss-20b.** Medium helped neither eval, costs 4 seconds an answer, and the same model sorts every message for the guard and extracts the label filter, so the setting slows those calls too. The documented local setup keeps it empty.
- **Two misses are retrieval, not memory.** Celecoxib's ulcer rate was searched in `adverse_reactions`, where a list of events under 0.1% holds GI bleeding; both runs reported ulcers at "less than 0.1%", counted as from memory because no passage holds it. Lisinopril's contraindication for angioedema on an earlier ACE inhibitor wasn't returned, and the answers stretched a related warning.
- **The one denial is #190's shape.** "How does a high dose of Ambien compare to Valium?" got "Molecula's data does not include information on Valium" and nothing else, although the zolpidem passages compare zolpidem 40 mg with diazepam 20 mg. Valium isn't stored, so the sentence is true; the answer drops what the search found. The medium answer said the same and then gave the passage.

## Limits

- One judge (the session that wrote the eval), 28 questions, one asking per effort. The rate is good for "common or rare", not for comparing efforts: a second asking would tighten it.
- Single-drug questions only. The no-label eval's controls, where memory showed up most, are comparisons; this eval doesn't clear those.
- The rules don't cover study details: answers that called the risperidone autism trials "double-blind" or an omeprazole study "open-label" without a passage saying so passed.
- The guard is left out. It doesn't change an answer's content: it refuses a question or puts the fixed emergency line before an overdose answer.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.from_memory
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    LLM_REASONING_EFFORT=medium uv run python -m evals.chat_model.from_memory
```

Answers are cached in `data/build/eval/from_memory/`, keyed by the model, the effort, every prompt file and the tool descriptions. A re-run with the same setup asks nothing and prints the table from the verdicts. A new setup writes a review sheet next to the cache that shows each answer under its tool results. `--times 2` asks each question a second time and keeps the first answers.
