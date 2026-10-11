# Local store: where the answers come from

> **Answer:** from a local store that the ingest steps build ahead of time: one SQLite file, `data/build/molecula.db`, plus structure files. The app never calls PubChem, ChEMBL, RCSB or openFDA while it answers, and there is no live fallback. **The store is the supported set:** a drug that isn't in it is answered as "not supported". Re-runs come from the HTTP cache in the same file, so a rebuild costs no requests and evals run with `OFFLINE=1`. A fresh clone will download the store as a release snapshot without that cache (decided, not built yet).

## Question

When someone asks about a drug, where do the facts come from: from the sources on every question, from a local copy, or from a local copy with the sources as a fallback?

The answer has to:
- be **about the right drug**, with a label, its targets and a reviewed complex, not just a structure;
- be **repeatable**, so evals give the same input every run (`OFFLINE=1`);
- survive **sources that throttle**: PubChem answers 503 when busy, and NCBI's edge blocks an IP for minutes.

## What we tried

- **A data check against the live APIs** on 2026-10-11 ([spike](../spikes/data-check/report.md)): names, salts, properties, 3D, ligand codes, complexes and labels for a dozen drugs.
- **The first plan: local store first, live fallback for cheap data.** Names, properties and 3D conformers would be fetched on a store miss and written through; complexes outside the reviewed hero set never (`docs/data-plan.md` §4 in the first commit).
- **What a fallback would return**, checked live while recording the PubChem fixtures: combination brands (#30, PR #31).
- **Full builds of the store** with the real clients: `ingest compounds` (PR #34) and `ingest targets` (PR #70), each run again from the cache and with `OFFLINE=1`.

## Result

**What PubChem returns for a combination brand** (checked 2026-10-11, again 2026-10-12)

| Name | Product | PubChem name lookup |
|---|---|---|
| Vicodin | hydrocodone + acetaminophen | CID 1983, acetaminophen only |
| Bactrim | trimethoprim + sulfamethoxazole | CID 5329, sulfamethoxazole only; its parent is 5329 again |

**Building the store**

| Run | Requests | Result |
|---|---|---|
| `ingest compounds`, first full run | in batches: NCBI blocked the IP (HTTP 429) after ~230 requests at ~1.2 req/s, a VPN server after ~390 | 134 drugs, no failures: 128 PubChem conformers, 4 from RDKit, 2 peptides without 3D; 4.1 MB |
| `ingest compounds` again, `OFFLINE=1` | 0 | exit 0; database and file times unchanged |
| `ingest targets`, first full run | – | no failures: 132 drugs with targets, 70 with candidate complexes; 190 targets, 104 ligand codes, 359 candidates |
| `ingest targets` again | 0 | every row identical, `fetched_at` included |
| `ingest targets`, `OFFLINE=1` (rerun 2026-10-12 on a copy of the store) | 0 | exit 0, same counts |
| `ingest compounds` without the cache, e.g. from a snapshot | ~670 PubChem requests | (estimate in #35) |

**Size of the HTTP cache**

| What | Size |
|---|---|
| Local store after `compounds` and `targets` (2026-10-12) | 1,493 cached responses, 7.9 MB of bodies; the file is 9.5 MB |
| Raw openFDA label pages for ibuprofen, imatinib and acetaminophen only | a 103 MB cache database; one page of 100 imatinib labels is 7.3 MB |

## What it shows

- **A live fallback can answer about the wrong drug.** PubChem maps a combination brand to one of its ingredients, and nothing in the response says so.
- **A fallback brings little.** For a drug outside the scope it can fetch properties and 3D, but no label, no targets and no reviewed complex, so there is little to answer with (#30).
- **The sources are fine for a build, not for a live request.** NCBI's block came well below PubChem's published limits and lasted minutes. A build stops on a block and resumes from the cache (`docs/data-plan.md` §3); the data plan's answer to flaky sources is the local store (§6).
- **The cache makes rebuilds free.** Every re-run made 0 requests and changed nothing, so `OFFLINE=1` runs and evals see exactly the same data.
- **The supported set is known and testable.** The UI lists it (#48), and "not supported" is a normal answer, not an error.

## Decided along the way

- **No live fallback** (#30, 2026-10-11). This replaced the first plan. The compound service has no source client, and a test checks its imports (PR #49). `CLAUDE.md` and `docs/data-plan.md` §4 say the store is the supported set.
- **Only ingest steps call sources**, all through the shared `SourceClient` (rate limit, retries, cache, `OFFLINE=1`). Every stored row records `source` and `fetched_at`.
- **404s are cached too** (PR #34). PubChem says "no 3D conformer" with a 404; without caching it, an `OFFLINE=1` run failed for the six drugs without one. The first version cached only 2xx (PR #24).
- **A body that fails to parse is dropped from the cache** (#64, PR #75), so an RCSB GraphQL error sent as HTTP 200 is fetched again next time. Offline it stays, because then the cache is the only copy.
- **A drug taken out of the scope leaves the store** (#33, PR #76). Otherwise it would still be supported. Only a complete run prunes (no failures, nothing left unattempted), and an empty scope is rejected, so a broken `scope.yaml` can't wipe the store.
- **`data/build/` is not in git** (PR #34): the database holds the raw HTTP cache, and no raw API dumps are committed.
- **Fresh clones get a release snapshot** (#35, decided, not built yet). `ingest export` writes `molecula.db` without `http_cache`, plus the structures and later the labels and index; `ingest fetch` downloads the release pinned in settings, checks its SHA-256 and schema version, and runs before the backend in Docker. The other options and why not:
  - the ingest as a setup step: every reviewer would run a minutes-long ingest that can hit NCBI's block;
  - commit only the conformer files (1.2 MB): still no database;
  - commit a database without the cache: growing binary data (labels, the index) in the git history;
  - Git LFS: its bandwidth quota counts every clone.
- **The app never creates an empty store file** (PR #58): an empty file would make `fetch` skip the download. Without a store, every drug is "not supported" until a build or fetch.
- **Runtime data stays out of the store** (#35, #40): usage logs go to `data/runtime/`, which is never exported.

## Limits

- **134 drugs.** Everything else is "not supported", with suggestions for typos ([name resolution](name-resolution.md)).
- **The data is as old as the build.** Labels are the only data that changes; the update step that re-indexes changed labels is planned (#25).
- **No snapshot yet** (#35). Until it exists, a fresh clone has to run the ingest, which needs PubChem and can hit NCBI's block.
- **A snapshot has no cache.** Re-running an ingest from it fetches everything again (~670 PubChem requests for the compounds) and can drift from the published data (#35).
- **The label pages are large.** The full labels run (#63) cached 1.97 GB of openFDA pages for 5.7 MB of stored label text: 361 requests the first time, 0 on a re-run. Only rebuilds need the cache; the planned snapshot (#35) leaves it out.
- **Remote MCP tools** for compounds outside the scope are a planned option (#45): off by default, never with `OFFLINE=1`, and the local tools stay first.

## Reproduce

```bash
cd backend
uv run python -m molecula.ingest compounds           # PubChem; on a block, wait and re-run: it resumes from the cache
uv run python -m molecula.ingest targets             # ChEMBL and RCSB, after compounds
OFFLINE=1 uv run python -m molecula.ingest targets   # served from the cache, no requests
sqlite3 ../data/build/molecula.db "select count(*), sum(length(body)) from http_cache"

curl "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/Vicodin/cids/JSON"   # live: {"CID": [1983]}
```

The data check is `docs/spikes/data-check/check_data.py` (`pip install -r requirements.txt`, then `python check_data.py`; it calls the live APIs and writes `report.md`).
