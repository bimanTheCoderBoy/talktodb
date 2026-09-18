#!/usr/bin/env bash
# ============================================================================
#  AAN Start — Load Docker images and launch the full stack.
#
#  Usage:
#    start.sh <hostname> <smb-user> <smb-password> [options]
#
#  Options:
#    --network_bill <path>     Override network BIL share path
#    --eds_url <host:port>     Override EDS API host:port
#    --cwe_url <host:port>     Override CWE API host:port
#
#  Example:
#    ./start.sh grgd-scm-vm01.ap.teo.earth chandan 'MyP@ss'
#    ./start.sh grgd-scm-vm01.ap.teo.earth chandan 'MyP@ss' --eds_url newhost:8687
#
#  Prerequisites:
#    - Docker running
#    - This folder was created by create-dist.sh
# ============================================================================

set -euo pipefail

usage() {
  echo "==============================================================="
  echo "  AAN Start — Load images and launch the full stack"
  echo "==============================================================="
  echo
  echo "  Usage: $(basename "$0") <hostname> <smb-user> <smb-password> [options]"
  echo
  echo "  Options:"
  echo "    --network_bill <path>     Override network BIL share path"
  echo "                              e.g. //newserver.domain/Mapdata/Bil_files"
  echo "    --eds_url <host:port>     Override EDS API host:port"
  echo "                              e.g. newhost.domain:8687"
  echo "    --cwe_url <host:port>     Override CWE API host:port"
  echo "                              e.g. newhost.domain:9984"
  echo
  echo "  Example:"
  echo "    $(basename "$0") grgd-scm-vm01.ap.teo.earth chandan 'MyP@ss'"
  echo "    $(basename "$0") grgd-scm-vm01.ap.teo.earth chandan 'MyP@ss' --eds_url newhost:8687"
  echo "    $(basename "$0") host.domain user pass --network_bill //server/share --eds_url h:8687 --cwe_url h:9984"
  echo
  echo "  Use single quotes around the password if it contains ! or \$"
  echo
  echo "  The hostname is used for:"
  echo "    - TLS certificate generation"
  echo "    - Keycloak URL (https://<hostname>:8443)"
  echo "    - Frontend Keycloak config (runtime injection)"
  echo "    - Backend KEYCLOAK_ISSUER"
  echo
  echo "  SMB credentials are used for the network map data volume."
}

# --- Validate minimum arguments ---
if [[ $# -lt 3 ]]; then
  usage
  exit 1
fi

NEW_HOST="$1"
SMB_USER="$2"
SMB_PASS="$3"
shift 3

# --- Initialize optional flags (empty = use defaults) ---
OPT_NETWORK_BILL=""
OPT_EDS_URL=""
OPT_CWE_URL=""

# --- Parse optional flags ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --network_bill)
      OPT_NETWORK_BILL="$2"
      shift 2
      ;;
    --eds_url)
      OPT_EDS_URL="$2"
      shift 2
      ;;
    --cwe_url)
      OPT_CWE_URL="$2"
      shift 2
      ;;
    *)
      echo "WARNING: Unknown option '$1' — ignoring"
      shift
      ;;
  esac
done

# --- Locate dist root (start.sh lives at dist root) ---
DIST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==============================================================="
echo "  AAN Start  (Linux)"
echo "  Hostname : $NEW_HOST"
echo "  SMB User : $SMB_USER"
echo "  Dist     : $DIST"
[[ -n "$OPT_NETWORK_BILL" ]] && echo "  Network BIL : $OPT_NETWORK_BILL"
[[ -n "$OPT_EDS_URL" ]] && echo "  EDS URL     : $OPT_EDS_URL"
[[ -n "$OPT_CWE_URL" ]] && echo "  CWE URL     : $OPT_CWE_URL"
echo "==============================================================="
echo

# Helper: rewrite a key=value line in a file
#   usage: set_env <file> <KEY> <new-value>
set_env() {
  local file="$1" key="$2" val="$3"
  if [[ ! -f "$file" ]]; then
    echo "        SKIP — $file not found"
    return 0
  fi
  awk -v k="$key" -v v="$val" '
    BEGIN { done=0 }
    index($0, k "=") == 1 && !done { print k "=" v; done=1; next }
    { print }
  ' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
}

# =====================================================================
#  SUBROUTINE: apply_network_bill
#  Updates .env files for network BIL path (full path like //server/share)
# =====================================================================
apply_network_bill() {
  local _NET_PATH="$1"
  # Convert forward slashes to UNC format for env files (backslashes)
  local _NET_UNC="${_NET_PATH//\//\\}"

  # --- .env (root): NETWORK_BIL_PATH (used by docker-compose.yml) ---
  if [[ -f "$ENV_FILE" ]]; then
    set_env "$ENV_FILE" "NETWORK_BIL_PATH" "$_NET_PATH"
    echo "            .env NETWORK_BIL_PATH updated"
  fi

  # --- setup/prod_envs/asp_backend/.env: COVERAGE_ROOT_OUTPUT_LOCATION ---
  if [[ -f "$ACSS_ENV" ]]; then
    set_env "$ACSS_ENV" "COVERAGE_ROOT_OUTPUT_LOCATION" "$_NET_UNC"
    echo "            asp_backend/.env COVERAGE_ROOT_OUTPUT_LOCATION updated"
  fi

  # --- setup/prod_envs/agent_server/.env: ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION ---
  if [[ -f "$BE_ENV" ]]; then
    set_env "$BE_ENV" "ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION" "$_NET_UNC"
    echo "            agent_server/.env ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION updated"
  fi
}

# =====================================================================
#  SUBROUTINE: apply_eds_url
#  Updates EDS API URLs in all relevant env files
# =====================================================================
apply_eds_url() {
  local _EDS_HOST="$1"

  # --- setup/prod_envs/asp_backend/.env ---
  if [[ -f "$ACSS_ENV" ]]; then
    set_env "$ACSS_ENV" "EDS_CREATE_URL" "http://${_EDS_HOST}/v1/EDS/Create"
    set_env "$ACSS_ENV" "EDS_DELETE_URL" "http://${_EDS_HOST}/v1/EDS/Delete"
    echo "            asp_backend/.env EDS_CREATE_URL, EDS_DELETE_URL updated"
  fi

  # --- setup/prod_envs/agent_server/.env ---
  if [[ -f "$BE_ENV" ]]; then
    set_env "$BE_ENV" "EDS_API_BASE_URL" "http://${_EDS_HOST}/v1/EDS/Update/"
    set_env "$BE_ENV" "EDS_UPDATE_URL" "http://${_EDS_HOST}/v1/EDS/Update"
    echo "            agent_server/.env EDS_API_BASE_URL, EDS_UPDATE_URL updated"
  fi

  # --- setup/prod_envs/pipeline/.env ---
  PIPE_ENV="$DIST/setup/prod_envs/pipeline/.env"
  if [[ -f "$PIPE_ENV" ]]; then
    set_env "$PIPE_ENV" "EDS_API_BASE_URL" "http://${_EDS_HOST}/v1/EDS/Query/"
    echo "            pipeline/.env EDS_API_BASE_URL updated"
  fi
}

# =====================================================================
#  SUBROUTINE: apply_cwe_url
#  Updates CWE (Coverage) API URLs in all relevant env files
# =====================================================================
apply_cwe_url() {
  local _CWE_HOST="$1"

  # --- setup/prod_envs/asp_backend/.env ---
  if [[ -f "$ACSS_ENV" ]]; then
    set_env "$ACSS_ENV" "COVERAGE_API_CREATE_ENDPOINT" "http://${_CWE_HOST}/v1/CWE/create"
    set_env "$ACSS_ENV" "COVERAGE_API_STATUS_ENDPOINT" "http://${_CWE_HOST}/v1/CWE/query"
    echo "            asp_backend/.env COVERAGE_API_CREATE_ENDPOINT, COVERAGE_API_STATUS_ENDPOINT updated"
  fi

  # --- setup/prod_envs/agent_server/.env ---
  if [[ -f "$BE_ENV" ]]; then
    set_env "$BE_ENV" "COVERAGE_API_CREATE_COVERAGE_ENDPOINT" "http://${_CWE_HOST}/v1/CWE/create"
    set_env "$BE_ENV" "COVERAGE_API_STATUS_POLLING_ENDPOINT" "http://${_CWE_HOST}/v1/CWE/query/"
    echo "            agent_server/.env COVERAGE_API_CREATE_COVERAGE_ENDPOINT, COVERAGE_API_STATUS_POLLING_ENDPOINT updated"
  fi
}

# =====================================================================
#  STEP 1 — Stop any running containers
# =====================================================================
echo "[1/10] Stopping auth_server containers (if running)..."
docker compose -f "$DIST/auth_server/docker-compose.yml" --env-file "$DIST/auth_server/.env" down >/dev/null 2>&1 || true
echo "       OK"
echo

echo "[2/10] Stopping core-service containers (if running)..."
docker compose -f "$DIST/docker-compose.yml" --env-file "$DIST/.env" down >/dev/null 2>&1 || true
echo "       OK"
echo

# =====================================================================
#  STEP 3 — Check required ports are free
# =====================================================================
echo "[3/10] Checking required ports are free..."
PORTS=(8443 8001 80 443 8502 4317 6006 9999 5432 8003 8009 6379 5433 8002 8010)
BLOCKED=0
for p in "${PORTS[@]}"; do
  if ss -tln 2>/dev/null | grep -qE ":${p}([[:space:]]|$)" || \
     netstat -tln 2>/dev/null | grep -qE ":${p}([[:space:]]|$)"; then
    echo "       BLOCKED: port $p is in use"
    BLOCKED=1
  fi
done
if [[ $BLOCKED -eq 1 ]]; then
  echo
  echo "       ERROR: One or more required ports are occupied. Free them and retry."
  exit 1
fi
echo "       OK"
echo

# =====================================================================
#  STEP 4 — Generate TLS certificate for the hostname
# =====================================================================
echo "[4/10] Generating TLS certificate for $NEW_HOST..."
CERT_SCRIPT="$DIST/setup/certs/generate-certs.sh"
if [[ ! -f "$CERT_SCRIPT" ]]; then
  echo "       ERROR: $CERT_SCRIPT not found"
  exit 1
fi
chmod +x "$CERT_SCRIPT"
if ! bash "$CERT_SCRIPT" "$NEW_HOST" 365; then
  echo "       ERROR: Certificate generation failed"
  exit 1
fi
echo "       OK"
echo

# =====================================================================
#  STEP 5 — Rewrite .env files with hostname and SMB credentials
# =====================================================================
echo "[5/10] Updating environment files for $NEW_HOST..."

# --- 5a) .env (root) ---
echo "       5a) .env  (SMB_USERNAME, SMB_PASSWORD, VITE_KEYCLOAK_URL, TEOCO_DATA_DIR)"
ENV_FILE="$DIST/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "       ERROR writing .env"
  exit 1
fi
set_env "$ENV_FILE" "SMB_USERNAME"      "$SMB_USER"
set_env "$ENV_FILE" "SMB_PASSWORD"      "$SMB_PASS"
set_env "$ENV_FILE" "VITE_KEYCLOAK_URL" "https://${NEW_HOST}:8443"
set_env "$ENV_FILE" "TEOCO_DATA_DIR"    "\${HOME}/teoco_data_store"
echo "       OK"

# --- 5b) auth_server/.env ---
echo "       5b) auth_server/.env  (KC_HOSTNAME)"
AUTH_ENV="$DIST/auth_server/.env"
if [[ -f "$AUTH_ENV" ]]; then
  set_env "$AUTH_ENV" "KC_HOSTNAME" "$NEW_HOST"
  echo "       OK"
else
  echo "       SKIP — auth_server/.env not found"
fi

# --- 5c) setup/prod_envs/agent_server/.env ---
echo "       5c) setup/prod_envs/agent_server/.env  (KEYCLOAK_ISSUER)"
BE_ENV="$DIST/setup/prod_envs/agent_server/.env"
if [[ -f "$BE_ENV" ]]; then
  set_env "$BE_ENV" "KEYCLOAK_ISSUER" "https://${NEW_HOST}:8443"
  echo "       OK"
else
  echo "       SKIP — file not found"
fi

# --- 5d) setup/prod_envs/asp_backend/.env ---
echo "       5d) setup/prod_envs/asp_backend/.env  (KEYCLOAK_ISSUER)"
ACSS_ENV="$DIST/setup/prod_envs/asp_backend/.env"
if [[ -f "$ACSS_ENV" ]]; then
  set_env "$ACSS_ENV" "KEYCLOAK_ISSUER" "https://${NEW_HOST}:8443"
  echo "       OK"
else
  echo "       SKIP — file not found"
fi

# =====================================================================
#  STEP 5e — Apply optional overrides (--network_bill, --eds_url, --cwe_url)
# =====================================================================
if [[ -n "$OPT_NETWORK_BILL" ]]; then
  echo "       5e - Applying --network_bill override: $OPT_NETWORK_BILL"
  apply_network_bill "$OPT_NETWORK_BILL"
fi

if [[ -n "$OPT_EDS_URL" ]]; then
  echo "       5f - Applying --eds_url override: $OPT_EDS_URL"
  apply_eds_url "$OPT_EDS_URL"
fi

if [[ -n "$OPT_CWE_URL" ]]; then
  echo "       5g - Applying --cwe_url override: $OPT_CWE_URL"
  apply_cwe_url "$OPT_CWE_URL"
fi
echo

# =====================================================================
#  STEP 6 — Load all Docker images from tar
# =====================================================================
echo "[6/10] Loading Docker images from all-images.tar (this may take a while)..."
if ! docker load -i "$DIST/all-images.tar"; then
  echo "       ERROR: docker load failed"
  exit 1
fi
echo "       OK"
echo

# =====================================================================
#  STEP 7 — Create TEOCO data store directory
# =====================================================================
echo "[7/10] Ensuring TEOCO data store directory exists..."
if [[ ! -d "$HOME/teoco_data_store" ]]; then
  mkdir -p "$HOME/teoco_data_store"
  echo "       Created $HOME/teoco_data_store"
else
  echo "       Already exists"
fi
echo

# =====================================================================
#  STEP 8 — Copy initial seed data into teoco_data_store
# =====================================================================
echo "[8/10] Copying initial config data to teoco_data_store..."
INIT_SH="$DIST/setup/init/init.sh"
if [[ -f "$INIT_SH" ]]; then
  chmod +x "$INIT_SH"
  if ! bash "$INIT_SH"; then
    echo "       ERROR: init.sh failed"
    exit 1
  fi
  echo "       OK"
else
  echo "       SKIP — init.sh not found"
fi
echo

# =====================================================================
#  STEP 9 — Start auth_server (Keycloak must start first)
# =====================================================================
echo "[9/10] Starting auth_server (Keycloak)..."
if ! docker compose -f "$DIST/auth_server/docker-compose.yml" --env-file "$DIST/auth_server/.env" up -d; then
  echo "       ERROR: auth_server compose up failed"
  exit 1
fi
echo "       OK"
echo

# =====================================================================
#  STEP 10 — Start core services
# =====================================================================
echo "[10/10] Starting core services..."
if ! docker compose -f "$DIST/docker-compose.yml" --env-file "$DIST/.env" up -d; then
  echo "       ERROR: core compose up failed"
  exit 1
fi
echo "       OK"
echo

# =====================================================================
#  Done
# =====================================================================
echo "==============================================================="
echo "  Deployment complete!"
echo
echo "  Keycloak : https://${NEW_HOST}:8443"
echo "  Frontend : https://${NEW_HOST}"
echo "  Dozzle   : http://${NEW_HOST}:9999"
echo "  Pipeline : http://${NEW_HOST}:8502"
echo "  Phoenix  : http://${NEW_HOST}:6006"
echo "  RAG      : http://${NEW_HOST}:8010"
echo
echo "  Tip: If you see certificate warnings, that's expected (self-signed)."
echo "  Tip: If you see stale Keycloak tokens, clear browser localStorage."
echo "==============================================================="

exit 0
