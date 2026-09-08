#!/usr/bin/env bash
# Shared launch helpers so boot-demo.sh and compose-ignite.sh start the API +
# Functions host identically and record PIDs for a clean restart.
set -euo pipefail
PIDDIR="${ZAVA_REPO_ROOT:-$PWD}/.compose"
mkdir -p "$PIDDIR"

# The Azure Functions worker never reads .env -- only the FastAPI side calls
# load_dotenv(). Without propagating it the worker runs on different settings
# than the API: the wrong vertical pack (every orchestration start then fails
# with "orchestrator doesn't exist") and the wrong LLM runtime (agent
# activities time out). Load .env into the worker's environment, letting any
# value already exported by the caller win.
_export_env_file() {
  local env_file="${ZAVA_REPO_ROOT:-$PWD}/.env"
  [ -f "$env_file" ] || return 0
  local line key value
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    value="${value%$'\r'}"
    # Strip one layer of surrounding quotes, mirroring python-dotenv.
    if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    # An explicitly exported value (e.g. `ZAVA_VERTICAL=x make up`) wins.
    [ -n "${!key:-}" ] && continue
    export "$key=$value"
  done <"$env_file"
}

start_api() {
  # --frozen --no-sync: use the committed lockfile + existing venv. A fresh
  # re-resolve fails on the pre-existing agent-framework/py-3.14 lock conflict.
  ( uv run --frozen --no-sync uvicorn api.server.main:app --port 3101 >>"$PIDDIR/api.log" 2>&1 &
    echo $! >"$PIDDIR/api.pid" )
}

start_func() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      ( NPM_BIN="$(cygpath -u "$APPDATA")/npm"
        source .funcvenv/Scripts/activate
        _export_env_file
        ENTITY_PLANE_ENABLED=0 PATH="$NPM_BIN:$PATH" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH="$(pwd)" \
          func start --port 7071 >>"$PIDDIR/func.log" 2>&1 &
        echo $! >"$PIDDIR/func.pid" )
      ;;
    *)
      ( source .venv/bin/activate
        _export_env_file
        ENTITY_PLANE_ENABLED=0 PYTHONPATH="$(pwd)" func start --port 7071 >>"$PIDDIR/func.log" 2>&1 &
        echo $! >"$PIDDIR/func.pid" )
      ;;
  esac
}

stop_pid() {  # $1 = pidfile
  local f="$1"
  [ -f "$f" ] || return 0
  local pid; pid="$(cat "$f")"
  if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; fi
  rm -f "$f"
}
