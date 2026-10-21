# Label update: which labels does an update fetch again?

> **Answer:** only those of drugs whose chosen label openFDA withdrew or published a new version of. Two count queries over the store's own labels find them: 9 requests and 3 s for all 133 drugs when nothing changed, and 1 request when openFDA has published nothing since the last run. The plan in #25, every label published since the last run, needs a margin of weeks because openFDA publishes labels late; with 60 days it marked 110 of 133 drugs, about 1.85 GB of label pages to fetch again each week.

## Question

FDA labels are the only data in the store that changes after the build. #25 planned the update as a search per drug for labels with `effective_time:[last_run TO *]`, fetching all labels of a drug that has one and running the canonical selection ([drug labels](drug-labels.md)) again. How few requests find the labels that changed, without missing any?

## What we tried

All against openFDA on 2026-10-21, without a VPN: the query checks without an API key, the update runs with the configured key, which changes nothing in the answers. The store's labels were fetched on 2026-10-12 (133 drugs, 156 labels). The query shapes were checked first in #340.

- **A window on `effective_time`.** One `count` on `openfda.generic_name.exact` per 30 drug names, over `effective_time:[since TO *]`, keeping the generic names of one ingredient (no `,`, `/`, `AND` or `WITH`; combination labels are never chosen). A drug whose name appears in one is marked, and a marked drug's label pages in the store's HTTP cache give the size of fetching it again.
- **How late openFDA publishes.** The data updated on 2026-10-20 holds no ibuprofen label newer than 2026-09-09, and only two labels under acetaminophen, ibuprofen and imatinib from 2026-09-15 on, both combinations. A window that starts at the last run misses a label that is published weeks after its effective date, so it needs a margin of at least six weeks.
- **The store's own labels.** `count=set_id` over our labels, 50 per request (about 4.6 kB each), lists those openFDA still has; a missing one was withdrawn. One `count=set_id` over `(set_id:"…" AND effective_time:{<stored> TO *])` clauses, 50 per request, returns the labels whose effective time is later than the stored one: those with a new version. Setting five stored dates back returned exactly those five.
- **A gate.** Any count response carries `meta.last_updated`, the date openFDA last published data. One count for a single label reads it; when it equals the last run's, nothing can have changed.

The numbers come from `docs/spikes/label-update/window_estimate.py` and three runs of `python -m molecula.ingest update` on a copy of the store.

## Result

| How the update finds changed drugs | Drugs fetched again | Label pages | Download |
|---|---|---|---|
| window from 30 days before the fetch | 12 | 51 | 119 MB |
| window from 60 days before | 110 | 335 | 1,848 MB |
| window from 90 days before | 122 | 349 | 1,923 MB |
| the store's own labels (9 requests) | 0 | 0 | about 20 kB |

Runs of the update on a copy of the store:

| Run | Requests to openFDA | Drugs fetched again | Labels changed | Time |
|---|---|---|---|---|
| first run | 9 | 0 | 0 | 3 s |
| again right after | 1 (nothing new since 2026-10-20) | 0 | 0 | not timed |
| Gleevec's stored date set back a day in the copy | 9 + 1 page of imatinib labels | 1 | 1, re-embedded and re-indexed (97 chunks) | 51 s, with about 10 s to load bge-m3 on the CPU |

## What it shows

A window can't be both cheap and complete. Because openFDA publishes labels weeks after their effective date, the window has to reach back weeks, and in any few weeks most of our drugs get a new label from some manufacturer. A narrow window stays small but misses the late ones. Checking our own labels needs no window: each label's stored effective time is its own lower bound, so a new version is found however late openFDA publishes it.

## Decided along the way

- **An update follows the chosen label.** When it gets a new version or is withdrawn, the drug's labels are fetched again and the canonical selection runs again. A label from another manufacturer that the selection would now prefer is picked up by `python -m molecula.ingest labels`, the full step, not by an update. This also stops a weekly swap of one generic label for an identical one, which the selection would make since it prefers the newest of equal labels.
- **A changed drug is re-indexed before its label rows are replaced.** If the run stops in between, the stored label still reads as old, and the next run does both again.
- **The store keeps every run** in `label_update` and `label_change` (schema version 7): when, openFDA's data date, drugs checked and fetched again, the outcome, and each label's old and new `set_id` and effective time. The snapshot carries them. `ingest fetch` now accepts a release of an older schema version, which the app upgrades when it opens the store.
- **The store uses write-ahead logging**, so the app's reads don't wait while an update writes, and each drug's label rows change in one transaction.
- **The command runs with the backend stopped.** The backend keeps the label index open, and a second process can't safely write to it. The nightly run inside the backend is #342.

## Limits

- A new label that the selection would now prefer, such as a first brand label, isn't picked until `ingest labels` runs.
- A new version that keeps its effective time isn't seen. None was observed; openFDA's effective time is the label's version date.
- No real new version of a stored label appeared between 2026-10-12 and 2026-10-21, so the third run changed the copy's stored date by hand to take the path of a change. The working store was not touched.
- The cost of a window was measured on one week's data. Its shape (most drugs marked from about six weeks on) follows from the publishing lag, not from that week.

## Reproduce

```
cd backend
OFFLINE=0 uv run python ../docs/spikes/label-update/window_estimate.py ../data/build/molecula.db
OFFLINE=0 uv run python -m molecula.ingest update       # with the backend stopped
```
