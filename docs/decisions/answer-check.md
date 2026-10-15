# Answer check: each claim of an answer judged against its sources

> **Answer:** after the answer has streamed, a `SourceCheck` splits it into claims and judges each against the tool results it cites, and the chat gets a `source_check` event that marks each claim `supported`, `unsupported` or `not_a_claim`. Nothing is hidden or rewritten: the user sees what comes from the sources and what doesn't. The checker is gpt-oss-20b with structured output (`guard/source_check.py`) at its own reasoning effort, medium. On 181 hand-labelled claims it catches 85% of the unsupported ones and wrongly marks 3% of the supported ones. That 85% is mostly uncited facts (31 of 32); of the 17 additions that carry a citation it catches only 6 or 7 at the default effort, 10 at medium. A first design that let only checked answers through, with a rewrite on a rejection (#205), was built and measured in #213 and dropped: it cut answers from memory (5 of 84 against 4 of 28 on main, a rough comparison) but fell back to a partial answer in half the answers, lost the answering sentence in one in five, and took 38 s per answer. The design is #205, the checker's measurement #212, the loop's #213.

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

## The submit loop, built and dropped (#213)

The first design let an answer reach the user only through a tool, `submit_answer`, which ran the check; the agent rewrote what it rejected, and after two rejections the user got only the claims that passed with "Part of this answer couldn't be verified against Molecula's sources." It was built (branch `feat/213-submit-answer`) and asked the 28 from-memory questions three times each with gpt-oss-20b, the check at medium effort. The 84 answers were judged by hand against the from-memory rules (`backend/evals/chat_model/from_memory_verdicts/openai_gpt-oss-20b-check-medium-bbfca19608c5.yaml`).

| Setup | Answers | From memory | Rewritten | Fell back | Lost the answer | Seconds p50 | p95 |
|---|---|---|---|---|---|---|---|
| main, citation-first prompt (#208) | 28 | 4 | - | - | - | 7.2 | - |
| submit loop, check at medium | 84 | 5 | 64 | 43 | 16 | 38.4 | 71.5 |

- **It cut answers from memory, at a price no answer should pay.** 5 of 84 (6%) against 4 of 28 (14%), but the main run asked each question once, so that comparison is rough. 43 answers fell back to the claims that passed, and in 16 the sentence that answered the question was dropped ("Yes, ciprofloxacin is approved for plague", "do not use with an MAOI"). An answer took 5 times as long.
- **The check was mostly right; the rewrite was the problem.** 83 of the 98 claims rejected on a first submit were uncited, nearly all true facts from a returned passage, and 16 of the 55 rejected on the second submit were the same sentence again. gpt-oss-20b doesn't fix its citations when told which sentence lacks one.
- **Two rewrites came back as garbage** ("Tamiz?", and a line of dots with leaked channel text); the check passed "Tamiz?" as not a claim.
- **LM Studio failed one call in five with `tool_choice: auto`.** gpt-oss-20b sometimes wrote the `submit_answer` call on its final channel, which LM Studio's parser rejects with a 500 (2 of 10 replays of one request, 0 of 10 with `"required"`). A named tool choice is refused.
- **Dropped for the check after the answer.** It costs one check call after the answer is already on screen, removes nothing, and shows the reader which sentence comes from which source. Only the from-memory eval was run for the loop; the rest of the planned before → after (no-label, citations, safety) was stopped once these numbers were in, by the owner's call.

## Decided along the way

- **No model call only for refs no tool returned.** #205 says a claim about a drug without a returned `[ref]` is rejected outright. Telling a drug fact from advice or "Molecula doesn't cover this" needs the model, and a rule by drug name would reject both, so an uncited sentence goes to the model, and the prompt says an uncited drug fact is `unsupported`. Only a claim whose refs no tool returned is rejected without a call.
- **One call per answer, not per claim.** It runs in the live chat, where a call per claim would multiply the wait. The model sees each claim's refs and only the cited results. One call per claim, with only that claim's results, is the obvious next thing to try for cited additions.
- **Claims are labelled against the results they cite.** An uncited fact is `unsupported` even when another returned result holds it, because the chat's rule is a ref on every drug sentence (#208). The set records which returned result holds it (`held_by`), so additions and citation misses are counted apart.
- **The check now judges against every returned result, and a citation miss is `held_elsewhere`, not `unsupported` (#220).** Once the marks were in the chat (#214), the owner found a true sentence underlined: "Ibuprofen is a non-steroidal anti-inflammatory drug (NSAID) that is used to relieve pain, reduce fever…" cited only the Indications passage, while the Clinical pharmacology passage of the same answer says "analgesic and antipyretic activities… like that of other NSAIDs". At medium effort 29 of the check's 79 underlines were such misses. Underlining them tells the reader a fact isn't in Molecula's sources when it is. The check now gets every returned result and names the refs that hold a claim its citations miss, and the chat shows that result as a chip instead of an underline. The hand labels stay as they are, since `held_by` already says which result should be named.
- **Statements about coverage are not claims.** "Molecula's data doesn't include X" is judged by the no-label eval, not by this check, even when it is wrong.
- **The protocol lives in `schemas/source_check.py`**, so the guard and the evals share it. Kev and Jev (#215) replace the checker in one line.
- **A failing check leaves the answer unmarked, not hidden** (#213). The answer is already on screen when the check runs, so `source_check` says `checked: false` and the chat says "Not checked against the sources" under it (#214).

## Limits

- 181 claims and 17 cited additions: the intervals of the three cited-addition counts overlap.
- One labelling pass by subagents; I reviewed every unsupported label and the disagreements, not every supported one.
- The answers are all gpt-oss-20b's; a different writer makes different mistakes.
- Advice that carries a drug fact ("may consider an angiotensin-receptor blocker") is read as advice and passes.

## Reproduce

See the [source check eval](../evals/source-check-2026-10-14.md#reproduce).
