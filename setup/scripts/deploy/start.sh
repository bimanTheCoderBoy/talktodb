#!/usr/bin/env bash
# talkToDB — load dist images and start Keycloak + core stack.
#
# Usage: ./start.sh <hostname>
# Example: ./start.sh myhost.example.com
#
# Prerequisites: dist/ from create-dist.sh, Docker running.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $(basename "$0") <hostname>"
  echo "  Sets TLS cert, VITE_KEYCLOAK_URL, KEYCLOAK_ISSUER, TALKTODB_DATA_DIR"
  exit 1
fi

NEW_HOST="$1"
DIST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

set_env() {
  local file="$1" key="$2" val="$3"
  [[ -f "$file" ]] || return 0
  awk -v k="$key" -v v="$val" '
    BEGIN { done=0 }
    index($0, k "=") == 1 && !done { print k "=" v; done=1; next }
    { print }
  ' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
}

echo "==============================================================="
echo "  talkToDB start"
echo "  Hostname: $NEW_HOST"
echo "  Dist:     $DIST"
echo "==============================================================="

echo "[1/8] Stopping existing containers..."
docker compose -f "$DIST/auth_server/docker-compose.yml" --env-file "$DIST/auth_server/.env" down >/dev/null 2>&1 || true
docker compose -f "$DIST/docker-compose.yml" --env-file "$DIST/.env" down >/dev/null 2>&1 || true

echo "[2/8] Checking ports..."
PORTS=(8443 80 443 5432 6379 6006 4317 8010)
for p in "${PORTS[@]}"; do
  if ss -tln 2>/dev/null | grep -qE ":${p}([[:space:]]|$)" || \
     netstat -tln 2>/dev/null | grep -qE ":${p}([[:space:]]|$)"; then
    echo "  BLOCKED: port $p is in use"
    exit 1
  fi
done

echo "[3/8] TLS certificate for $NEW_HOST..."
CERT_SCRIPT="$DIST/setup/certs/generate-certs.sh"
[[ -f "$CERT_SCRIPT" ]] || { echo "Missing $CERT_SCRIPT"; exit 1; }
chmod +x "$CERT_SCRIPT"
bash "$CERT_SCRIPT" "$NEW_HOST" 365

ENV_FILE="$DIST/.env"
set_env "$ENV_FILE" "VITE_KEYCLOAK_URL" "https://${NEW_HOST}:8443"
set_env "$ENV_FILE" "TALKTODB_DATA_DIR" "\${HOME}/talktodb_data"

BE_ENV="$DIST/setup/prod_envs/agent_server/.env"
if [[ -f "$BE_ENV" ]]; then
  set_env "$BE_ENV" "KEYCLOAK_ISSUER" "https://${NEW_HOST}:8443"
fi

AUTH_ENV="$DIST/auth_server/.env"
if [[ -f "$AUTH_ENV" ]]; then
  set_env "$AUTH_ENV" "KC_HOSTNAME" "$NEW_HOST"
fi

echo "[4/8] Loading Docker images..."
docker load -i "$DIST/all-images.tar"

echo "[5/8] Data store layout..."
mkdir -p "$HOME/talktodb_data"
INIT_SH="$DIST/setup/init/init.sh"
if [[ -f "$INIT_SH" ]]; then
  chmod +x "$INIT_SH"
  TALKTODB_DATA_DIR="$HOME/talktodb_data" bash "$INIT_SH"
fi

echo "[6/8] Starting Keycloak..."
docker compose -f "$DIST/auth_server/docker-compose.yml" --env-file "$DIST/auth_server/.env" up -d

echo "[7/8] Starting talkToDB services..."
docker compose -f "$DIST/docker-compose.yml" --env-file "$DIST/.env" up -d

echo "[8/8] Done."
echo "  Keycloak : https://${NEW_HOST}:8443"
echo "  Frontend : https://${NEW_HOST}"
echo "  RAG      : http://${NEW_HOST}:8010"
echo "  Phoenix  : http://${NEW_HOST}:6006"
