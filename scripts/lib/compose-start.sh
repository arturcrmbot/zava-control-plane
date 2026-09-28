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
    printenv "$key" >/dev/null && continue
    export "$key=$value"
  done <"$env_file"
}

start_laya() {
  # Laya is the local model a pack's personas and world read with. Start it
  # when .env points LAYA_URL at this machine and it is not already up.
  # Without it those readings fall back to the pack's rules, and say so.
  # Writes $PIDDIR/laya.pid only when this call started it.
  local url port script
  rm -f "$PIDDIR/laya.pid"
  url="$( _export_env_file; printf '%s' "${LAYA_URL:-}" )"
  case "$url" in
    http://127.0.0.1:*|http://localhost:*) ;;
    *) return 0 ;;
  esac
  port="${url#http://*:}"
  port="${port%%/*}"
  if curl -s --max-time 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    echo "    Laya already running on :$port"
    return 0
  fi
  script="${LAYA_START_SCRIPT:-$HOME/.copilot/skills/laya/scripts/start.sh}"
  if [ ! -x "$script" ]; then
    echo "    warn: LAYA_URL is set but $script is missing; readings fall back to the rules"
    return 0
  fi
  ( LAYA_PORT="$port" "$script" >>"$PIDDIR/laya.log" 2>&1 &
    echo $! >"$PIDDIR/laya.pid" )
  for _ in $(seq 1 45); do
    sleep 1
    if curl -s --max-time 1 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      echo "    Laya ready on :$port"
      return 0
    fi
  done
  echo "    warn: Laya not ready after 45 s (see $PIDDIR/laya.log); readings fall back to the rules"
}

start_api() {
  # --frozen --no-sync: use the committed lockfile + existing venv. A fresh
  # re-resolve fails on the pre-existing agent-framework/py-3.14 lock conflict.
  ( uv run --frozen --no-sync uvicorn api.server.main:app --host 127.0.0.1 --port 3101 >>"$PIDDIR/api.log" 2>&1 &
    echo $! >"$PIDDIR/api.pid" )
}

start_func() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      ( NPM_BIN="$(cygpath -u "$APPDATA")/npm"
        source .funcvenv/Scripts/activate
        _export_env_file
        Kestrel__Endpoints__Local__Url=http://127.0.0.1:7071 ENTITY_PLANE_ENABLED=0 PATH="$NPM_BIN:$PATH" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH="$(pwd)" \
          func start --port 7071 >>"$PIDDIR/func.log" 2>&1 &
        echo $! >"$PIDDIR/func.pid" )
      ;;
    *)
      ( source .venv/bin/activate
        _export_env_file
        Kestrel__Endpoints__Local__Url=http://127.0.0.1:7071 ENTITY_PLANE_ENABLED=0 PYTHONPATH="$(pwd)" func start --port 7071 >>"$PIDDIR/func.log" 2>&1 &
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
