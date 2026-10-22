# Molecula

[![License: MIT](https://img.shields.io/badge/code-MIT-blue)](LICENSE)
[![Data: CC BY-SA 3.0](https://img.shields.io/badge/data-CC%20BY--SA%203.0-lightgrey)](#data-sources-and-licences)
[![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](backend/)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white)](backend/src/molecula/agent/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](frontend/)
[![Docker](https://img.shields.io/badge/docker%20compose-up-2496ED?logo=docker&logoColor=white)](docker-compose.yaml)
[![Runs offline](https://img.shields.io/badge/runs-offline-2E7D32)](docs/setup.md)

A medicines chatbot that answers with real 3D molecular structures. Ask "How does imatinib fight leukemia?" and it explains the mechanism from FDA drug labels, cites its sources, and shows the drug sitting in the pocket of its target protein.

https://github.com/user-attachments/assets/2db2bf0b-647a-4ed8-90e8-022c327f57c4

> **Not medical advice.** Molecula explains how medicines work. It does not give personal dosing or treatment advice.

## How it works

- **A store built ahead of time.** Ingest steps pull 133 drugs from PubChem, ChEMBL, RCSB PDB and openFDA into one SQLite file plus a vector index of the label text. The app answers only from this store, so the supported drugs are a known list, and no answer waits on one of those APIs.
- **An agent with six tools.** A LangChain agent resolves the drug name, then looks things up instead of guessing: properties, targets, the 3D complex, a comparison, and a search over the FDA label passages. Every fact in the answer cites the passage or data page it came from.
- **A guard around it.** Each message is sorted before the agent runs: overdose questions get emergency help first, and dosing advice, lethal doses, synthesis and off-topic questions get a fixed answer. After the answer streams, a source check marks claims their sources don't back.
- **3D for 73 drugs.** Each one shows a reviewed PDB structure of the drug bound to its therapeutic target, with the pocket and hydrogen bonds marked.
- **Local or cloud.** With `OFFLINE=1`, gpt-oss-20b in LM Studio answers and nothing leaves the machine; online, gpt-6-luna on OpenRouter answers. The same tools are an MCP server.

[Architecture](docs/architecture.md) follows one question from start to end and lists the key design choices.

## Quick start

```
cp .env.example .env              # add OPENROUTER_API_KEY for the cloud model, or run LM Studio
docker compose up --build         # frontend on http://localhost:3000, backend on http://localhost:8000/health
```

The first start downloads the built store (about 90 MB) and the embedding model bge-m3 (about 2.3 GB). [Setup](docs/setup.md) covers running without Docker, the models and `OFFLINE`, the nightly label update, the login, deploying, and the MCP server.

## Docs

| Doc | What's in it |
|---|---|
| [Architecture](docs/architecture.md) | The pieces, one question from start to end, the ingest steps, the key design choices, and the list of every decision and eval |
| [Setup](docs/setup.md) | Running it with and without Docker, every setting worth knowing, login, deploy, MCP |
| [Design details](docs/design/) | The full reasoning behind every design choice, one page per area: data, 3D structures, label search, agent, safety, the app, running and deploying |
| [Data plan](docs/data-plan.md) | Every source and query, verified live, and what each ingest step stores |
| [Decisions](docs/decisions/) | The big questions with evidence: what we tried, what we measured, what we picked |
| [Evals](docs/evals/) | Dated eval reports with their numbers |

## Stack

- **Backend:** Python, FastAPI, LangChain; LLMs via OpenRouter or a local model (Ollama / LM Studio)
- **Frontend:** Next.js
- **Data:** a local store built from PubChem, ChEMBL, RCSB PDB and openFDA, served through its own API and an MCP server
- **Runs in Docker:** `docker compose up --build`

## Layout

```
backend/    FastAPI app, LangChain agent, data services, MCP server, tests, evals
frontend/   Next.js chat UI, 3D viewer and benchmark page
data/       curated inputs (drug scope, hero complexes) and the built store
docs/       architecture, setup, data plan, design details, decisions, eval results
```

## Data sources and licences

The code is under the [MIT License](LICENSE). The data is not; it keeps its sources' terms:

openFDA drug labels (CC0) · RCSB PDB (CC0) · PubChem (mostly public domain) · ChEMBL (CC BY-SA 3.0). The published store contains data derived from ChEMBL, so the [store release](https://github.com/DannyKuk/molecula/releases/tag/store-2026-10-21) as a whole is shared under CC BY-SA 3.0. The recorded API responses in `backend/tests/fixtures/` are under the terms of the source they came from; ChEMBL's are CC BY-SA 3.0.
