# talkToDB

Chat with your database: Keycloak login, LangGraph **computer** agent, semantic catalog (Postgres + RAG). SQL execution is client-side (local connector) in later phases.

Monorepo: [uv](https://docs.astral.sh/uv/) workspace + [poethepoet](https://poethepoet.naber.dev/) tasks.

## Stack

| Component | Path | Dev port | Role |
|-----------|------|----------|------|
| Frontend | `frontend/` | 5173 | React chat UI |
| Agent server | `agent_server/` | 2024 (`langgraph dev`) | `computer` graph + JWT middleware |
| RAG retrieval | `rag_retrieval_server/` | 8010 | Catalog / doc vector search (LanceDB) |
| Shared libs | `shared_server_libs/` | — | talkToDB Postgres session (`db_access`) |
| Auth | `auth_server/` | 8443 | Keycloak (separate `docker compose`) |

**Docker Compose** (`docker-compose.yml`): Postgres, Redis, agent, frontend, RAG. (Phoenix tracing is **disabled** for now — use LangSmith via agent env; the Phoenix service block remains commented in compose for later.)

| Postgres DB | Purpose |
|-------------|---------|
| `langgraph_data` | LangGraph checkpoints |
| `talktodb` | App data: semantic catalog and future tables (`TALKTODB_DB_NAME`) |

## Prerequisites

- [uv](https://docs.astral.sh/uv/), [Node.js](https://nodejs.org/), Docker
- Keycloak: `cd auth_server && docker compose up -d`
- Data directories: `bash setup/init/init.sh` → `~/talktodb_data`

## Environment

| File | Use |
|------|-----|
| `.env` | Compose — copy from [`.env.example`](.env.example) |
| `setup/prod_envs/agent_server/.env` | Production / container agent (Postgres, Redis, Keycloak, RAG URL) |
| `setup/prod_envs/rag_retrieval_server/.env` | `STORAGE_BASE_PATH` → LanceDB under `talktodb_data` |
| `frontend/.env` | Dev: `VITE_LANGGRAPH_API_URL=http://localhost:2024`, Keycloak client |

Removed legacy env (no longer used): `IID_HASHING_ENABLED`, `API_DB_*`, ACSS/PDF/download/pipeline/Prefect/SMB map paths.

## Dev quick start

```bash
cp .env.example .env   # if needed
bash setup/init/init.sh
uv sync
cd frontend && npm install && cd ..
uv run poe dev
```

`poe dev` → [`setup/dev/run.bat`](setup/dev/run.bat) `-base`: Postgres, Redis; terminals for LangGraph, Vite, RAG. Terminal PIDs are stored in `setup/dev/dev-session.properties`.

| Command | Purpose |
|---------|---------|
| `uv run poe dev:status` | On/off for Keycloak, compose services, and local dev servers |
| `uv run poe dev:stop` | Stop local terminals only (backend, frontend, rag) from the last `poe dev` |

Works from **CMD or PowerShell** — same `uv run poe …` commands, or run the bats directly (e.g. `setup\dev\status.bat`). Session reset and `dev:stop` local kills are pure CMD. `run.bat` / `status.bat` call `dev-invoke.ps1` + `dev-lib.ps1` only to open tracked terminal windows and print the status table (hard to do cleanly in batch).

Login via Keycloak → new chat → messages hit the `computer` assistant.

## Catalog bootstrap

1. Load CSV into Postgres: [`experiments/manage_db_context/run.py`](experiments/manage_db_context/run.py) (targets `talktodb`).
2. Build / sync catalog LanceDB per `rag_retrieval_server` config (`STORAGE_BASE_PATH/document_rag/catalog_store`).

**Migrating an old dev Postgres volume:** app data lives in Postgres database `talktodb` (`TALKTODB_DB_NAME`). Legacy names: set `TALKTODB_DB_NAME=talktodb_config` or `CATALOG_DB_NAME=talktodb_config` until you migrate data into `talktodb`. Init script `01_catalog_only.sql` drops legacy `user_project_config`. Old per-project Postgres databases (if any) are not removed automatically.

## Build & deploy

```bash
bash setup/scripts/local-build/local-build.sh -all
bash setup/scripts/deploy/create-dist.sh
# On target host (from dist/):
./start.sh <hostname>
```

See [`setup/scripts/deploy/start.sh`](setup/scripts/deploy/start.sh) — hostname + TLS + Keycloak URL only (no ACSS/coverage/pipeline).

## Layout

```
agent_server/          LangGraph computer + FastAPI auth wrapper
frontend/              talkToDB UI
rag_retrieval_server/  RAG API
shared_server_libs/    db_access (talkToDB Postgres ORM + session)
auth_server/           Keycloak
experiments/manage_db_context/
setup/                 init, certs, dev runner, deploy scripts
docker-compose.yml
pyproject.toml
```
