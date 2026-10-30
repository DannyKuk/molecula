# Setup

The [README](../README.md) has the quick start. This page has the rest: the first start, running without Docker, the models and `OFFLINE`, the nightly label update, the login and the deploy, and the MCP server.

## First start

The first start downloads the data into `data/build/`: the built store from this repo's GitHub release (`STORE_RELEASE`, about 90 MB) and the embedding model bge-m3 from Hugging Face (about 2.3 GB). Both are checked by SHA-256. Later starts find them and download nothing; a store without the BM25 index gets it built from the vector index. This needs the internet once, also with `OFFLINE=1`; `OFFLINE` only decides whether the app calls cloud models. `python -m molecula.ingest fetch --force` replaces the store with the release ([data plan](data-plan.md#4-architecture-answers-come-from-the-local-store)).

## Without Docker

The backend needs [uv](https://docs.astral.sh/uv/) and runs on the CPU; it reads `.env` from the repo root and the store from `data/`. Set `LOCAL_LLM_BASE_URL=http://localhost:1234/v1` in `.env`: the address in `.env.example` is the host as seen from Docker.

```
cd backend
uv sync
uv run python -m molecula.ingest fetch      # once: the store and the embedding model, as above
uv run uvicorn molecula.main:app --reload   # http://localhost:8000, restarts when the code changes
uv run python -m molecula.ingest update     # the newest FDA labels now; stop the backend first
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Frontend development needs Node.js 22. The dev server expects the backend on http://localhost:8000; set `NEXT_PUBLIC_API_URL` to point it elsewhere.

```
cd frontend
npm ci
npm run dev                       # http://localhost:3000
npm run format:check && npm run lint && npm run typecheck && npm test && npm run build
```

`scripts/dev.ps1 start` starts both on Windows, with pid and log files in `.dev/` (`stop` and `status` too; `-Port 3001` runs a second pair on 3001 and 8001). `git config core.hooksPath .githooks` turns on the pre-commit hook, which runs the format, lint and type checks and `scripts/check_docs.py`.

## Label update

`ingest update` asks openFDA which of the stored labels were withdrawn or have a new version, and fetches and re-indexes only those drugs: about 10 requests and a few seconds when nothing changed ([label update](decisions/label-update.md)). It needs `OFFLINE=0` and the backend stopped, since the backend keeps the label index open.

A running backend does the same by itself every night ([#342](https://github.com/DannyKuk/molecula/issues/342)), with `OFFLINE=0` and a built store. Three settings in `.env` control it:

- `LABEL_UPDATE_HOUR`: the UTC hour of the nightly run, 0–23, default 3.
- `LABEL_UPDATE_SCHEDULE=0` turns the nightly run off, e.g. on a machine whose store is the eval baseline.
- `LABEL_UPDATE_BUTTON=1` shows an Update now button on the dashboard and opens `POST /labels/update` for it. Off by default: then the route answers 404, so nobody starts a run with a plain request.

## Models, online and offline

`OFFLINE` switches between the two setups, so both can stay in `.env`: with `OFFLINE=0` and `OPENROUTER_API_KEY` set, `openai/gpt-6-luna` answers on OpenRouter, the measured cloud default ([chat model](decisions/chat-model.md)); with `OFFLINE=1` the local chat model answers and nothing goes out. The local chat model in `.env.example` is `openai/gpt-oss-20b` in LM Studio as a backend in Docker reaches it, `http://host.docker.internal:1234/v1`; without Docker set `LOCAL_LLM_BASE_URL=http://localhost:1234/v1`, or `http://localhost:11434/v1` for Ollama. The backend's log says at the start which model writes the answers and at which server. `LLM_REASONING_EFFORT` sets only the message check and the label filter; leave it empty for gpt-oss-20b. The answers have their own setting, `ANSWER_REASONING_EFFORT`, medium by default, because at its default gpt-oss-20b answered parts of comparisons from memory ([comparisons eval](evals/comparisons-2026-10-17.md), #254). The embedding model runs on the CPU; running the backend on an NVIDIA or AMD GPU was closed as not planned ([#90](https://github.com/DannyKuk/molecula/issues/90)).

The Settings button at the bottom of the chat sidebar lets a user pick another model to write the answers ([#37](https://github.com/DannyKuk/molecula/issues/37)): every chat model the server at `LOCAL_LLM_BASE_URL` lists (LM Studio lists everything it has downloaded) and, online, the OpenRouter models in `LLM_MODELS` next to `LLM_MODEL`. Above the list, **Model that checks the message** picks who sorts each question and checks the answer ([#363](https://github.com/DannyKuk/molecula/issues/363)): Jev (online, the default), gpt-oss-20b (the default offline) or the model that writes the answer. A local model checked by gpt-oss-20b or by itself asks no cloud chat model. Every eval ran on gpt-oss-20b and gpt-6-luna, so another model may answer worse. Load a local model with at least 32k tokens of context, as for gpt-oss-20b: one answer with a label search already needs about 9k.

Online, Jev sorts each message for the guard before the agent sees it: `DECISION_MODEL` (default `jev-1.13`) on OpenRouter with `OPENROUTER_API_KEY`, as accurate as gpt-oss-20b on the safety eval's messages and about five times faster ([eval](evals/input-check-decision-2026-10-16.md)). It also fills the label filter, the drugs and label sections a search runs under, as well as gpt-oss-20b in 0.27 s instead of about 3 s, and the chat model takes over when it fails ([eval](evals/label-filter-decision-2026-10-19.md)). With `OFFLINE=1` or without the key the chat model sorts them, so the local setup sends nothing out. Online, every message goes to OpenRouter and TypeSafe, also with a local chat model. An OpenRouter workspace guardrail can block Jev; OpenRouter then answers 404 and names the guardrail page.

On a server too small for bge-m3 (2.3 GB in RAM, embedding on the CPU), the cloud setup embeds in the cloud too: set `EMBEDDING_MODEL=google/gemini-embedding-2`, with `OFFLINE=0` and `OPENROUTER_API_KEY`. A cloud model turns the section boost off unless `RETRIEVAL_SECTION_GROUP_BOOST` says otherwise. `ingest fetch` then skips bge-m3 and builds that model's index from the stored labels, once: about 3 minutes and $0.56. Copying `data/build/index/cloud/` from a machine that built it from the same store release works too, and `fetch` then builds nothing. The nightly update re-embeds changed labels through the same model. With the boost off it finds the answering passage in the top 5 for 98% of the 94 retrieval questions, against 91% for bge-m3 ([embeddings](decisions/embeddings.md)).

The label search can translate its queries before it searches (#446). `QUERY_TRANSLATION=translate` has the model that extracts the label filter translate a German search question into English. `multi_query` has it write 3 rewrites, searched with the question and merged by reciprocal rank fusion. Both are off by default: on gpt-oss-20b, translation found the answering passage for 3 more of 94 German questions at about 4 s per search, and the rewrites found 5 fewer ([query translation](evals/query-translation-2026-10-16.md)). The evidence panel shows what was searched under Translation, and the daily cost limit counts the extra model call.

## Login for a deployed app

A deployed Molecula can sit behind a [Clerk](https://clerk.com) login, so only testers you invite use it, on your OpenRouter key ([#343](https://github.com/DannyKuk/molecula/issues/343)). Without the keys below the login is off, as for local development and the evals.

1. Create an application in the [Clerk Dashboard](https://dashboard.clerk.com) with email sign-in. On its Restrictions page set the sign-up mode to **Restricted**: only people you invite can create an account ([#458](https://github.com/DannyKuk/molecula/issues/458)).
2. Put three values in `.env`. From API keys: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` for the frontend, and the **JWKS Public Key** as `CLERK_JWT_KEY` for the backend, on one line in double quotes. Set `CORS_ORIGINS` to the frontend's address, e.g. `["https://molecula.example.com"]`: the backend accepts only tokens issued for those sites.
3. Rebuild the frontend (`docker compose up --build`): the publishable key is built into the page, so each Clerk instance (development or production) needs its own build.

For production, Clerk needs a domain you own: `npx clerk@latest deploy` creates the production instance, and Clerk's Domains page lists the DNS records to add (on Cloudflare, set them to "DNS only"). The production keys replace the development ones in `.env`.

**Inviting people:** in the Clerk Dashboard, Users → Invitations → **Invite** sends a tester an email whose link opens the sign-up form, where they set their password. A user is removed under Users.

With the login on, every page needs a signed-in user, and every backend route but `/health` answers 401 without a valid session token. The backend checks the token with the public key, without a call to Clerk, so the check also works with `OFFLINE=1`. The chat's request limits count per user instead of per IP. The MCP server below has no login: keep its port off the internet.

## Deploying on Coolify

`docker-compose.coolify.yaml` runs the app on a server managed by [Coolify](https://coolify.io) ([#383](https://github.com/DannyKuk/molecula/issues/383)). It differs from `docker-compose.yaml` where a server needs it: no published ports (Coolify's proxy routes each domain to its container, and Coolify's own dashboard already uses port 8000), no MCP server, the store in a named volume that survives redeploys, and fixed `OFFLINE=0`, `TRUST_PROXY=1` and cloud embeddings by default, since a small server can't hold bge-m3. It uses Coolify's `exclude_from_hc` key, so plain Docker Compose won't read it.

1. Add two DNS A records pointing at the server, one for the app and one for its API, e.g. `molecula.example.com` and `api.molecula.example.com`.
2. In Coolify: New Resource → Private Repository (with GitHub App), this repo, branch `main`, Build Pack **Docker Compose**, Docker Compose Location `/docker-compose.coolify.yaml`.
3. Under Advanced → Build, set build arguments to **Managed manually in Dockerfile**. Otherwise Coolify adds every variable, the API keys too, as an `ARG` to the Dockerfiles, and Docker records them in the image history. The compose file passes the frontend the two values it needs at build time.
4. Under Domains, give `frontend` `https://molecula.example.com` and `backend` `https://api.molecula.example.com`; the ports come from the file's `expose`. Coolify hands the frontend's domain to the build as `SERVICE_URL_FRONTEND`, which the preview card's links start with (#461).
5. Under Environment Variables, fill `OPENROUTER_API_KEY`, `NEXT_PUBLIC_API_URL=https://api.molecula.example.com`, `CORS_ORIGINS=["https://molecula.example.com"]` (brackets and quotes included) and the three Clerk keys from the section above. Paste `CLERK_JWT_KEY` on one line with **Is Multiline?** off: a multiline value arrived empty in the backend, which then ran with the login off (its log says so). Fields left empty keep the defaults in `.env.example`.
6. Deploy. The first deploy downloads the store into the volume and builds the cloud index from it (about 3 minutes and $0.56, see above); later deploys reuse both. The build needs outgoing HTTP (port 80) for Debian's packages, and the GitHub App needs the server's clock in sync (NTP, outgoing UDP 123).

Check the login after a deploy: `https://api.molecula.example.com/stats` must answer 401.

## MCP server

The agent's six tools (`resolve_drug`, `get_properties`, `get_targets`, `get_complex`, `search_labels`, `compare_drugs`) are also an MCP server, with the same descriptions and answers. It reads the same `.env` and store as the backend and takes about 30 seconds to start while it loads the embedding model. Every tool but `search_labels` reads only the store; a label search that names no drug also makes one model call to read the filter from the question (Jev online, the local chat model with `OFFLINE=1`), as in the chat. The app shows the same setup under "MCP server" in the chat sidebar (#301).

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

Claude Desktop started from the Dock doesn't see your shell's `PATH`, so if it says it can't start the server, put the full path from `which uv` (e.g. `/opt/homebrew/bin/uv`) in `command`. Its log is `~/Library/Logs/Claude/mcp-server-molecula.log` on macOS.

To use the server in Docker instead (`docker compose --profile mcp up --build`), let Claude Desktop reach it through [mcp-remote](https://www.npmjs.com/package/mcp-remote), because its config file starts only local commands and its URL connectors connect from Anthropic's cloud, which can't reach localhost. `npx` needs `node` on the `PATH` (`which node`):

```json
{
  "mcpServers": {
    "molecula": {
      "command": "npx",
      "args": ["-y", "mcp-remote@0.14.3", "http://localhost:8001/mcp"],
      "env": { "PATH": "/opt/homebrew/bin:/usr/bin:/bin" }
    }
  }
}
```

Every result names where its facts come from. Each source has a `ref`, the number the model cites it with as `[ref]`, counted per MCP session: the same PubChem page or label passage keeps its number across calls, and two calls never share one. The result's `structuredContent` also lists its sources (kind, name, URL, label section and date, `ref`), so a client can show where an answer came from (#299).

The chat gets its tools from this server too, through in-memory sessions inside the backend (`AGENT_TOOLS=mcp`, the default; `AGENT_TOOLS=local` calls them directly). The answer looks the same either way: the same sources list and retrieval trace, and the daily cost limit counts the label searches' model calls (#316).
