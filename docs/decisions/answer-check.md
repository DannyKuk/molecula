# Answer check: only claims the sources back reach the user

> **Answer:** the chat answers through a tool, `submit_answer(text)`. A `SourceCheck` splits the answer into claims and judges each against the tool results it cites. The agent rewrites what it rejects, and after two rejections the user gets only the claims that passed. The first checker is gpt-oss-20b with structured output (`guard/source_check.py`). On 181 hand-labelled claims it catches 85% of the unsupported ones and wrongly rejects 3% of the supported ones, which passes the proposed bar: **go**. That 85% is mostly uncited facts (31 of 32). Of the 17 additions that carry a citation, it catches only 6 or 7 at the default effort, 10 at medium effort. The design is #205; the measurement is #212.

## Question

gpt-oss-20b adds facts from memory to answers about drugs that have a label, about one answer in seven, and a better prompt (#208) or a stronger writer didn't stop it ([from memory](../evals/from-memory-2026-10-14.md)). Most of these additions carry a citation, so a valid `[n]` doesn't prove the fact. Can a check in code keep them from reaching the user, and is gpt-oss-20b good enough to be that check, offline?

## What we tried

- **The design (#205).** Rejected alternatives: a check after the answer that deletes sentences (it can't look anything up to fix a claim), an advisor tool the model may call (it can skip it), and quoting label text only (no explanations or comparisons).
- **A claim splitter** (`guard/claims.py`, pure functions): one claim per sentence, `[n]` and `【n】` both read, a list or table under one citation as one claim, a lead-in ending in ":" kept with its list, the guard's emergency line left out. Tested on the 65 answers of the set and in `tests/guard/test_claims.py`.
- **The checker** (`ChatModelSourceCheck`): one structured-output call per answer with every claim, its refs and the cited results, without ids, links and scores. A missing or malformed verdict counts as `unsupported`.
- **A hand-labelled set** of 181 claims from 65 answers that were already judged as whole answers, and a runner that scores a checker on it ([source check eval](../evals/source-check-2026-10-14.md)).
- **Two prompts and two efforts:** the first prompt once, a revised prompt that first asks whether a claim states a drug fact at all twice, and the revised prompt at medium effort once.

## Result

| Checker | Unsupported caught | Additions with a citation | Supported rejected | Non-claims rejected | Seconds p50 |
|---|---|---|---|---|---|
| first prompt | 70/80 (88%) | 7/17 | 2/71 | 14/30 | 6.0 |
| revised prompt, two runs | 68/80 (85%) | 6/17, 7/17 | 2/71 | 2/30, 3/30 | 6.5, 6.8 |
| revised prompt, medium effort | 70/80 (88%) | 10/17 | 3/71 | 6/30 | 11.5 |

Of the 28 single-drug answers in the set, 8 have an addition. After the check, 4 or 5 still carry one at the default effort and 3 at medium effort.

## What it shows

- **The check works on what it was easiest to build for, and is weak on what it was built for.** Uncited facts and citation misses are caught nearly always. Cited facts the passage doesn't hold are mostly let through: these are misreadings of a passage that is close to the claim (ulcers given the rate the label gives for bleeding, overdose effects the label calls unlikely in overdose, an age band moved).
- **Go for #213, with that limit stated.** The bar as proposed is met, a false rejection costs one rewrite, and without a check every addition reaches the user. The check halves the answers that carry one. It is not a guarantee that every cited sentence says what its source says, and the docs and the app shouldn't claim that.
- **Medium effort is worth trying for the check alone.** It caught 10 of 17 cited additions against 6 or 7, for 5 seconds more per answer and twice the output tokens. The writer gained nothing from medium effort (#206), so #213 should give the checker its own effort setting rather than raise it for every call. 17 claims are too few to call this a measured gain.

## Decided along the way

- **No model call only for refs no tool returned.** #205 says a claim about a drug without a returned `[ref]` is rejected outright. Telling a drug fact from advice or "Molecula doesn't cover this" needs the model, and a rule by drug name would reject both, so an uncited sentence goes to the model, and the prompt says an uncited drug fact is `unsupported`. Only a claim whose refs no tool returned is rejected without a call.
- **One call per answer, not per claim.** It runs in the live chat, where a call per claim would multiply the wait. The model sees each claim's refs and only the cited results. One call per claim, with only that claim's results, is the obvious next thing to try for cited additions.
- **Claims are labelled against the results they cite.** An uncited fact is `unsupported` even when another returned result holds it, because the chat's rule is a ref on every drug sentence (#208). The set records which returned result holds it (`held_by`), so additions and citation misses are counted apart.
- **Statements about coverage are not claims.** "Molecula's data doesn't include X" is judged by the no-label eval, not by this check, even when it is wrong.
- **The protocol lives in `schemas/source_check.py`**, so the tool in #213, the guard and the evals share it without `tools/` importing `guard/`. Kev and Jev (#215) replace the checker in one line.

## Limits

- 181 claims and 17 cited additions: the intervals of the three cited-addition counts overlap.
- One labelling pass by subagents; I reviewed every unsupported label and the disagreements, not every supported one.
- The answers are all gpt-oss-20b's; a different writer makes different mistakes.
- Advice that carries a drug fact ("may consider an angiotensin-receptor blocker") is read as advice and passes.

## Reproduce

See the [source check eval](../evals/source-check-2026-10-14.md#reproduce).
