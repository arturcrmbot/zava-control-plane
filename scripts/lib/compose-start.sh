#!/usr/bin/env bash
# Shared launch helpers so boot-demo.sh and compose-ignite.sh start the API +
# Functions host identically and record PIDs for a clean restart.
set -euo pipefail
PIDDIR="${ZAVA_REPO_ROOT:-$PWD}/.compose"
mkdir -p "$PIDDIR"

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
        ENTITY_PLANE_ENABLED=0 PATH="$NPM_BIN:$PATH" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH="$(pwd)" \
          func start --port 7071 >>"$PIDDIR/func.log" 2>&1 &
        echo $! >"$PIDDIR/func.pid" )
      ;;
    *)
      ( source .venv/bin/activate
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
