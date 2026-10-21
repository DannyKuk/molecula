# Molecula

A medicines chatbot that answers with real 3D molecular structures. Ask "How does imatinib fight leukemia?" and it explains the mechanism from FDA drug labels, cites its sources, and shows the drug sitting in the pocket of its target protein.

> **Not medical advice.** Molecula explains how medicines work. It does not give personal dosing or treatment advice.

## Status

Early development. [`docs/data-plan.md`](docs/data-plan.md) describes the verified data sources and the pipeline.

## Contents

| Doc | What's in it |
|---|---|
| [Architecture](docs/architecture.md) | The pieces and what's built, one question from start to end, the ingest steps, the key design choices |
| [Data plan](docs/data-plan.md) | Every source and query, verified live, and what each ingest step stores |
| [Local store](docs/decisions/local-store.md) | Why the app answers only from a store built ahead of time, with no live fallback |
| [Name resolution](docs/decisions/name-resolution.md) | How brands, salt names and typos find a supported drug, and why suggestions are never applied on their own |
| [Complex candidates](docs/decisions/complex-candidates.md) | How the PDB entries showing a drug bound to its target are found and ranked, and why viral targets need their own species |
| [Drug labels](docs/decisions/drug-labels.md) | Which openFDA label each drug's answers come from, and which sections are never stored |
| [Embeddings](docs/decisions/embeddings.md) | Why bge-m3 embeds the labels: 14 models on 94 questions, CPU against GPU and cloud, and what a strict answer key hides |
| [Data check](docs/spikes/data-check/report.md) | The first live check of names, properties, complexes and labels |

## Stack

- **Backend:** Python, FastAPI, LangChain; LLMs via OpenRouter or a local model (Ollama / LM Studio)
- **Frontend:** Next.js
- **Data:** a local store built from PubChem, ChEMBL, RCSB PDB and openFDA, served through its own API and an MCP server. The app answers only from this store, so the supported drugs are a known list.
- **Runs in Docker:** `docker compose up --build`

## Running it

```
cp .env.example .env              # fill in what you need; every key is optional for now
docker compose up --build         # frontend on http://localhost:3000, backend on http://localhost:8000/health
```

The first start downloads the data into `data/build/`: the built store from this repo's GitHub release (`STORE_RELEASE`, about 80 MB) and the embedding model bge-m3 from Hugging Face (about 2.3 GB). Both are checked by SHA-256. Later starts find them and download nothing; a store without the BM25 index gets it built from the vector index. This needs the internet once, also with `OFFLINE=1`; `OFFLINE` only decides whether the app calls cloud models. `python -m molecula.ingest fetch --force` replaces the store with the release ([data plan](docs/data-plan.md#4-architecture-answers-come-from-the-local-store)).

### Without Docker

The backend needs [uv](https://docs.astral.sh/uv/) and runs on the CPU; it reads `.env` from the repo root and the store from `data/`.

```
cd backend
uv sync
uv run python -m molecula.ingest fetch      # once: the store and the embedding model, as above
uv run uvicorn molecula.main:app --reload   # http://localhost:8000, restarts when the code changes
uv run python -m molecula.ingest update     # the newest FDA labels now; stop the backend first
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

`ingest update` asks openFDA which of the stored labels were withdrawn or have a new version, and fetches and re-indexes only those drugs: about 10 requests and a few seconds when nothing changed ([label update](docs/decisions/label-update.md)). It needs `OFFLINE=0` and the backend stopped, since the backend keeps the label index open.

A running backend does the same by itself every night ([#342](https://github.com/DannyKuk/molecula/issues/342)), with `OFFLINE=0` and a built store. Three settings in `.env` control it:

- `LABEL_UPDATE_HOUR`: the UTC hour of the nightly run, 0–23, default 3.
- `LABEL_UPDATE_SCHEDULE=0` turns the nightly run off, e.g. on a machine whose store is the eval baseline.
- `LABEL_UPDATE_BUTTON=1` shows an Update now button on the dashboard and opens `POST /labels/update` for it. Off by default: then the route answers 404, so nobody starts a run with a plain request.

`OFFLINE` switches between the two setups, so both can stay in `.env`: with `OFFLINE=0` and `OPENROUTER_API_KEY` set, `openai/gpt-6-luna` answers on OpenRouter, the measured cloud default ([chat model](docs/decisions/chat-model.md)); with `OFFLINE=1` the local chat model answers and nothing goes out. For the local chat model, set `LOCAL_LLM_BASE_URL` and `LOCAL_LLM_MODEL` in `.env`, e.g. `http://localhost:1234/v1` and `openai/gpt-oss-20b` for LM Studio, or `http://localhost:11434/v1` for Ollama. Leave `LLM_REASONING_EFFORT` empty for gpt-oss-20b: medium answered no better and took about 4 s longer per answer ([eval](docs/evals/from-memory-2026-10-14.md)). A backend in Docker can't reach the host as `localhost` and needs `http://host.docker.internal:1234/v1` instead. Running the embedding model on an NVIDIA or AMD GPU is [#90](https://github.com/DannyKuk/molecula/issues/90).

Online, Jev sorts each message for the guard before the agent sees it: `DECISION_MODEL` (default `jev-1.13`) on OpenRouter with `OPENROUTER_API_KEY`, as accurate as gpt-oss-20b on the safety eval's messages and about five times faster ([eval](docs/evals/input-check-decision-2026-10-16.md)). It also fills the label filter, the drugs and label sections a search runs under, as well as gpt-oss-20b in 0.27 s instead of about 3 s, and the chat model takes over when it fails ([eval](docs/evals/label-filter-decision-2026-10-19.md)). With `OFFLINE=1` or without the key the chat model sorts them, so the local setup sends nothing out. Online, every message goes to OpenRouter and TypeSafe, also with a local chat model. An OpenRouter workspace guardrail can block Jev; OpenRouter then answers 404 and names the guardrail page.

On a server too small for bge-m3 (2.3 GB in RAM, embedding on the CPU), the cloud setup embeds in the cloud too: set `EMBEDDING_MODEL=google/gemini-embedding-2` and `RETRIEVAL_SECTION_GROUP_BOOST=0`, with `OFFLINE=0` and `OPENROUTER_API_KEY`. `ingest fetch` then skips bge-m3 and builds that model's index from the stored labels, once: about 3 minutes and $0.56. Copying `data/build/index/cloud/` from a machine that built it from the same store release works too, and `fetch` then builds nothing. The nightly update re-embeds changed labels through the same model. With the boost off it finds the answering passage in the top 5 for 98% of the 94 retrieval questions, against 91% for bge-m3 ([embeddings](docs/decisions/embeddings.md)).

Frontend development needs Node.js 22. The dev server expects the backend on http://localhost:8000; set `NEXT_PUBLIC_API_URL` to point it elsewhere.

```
cd frontend
npm ci
npm run dev                       # http://localhost:3000
npm run format:check && npm run lint && npm test && npm run build
```

### MCP server

The agent's six tools (`resolve_drug`, `get_properties`, `get_targets`, `get_complex`, `search_labels`, `compare_drugs`) are also an MCP server, with the same descriptions and answers. It reads the same `.env` and store as the backend and takes about 30 seconds to start while it loads the embedding model. Every tool but `search_labels` reads only the store; each label search also makes one model call to read the filter from the question (Jev online, the local chat model with `OFFLINE=1`), as in the chat. The app shows the same setup under "MCP server" in the chat sidebar (#301).

```
cd backend
uv run python -m molecula.mcp                                     # stdio
uv run python -m molecula.mcp --transport streamable-http         # http://localhost:8001/mcp
docker compose --profile mcp up --build                           # the same, in Docker
```

[MCP Inspector](https://github.com/modelcontextprotocol/inspector): run `npx @modelcontextprotocol/inspector uv --directory backend run python -m molecula.mcp` from the repo root for stdio, or start it with no arguments and connect to `http://localhost:8001/mcp` with the Streamable HTTP transport. The HTTP server has no auth and answers only requests addressed to localhost.

Claude Desktop: add the server to `claude_desktop_config.json` (Settings → Developer → Edit Config), with the path to your checkout, and restart Claude Desktop:

```json
{
  "mcpServers": {
    "molecula": {
      "command": "uv",
      "args": ["--directory", "/path/to/molecula/backend", "run", "python", "-m", "molecula.mcp"]
    }
  }
}
```

Every result names where its facts come from. Each source has a `ref`, the number the model cites it with as `[ref]`, counted per MCP session: the same PubChem page or label passage keeps its number across calls, and two calls never share one. The result's `structuredContent` also lists its sources (kind, name, URL, label section and date, `ref`), so a client can show where an answer came from (#299).

With `AGENT_TOOLS=mcp` in `.env` the chat gets its tools from this server too, through an in-memory session inside the backend; the answer then shows no sources list or retrieval trace, and the daily cost limit doesn't count the label searches' model calls (#316).

## Layout

```
backend/    FastAPI app, LangChain agent, data services, MCP server, tests, evals
frontend/   Next.js chat UI, 3D viewer and benchmark page
data/       curated inputs (drug scope, hero complexes) and the built store
docs/       data plan, architecture, decisions, eval results
```

## Data sources and licences

openFDA drug labels (CC0) · RCSB PDB (CC0) · PubChem (mostly public domain) · ChEMBL (CC BY-SA 3.0). The published store contains data derived from ChEMBL, so the [store release](https://github.com/DannyKuk/molecula/releases/tag/store-2026-10-16) as a whole is shared under CC BY-SA 3.0.
