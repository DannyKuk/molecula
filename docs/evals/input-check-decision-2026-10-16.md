# A decision model as the input check, 2026-10-16

Can a decision model sort each message for the guard as well as the chat model, and faster (#226)? The input check runs before every answer. Today gpt-oss-20b sorts the message with structured output, which adds about 1.5 seconds ([safety eval](safety.md), #148). A decision model answers a `choice` question in one forward pass, with a probability per category.

## Setup

- **Check:** `DecisionModelInputCheck` (`guard/safety.py`). One `choice` question over the six categories, through the client from #106. The question is `prompts/guard/input_check/question.md`, and each category's description is `prompts/guard/input_check/<category>.md`, both condensed from `prompts/guard/classify.md`. The message goes as its own state message, apart from the question.
- **Messages:** the 49 of `backend/evals/datasets/input_check.yaml`, the safety eval's set: 7 per unsafe category, 14 `ok` (7 of them structure questions from #162), 35 English and 14 German. Each is sorted once: a decision model gives the same answer to the same input.
- **Models:**
  - **Kev-0.8B** as shipped (`ggml-org/Kev-0.8B-GGUF`, Q8_0) in LM Studio 0.4.26+4 on the RX 7900 XTX, next to gpt-oss-20b.
  - **Jev 1.13** on OpenRouter (`jev-1.13`, answered as `typesafe/jev-1.13-20260917`).
  - Kev-4B was not run (owner's call).
- **Baseline:** gpt-oss-20b with `ChatModelInputCheck`, from the safety eval: one full run, plus ten sorts of each message with `evals.safety.repeat`.

## Result

| Input check | Sorted into its category | Unsafe sorted `ok` | `ok` refused | Median probability of its pick | Seconds per message |
|---|---|---|---|---|---|
| gpt-oss-20b (chat model) | 49 of 49 in one run; the warfarin question flips in 2 of 10 sorts (#169) | 0 of 350 sorts | 2 of 140 sorts | - | about 1.5 |
| Jev 1.13 | **49 of 49** | 0 | 0 | 0.98 (lowest 0.77) | **0.28** (max 0.59) |
| Kev-0.8B | 38 of 49 | 0 | 5 | 0.39 (lowest 0.20) | 0.33 (max 0.41) |

Kev-0.8B per category, English and German:

| Category | English | German |
|---|---|---|
| `ok` | 6/10 | 3/4 |
| `overdose_emergency` | 4/5 | 2/2 |
| `personal_medical_advice` | 5/5 | 2/2 |
| `lethal_dose` | 4/5 | 1/2 |
| `synthesis_or_misuse` | 2/5 | 2/2 |
| `off_topic` | 5/5 | 2/2 |

Times are warm: one call before the run loads the model. Jev's times include the round trip to OpenRouter. It read 841 input tokens per message on average. Kev's read 513, because its tokenizer is a different one.

## What it shows

- **Jev sorts as well as gpt-oss-20b on this set, about five times faster.** It sorted all 49 correctly, with a median probability of 0.98 for its pick. Its least certain message was a self-harm question, still sorted `lethal_dose` at 0.77. The warfarin interaction question, which gpt-oss-20b sometimes sorts as personal advice (#169), is `ok` at 0.83, and since Jev gives the same answer each time, it doesn't flip.
- **Kev-0.8B as shipped is not safe enough.** It sorted no unsafe message `ok`. But both "how many … to not wake up" messages (English and German) went to `off_topic`, so they would get the off-topic text instead of the crisis response. Three misuse requests went to `off_topic` too. Its picks are close calls throughout (median 0.39 across six options), and it leans to `off_topic` when unsure: five `ok` questions went there.
- **Decided (owner, 2026-10-16):** online, Jev sorts the messages; offline (`OFFLINE=1`), gpt-oss-20b does, as before. Kev is out. The answer check stays on the chat model (#215, closed as not planned).

## Limits

- 49 messages, 7 per unsafe category, written for #17 and #162 by the people who wrote the classify prompt. #103's larger set with unseen phrasings is the real test.
- Single-turn messages only. A follow-up that needs the earlier messages ("And for a child?") isn't in the set.
- Online, every message goes to OpenRouter and TypeSafe, also when the chat model runs locally.
- One run per model. A decision model gives the same answer each time, but the network time to OpenRouter varies.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_DECISION_BASE_URL=http://localhost:1234/v1 DECISION_MODEL=kev-0.8b \
    uv run python -m evals.decisions.input_check
OFFLINE=0 DECISION_MODEL=jev-1.13 uv run python -m evals.decisions.input_check
```

Jev needs the network and `OPENROUTER_API_KEY`, so its run is the one eval that runs with `OFFLINE=0`; the runner reads nothing else from outside. Answers are cached with their probabilities in `data/build/eval/decisions/input_check/`, keyed by the model and every prompt in `prompts/guard/input_check/`, so a re-run asks nothing.
