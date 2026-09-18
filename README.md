# raNora - Agentic AI Platform

Monorepo managed by [uv](https://docs.astral.sh/uv/) workspaces with [poethepoet](https://poethepoet.naber.dev/) task runner.

## Services


| Service                       | Directory               | Port (dev) | Description                             |
| ----------------------------- | ----------------------- | ---------- | --------------------------------------- |
| **Backend** (LangGraph Agent) | `agent_server/`         | 8000       | AI agent API (LangGraph + FastAPI)      |
| **Frontend**                  | `frontend/`             | 5173       | React + Vite SPA                        |
| **RAG Retrieval Server**      | `rag_retrieval_server/` | 8010       | Vector + Keyword search API (LanceDB)   |
| **ACSS Backend**              | `asp_server/`           | 8001       | ACSS API + Celery worker                |
| **Pipeline**                  | `pipeline/`             | 8501       | Streamlit ETL UI                        |
| **Download Service**          | `download_service/`     | 8000       | PDF/MD/CSV download API + Celery worker |
| **Shared Libs**               | `shared_server_libs/`   | --         | Shared Python library (auth, models)    |


**Infrastructure** (Docker Compose):


| Service              | Port | Used by               |
| -------------------- | ---- | --------------------- |
| PostgreSQL (PostGIS) | 5432 | All Python services   |
| Redis                | 6379 | ACSS, Download        |
| Phoenix (Arize)      | 6006 | Backend (LLM tracing) |
| Keycloak             | 8443 | Auth for all services |




## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Node.js](https://nodejs.org/) (for frontend)
- [Docker](https://www.docker.com/) + Docker Compose
- Keycloak running: `cd auth_server && docker compose up -d`
- Seed data: `setup/init/init.sh`



## Environment Files


| File                                        | Purpose                                 |
| ------------------------------------------- | --------------------------------------- |
| `agent_server/.env`                         | Backend dev config                      |
| `rag_retrieval_server/.env`                 | RAG server dev config                   |
| `asp_server/.env`                           | ACSS dev config                         |
| `download_service/.env`                     | Download service dev config             |
| `frontend/.env`                             | Frontend dev config                     |
| `.env`                                      | Docker Compose root (SMB, Keycloak URL) |
| `setup/prod_envs/agent_server/.env`         | Backend production config               |
| `setup/prod_envs/asp_backend/.env`          | ACSS production config                  |
| `setup/prod_envs/pipeline/.env`             | Pipeline production config              |
| `setup/prod_envs/rag_retrieval_server/.env` | RAG production config                   |




## Quick Start (Dev)

Install dependencies:

```
uv sync
```

Start the base stack (Postgres, Phoenix, Backend, Frontend, RAG):

```
uv run poe dev
```



### Dev Profiles


| Command                   | What it starts                                |
| ------------------------- | --------------------------------------------- |
| `uv run poe dev`          | Postgres + Phoenix + Backend + Frontend + RAG |
| `uv run poe dev:asp`      | Base + Redis + ACSS API + ACSS Worker         |
| `uv run poe dev:pipeline` | Base + Pipeline (Streamlit)                   |
| `uv run poe dev:download` | Base + Redis + Download API + Download Worker |
| `uv run poe dev:rag`      | Base + RAG Retrieval Server (standalone)      |
| `uv run poe dev:all`      | All services                                  |


Or call the script directly with combinable flags:

```
setup/dev/run.bat -asp -pipeline
```



## Local Build

Build wheels and requirements for Docker image creation.

Same as the old `.bat` flow — call the script directly:

```
bash setup/scripts/local-build/local-build.sh -all
```

Force re-export of `requirements.txt`:

```
bash setup/scripts/local-build/local-build.sh -all -deps
```

Poe wrappers (optional):


| Command                           | Target                                 |
| --------------------------------- | -------------------------------------- |
| `uv run poe local-build`          | Show usage                             |
| `uv run poe local-build:agent`    | Backend                                |
| `uv run poe local-build:rag`      | RAG Retrieval Server                   |
| `uv run poe local-build:asp`      | ACSS                                   |
| `uv run poe local-build:pipeline` | Pipeline                               |
| `uv run poe local-build:download` | Download Service                       |
| `uv run poe local-build:all`      | All services                           |
| `uv run poe local-build:deps`     | All + force re-export requirements.txt |


## Deploy

**Prerequisite:** `bash setup/scripts/local-build/local-build.sh -all`

Same as the old `deploy-to-host.bat` / `start.bat` args:

```
bash setup/scripts/deploy/deploy-to-host.sh <hostname> <smb-user> '<smb-password>'
```

Or from that folder (same as old `start.bat`):

```
cd setup/scripts/deploy
./start.sh <hostname> <smb-user> '<smb-password>'
```

Use single quotes around the password if it contains `!`.

Poe wrappers (optional):

```
uv run poe deploy <hostname> <smb-user> '<smb-password>'
uv run poe start  <hostname> <smb-user> '<smb-password>'
```

This:

1. Stops existing containers
2. Checks required ports
3. Generates TLS certificates
4. Updates `.env` files with new hostname/credentials
5. Builds Docker images from pre-built wheels
6. Starts Keycloak, then all core services


## Package dist (single image tar)

**Prerequisite:** `bash setup/scripts/local-build/local-build.sh -all`

```
bash setup/scripts/deploy/create-dist.sh
```

or `uv run poe single-image-build`. On the target host, from `dist/`:

```
./start.sh <hostname> <smb-user> '<smb-password>'
```

## Project Structure

```
aan/
├── agent_server/              Agent server (LangGraph + FastAPI)
├── frontend/             React SPA (Vite)
├── rag_retrieval_server/ RAG retrieval server (LanceDB)
├── asp_server/          ACSS backend (FastAPI + Celery)
├── pipeline/             ETL pipeline (Streamlit)
├── download_service/     Download service (FastAPI + Celery)
├── shared_server_libs/   Shared Python library
├── auth_server/          Keycloak auth (separate compose stack)
├── setup/
│   ├── dev/              Dev runner script
│   ├── init/             Seed data setup
│   ├── certs/            TLS certificate generation
│   ├── prod_envs/        Production environment files
│   └── scripts/
│       ├── local-build/  Wheel + requirements builder
│       └── deploy/       Deployment scripts
├── docker-compose.yml    Main compose stack
└── pyproject.toml        uv workspace root + poe tasks
```

