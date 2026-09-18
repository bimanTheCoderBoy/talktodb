#!/usr/bin/env bash
# ============================================================================
#  Build all Docker images and package them into a portable dist/ folder.
#
#  Usage:
#    setup/scripts/deploy/create-dist.sh
#
#  Output:
#    dist/               — ready-to-ship folder with everything QA needs
#    dist/all-images.tar — every Docker image (built + pulled)
#    dist/start.sh       — QA runs: start.sh <hostname> <smb-user> <smb-pass>
# ============================================================================

set -euo pipefail

# --- Locate repo root (script lives in setup/scripts/deploy/) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DIST="$REPO/dist"

echo "==============================================================="
echo "  AAN Create-Dist  (Linux)"
echo "  Repo : $REPO"
echo "  Dist : $DIST"
echo "==============================================================="
echo

# =====================================================================
#  PRE-FLIGHT — Verify dist/ folders exist (local-build.sh must run first)
# =====================================================================
echo "[pre-flight] Checking that wheel artifacts exist..."
PREFLIGHT_OK=1
for d in asp_server agent_server pipeline download_service rag_retrieval_server; do
  if [[ ! -f "$REPO/$d/dist/requirements.txt" ]]; then
    echo "       MISSING: $d/dist/requirements.txt"
    PREFLIGHT_OK=0
  fi
done
if [[ "$PREFLIGHT_OK" -eq 0 ]]; then
  echo
  echo "       ERROR: One or more dist/ folders are missing."
  echo "       Run  setup/scripts/local-build/local-build.sh -all  first."
  exit 1
fi
echo "       OK — all dist/ folders present"
echo

# =====================================================================
#  STEP 1 — Build all custom images from pre-built dist/ wheels
# =====================================================================
echo "[1/5] Building all Docker images from pre-built dist/ wheels..."
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
docker compose -f "$REPO/docker-compose.yml" --env-file "$REPO/.env" build
echo "       OK"
echo

# =====================================================================
#  STEP 2 — Pull third-party images
# =====================================================================
echo "[2/5] Ensuring third-party images are available..."
for img in \
  "postgis/postgis:16-3.4" \
  "redis:7-alpine" \
  "amir20/dozzle:v10.7.1" \
  "arizephoenix/phoenix:20.3.0" \
  "postgres:16-alpine" \
  "quay.io/keycloak/keycloak:25.0.2"
do
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "       Already present: $img"
  else
    echo "       Pulling $img ..."
    docker pull "$img"
  fi
done
echo "       OK"
echo

# =====================================================================
#  STEP 3 — Save all images into a single tar
# =====================================================================
echo "[3/5] Saving all images to all-images.tar (this may take a while)..."

rm -rf "$DIST"
mkdir -p "$DIST"

docker save -o "$DIST/all-images.tar" \
  aana_core_services-frontend \
  aana_core_services-agent_server \
  aana_core_services-download_api \
  aana_core_services-download_worker \
  aana_core_services-acss_api \
  aana_core_services-acss_worker \
  aana_core_services-pipeline_streamlit \
  aana_core_services-rag_retrieval_server \
  postgis/postgis:16-3.4 \
  redis:7-alpine \
  amir20/dozzle:v10.7.1 \
  arizephoenix/phoenix:20.3.0 \
  postgres:16-alpine \
  quay.io/keycloak/keycloak:25.0.2
echo "       OK"
echo

# =====================================================================
#  STEP 4 — Assemble config files into dist/
# =====================================================================
echo "[4/5] Copying config files to dist/ ..."

# --- Root compose + env ---
cp "$REPO/docker-compose.yml" "$DIST/docker-compose.yml"
cp "$REPO/.env"               "$DIST/.env"
# Linux hosts: rewrite Windows USERPROFILE placeholders (e.g. TEOCO_DATA_DIR)
sed -i 's/\${USERPROFILE}/\${HOME}/g' "$DIST/.env"

# --- Auth server ---
mkdir -p "$DIST/auth_server/realms"
cp "$REPO/auth_server/docker-compose.yml" "$DIST/auth_server/docker-compose.yml"
if [[ -f "$REPO/auth_server/.env" ]]; then
  cp "$REPO/auth_server/.env" "$DIST/auth_server/.env"
fi
if [[ -d "$REPO/auth_server/realms" ]]; then
  cp -a "$REPO/auth_server/realms/." "$DIST/auth_server/realms/"
fi

# --- TLS certs ---
mkdir -p "$DIST/setup/certs"
if [[ -f "$REPO/setup/certs/tls.crt" ]]; then
  cp "$REPO/setup/certs/tls.crt" "$DIST/setup/certs/tls.crt"
  cp "$REPO/setup/certs/tls.key" "$DIST/setup/certs/tls.key"
fi
cp "$REPO/setup/certs/generate-certs.sh" "$DIST/setup/certs/generate-certs.sh"

# --- Prod env files ---
mkdir -p "$DIST/setup/prod_envs/agent_server"
mkdir -p "$DIST/setup/prod_envs/asp_backend"
mkdir -p "$DIST/setup/prod_envs/pipeline"
mkdir -p "$DIST/setup/prod_envs/rag_retrieval_server"
if [[ -f "$REPO/setup/prod_envs/agent_server/.env" ]]; then
  cp "$REPO/setup/prod_envs/agent_server/.env" "$DIST/setup/prod_envs/agent_server/.env"
fi
if [[ -f "$REPO/setup/prod_envs/asp_backend/.env" ]]; then
  cp "$REPO/setup/prod_envs/asp_backend/.env" "$DIST/setup/prod_envs/asp_backend/.env"
fi
if [[ -f "$REPO/setup/prod_envs/pipeline/.env" ]]; then
  cp "$REPO/setup/prod_envs/pipeline/.env" "$DIST/setup/prod_envs/pipeline/.env"
fi
if [[ -f "$REPO/setup/prod_envs/rag_retrieval_server/.env" ]]; then
  cp "$REPO/setup/prod_envs/rag_retrieval_server/.env" "$DIST/setup/prod_envs/rag_retrieval_server/.env"
fi

# --- Postgres init scripts ---
mkdir -p "$DIST/setup/scripts/postgres_init_scripts"
if [[ -d "$REPO/setup/scripts/postgres_init_scripts" ]]; then
  cp -a "$REPO/setup/scripts/postgres_init_scripts/." "$DIST/setup/scripts/postgres_init_scripts/"
fi

# --- Init config data (seed data for teoco_data_store) ---
mkdir -p "$DIST/setup/init"
cp "$REPO/setup/init/init.sh" "$DIST/setup/init/init.sh"
if [[ -d "$REPO/setup/init/init_config_setup" ]]; then
  mkdir -p "$DIST/setup/init/init_config_setup"
  cp -a "$REPO/setup/init/init_config_setup/." "$DIST/setup/init/init_config_setup/"
fi

echo "       OK"
echo

# =====================================================================
#  STEP 5 — Copy start.sh into dist/
# =====================================================================
echo "[5/5] Copying start.sh into dist/ ..."
cp "$REPO/setup/scripts/deploy/start.sh" "$DIST/start.sh"
chmod +x "$DIST/start.sh" "$DIST/setup/certs/generate-certs.sh" "$DIST/setup/init/init.sh"
echo "       OK"
echo

# =====================================================================
#  Done
# =====================================================================
echo "==============================================================="
echo "  dist/ folder is ready!"
echo
echo "  Contents:"
echo "    dist/all-images.tar          — all Docker images"
echo "    dist/docker-compose.yml      — core services compose"
echo "    dist/.env                    — root env"
echo "    dist/auth_server/            — Keycloak compose, env, realm"
echo "    dist/setup/                  — certs, prod envs, storage init"
echo "    dist/start.sh                — QA runs this"
echo
echo "  Ship the dist/ folder to the target machine."
echo "  QA runs:  ./start.sh <hostname> <smb-user> <smb-password>"
echo "==============================================================="
