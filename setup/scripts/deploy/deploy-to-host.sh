#!/usr/bin/env bash
# ============================================================================
#  Deploy AAN stack to a new hostname (Linux).
#
#  Usage:
#    setup/scripts/deploy/deploy-to-host.sh <hostname> <smb-user> <smb-password> [options]
#
#  Options:
#    --network_bill <path>     Override network BIL share path
#    --eds_url <host:port>     Override EDS API host:port
#    --cwe_url <host:port>     Override CWE API host:port
#
#  Example:
#    setup/scripts/deploy/deploy-to-host.sh grgd-scm-vm01.ap.teo.earth chandan 'MyP@ss'
#    setup/scripts/deploy/deploy-to-host.sh host.domain user pass --eds_url newhost:8687
#
#  Prerequisites:
#    - Run setup/scripts/local-build/local-build.sh -all  FIRST
#      (builds wheels + requirements into each service's dist/ folder)
#
#  Steps:
#    1.  docker compose down  (auth_server)
#    2.  docker compose down  (root / core services)
#    3.  Check required ports are free
#    4.  Generate TLS certificate for new hostname
#    5.  (reserved — Keycloak volume removal, currently disabled)
#    6.  Rewrite hostname / credentials in .env files
#    7.  docker compose build (builds images from pre-built dist/ wheels)
#    8.  docker compose up -d (auth_server — Keycloak first, creates external network)
#    9.  docker compose up -d (root — core services)
# ============================================================================

set -euo pipefail

usage() {
  echo "==============================================================="
  echo "  AAN Deploy-to-Host — Build and deploy the full stack"
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
  echo "    $(basename "$0") host.domain user pass --eds_url newhost:8687"
  echo "    $(basename "$0") host.domain user pass --network_bill //server/share --eds_url h:8687 --cwe_url h:9984"
  echo
  echo "  Prerequisites:"
  echo "    Run setup/scripts/local-build/local-build.sh -all FIRST"
}

# -----------------------------------------------------------------------
# Validate minimum arguments
# -----------------------------------------------------------------------
if [[ $# -lt 3 ]]; then
  usage
  exit 1
fi

NEW_HOST="$1"
SMB_USER="$2"
SMB_PASS="$3"
shift 3

# Initialize optional flags (empty = use defaults)
OPT_NETWORK_BILL=""
OPT_EDS_URL=""
OPT_CWE_URL=""

# Parse optional flags
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

# -----------------------------------------------------------------------
# Locate repo root (script lives in setup/scripts/deploy/)
# -----------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO"

echo "==============================================================="
echo "  AAN Deploy-to-Host  (Linux)"
echo "  Hostname : $NEW_HOST"
echo "  SMB User : $SMB_USER"
echo "  Repo     : $REPO"
[[ -n "$OPT_NETWORK_BILL" ]] && echo "  Network BIL : $OPT_NETWORK_BILL"
[[ -n "$OPT_EDS_URL" ]] && echo "  EDS URL     : $OPT_EDS_URL"
[[ -n "$OPT_CWE_URL" ]] && echo "  CWE URL     : $OPT_CWE_URL"
echo "==============================================================="
echo

# -----------------------------------------------------------------------
# Helper: rewrite a key=value line in a file
#   usage: set_env <file> <KEY> <new-value>
# -----------------------------------------------------------------------
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
#  STEP 1 — docker compose down (auth_server)
# =====================================================================
echo "[1/9] Stopping auth_server containers..."
if docker compose -f "$REPO/auth_server/docker-compose.yml" \
     --env-file "$REPO/auth_server/.env" down; then
  echo "       OK"
else
  echo "       WARNING: auth_server compose down returned an error (may already be stopped)"
fi
echo

# =====================================================================
#  STEP 2 — docker compose down (core services)
# =====================================================================
echo "[2/9] Stopping core-service containers..."
if docker compose -f "$REPO/docker-compose.yml" \
     --env-file "$REPO/.env" down; then
  echo "       OK"
else
  echo "       WARNING: core compose down returned an error (may already be stopped)"
fi
echo

# =====================================================================
#  STEP 3 — Check required ports are free
# =====================================================================
echo "[3/9] Checking required ports are free..."
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
echo "       OK — all ports free"
echo

# =====================================================================
#  STEP 4 — Generate TLS certificate
# =====================================================================
echo "[4/9] Generating TLS certificate for $NEW_HOST..."
CERT_SCRIPT="$REPO/setup/certs/generate-certs.sh"
if [[ ! -f "$CERT_SCRIPT" ]]; then
  echo "       ERROR: $CERT_SCRIPT not found"
  exit 1
fi
chmod +x "$CERT_SCRIPT"
bash "$CERT_SCRIPT" "$NEW_HOST" 365
echo "       OK"
echo

# =====================================================================
#  STEP 5 — Remove Keycloak Postgres volume (force realm re-import)
# =====================================================================
# echo "[5/9] Removing Keycloak DB volume (forces fresh realm import)..."
# if docker volume rm aana_auth_server_keycloak_postgres_data 2>/dev/null; then
#   echo "       OK — volume removed"
# else
#   echo "       WARNING: Volume not found or already removed — continuing"
# fi
# echo

# =====================================================================
#  STEP 6 — Rewrite .env files
# =====================================================================
echo "[6/9] Updating environment files..."

# --- 6a) .env (root) ---
echo "       6a) .env  (SMB_USERNAME, SMB_PASSWORD, VITE_KEYCLOAK_URL, TEOCO_DATA_DIR)"
set_env "$REPO/.env" "SMB_USERNAME"      "$SMB_USER"
set_env "$REPO/.env" "SMB_PASSWORD"      "$SMB_PASS"
set_env "$REPO/.env" "VITE_KEYCLOAK_URL" "https://${NEW_HOST}:8443"
set_env "$REPO/.env" "TEOCO_DATA_DIR"    "\${HOME}/teoco_data_store"
echo "       OK"

# --- 6b) auth_server/.env ---
echo "       6b) auth_server/.env  (KC_HOSTNAME)"
set_env "$REPO/auth_server/.env" "KC_HOSTNAME" "$NEW_HOST"
echo "       OK"

# --- 6c) setup/prod_envs/agent_server/.env ---
echo "       6c) setup/prod_envs/agent_server/.env  (KEYCLOAK_ISSUER)"
BE_ENV="$REPO/setup/prod_envs/agent_server/.env"
if [[ -f "$BE_ENV" ]]; then
  set_env "$BE_ENV" "KEYCLOAK_ISSUER" "https://${NEW_HOST}:8443"
  echo "       OK"
else
  echo "       SKIP — file not found"
fi

# --- 6d) setup/prod_envs/asp_backend/.env ---
echo "       6d) setup/prod_envs/asp_backend/.env  (KEYCLOAK_ISSUER)"
ACSS_ENV="$REPO/setup/prod_envs/asp_backend/.env"
if [[ -f "$ACSS_ENV" ]]; then
  set_env "$ACSS_ENV" "KEYCLOAK_ISSUER" "https://${NEW_HOST}:8443"
  echo "       OK"
else
  echo "       SKIP — file not found"
fi

# =====================================================================
#  STEP 6e-g — Apply optional overrides (--network_bill, --eds_url, --cwe_url)
# =====================================================================
PIPE_ENV="$REPO/setup/prod_envs/pipeline/.env"

if [[ -n "$OPT_NETWORK_BILL" ]]; then
  echo "       6e) Applying --network_bill override: $OPT_NETWORK_BILL"
  # Convert to UNC path format (backslashes) for env files
  NET_UNC="${OPT_NETWORK_BILL//\//\\}"
  
  # .env (root): NETWORK_BIL_PATH (used by docker-compose.yml)
  ENV_FILE="$REPO/.env"
  if [[ -f "$ENV_FILE" ]]; then
    set_env "$ENV_FILE" "NETWORK_BIL_PATH" "$OPT_NETWORK_BILL"
    echo "            .env NETWORK_BIL_PATH updated"
  fi
  
  # asp_backend/.env: COVERAGE_ROOT_OUTPUT_LOCATION
  if [[ -f "$ACSS_ENV" ]]; then
    set_env "$ACSS_ENV" "COVERAGE_ROOT_OUTPUT_LOCATION" "$NET_UNC"
    echo "            asp_backend/.env COVERAGE_ROOT_OUTPUT_LOCATION updated"
  fi
  
  # agent_server/.env: ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION
  if [[ -f "$BE_ENV" ]]; then
    set_env "$BE_ENV" "ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION" "$NET_UNC"
    echo "            agent_server/.env ROOT_OUTPUT_LOCATION_ROOT_OUTPUT_LOCATION updated"
  fi
fi

if [[ -n "$OPT_EDS_URL" ]]; then
  echo "       6f) Applying --eds_url override: $OPT_EDS_URL"
  
  # asp_backend/.env: EDS_CREATE_URL, EDS_DELETE_URL
  if [[ -f "$ACSS_ENV" ]]; then
    set_env "$ACSS_ENV" "EDS_CREATE_URL" "http://${OPT_EDS_URL}/v1/EDS/Create"
    set_env "$ACSS_ENV" "EDS_DELETE_URL" "http://${OPT_EDS_URL}/v1/EDS/Delete"
    echo "            asp_backend/.env EDS_CREATE_URL, EDS_DELETE_URL updated"
  fi
  
  # agent_server/.env: EDS_API_BASE_URL, EDS_UPDATE_URL
  if [[ -f "$BE_ENV" ]]; then
    set_env "$BE_ENV" "EDS_API_BASE_URL" "http://${OPT_EDS_URL}/v1/EDS/Update/"
    set_env "$BE_ENV" "EDS_UPDATE_URL" "http://${OPT_EDS_URL}/v1/EDS/Update"
    echo "            agent_server/.env EDS_API_BASE_URL, EDS_UPDATE_URL updated"
  fi
  
  # pipeline/.env: EDS_API_BASE_URL
  if [[ -f "$PIPE_ENV" ]]; then
    set_env "$PIPE_ENV" "EDS_API_BASE_URL" "http://${OPT_EDS_URL}/v1/EDS/Query/"
    echo "            pipeline/.env EDS_API_BASE_URL updated"
  fi
fi

if [[ -n "$OPT_CWE_URL" ]]; then
  echo "       6g) Applying --cwe_url override: $OPT_CWE_URL"
  
  # asp_backend/.env: COVERAGE_API_CREATE_ENDPOINT, COVERAGE_API_STATUS_ENDPOINT
  if [[ -f "$ACSS_ENV" ]]; then
    set_env "$ACSS_ENV" "COVERAGE_API_CREATE_ENDPOINT" "http://${OPT_CWE_URL}/v1/CWE/create"
    set_env "$ACSS_ENV" "COVERAGE_API_STATUS_ENDPOINT" "http://${OPT_CWE_URL}/v1/CWE/query"
    echo "            asp_backend/.env COVERAGE_API_CREATE_ENDPOINT, COVERAGE_API_STATUS_ENDPOINT updated"
  fi
  
  # agent_server/.env: COVERAGE_API_CREATE_COVERAGE_ENDPOINT, COVERAGE_API_STATUS_POLLING_ENDPOINT
  if [[ -f "$BE_ENV" ]]; then
    set_env "$BE_ENV" "COVERAGE_API_CREATE_COVERAGE_ENDPOINT" "http://${OPT_CWE_URL}/v1/CWE/create"
    set_env "$BE_ENV" "COVERAGE_API_STATUS_POLLING_ENDPOINT" "http://${OPT_CWE_URL}/v1/CWE/query/"
    echo "            agent_server/.env COVERAGE_API_CREATE_COVERAGE_ENDPOINT, COVERAGE_API_STATUS_POLLING_ENDPOINT updated"
  fi
fi
echo

# =====================================================================
#  STEP 7 — docker compose build (core services)
#  BuildKit is required for --mount=type=cache in Dockerfiles.
# =====================================================================
echo "[7/9] Building Docker images from pre-built dist/ wheels..."
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
docker compose -f "$REPO/docker-compose.yml" --env-file "$REPO/.env" build
echo "       OK"
echo

# =====================================================================
#  STEP 8 — docker compose up -d (auth_server — must start first)
# =====================================================================
echo "[8/9] Starting auth_server (Keycloak)..."
docker compose -f "$REPO/auth_server/docker-compose.yml" \
  --env-file "$REPO/auth_server/.env" up -d
echo "       OK"
echo

# =====================================================================
#  STEP 9 — docker compose up -d (core services)
# =====================================================================
echo "[9/9] Starting core services..."
docker compose -f "$REPO/docker-compose.yml" --env-file "$REPO/.env" up -d
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
echo "  Tip: If you see stale Keycloak tokens, clear browser localStorage."
echo "==============================================================="
