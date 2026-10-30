# raNora — DB assistant (bare minimum stack)

Monorepo managed by [uv](https://docs.astral.sh/uv/) workspaces with [poethepoet](https://poethepoet.naber.dev/) task runner.

## Services

| Service | Directory | Port (dev) | Description |
| -------- | ----------- | ------------ | ------------- |
| **Backend** (Computer agent) | `agent_server/` | 2024 (`langgraph dev`) | LangGraph computer graph + FastAPI |
| **Frontend** | `frontend/` | 5173 | React + Vite SPA |
| **RAG Retrieval** | `rag_retrieval_server/` | 8010 | Catalog + document vector/keyword search (LanceDB) |
| **Shared libs** | `shared_server_libs/` | — | DB access, auth helpers |

**Infrastructure** (Docker Compose):

| Service | Port | Used by |
| -------- | ------ | --------- |
| PostgreSQL (PostGIS) | 5432 | LangGraph checkpoints, `ranora_config`, project DBs |
| Redis | 6379 | Agent DB RLS cache |
| Phoenix (Arize) | 6006 | Optional LLM tracing |
| Keycloak | 8443 | Login (`auth_server/`, separate compose) |

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/)
- [Docker](https://www.docker.com/) + Docker Compose
- Keycloak: `cd auth_server && docker compose up -d`
- Data store layout: `bash setup/init/init.sh` (creates `~/teoco_data_store`)

## Environment files

| File | Purpose |
| ------ | --------- |
| `agent_server/.env` | Postgres, Redis, `RAG_RETRIEVAL_SERVICE_URL`, JWT/Keycloak |
| `rag_retrieval_server/.env` | Lance paths under `teoco_data_store` |
| `frontend/.env` | `VITE_LANGGRAPH_API_URL`, Keycloak client |
| `.env` | Docker Compose (`TEOCO_DATA_DIR`, etc.) |
| `setup/prod_envs/agent_server/.env` | Production backend |
| `setup/prod_envs/rag_retrieval_server/.env` | Production RAG |

## Quick start (dev)

```bash
uv sync
cd frontend && npm install && cd ..
uv run poe dev
```

`poe dev` runs [`setup/dev/run.bat`](setup/dev/run.bat) `-base`: Postgres, Redis, Phoenix, then opens terminals for `langgraph dev`, Vite, and the RAG server.

## Catalog bootstrap (manual)

Until onboarding UI exists:

1. Seed Postgres catalog tables via [`experiments/manage_db_context/run.py`](experiments/manage_db_context/run.py) (CSV → `ranora_config`).
2. Ensure catalog LanceDB is built for paths in `rag_retrieval_server` config (see `catalog_store_config.py`).

## Local build

```bash
bash setup/scripts/local-build/local-build.sh -all
bash setup/scripts/local-build/local-build.sh -all -deps   # force requirements.txt refresh
```

| Command | Target |
| --------- | -------- |
| `uv run poe local-build:agent` | agent_server |
| `uv run poe local-build:rag` | rag_retrieval_server |
| `uv run poe local-build:all` | both |

## Deploy / dist

```bash
bash setup/scripts/local-build/local-build.sh -all
bash setup/scripts/deploy/create-dist.sh
```

## Project structure

```
├── agent_server/           Computer LangGraph agent + API
├── frontend/               React SPA
├── rag_retrieval_server/   RAG API
├── shared_server_libs/     Shared Python library
├── auth_server/            Keycloak
├── experiments/manage_db_context/  Catalog CSV → SQL helper
├── setup/                  dev runner, certs, prod envs, scripts
├── docker-compose.yml
└── pyproject.toml
```
