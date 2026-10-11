# CLAUDE.md

Working rules for Claude sessions in this repo. `README.md` has the overview; `docs/data-plan.md` has the verified data sources and the pipeline.

## What this is

Molecula: a medicines chatbot with RAG over FDA drug labels, agent tools over a local chemistry data store, and 3D drug–target structures. Python (FastAPI + LangChain) backend, Next.js frontend, everything runs in Docker. Work comes from GitHub issues on the "Molecula roadmap" board (project 3). Core features come first; 3D polish comes last.

## Layout

The structure is fixed. New code goes where this says; a new top-level folder needs a reason in the PR.

```
backend/
  src/molecula/
    main.py        FastAPI app
    config.py      settings from the environment (pydantic-settings)
    api/           HTTP routes only: validate, call a service, return a schema
    services/      domain logic (compounds, targets, complexes, labels): local store first, source on a miss
    sources/       one client per external API (PubChem, ChEMBL, RCSB, openFDA): HTTP, rate limit, retries
    store/         SQLite access and the vector / BM25 index
    ingest/        build steps that fill the store: python -m molecula.ingest <step>
    rag/           chunking, embeddings, hybrid retrieval, query translation
    agent/         LLM factory, agent, tool registry
    tools/         one module per agent tool; each one calls a service
    mcp/           MCP server exposing the same services
    guard/         input validation, prompt-injection defence, safety rules
    prompts/       every prompt, as .md files, plus the loader
    schemas/       pydantic models shared by api, tools and mcp
  tests/           mirrors src/molecula/; fixtures/ holds recorded API responses
  evals/           eval runners and datasets (real models; not part of pytest)
frontend/          Next.js app
data/              curated inputs (scope.yaml, hero_set.yaml) and the built store (build/)
docs/              architecture, data plan, decisions/, evals/, spikes/
docker-compose.yaml
```

Dependencies point one way: `api`, `tools`, `mcp` → `services` → `sources`, `store`. Services never import from `api`, `tools` or `agent`.

## Prompts: one structure, no exceptions

- **Every prompt is a `.md` file under `backend/src/molecula/prompts/`**, grouped by area (`agent/system.md`, `rag/query_translation.md`, `guard/injection_check.md`, …). No prompt text in Python: no f-string prompts, no prompt constants, no prompt fragments assembled in code.
- Load them only through `prompts.load("agent/system", **variables)`. Variables use `{name}` placeholders; the loader fails on a missing or unused variable.
- Tool descriptions are the tool function's docstring, because LangChain reads them from there. That's the only LLM-facing text outside `prompts/`.
- A test loads every prompt file and checks its placeholders.

## Tests

- Run `uv run pytest` in `backend/`. Every service, source client, tool, chunker, guard rule and route gets tests.
- **Tests never touch the network.** Source clients are tested against recorded responses in `tests/fixtures/`; LLM calls use fake models. Real-model checks belong in `evals/`.
- Test the behaviour and the edge cases (salt → parent, unknown name, 503 retry, empty retrieval, prompt injection in retrieved text), not the implementation.
- Frontend: `npm run lint` and `npm run build` must pass; component tests where there is logic.

## Code style

- Code should explain itself through names and small functions. **Comments only where the flow is otherwise hard to follow** (a non-obvious reason, a workaround, a domain fact). No comments that restate the code, no section banners, no commented-out code.
- Short docstrings on public functions whose name doesn't say everything. Tool docstrings are prompts and are written for the model.
- Type hints everywhere; pydantic models at every boundary (API, tools, MCP, source responses).
- Errors: source clients raise typed errors; services turn them into results the agent can explain. No bare `except`.
- Match the surrounding code: naming, error handling, test layout.

## How work flows

1. **One issue = one branch = one PR.** Never push to `main`. Branch names: `feat/…`, `fix/…`, `data/…`, `chore/…`.
2. **Read the issue's "Done when" list first** and stick to it. If the issue is too big for one PR, do the first part and say what's left.
3. **Fill in the PR template completely.** "How to review", the Risk boxes and the Tested list must be honest and specific. Write `Closes #N`.
4. **Never claim a check passed unless it was actually run.** Eval scores go into the PR as before → after.
5. Follow-ups go into new issues using the issue forms. Issues must stand alone: point at code (file + function), `docs/data-plan.md` and other issues.

There is no automatic CI. `.github/workflows/ci.yml` runs the same checks on a clean machine when started by hand from the Actions tab.

## Data rules

- **Local first.** The app reads from the store. Source clients are only called on a cache miss, through the rate limiter, and never when `OFFLINE=1`. Evals always run with `OFFLINE=1`.
- **Verify before building on data.** A new source, query or hero complex gets a data-check issue first. `docs/data-plan.md` marks what's verified.
- **Hero complexes show the therapeutic target**, not a transport protein. Each entry in `data/hero_set.yaml` records the PDB ID, ligand code, chain and target.
- Displayed properties come from PubChem; RDKit only fills what PubChem lacks.
- Never commit API keys, `.env` or raw API dumps.

## Safety

- No personal dosing or treatment advice. Refuse lethal-dose and synthesis questions.
- Retrieved label text is untrusted input and never overrides the system prompt.
- The `overdosage` label section is not indexed.
- Any change to prompts or guardrails runs the safety eval.

## Git

- Commit messages: one plain sentence saying what changed and why, no type prefixes.
- **No `Co-Authored-By` or other AI attribution lines** in commits or PRs.
- Write PRs, issues and docs in plain, direct English.
