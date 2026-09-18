#!/usr/bin/env bash
# ============================================================================
#  Build wheels + requirements for backend services.
#
#  Usage (run from repo root or any directory):
#    setup/scripts/local-build/local-build.sh [-asp] [-langgraph] [-pipeline] [-download] [-rag] [-all] [-deps]
#
#  Each flag builds:
#    shared-server-libs wheel (if the target depends on it) +
#    project wheel  -->  <project>/dist/
#
#  The -deps flag forces re-export of requirements.txt even if uv.lock
#  hasn't changed.  Without -deps, requirements.txt is only regenerated
#  when uv.lock changes — this preserves Docker layer cache for the
#  expensive pip-install layer.
# ============================================================================

set -euo pipefail

# --- Locate repo root (script lives in setup/scripts/local-build/) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO"

BUILD_ASP=0
BUILD_LANGGRAPH=0
BUILD_PIPELINE=0
BUILD_DOWNLOAD=0
BUILD_RAG=0
FORCE_DEPS=0

usage() {
  echo "Usage: local-build.sh [-asp] [-langgraph] [-pipeline] [-download] [-rag] [-all] [-deps]"
  echo
  echo "  -asp        Build shared-server-libs + asp_server wheels into asp_server/dist"
  echo "  -langgraph  Build shared-server-libs + agent_server wheels into agent_server/dist"
  echo "  -pipeline   Build shared-server-libs + pipeline wheels into pipeline/dist"
  echo "  -download   Build download-service wheel into download_service/dist"
  echo "  -rag        Build shared-server-libs + rag_retrieval_server wheels into rag_retrieval_server/dist"
  echo "  -all        Build everything"
  echo "  -deps       Force re-export of requirements.txt even if uv.lock is unchanged"
  echo
  echo "You can combine flags: local-build.sh -asp -langgraph -pipeline -download -rag"
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "${1,,}" in
    -asp)       BUILD_ASP=1 ;;
    -langgraph) BUILD_LANGGRAPH=1 ;;
    -pipeline)  BUILD_PIPELINE=1 ;;
    -download)  BUILD_DOWNLOAD=1 ;;
    -rag)       BUILD_RAG=1 ;;
    -deps)      FORCE_DEPS=1 ;;
    -all)
      BUILD_ASP=1
      BUILD_LANGGRAPH=1
      BUILD_PIPELINE=1
      BUILD_DOWNLOAD=1
      BUILD_RAG=1
      ;;
  esac
  shift
done

if [[ "$BUILD_ASP" -eq 0 && "$BUILD_LANGGRAPH" -eq 0 && "$BUILD_PIPELINE" -eq 0 && "$BUILD_DOWNLOAD" -eq 0 && "$BUILD_RAG" -eq 0 ]]; then
  echo "ERROR: No valid build target specified."
  exit 1
fi

echo
echo "==============================================================="
echo "  AAN Local Build"
echo "  Repo: $REPO"
echo "==============================================================="
echo

# =====================================================================
#  Compute uv.lock hash to decide whether requirements.txt needs
#  regeneration.  Each service stores the hash it was last exported
#  against in dist/.lock-hash.
# =====================================================================
LOCK_FILE="$REPO/uv.lock"
CURRENT_LOCK_HASH=""
if [[ -f "$LOCK_FILE" ]]; then
  if command -v sha256sum >/dev/null 2>&1; then
    CURRENT_LOCK_HASH=$(sha256sum "$LOCK_FILE" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    CURRENT_LOCK_HASH=$(shasum -a 256 "$LOCK_FILE" | awk '{print $1}')
  fi
fi
if [[ -z "$CURRENT_LOCK_HASH" ]]; then
  echo "WARNING: Could not hash uv.lock — will force requirements export"
  FORCE_DEPS=1
fi

maybe_export_reqs() {
  # Usage: maybe_export_reqs <service_dir> <uv_package_name> <dist_dir>
  #
  # Re-exports requirements.txt only when uv.lock has changed since the
  # last export (or when -deps was passed).  Saves the lock hash into
  # dist/.lock-hash so subsequent builds skip the export and preserve
  # the Docker layer cache.
  local svc_dir="$1"
  local pkg_name="$2"
  local dist_dir="$3"
  local marker="${dist_dir}/.lock-hash"
  local need_export=0
  local old_hash=""

  if [[ "$FORCE_DEPS" -eq 1 ]]; then
    need_export=1
  fi
  if [[ ! -f "${dist_dir}/requirements.txt" ]]; then
    need_export=1
  fi

  if [[ "$need_export" -eq 0 ]]; then
    if [[ -f "$marker" ]]; then
      old_hash=$(tr -d '\r\n' < "$marker")
    fi
    if [[ "$old_hash" != "$CURRENT_LOCK_HASH" ]]; then
      need_export=1
    fi
  fi

  if [[ "$need_export" -eq 1 ]]; then
    echo "=== Exporting ${svc_dir} requirements.txt  (deps changed) ==="
    uv export --no-hashes --no-dev --no-emit-project --no-emit-workspace \
      --package "$pkg_name" -o "${dist_dir}/requirements.txt"
    printf '%s\n' "$CURRENT_LOCK_HASH" > "$marker"
  else
    echo "=== Skipping ${svc_dir} requirements.txt  (uv.lock unchanged — Docker cache preserved) ==="
  fi
}

prepare_dist() {
  local dist_dir="$1"
  mkdir -p "$dist_dir"
  rm -f "$dist_dir"/*.whl
}

# === Build shared-server-libs + wheels (preserve dist/requirements.txt) ===

if [[ "$BUILD_ASP" -eq 1 ]]; then
  echo "=== [shared-server-libs] Building for asp_server ==="
  prepare_dist "asp_server/dist"
  uv build shared_server_libs --wheel --out-dir asp_server/dist
fi

if [[ "$BUILD_LANGGRAPH" -eq 1 ]]; then
  echo "=== [shared-server-libs] Building for agent_server ==="
  prepare_dist "agent_server/dist"
  uv build shared_server_libs --wheel --out-dir agent_server/dist
fi

if [[ "$BUILD_PIPELINE" -eq 1 ]]; then
  echo "=== [shared-server-libs] Building for pipeline ==="
  prepare_dist "pipeline/dist"
  uv build shared_server_libs --wheel --out-dir pipeline/dist
fi

if [[ "$BUILD_DOWNLOAD" -eq 1 ]]; then
  echo "=== [download-service] Preparing dist ==="
  prepare_dist "download_service/dist"
fi

if [[ "$BUILD_RAG" -eq 1 ]]; then
  echo "=== [shared-server-libs] Building for rag_retrieval_server ==="
  prepare_dist "rag_retrieval_server/dist"
  uv build shared_server_libs --wheel --out-dir rag_retrieval_server/dist
fi

# === Build ASP (asp_server) ===
if [[ "$BUILD_ASP" -eq 1 ]]; then
  echo
  echo "=== Building asp-server wheel ==="
  uv build asp_server --wheel --out-dir asp_server/dist
  maybe_export_reqs asp_server asp-server "asp_server/dist"
  echo
  echo "[ASP] Build artifacts:"
  ls -1 asp_server/dist/*.whl
  echo "requirements.txt: asp_server/dist/requirements.txt"
  echo
fi

# === Build LangGraph (agent_server) ===
if [[ "$BUILD_LANGGRAPH" -eq 1 ]]; then
  echo
  echo "=== Building agent_server wheel ==="
  uv build agent_server --wheel --out-dir agent_server/dist
  maybe_export_reqs agent_server agent-server "agent_server/dist"
  echo
  echo "[LangGraph] Build artifacts:"
  ls -1 agent_server/dist/*.whl
  echo "requirements.txt: agent_server/dist/requirements.txt"
  echo
fi

# === Build Pipeline ===
if [[ "$BUILD_PIPELINE" -eq 1 ]]; then
  echo
  echo "=== Building pipeline wheel ==="
  uv build pipeline --wheel --out-dir pipeline/dist
  maybe_export_reqs pipeline eds-pipeline "pipeline/dist"
  echo
  echo "[Pipeline] Build artifacts:"
  ls -1 pipeline/dist/*.whl
  echo "requirements.txt: pipeline/dist/requirements.txt"
  echo
fi

# === Build Download Service ===
if [[ "$BUILD_DOWNLOAD" -eq 1 ]]; then
  echo
  echo "=== Building download-service wheel ==="
  uv build download_service --wheel --out-dir download_service/dist
  maybe_export_reqs download_service download-service "download_service/dist"
  echo
  echo "[Download] Build artifacts:"
  ls -1 download_service/dist/*.whl
  echo "requirements.txt: download_service/dist/requirements.txt"
  echo
fi

# === Build RAG Retrieval Server ===
if [[ "$BUILD_RAG" -eq 1 ]]; then
  echo
  echo "=== Building rag_retrieval_server wheel ==="
  uv build rag_retrieval_server --wheel --out-dir rag_retrieval_server/dist
  maybe_export_reqs rag_retrieval_server rag-retrieval-server "rag_retrieval_server/dist"
  echo
  echo "[RAG] Build artifacts:"
  ls -1 rag_retrieval_server/dist/*.whl
  echo "requirements.txt: rag_retrieval_server/dist/requirements.txt"
  echo
fi

echo
echo "==============================================================="
echo "  Build complete! Next steps:"
echo "==============================================================="
[[ "$BUILD_ASP" -eq 1 ]]       && echo "  ASP:       docker compose build acss_api"
[[ "$BUILD_LANGGRAPH" -eq 1 ]] && echo "  LangGraph: docker compose build agent_server"
[[ "$BUILD_PIPELINE" -eq 1 ]]  && echo "  Pipeline:  docker compose build pipeline_streamlit"
[[ "$BUILD_DOWNLOAD" -eq 1 ]]  && echo "  Download:  docker compose build download_api"
[[ "$BUILD_RAG" -eq 1 ]]       && echo "  RAG:       docker compose build rag_retrieval_server"
echo
echo "  Or run deploy-to-host.sh to build images and deploy."
echo "==============================================================="
echo
