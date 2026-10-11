## What and why

<!-- One short paragraph: what changes for the user, and why. -->

Closes #

## How to review

<!-- A guide for the reviewer. Keep it honest: point at the risky parts. -->

**Read in this order:**
1. `backend/src/molecula/...`: what to look for here
2. 

**Look hard at:**
- 

**Safe to skim** (mechanical, renames, generated, moved code):
- 

## Risk

<!-- Tick what this PR touches and say how it's handled. Delete the lines that don't apply. -->

- [ ] Changes the database schema or ingest output (the data must be rebuilt; say how)
- [ ] Calls an external API at runtime (must go through the rate limiter and respect `OFFLINE=1`)
- [ ] Changes system prompts, guardrails or refusal rules (run the safety eval)
- [ ] Changes retrieval: chunking, embeddings, hybrid weights or query translation (run the RAG eval)
- [ ] Adds or changes a hero complex (therapeutic target checked, chain and contacts recorded)
- [ ] Adds a dependency or changes a Dockerfile / `docker-compose.yaml`
- [ ] None of the above

## Tested

- [ ] `uv run ruff check . && uv run pytest` (in `backend/`)
- [ ] `npm run format:check && npm run lint && npm test && npm run build` (in `frontend/`)
- [ ] `docker compose up --build`: <!-- what you asked in the chat and what happened -->
- [ ] Evals: <!-- suite, scores before → after, or "not needed" -->

## Screenshots

<!-- For UI changes: before / after. Delete if not a UI change. -->

## Before merging

- [ ] Follow-ups are filed as issues (not left only in docs)
- [ ] README / docs updated where behaviour changed
- [ ] A design decision made or changed here is in the docs: a topic doc in `docs/decisions/` or a bullet under "Key design choices" in `docs/architecture.md`
- [ ] No API keys, `.env` files or raw data dumps committed
