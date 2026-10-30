#!/usr/bin/env bash
# Build Docker images and package into dist/ for offline deploy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DIST="$REPO/dist"

echo "Create-Dist — Repo: $REPO"

echo "[pre-flight] Checking wheel artifacts..."
PREFLIGHT_OK=1
for d in agent_server rag_retrieval_server; do
  if [[ ! -f "$REPO/$d/dist/requirements.txt" ]]; then
    echo "       MISSING: $d/dist/requirements.txt"
    PREFLIGHT_OK=0
  fi
done
if [[ "$PREFLIGHT_OK" -eq 0 ]]; then
  echo "Run: setup/scripts/local-build/local-build.sh -all"
  exit 1
fi

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
docker compose -f "$REPO/docker-compose.yml" --env-file "$REPO/.env" build

for img in \
  "postgis/postgis:16-3.4" \
  "redis:7-alpine" \
  "arizephoenix/phoenix:20.3.0" \
  "quay.io/keycloak/keycloak:25.0.2"
do
  docker image inspect "$img" >/dev/null 2>&1 || docker pull "$img"
done

rm -rf "$DIST"
mkdir -p "$DIST"

docker save -o "$DIST/all-images.tar" \
  aana_core_services-frontend \
  aana_core_services-agent_server \
  aana_core_services-rag_retrieval_server \
  postgis/postgis:16-3.4 \
  redis:7-alpine \
  arizephoenix/phoenix:20.3.0 \
  quay.io/keycloak/keycloak:25.0.2

cp "$REPO/docker-compose.yml" "$DIST/docker-compose.yml"
cp "$REPO/.env"               "$DIST/.env"
sed -i 's/\${USERPROFILE}/\${HOME}/g' "$DIST/.env"

mkdir -p "$DIST/auth_server/realms"
cp "$REPO/auth_server/docker-compose.yml" "$DIST/auth_server/docker-compose.yml"
[[ -f "$REPO/auth_server/.env" ]] && cp "$REPO/auth_server/.env" "$DIST/auth_server/.env"
[[ -d "$REPO/auth_server/realms" ]] && cp -a "$REPO/auth_server/realms/." "$DIST/auth_server/realms/"

mkdir -p "$DIST/setup/certs"
[[ -f "$REPO/setup/certs/tls.crt" ]] && cp "$REPO/setup/certs/tls.crt" "$DIST/setup/certs/tls.crt"
[[ -f "$REPO/setup/certs/tls.key" ]] && cp "$REPO/setup/certs/tls.key" "$DIST/setup/certs/tls.key"
cp "$REPO/setup/certs/generate-certs.sh" "$DIST/setup/certs/generate-certs.sh"

mkdir -p "$DIST/setup/prod_envs/agent_server"
mkdir -p "$DIST/setup/prod_envs/rag_retrieval_server"
[[ -f "$REPO/setup/prod_envs/agent_server/.env" ]] && \
  cp "$REPO/setup/prod_envs/agent_server/.env" "$DIST/setup/prod_envs/agent_server/.env"
[[ -f "$REPO/setup/prod_envs/rag_retrieval_server/.env" ]] && \
  cp "$REPO/setup/prod_envs/rag_retrieval_server/.env" "$DIST/setup/prod_envs/rag_retrieval_server/.env"

mkdir -p "$DIST/setup/scripts/postgres_init_scripts"
[[ -d "$REPO/setup/scripts/postgres_init_scripts" ]] && \
  cp -a "$REPO/setup/scripts/postgres_init_scripts/." "$DIST/setup/scripts/postgres_init_scripts/"

mkdir -p "$DIST/setup/init"
cp "$REPO/setup/init/init.sh" "$DIST/setup/init/init.sh"

cp "$REPO/setup/scripts/deploy/start.sh" "$DIST/start.sh"
chmod +x "$DIST/start.sh" "$DIST/setup/certs/generate-certs.sh" "$DIST/setup/init/init.sh"

echo "dist/ ready."
