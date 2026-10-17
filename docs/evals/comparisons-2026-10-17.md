# Comparisons and reasoning effort, 2026-10-17

"Show me a 3d model of ibuprofen and complain it to aspirin" ("complain" is a typo for "compare") got the ibuprofen 3D view and then a comparison table and three paragraphs that no tool result held (#254). The agent had called `resolve_drug` twice and `get_complex` once: no label search and no target lookup for either drug. Does the chat look up each drug when a question compares two, and what changes it?

## Setup

- **Chat:** `ChatAgent.stream` as `main.py` builds it, with `OFFLINE=1`, the built store and the bge-m3 index, without the guard (`python -m evals.chat_model.comparisons`).
- **Model:** `openai/gpt-oss-20b` (MXFP4) in LM Studio, 32,768 tokens of context, one parallel slot, temperature 0.2. Main's prompt and tools at 3d09736.
- **Questions:** `backend/evals/datasets/comparison_questions.yaml`: the owner's question, the same without the typo, four comparisons of two drugs (one in German), and two single-drug controls. Each asked 3 times per setting.
- **Scoring:** by script, whether every drug the question names got a `search_labels` or `get_targets` call naming it (a 3D view or the properties say nothing about how a drug works, its uses or its side effects). By hand, for the 3D questions, whether the answer states something about a drug that no tool result holds, the from-memory eval's rule ([answers from memory](from-memory-2026-10-14.md)).

## What we tried

1. **A rule in `prompts/agent/system.md`** that a question with several parts or drugs gets the tools for every part and drug, naming `get_complex`, `get_properties` and `compare_drugs` as covering only their part, plus the same sentence in the `compare_drugs` docstring. Asked once, 3 times each: the 3D questions still got no label search (0 of 6), and the plain comparisons got worse, 6 of 12 against 10 of 12, every miss stopping at `compare_drugs`. Naming the tool seems to pull the model towards it. Reverted.
2. **Medium reasoning effort for the answers**, main's prompt unchanged. This is the result below.

## Result

| Question | Answers | Evidence for every drug, default | medium | Seconds p50, default | medium |
|---|---|---|---|---|---|
| 3D + compare, with the typo | 3 | 0 | 0 | 7.9 | 18.1 |
| 3D + compare | 3 | 0 | 0 | 6.9 | 13.3 |
| Compare ibuprofen and naproxen | 3 | 2 | 3 | 10.1 | 18.5 |
| How is metformin different from glimepiride? | 3 | 3 | 3 | 11.2 | 24.0 |
| Vergleiche Ibuprofen mit Paracetamol | 3 | 2 | 3 | 11.7 | 21.0 |
| omeprazole vs famotidine | 3 | 3 | 3 | 11.5 | 18.0 |
| Control: What is ibuprofen used for? | 3 | 3 | 3 | 4.2 | 9.5 |
| Control: Show me aspirin in 3D | 3 | - | - | 3.8 | 5.7 |

The 3D answers by hand:

| | default | medium |
|---|---|---|
| States a drug fact no tool returned | **4 of 6** | **0 of 6** |
| Borderline | 1 ("binds reversibly") | 1 ("ibuprofen targets COX-2", read off the one structure) |
| Other | 1 gives aspirin 0 H-bond donors and 0 rotatable bonds, against PubChem's 1 and 3 | - |

No errors in either run. Quick safety eval at medium: 15 of 15, 163 s of answers.

## What it shows

- **At the default effort the 3D view is where the model stops.** It shows the structure, sometimes adds the properties, and writes how the drugs work from memory: aspirin acetylating "a serine residue in PTGS2" (the stored structure is COX-1), ibuprofen "competing with arachidonic acid", and for the typo a made-up dialogue between the two drugs. None of that is in a tool result.
- **At medium the 3D answers stay with the tool data.** They fetch both structures (or one structure and a label search) and compare what those hold: the target, the species, the contacts, and aspirin's covalent Ser530 from the structure's caption. They still don't search the labels for how each drug works, so the table counts 0 there; the answers just don't claim more than the structures say.
- **The plain comparisons searched both labels more often**, 12 of 12 against 10 of 12. The two misses at the default stopped at `compare_drugs`; one then added "faster onset but shorter half-life" from memory.
- **Medium costs time:** about 5 s more for a simple question (4.2 → 9.5 s) and 7 to 13 s more for a comparison. The setting covers only the answers, so the guard and the filter extraction keep their speed.
- **This doesn't contradict #197.** There, medium made no difference on single-drug label questions, where the label search is the obvious first step. It pays off when the question has several parts.

## Decided along the way

- **`ANSWER_REASONING_EFFORT`, medium unless set,** applies only to the answering agent; `LLM_REASONING_EFFORT` stays for the guard's sorting and the filter extraction (owner's choice, 2026-10-17: "medium for answers only").
- **The prompt stays as it was.** The rule that named the tools made things worse.

## Limits

- 3 askings per question and 8 questions, one judge for the 3D answers. Enough to see the 3D answers change from mostly memory to none; not enough to measure a rate.
- Medium still has flaws the script can't count: one German answer searched only ibuprofen and said Molecula has no data on paracetamol, which it has.
- The cloud model (gpt-6-luna) now also answers at medium. Its measurement in [chat model](../decisions/chat-model.md) was at its default effort, and this run didn't measure it.
- The earlier run with LM Studio's own load (8,192 tokens of context, 4 slots) was thrown away. A model that LM Studio loads on demand gets those defaults, so load it with `lms load openai/gpt-oss-20b -c 32768 --parallel 1` first.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    ANSWER_REASONING_EFFORT=default uv run python -m evals.chat_model.comparisons --times 3
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.comparisons --times 3
```

Answers are cached in `data/build/eval/comparisons/`, keyed by the model, the answer effort, the system prompt and the tool descriptions (`openai_gpt-oss-20b-fb34099f8149.jsonl` at the default, `openai_gpt-oss-20b-answer-medium-2945cdbdc5a2.jsonl` at medium).
