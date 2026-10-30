#!/usr/bin/env bash
# ============================================================================
#  Build wheels + requirements for backend services.
#
#  Usage:
#    setup/scripts/local-build/local-build.sh [-langgraph] [-rag] [-all] [-deps]
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO"

BUILD_LANGGRAPH=0
BUILD_RAG=0
FORCE_DEPS=0

usage() {
  echo "Usage: local-build.sh [-langgraph] [-rag] [-all] [-deps]"
  echo
  echo "  -langgraph  Build shared-server-libs + agent_server wheels into agent_server/dist"
  echo "  -rag        Build shared-server-libs + rag_retrieval_server wheels into rag_retrieval_server/dist"
  echo "  -all        Build everything"
  echo "  -deps       Force re-export of requirements.txt even if uv.lock is unchanged"
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "${1,,}" in
    -langgraph) BUILD_LANGGRAPH=1 ;;
    -rag)       BUILD_RAG=1 ;;
    -deps)      FORCE_DEPS=1 ;;
    -all)
      BUILD_LANGGRAPH=1
      BUILD_RAG=1
      ;;
    *) echo "Unknown flag: $1"; usage; exit 1 ;;
  esac
  shift
done

if [[ "$BUILD_LANGGRAPH" -eq 0 && "$BUILD_RAG" -eq 0 ]]; then
  echo "ERROR: No valid build target specified."
  exit 1
fi

echo
echo "==============================================================="
echo "  Local Build"
echo "  Repo: $REPO"
echo "==============================================================="
echo

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
  local svc_dir="$1"
  local pkg_name="$2"
  local dist_dir="$3"
  local marker="${dist_dir}/.lock-hash"
  local need_export=0
  local old_hash=""

  if [[ "$FORCE_DEPS" -eq 1 ]]; then need_export=1; fi
  if [[ ! -f "${dist_dir}/requirements.txt" ]]; then need_export=1; fi
  if [[ "$need_export" -eq 0 ]]; then
    if [[ -f "$marker" ]]; then old_hash=$(tr -d '\r\n' < "$marker"); fi
    if [[ "$old_hash" != "$CURRENT_LOCK_HASH" ]]; then need_export=1; fi
  fi

  if [[ "$need_export" -eq 1 ]]; then
    echo "=== Exporting ${svc_dir} requirements.txt  (deps changed) ==="
    uv export --no-hashes --no-dev --no-emit-project --no-emit-workspace \
      --package "$pkg_name" -o "${dist_dir}/requirements.txt"
    printf '%s\n' "$CURRENT_LOCK_HASH" > "$marker"
  else
    echo "=== Skipping ${svc_dir} requirements.txt  (uv.lock unchanged) ==="
  fi
}

prepare_dist() {
  mkdir -p "$1"
  rm -f "$1"/*.whl
}

if [[ "$BUILD_LANGGRAPH" -eq 1 ]]; then
  echo "=== [shared-server-libs] Building for agent_server ==="
  prepare_dist "agent_server/dist"
  uv build shared_server_libs --wheel --out-dir agent_server/dist
fi

if [[ "$BUILD_RAG" -eq 1 ]]; then
  echo "=== [shared-server-libs] Building for rag_retrieval_server ==="
  prepare_dist "rag_retrieval_server/dist"
  uv build shared_server_libs --wheel --out-dir rag_retrieval_server/dist
fi

if [[ "$BUILD_LANGGRAPH" -eq 1 ]]; then
  echo
  echo "=== Building agent_server wheel ==="
  uv build agent_server --wheel --out-dir agent_server/dist
  maybe_export_reqs agent_server agent-server "agent_server/dist"
  echo "[LangGraph] agent_server/dist/"
fi

if [[ "$BUILD_RAG" -eq 1 ]]; then
  echo
  echo "=== Building rag_retrieval_server wheel ==="
  uv build rag_retrieval_server --wheel --out-dir rag_retrieval_server/dist
  maybe_export_reqs rag_retrieval_server rag-retrieval-server "rag_retrieval_server/dist"
  echo "[RAG] rag_retrieval_server/dist/"
fi

echo
echo "Build complete. Next: docker compose build agent_server rag_retrieval_server frontend"
echo
