# A decision model as the label filter, 2026-10-19

Can Jev fill the label filter as well as gpt-oss-20b, and faster (#287, part of #104)? Before a label search, the filter says which drugs, which parts of the label and which product type (prescription or over the counter) the question is about. Today gpt-oss-20b extracts it with structured output in about 3 seconds ([filter extraction](chat-model-filters-2026-10-12.md)). A decision model answers typed questions with probabilities in one forward pass, but it can't write out a drug name.

## Setup

- **Jev 1.13** on OpenRouter through `DecisionFilterExtractor` (`rag/filters.py`). One call per question: a yes/no (`noul`) for each of the 14 section groups and a `choice` of `rx`, `otc` or `either` for the product type. The questions are `prompts/rag/label_filter/`: the group descriptions are those of `extract_filters.md`. The groups with a yes probability of 0.5 or more are picked, likeliest first, at most three, the same limit gpt-oss has. The question goes as its own message, apart from the questions, like the input check's.
- **Drug names by code** for Jev's filter; gpt-oss-20b still writes them itself. Both filters then go through the same check against the store (`FilterCheck`). `CompoundService.find_names` takes every scope name, alias and label brand in the question as written, then every other word of five letters or more that is close to one (`difflib` ratio 0.85 or more). A misspelled word goes to `resolve` as it is, which answers "not supported" and suggests the drug, and never takes it for that drug, because look-alike names (Celexa, Celebrex) make a silent correction unsafe ([name resolution](../decisions/name-resolution.md)).
  - Label brands match only with a capital first letter, with a hyphen or a space between words ("Tirosint-SOL" for the label's "Tirosint SOL"), because some brands are ordinary words: "Stay Awake", "Mucus Relief", "anti-diarrheal". Names and aliases alone found the drug of 88 of the 94 questions; with label brands, 94.
  - The cutoff: over the 94 questions and the 280 input-check messages, 0.8 also took English words ("raise" for Gralise, "store", "score", "reaction"); 0.85 took only drug names, 16 of them German spellings ("Cetirizin") and one typo ("Metoprolool").
- **gpt-oss-20b** as in the app (`FilterExtractor.extract`, `prompts/rag/extract_filters.md`), rescored from the cached extractions of 2026-10-12, which the current code reproduces: recall@5 0.91.
- **Questions:** the 94 of `backend/evals/datasets/retrieval_questions.yaml`, all English, and 18 of them with the drug name misspelled the way people type it (`retrieval_questions_typos.yaml`, written for this issue: "Gleevc", "metfromin", "Lipiter", "Alleve", "Singular"). Each is scored with the original's answer key. bge-m3 search, top 10, as in the filter eval.
- A second Jev call per question asks one `choice` over the 14 groups instead of the yes/no questions, to compare. Every answer is cached with its probabilities.

## Result

| Filter | Drug named | Right group among picks | Groups per question | recall@5 | MRR@10 | Seconds per question |
|---|---|---|---|---|---|---|
| answer key: drug | 94 | - | - | 0.85 | 0.643 | - |
| answer key: drug + section group | 94 | 94 | 1 | 0.97 | 0.877 | - |
| gpt-oss-20b, extracted | 94 | 74 | 1.4 | **0.91** | 0.759 | 3.2 (p95 3.6) |
| Jev, a yes/no per group at 0.5 | 94 | 83 | 2.0 | **0.90** | 0.733 | **0.27** (p95 0.32) |
| Jev, one choice over the groups | 94 | 70 | 1 | 0.90 | 0.794 | (a second call) |

The threshold, chosen on these same questions:

| Threshold | Groups per question | No group | Right group among picks | recall@5 | MRR@10 |
|---|---|---|---|---|---|
| 0.3 | 2.6 | 0 | 86 | 0.89 | 0.708 |
| 0.4 | 2.4 | 0 | 85 | 0.89 | 0.712 |
| **0.5** | 2.0 | 0 | 83 | **0.90** | 0.733 |
| 0.6 | 1.7 | 1 | 78 | 0.89 | 0.743 |
| 0.7 | 1.1 | 18 | 63 | 0.88 | 0.756 |
| 0.8 | 0.6 | 38 | 45 | 0.89 | 0.765 |

The misspelled names:

| Filter | Searched as the drug | "Not supported", the drug suggested | Lost | recall@5 |
|---|---|---|---|---|
| gpt-oss-20b | 9 | 9 | 0 | 0.44 |
| Jev (names by code) | 0 | 17 | 1 ("Zyrtek") | 0.06 |

Jev's filter calls cost $0.0051 for the 94 questions and $0.0010 for the 18, at 1,291 input tokens per question.

## What it shows

- **Jev fills the filter as well as gpt-oss-20b, 12 times faster.** recall@5 0.90 against 0.91, one question apart, in 0.27 s against 3.2 s. Both name the right drug for all 94 questions, so the difference is the section groups: Jev picks the right group more often (83 against 74) because it picks more of them (2.0 against 1.4), and since the groups only rank the search ([soft section groups](chat-model-filters-2026-10-12.md), #112), more picks cost a little order (MRR 0.733 against 0.759) and no recall. No threshold beats 0.5 on recall; 0.8 trades recall for MRR.
- **One choice over the groups ranks best** (MRR 0.794) at the same recall, though it gets the group right less often (70). It was measured as a separate call and isn't built; it would replace the 14 yes/no questions with one.
- **Misspellings split the two.** gpt-oss-20b wrote 9 of the 18 names correctly ("Gleevec" for "Gleevc", "Dilantin" for "Dilantn") although its prompt says to keep names as written, so those 9 are searched; the other 9 come back "not supported" with the drug suggested. With the names by code, 17 of 18 come back "not supported" with the drug suggested, and the chat asks "did you mean …?" ([unknown drug names](not-found-2026-10-16.md)); the search finds the answer only for "Zyrtek", which is too far from "Zyrtec" (0.83) to count as a name and leaves the whole index searched. That is the rule `resolve` already follows, but it answers fewer typos on the first turn than gpt-oss-20b does.
- **Jev sets the product type far more often**: prescription for 61 questions and over the counter for 7, where gpt-oss-20b set one for 7 (all prescription). The prompt asks for `either` unless the question says which. Here it changes nothing (recall@5 0.90 with or without it), because the drugs of these questions have the labels it picked; on a question about a drug with both kinds of label, a wrong pick hides the other label's passages.

## Decided along the way

- The drug names come from code (`CompoundService.find_names`), as the first comment on #102 planned: scope names, aliases, label brands with a capital first letter, and words at a ratio of 0.85 or more to one of them, sent to `resolve` as written.
- `FilterCheck` holds the store check that both extractors share; `FilterExtractor.check` calls it.
- **Jev fills the filter online, gpt-oss-20b offline**, the same split as the input check, without the product-type question (owner, 2026-10-19). The product type changed no score here and is the one place Jev picks where the question doesn't say. Wiring it in, with a fallback to the chat model when Jev fails, is #290.

## Limits

- 94 English questions with one drug each, plus 18 typos written for this run; the threshold and the cutoff were picked on them. German questions are #114 and #46.
- The product type has no answer key, so a wrong pick is only counted, not scored.
- One gpt-oss-20b extraction per question (temperature 0.2), from 2026-10-12; a rerun in 2026-10-13 moved a few extractions and not the score.
- Jev's times are from one evening over OpenRouter, warm.

## Reproduce

In `backend/`, with the store built and the network for Jev (OpenRouter key in `.env`):

```
OFFLINE=0 DECISION_MODEL=jev-1.13 LOCAL_DECISION_BASE_URL= \
    uv run python -m evals.decisions.label_filter [--typos]
OFFLINE=1 uv run python -m evals.chat_model.filters [--typos]
```

Answers are cached in `data/build/eval/decisions/label_filter/` and `data/build/eval/filters/`, so a rerun scores from the cache.
