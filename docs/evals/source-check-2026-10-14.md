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
    SOURCE_CHECK_REASONING_EFFORT=default uv run python -m evals.chat_model.source_check
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    SOURCE_CHECK_REASONING_EFFORT=medium uv run python -m evals.chat_model.source_check
```

The runs above set `LLM_REASONING_EFFORT`; since #213 the check has its own setting, `SOURCE_CHECK_REASONING_EFFORT` (medium unless set), and the cache names are the same.

The run needs the from-memory and no-label caches in `data/build/eval/` and stops if an answer no longer splits into its labelled claims. Checks are cached in `data/build/eval/source_check/`, keyed by the model, the effort and the checker's prompt: `openai_gpt-oss-20b-e1d7c7553d62.jsonl` (first prompt), `…-25a5986caf0f.jsonl` (revised prompt) and `…-medium-89949973d5c1.jsonl`. For the repeat, the first revised-prompt cache was moved aside; the second run is `…-25a5986caf0f.run2.jsonl`. The table splits cited from uncited additions, and the answer counts come from those caches.

#220's runs are `…-medium-b8c92b98980d.jsonl` and `….run2.jsonl`. `--cache <file>` reports a cache as it is, without a model, so the medium run of 2026-10-14 can be scored the same way: `uv run python -m evals.chat_model.source_check --cache ../data/build/eval/source_check/openai_gpt-oss-20b-medium-89949973d5c1.jsonl`.

## Changes since this baseline

Amber = the claims the chat underlines (`unsupported`). A citation miss counts as caught by the baseline runs and as `held_elsewhere` from #220 on, so it has its own column. Every row is scored with the labels as they stand since #220 (see the hedge rule below): 47 additions, 15 of them cited, and 73 supported claims. The tables above use the labels of 2026-10-14.

| Change | Additions amber | Citation misses amber | Supported amber | Non-claims amber | Seconds p50 |
|---|---|---|---|---|---|
| Baseline: revised prompt, no effort | 37/47, both runs | 30–31/31 | 2–3/73 | 2–3/30 | 6.5–6.8 |
| The same prompt at medium effort, as the chat runs it since #213 | 40/47 (85%) | 29/31 | 4/73 | 6/30 | 11.5 |
| The check sees every returned result; a fact another result holds is `held_elsewhere` (#220) | 36/47 (77%), both runs | 9/31, both runs | 5/73, both runs | 1–4/30 | 7.6–7.8 |
| Not adopted: a prompt rule that a dropped hedge or another name for the same thing counts as held | 34–36/47 | 5–7/31 | 3–5/73 | 1–3/30 | 7.9 |

### Judged against every returned result (#220)

The check now gets every result the answer's tools returned, not only the cited ones, and has a third verdict: `held_elsewhere`, with the refs that hold the claim (`held_by`). The chat shows those refs as a chip instead of an underline. Medium effort, the same 181 claims, run twice; before is the medium run above (`…-medium-89949973d5c1`), scored with the new runner and labels.

| | Before | After, run 1 | After, run 2 |
|---|---|---|---|
| Amber marks | 79 | 51 | 54 |
| Citation misses held elsewhere, naming a labelled ref | 0 of 31 | 18 | 20 |
| Additions, cited, amber | 9/15 | 9/15 | 9/15 |
| Additions, uncited, amber | 31/32 | 27/32 | 27/32 |
| Supported amber | 4/73 | 5/73 | 5/73 |
| Answers failing the check | 40/65 | 28/65 | 31/65 |
| Seconds per check p50 / mean / max | 11.5 / 14.4 / 47.7 | 7.8 / 8.1 / 27.3 | 7.6 / 8.4 / 41.7 |
| Output tokens per check, mean | 555 | 708 | 777 |

- **A third fewer underlines, and most of the drop is the misses #220 was about.** 18 or 20 of the 31 citation misses now get a chip for a result the labels name, against 9 still underlined.
- **It lets 4 more additions through, all uncited.** Of the 32 uncited additions, 2 or 4 are now `held_elsewhere`, and in run 1 two more are `supported`. I read the 11 additions run 1 let through against their full passages: 7 are clear misreadings the chat now shows as backed (bupropion overdoses "alone", omeprazole's age bands, spironolactone's "unlikely due to acute overdosage", atorvastatin's side-effect ranges given a chip, an atorvastatin answer in German, the dipyrone list, advice about other PPIs), 4 are close calls (celecoxib's ulcers as a serious event, "lower its effectiveness in preventing heart attacks", and similar). Below the proposed 80% bar (77%). The owner decided on 2026-10-15 that about 25 fewer wrong warnings are worth 4 more additions passing; a stronger checker is #215.
- **No slower.** More passages go into the call and the model writes more tokens, yet the median is 4 s lower. The before run is from another day, so read this as "not slower", not as a gain.
- **Supported claims underlined: 4 before, 5 after, of 73** (7%), within the proposed 10%. Two of the five are list items that state more than the one passage they cite.

### Hedges count as held (#220, labels only)

In the live chat the owner found "This inhibition also explains its antipyretic (fever-reducing) effect [1]" underlined, while passage 2 of the same answer says ibuprofen "possesses analgesic and antipyretic activities. Its mode of action… may be related to prostaglandin synthetase inhibition." The sentence before it, "Its main way of working is to inhibit… prostaglandin synthetase", made the same step from "may be related" to a plain statement and passed. The owner decided that a dropped hedge ("may", "probable", "may be related to") and another common name for the same thing count as held, and that numbers, rates, populations and which drug a fact is about stay strict.

- **Labels:** two claims change from unsupported to supported, both ibuprofen mechanism sentences of the same kind ("This reduces the signals that cause pain and lowers the fever-raising effect of inflammation [1][2]", and cyclo-oxygenase for prostaglandin synthetase). The other 78 unsupported labels add a fact no passage has or misread a number or a population, and stay. The rule is in the dataset's header.
- **The same rule in the checker's prompt was not adopted.** Two runs (`…-medium-499c108390c6.jsonl`, `….run2.jsonl`): amber marks 47 and 47 against 51 and 54, additions caught 36 and 34 of 47 against 36 and 36, and uncited additions given a chip 5 and 8 against 2 and 4: within the spread, apart from more chips on facts no source holds. On the owner's answer, checked five times with the same passages, the antipyretic sentence was underlined 5 of 5 times with the rule; at `SOURCE_CHECK_REASONING_EFFORT=high` 5 of 5, and the "main way of working" sentence 5 of 5 as well. gpt-oss-20b reads "explains" against "may be related to" literally whatever the prompt says, so the fix belongs to a stronger checker (#215).
