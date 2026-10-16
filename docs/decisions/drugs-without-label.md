# Drugs without a US label

> **Answer:** Molecula supports only drugs that have a US label. Metamizole, the one stored drug without a label, was removed from `data/scope.yaml` and from the store (#196). Asked about it, the chat now says it isn't among the drugs Molecula covers, like any other drug outside the store. The code still handles a drug without a label (`drugs_without_label` in `search_labels`), so a later addition that has no label still works.

## Question

Metamizole (dipyrone, Novalgin, Novaminsulfon) isn't approved in the US, so openFDA has no label for it. Molecula had its PubChem properties and one ChEMBL target, cyclooxygenase, but nothing on what it is used for, its side effects or its warnings. Can the chat answer about such a drug well enough to keep it, or should the supported set be only drugs with a label?

## What we tried

- **A no-label eval** (#192, [no-label eval](../evals/no-label-2026-10-14.md)): 8 metamizole questions under its four names, in English and German, and 3 controls about two labelled drugs, each asked 3 times on gpt-oss-20b and judged by hand. An answer passes when it adds nothing from memory and doesn't deny data Molecula has.
- **Five changes to the prompt and tools** (#193, #208): rules for drugs without a label in the prompt and the tool descriptions, a `has_label` flag on property results, metamizole's ChEMBL mechanism inside the `search_labels` result, and the citation-first prompt with every tool's result numbered.
- **Other models** with main's prompt (#98, [chat model](chat-model.md)).
- **Comparisons in the cached runs** (#200): which drugs each comparison question searched.

## Result

| Setup, gpt-oss-20b | Metamizole: pass | From memory | Denies data | Controls pass |
|---|---|---|---|---|
| Baseline, main 590ae1b | 13 of 24 | 2 | 9 | 5 of 9 |
| Best prompt and tool change tried (1 to 3) | 13 of 24 | 8 | 3 | 7 of 9 |
| Citation-first prompt with every result numbered (#208, on main) | 14 of 24 | 2 | 8 | 7 of 9 |

- gpt-5-mini passed 21 of 24 with main's prompt; deepseek-v4-flash called metamizole a painkiller from memory in 13 of 24.
- In the cached gpt-oss-20b runs, a comparison of two labelled drugs searched both drugs in 54 of 54 answers. A comparison whose first drug was metamizole missed the second drug in 23 of 60 (#200).

## What it shows

- **On the local model, a drug without a label is answered badly either way.** Telling the model the drug is covered makes it fill the gaps from memory ("a pain and fever reducer"); not telling it makes it deny the data Molecula has. No change beat main on both.
- **It drags the other drug down too.** A comparison with metamizole often searched only metamizole and then said it couldn't compare, although the other drug has a label (#200).
- **Every other stored drug has a label**, so one drug carried a whole class of failures, its own eval, and prompt rules for it.

## Decided along the way

- **Remove it rather than add a source** (owner, 2026-10-14). A European product information source (SmPC) would need its own data check (#86) and isn't planned.
- **Keep the code path.** `search_labels` still reports `drugs_without_label`, and the unit tests keep a fixture drug without a label, so a later drug without one doesn't break the chat.
- **The no-label eval stays as the record.** `backend/evals/chat_model/no_label.py` and its verdicts describe what was measured. Its metamizole questions now get "not supported", so it can't be re-run as it was.
- **#200 closed without a change.** It only happened with metamizole first.

## Limits

- One judge and 3 askings per question, so the counts show which failure is common, not a precise rate (see the no-label eval's limits).
- Only gpt-oss-20b was measured on all changes. The cloud chat model, gpt-6-luna, wasn't run on the no-label set.

## Reproduce

```
cd backend
OFFLINE=1 uv run python -m molecula.ingest compounds    # prunes compounds that left data/scope.yaml, from the HTTP cache
```

The run logs "pruned: metamizole (CID 3111)" and "removed 1 conformer files: 3111.sdf". Its targets go with it (the store's foreign keys cascade). It had no label sections or index chunks.
