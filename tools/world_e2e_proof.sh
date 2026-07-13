#!/usr/bin/env bash
# End-to-end proof of the world simulator closed loop on the REAL stack:
#   world engine (FastAPI :3101) -> sensor -> REAL Durable orchestration
#   (Functions host :7071) -> agent decides from world data -> actuator -> world drains.
#
# No mocks. Boots Azurite + Functions host + FastAPI(ZAVA_WORLD=toy), injects a
# demand surge, samples world state, queries the Durable runtime for the
# orchestration instance, then tears everything down.
#
# Usage:  bash tools/world_e2e_proof.sh
set -uo pipefail
cd "$(dirname "$0")/.."
D=.compose; mkdir -p "$D"; rm -rf "$D/proof-azurite"; mkdir -p "$D/proof-azurite"

cleanup() {
  echo "==> tearing down"
  for pf in "$D/proof-api.pid" "$D/proof-func.pid" "$D/proof-azurite.pid"; do
    [ -f "$pf" ] && kill "$(cat "$pf")" 2>/dev/null; rm -f "$pf"
  done
}
trap cleanup EXIT

echo "==> azurite"
azurite --silent --location "$D/proof-azurite" --blobHost 127.0.0.1 --queueHost 127.0.0.1 --tableHost 127.0.0.1 >"$D/proof-azurite.log" 2>&1 & echo $! >"$D/proof-azurite.pid"
for i in $(seq 1 20); do [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:10000/devstoreaccount1)" = "400" ] && break; sleep 1; done

echo "==> functions host (:7071)"
( source .venv/bin/activate && ENTITY_PLANE_ENABLED=0 PYTHONPATH="$(pwd)" func start --port 7071 >"$D/proof-func.log" 2>&1 & echo $! >"$D/proof-func.pid" )
for i in $(seq 1 24); do curl -s -o /dev/null http://localhost:7071/ 2>/dev/null && break; sleep 3; done

echo "==> fastapi (:3101, ZAVA_WORLD=toy)"
( ZAVA_WORLD=toy FUNCTIONS_HOST=http://localhost:7071 uv run --frozen --no-sync uvicorn api.server.main:app --port 3101 >"$D/proof-api.log" 2>&1 & echo $! >"$D/proof-api.pid" )
for i in $(seq 1 20); do curl -s -o /dev/null http://localhost:3101/health 2>/dev/null && break; sleep 3; done

echo "==> baseline"; curl -s localhost:3101/api/world/state
echo; echo "==> inject demand_surge"; curl -s -X POST localhost:3101/api/world/inject/demand_surge; echo
for i in $(seq 1 12); do
  sleep 1
  curl -s localhost:3101/api/world/state | python3 -c "import sys,json;d=json.load(sys.stdin);lr=d.get('last_response');print(f\"t+{$i:>2}s backlog={d['stocks']['support_backlog']:>6} agents={d['resources']['agents']:>5} breach={d['signals']['sla_breach_pct']:>6}\"+(f'  responder instance={lr[\"instance_id\"]} hired={lr[\"hired\"]}' if lr else ''))"
done

IID=$(curl -s localhost:3101/api/world/state | python3 -c "import sys,json;print((json.load(sys.stdin).get('last_response') or {}).get('instance_id',''))")
echo; echo "==> Durable runtime status for $IID (proof it really ran on :7071):"
curl -s "http://localhost:7071/runtime/webhooks/durabletask/instances/$IID?taskHub=InvoiceP2PHub&connection=Storage" | python3 -m json.tool
