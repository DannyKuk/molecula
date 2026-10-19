# Every citation of an answer, 2026-10-19

#166 reported two kinds of wrong citation from gpt-oss-20b, each seen once on 2026-10-13. In a follow-up about ibuprofen and naproxen, the answer cited Gleevec passages for their facts: another drug's label. And in a list of imatinib's warnings, a passage about embryo-fetal toxicity was cited for fluid retention: the right label, the wrong passage. The citation eval ([citations](citations-2026-10-13.md)) can't show either: it asks single-drug questions and counts an answer as right when some cited passage holds the answer key. Does either still happen, and how often?

## Setup

- **Chat:** `ChatAgent.stream` as `main.py` builds it, with `OFFLINE=1`, the built store and the bge-m3 index, without the guard (`python -m evals.chat_model.cited_passages`). Every turn but the last is answered by the agent and goes back as text only, as the frontend sends earlier turns; the last one is scored.
- **Model:** `openai/gpt-oss-20b` (MXFP4) in LM Studio, 32,768 tokens of context, one parallel slot, answers at medium reasoning effort. Main's prompt and tools at 5de6556.
- **Conversations:** `backend/evals/datasets/cited_passages.yaml`. There are ten:
  - the two cases from #166, word for word;
  - two drugs in one question, and three;
  - a follow-up about another drug than the first turn, one of them in German;
  - a property beside a label fact;
  - targets beside label warnings.
  
  Each was asked 6 times.
- **Scoring, by script, per cited sentence or list item:**
  - **Wrong drug:** the item (or its list's lead-in) names a drug, and the result it cites is about none of the drugs it names.
  - **Wrong passage:** the cited results hold under half of the item's distinctive words (six letters or more, cut to six so "cytopenias" finds "cytopenia", without drug names and words every warning shares). At the same time, one returned result the item doesn't cite holds at least half of them. German answers aren't scored for this, since their words aren't in the English labels.
  
  The source check (`ChatModelSourceCheck`, as the chat runs it) also judges each claim: `held_elsewhere` means the cited results don't hold it but another returned result does.
- **Checked by reading:** all 17 wrong-passage flags of main's first 30 answers (scored per claim) and all 5 ibuprofen/naproxen flags after the change were read against the passages. The 17 were all real misses. Of the 5, two are sentences saying a label "does not list" something, and one is a table row about both drugs, so they are not real misses.

## Result on main

| | main, 60 answers |
|---|---|
| Citations | 408 |
| Wrong drug | **0** |
| Tool calls for a drug the question doesn't name | 0 |
| Wrong passage (script) | **32 of 298 items (10.7%)** |
| Cited claims the source check calls `held_elsewhere` | 20 of 317 |

- **The wrong drug no longer shows.** In the #166 conversation the molecular weights now cite PubChem, and each drug's use cites its own label. Two changes since the report explain it. Every tool result carries its own `ref` (#207, #208), so a property has a number of its own. And a search for several drugs returns passages for each (#255).
- **The wrong passage does, mostly in lists.** 23 of the 32 are in "What does imatinib target, and what are the warnings on its label?". That answer lists four ChEMBL targets and then about 14 warnings from five passages. gpt-oss hands out the numbers down the list instead of by content: [6], [7], [8], [9], [10] for the first five warnings. So cytopenias get a passage about growth and tumour lysis, and heart failure gets one about the liver. In another run it cites [4], the Bcr/Abl target, for three label warnings.

## Why: the number came last

Each result reached the model as JSON with `ref` as its last field. For a passage, that is 13 fields after `text`, behind the score, set id, URL and the rest. So the number nearest to a passage's text was the previous passage's `ref`. Now every result the model can cite starts with its `ref` (`RefFirst` in `backend/src/molecula/schemas/tools.py`): passages, targets, properties, complexes and resolved drugs.

| gpt-oss-20b, 60 answers each | main | `ref` first |
|---|---|---|
| Wrong passage (script) | 32 of 298 (10.7%) | **16 of 294 (5.4%)** |
| … in the imatinib targets and warnings answer | 23 of 102 | 7 of 105 |
| `held_elsewhere` (source check) | 20 of 317 | **8 of 303** |
| Wrong drug | 0 | 0 |
| Answers that failed with no text | 1 | 3 |
| Seconds p50 | 16.1 | 15.7 |

On the 94 single-drug retrieval questions of the citation eval (`--variant ref-first`), nothing changes beyond noise:
- every citation is valid in 0.99 of answers either way;
- where the search returned the passage that answers the question, it is cited in 75 of 79 answers on main and 76 of 79 with `ref` first.

## What it shows

- **Putting `ref` first halves the wrong-passage citations.** The script and the source check agree, from different units (list items and claims).
- **What is left is mostly one pattern.** After the change, gpt-oss tends to cite the Highlights passage, which summarises every warning, for warnings the summary doesn't cover. That is the remaining 7 in the imatinib answer.
- **A sentence in the prompt didn't help.** It said: "In a list, find each item in the passages and cite the passage it is written in: not the next number, and not one passage for every item unless that passage states them all". On top of `ref` first, it gave 13 of 158 wrong passages, against 11 of 138 without it (3 runs each). The source check also called more claims unsupported (10 against 6). So it was left out, and the prompt is unchanged.
- **The source check catches fewer than the script.** In main's first 30 answers it called 13 cited claims `held_elsewhere`. The script found 17 there, and all 17 were confirmed by reading. In one imatinib answer it caught 1 of about 4. A stronger checker is #215.
- **The failed answers are another bug.** All failures are on the three-drug question. gpt-oss sometimes writes a garbled `drug` argument (`.??..??..`) and runs out of steps. That happened in 6 of 60 answers on main and 5 of 60 with `ref` first, so this change didn't cause it. It is #277.

## Limits

- 60 answers per setup, one model, ten conversations. The wrong-passage rule is a word count: it misses a citation whose passage shares the words but not the fact, and it flags some "the label does not list X" sentences. It is a lower bound with few false alarms, not a full count.
- The change is measured with gpt-oss-20b only. Field order is a property of the JSON, so it should matter less to a stronger model, but that wasn't run.

## Reproduce

```
cd backend
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.cited_passages --times 6 --variant ref-first
OFFLINE=1 LOCAL_LLM_BASE_URL=http://localhost:1234/v1 LOCAL_LLM_MODEL=openai/gpt-oss-20b \
    uv run python -m evals.chat_model.citations --variant ref-first
```

`--variant` names a code change that the cache key (model, system prompt, tool descriptions) can't see. For main's rows, run without it with main's `schemas/tools.py`. Answers and source checks are cached in `data/build/eval/cited_passages/`, and a run re-scores them without asking again.
