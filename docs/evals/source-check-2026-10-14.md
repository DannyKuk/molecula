# Source check on hand-labelled claims, 2026-10-14

Can gpt-oss-20b tell a claim its cited source holds from one it doesn't (#212)? The answer check (#205) splits each answer into claims and judges every claim against the tool results it cites. #213 builds the chat around it, so this measurement is the go/no-go. The design is in [answer check](../decisions/answer-check.md).

## Setup

- **Checker:** `ChatModelSourceCheck` (`guard/source_check.py`). `guard/claims.py` splits the answer into sentences, keeps a list or table under one citation as one claim, and leaves out the guard's emergency line. The model then gets every claim with its refs and the cited results, and returns `supported`, `unsupported` or `not_a_claim` per claim in one structured-output call per answer (`prompts/guard/source_check.md`). A claim whose refs no tool returned is `unsupported` without a model call; none of the 181 claims was one.
- **Model:** `openai/gpt-oss-20b` (MXFP4) in LM Studio on an RX 7900 XTX, 32,768 tokens of context, one slot, temperature 0.2, `OFFLINE=1`. Main at a2efd02.
- **Set:** `backend/evals/datasets/source_check_claims.yaml`, 65 gpt-oss-20b answers that were already judged by hand as whole answers. They are all 28 from-memory answers under #208's prompt (620e4d2be54c), the 12 from-memory answers that added something in the three earlier runs, and 25 of the 33 no-label answers (eight repeats of a one-sentence "no data" answer left out). Their text and tool results come from the eval caches in `data/build/eval/`. The set covers every addition #212 names: the MAOI list, cyclooxygenase, the celecoxib ulcer rate, "the virus remains in the body", clopidogrel "prevents heart attacks or strokes", metformin "a biguanide", zolpidem "higher than the usual maximum".
- **Labels:** 181 claims, labelled against the results each claim cites (the rules are in the dataset's header). 71 are `supported`, 30 `not_a_claim` and 80 `unsupported`. Of the 80, 49 are additions that no returned result holds, 17 of them carrying a citation, and 31 are citation misses: facts a returned result holds, but not one the claim cites. Four subagents labelled from review sheets; I checked every unsupported label and every disagreement with the earlier verdicts against the passages.
- **Runs:** the first prompt once, the revised prompt twice (the second time with the first run's cache moved aside), and the revised prompt once at `LLM_REASONING_EFFORT=medium`.

## Result

Rejected = labelled the claim `unsupported`.

| Prompt, effort | Unsupported caught | Additions, cited | Additions, uncited | Citation misses | Supported rejected | Non-claims rejected |
|---|---|---|---|---|---|---|
| first, none | 70/80 (88%) | 7/17 | 32/32 | 31/31 | 2/71 (3%) | 14/30 (47%) |
| revised, none | 68/80 (85%) | 6/17 | 31/32 | 31/31 | 2/71 (3%) | 2/30 (7%) |
| revised, none, again | 68/80 (85%) | 7/17 | 31/32 | 30/31 | 2/71 (3%) | 3/30 (10%) |
| revised, medium | 70/80 (88%) | **10/17** | 31/32 | 29/31 | 3/71 (4%) | 6/30 (20%) |

| Prompt, effort | Answers failing the check | Clean answers failing | Answers that keep an addition | …of the 28 from-memory answers | Seconds p50 / mean / max | Output tokens mean |
|---|---|---|---|---|---|---|
| first, none | 42/65 | 5/27 | 10/26 | 4 | 6.0 / 6.5 / 18.9 | 208 |
| revised, none | 36/65 | 1/27 | 12/26 | 5 | 6.5 / 6.9 / 25.0 | 230 |
| revised, none, again | 37/65 | 1/27 | 11/26 | 4 | 6.8 / 7.1 / 22.0 | 245 |
| revised, medium | 40/65 | 2/27 | 8/26 | 3 | 11.5 / 14.4 / 47.7 | 555 |

"Keep an addition": answers where at least one addition passed the check. In #213's loop only rejected claims are rewritten, so that sentence would reach the user. Of the 28 from-memory answers, the claim labels find an addition in 8.

**Go/no-go:** the proposed bar is to catch at least 80% of unsupported claims and wrongly reject at most 10% of supported ones. All four runs pass it.

## What it shows

- **Uncited facts are caught; cited mistakes mostly aren't.** The checker rejects 31 or 32 of the 32 uncited additions and nearly every citation miss, and that is what carries the 85%. Of the 17 additions that carry a citation, the case #205 was written for, it catches 6 or 7 at the default effort. The ones it lets through are misreadings of the passage they cite: ulcers at "fewer than 0.1%" where the label gives that rate for bleeding (celecoxib, in four answers); overdose effects the label calls "unlikely due to acute overdosage" (spironolactone); the 6-week use for babies aged 1 to 12 months given to babies under 1 month (omeprazole); respiratory failure "from bupropion alone" where the label says mainly in multiple-drug overdoses. The checker reads a near match as a match.
- **So at the default effort it is a citation enforcer and a weak judge of cited facts.** On the 28 from-memory answers, it brings the answers with an addition from 8 down to 4 or 5. Most of what is left is one misread detail in a cited, otherwise correct answer, and the chat would show it with a source chip.
- **Medium effort helps the checker, unlike the writer.** It caught 10 of 17 cited additions, and 3 of the 28 from-memory answers kept one. For writing, medium effort added no fewer facts from memory ([from memory](from-memory-2026-10-14.md)). It costs 5 seconds more at the median, up to 48 seconds on the longest answer, and rejects more advice and "not covered" sentences (6 of 30). This is one run on 17 cited additions: a direction, not a measured gain.
- **The first prompt rejected sentences for citing nothing.** It rejected 14 of 30 non-claims: "ask your doctor", "call 911", "Molecula's data doesn't cover this". In #213's loop those would be rewritten and, after two rejections, dropped. The revised prompt first asks whether a claim states a drug fact at all, and says that only drug facts need a source. That brought non-claims to 2 or 3 of 30 and clean answers failing the check from 5 to 1, at the cost of one or two caught claims (within the spread between the two identical runs: 0 to 1 per row).
- **Wrong rejections of supported claims are rare and partly arguable.** In 2 of 71: an ibuprofen use cited [1][6], where [6] is the naproxen label and [1] holds the use; and acetazolamide's "should not take it unless absolutely necessary", a close label I left as labelled rather than move it toward the model's answer. One run rejected risperidone's "keep out of reach of children【2】", which passage 2 holds.
- **For #213:** 36 or 37 of 65 answers would take a revision round: 23 or 24 for an addition, 12 for citation misses alone, and 1 clean answer.

## Limits

- **Small set.** 181 claims and 17 cited additions. The 95% (Wilson) intervals for the cited additions are 17% to 59% (6 of 17), 22% to 64% (7 of 17) and 36% to 78% at medium effort (10 of 17): they overlap. The set is weighted towards additions: 26 of 65 answers have one, against about 8 in 28 in normal use.
- **One labeller pass, reviewed on one side.** Subagents labelled all claims; I checked every unsupported label against the passages and only spot-checked the supported ones. The claim labels are stricter than the earlier whole-answer verdicts. They count misreadings in six answers those verdicts passed: spironolactone, atorvastatin's side-effect ranges, omeprazole's age bands, bupropion "alone", metamizole's acceptors (five instead of six), and atorvastatin for children with primary hyperlipidemia.
- **The no-call rule is untested on real data.** No answer in the set cites a ref no tool returned, because #208 brought dangling refs to 0.
- **Advice can carry a drug fact.** Lisinopril's "a healthcare professional may consider an angiotensin-receptor blocker" is labelled an addition; the revised prompt files it as advice (`not_a_claim`) in both runs.
- **Answers from gpt-oss-20b only.** Another writer's mistakes may be easier or harder to catch.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.source_check
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    LLM_REASONING_EFFORT=medium uv run python -m evals.chat_model.source_check
```

The run needs the from-memory and no-label caches in `data/build/eval/` and stops if an answer no longer splits into its labelled claims. Checks are cached in `data/build/eval/source_check/`, keyed by the model, the effort and the checker's prompt: `openai_gpt-oss-20b-e1d7c7553d62.jsonl` (first prompt), `…-25a5986caf0f.jsonl` (revised prompt) and `…-medium-89949973d5c1.jsonl`. For the repeat, the first revised-prompt cache was moved aside; the second run is `…-25a5986caf0f.run2.jsonl`. The table splits cited from uncited additions, and the answer counts come from those caches.

## Changes since this baseline

| Change | Unsupported caught | Additions, cited | Supported rejected | Non-claims rejected | Seconds p50 |
|---|---|---|---|---|---|
| Baseline: revised prompt, no effort | 68/80 | 6–7/17 | 2/71 | 2–3/30 | 6.5–6.8 |
