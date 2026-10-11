# Molecula

A medicines chatbot that answers with real 3D molecular structures. Ask "How does imatinib fight leukemia?" and it explains the mechanism from FDA drug labels, cites its sources, and shows the drug sitting in the pocket of its target protein.

> **Not medical advice.** Molecula explains how medicines work. It does not give personal dosing or treatment advice.

## Status

Early development. [`docs/data-plan.md`](docs/data-plan.md) describes the verified data sources and the pipeline.

## Stack

- **Backend:** Python, FastAPI, LangChain; LLMs via OpenRouter or a local model (Ollama / LM Studio)
- **Frontend:** Next.js
- **Data:** a local store built from PubChem, ChEMBL, RCSB PDB and openFDA, served through its own API and an MCP server. External APIs are only called on a cache miss.
- **Runs in Docker:** `docker compose up --build`

## Running it

```
cp .env.example .env              # fill in what you need; every key is optional for now
docker compose up --build         # backend on http://localhost:8000/health
```

Backend development needs [uv](https://docs.astral.sh/uv/):

```
cd backend
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Layout

```
backend/    FastAPI app, LangChain agent, data services, MCP server, tests, evals
frontend/   Next.js chat UI and 3D viewer
data/       curated inputs (drug scope, hero complexes) and the built store
docs/       data plan, architecture, decisions, eval results
```

## Data sources and licences

openFDA drug labels (CC0) · RCSB PDB (free to use) · PubChem (mostly public domain) · ChEMBL (CC BY-SA 3.0)
