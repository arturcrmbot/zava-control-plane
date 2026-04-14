# WPP Control Plane — Python POC1 (MAF Durable Agents)

End-to-end POC1 (Finance Procure-to-Pay) implementation using:
- Microsoft Agent Framework (MAF) — `agent-framework` v1.0.1, `agent-framework-github-copilot`, `agent-framework-azurefunctions`
- GHCP SDK Python (`github-copilot-sdk` v0.2.1) inside agent executors
- Azure Durable Functions (Azurite-backed locally) hosting the per-invoice durable orchestration
- React UI from `../control-plane/` (with new Orchestration tab + right-rail feed)

The single MAF Durable Workflow per invoice (`InvoiceP2POrchestrator`) drives 6 phase steps as activities; each step's per-phase MAF Pregel graph is real (`WorkflowBuilder` + typed Executors + validators); agent executors load one of 9 finance-agent SKILL.md files via `GitHubCopilotAgent`. HITL on the Approval step uses `wait_for_external_event`. Same `finance-agent` Hosted Agent identity for all 9 skills + a separate `fleet-manager-agent` identity for the always-on Fleet Manager.

## One-time setup

### 1. Install `uv` (Python package manager)
```bash
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies
```bash
cd control-plane-py
uv sync
```

### 3. Install Azure Functions Core Tools (REQUIRED — needs to be v4.9.0+)

Critical: Core Tools 4.0.x (notably 4.0.5455 shipped with many older MSI installers) will fail with Python worker + Durable extension bundle issues. Install the latest v4:
```bash
npm install -g azure-functions-core-tools@4.9.0   # or @latest
func --version   # should be 4.9.0 or newer
```

**Windows gotcha:** if `func --version` still shows an old version (e.g. 4.0.5455), you have two copies. The MSI-installed copy at `C:\Program Files\Microsoft\Azure Functions Core Tools\` is first on PATH and shadows the npm one. Either uninstall the MSI copy via "Add or Remove Programs", or prepend npm's bin to PATH: `export PATH="/c/Users/<you>/AppData/Roaming/npm:$PATH"`.

### 4. Create local.settings.json from template
```bash
cp local.settings.json.example local.settings.json
```

### 5. Authenticate with GitHub (for Copilot)
```bash
gh auth login   # if not already authenticated; needs Copilot license
```

### 6. (Optional but recommended) Create a Python 3.11 venv for the Functions worker
The `func` Core Tools' Python worker requires Python 3.11 specifically; uv may install Python 3.13. Create a 3.11 venv just for `func`:
```bash
make funcvenv     # uses requirements.txt to populate .funcvenv/
```

## Running

Open 4 terminals (or run via `tmux`/`docker compose` style):

**Terminal 1 — Storage:**
```bash
cd control-plane-py && docker compose up -d azurite
```

**Terminal 2 — Mock MCPs (TS, from v1):**
```bash
cd control-plane && npm run dev:mcp
```

**Terminal 3 — Azure Functions host (the durable runtime):**
```bash
cd control-plane-py && make functions
# Equivalently: source .funcvenv/Scripts/activate && PYTHONPATH=$(pwd) func start --port 7071
```

**Terminal 4 — FastAPI server (Fleet Manager + simulator + APIs):**
```bash
cd control-plane-py && make server
# Equivalently: uv run uvicorn src.server.main:app --port 3001 --reload
```

**Terminal 5 — React UI:**
```bash
cd control-plane
echo "VITE_API_BASE_URL=http://localhost:3001" > .env.local
npm run dev:client
# UI at http://localhost:5173
```

## Inject demo scenarios

Once the system is up:

```bash
# Normal workflow
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{}'

# Bounded-probabilism case: agent_gl_coder picks GL-9999 (inactive),
# validate_gl_active blocks, Fleet Manager wakes and composes exception
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
```

## Architecture

See [design spec](../docs/superpowers/specs/2026-04-13-wpp-control-plane-py-poc1-design.md).

Three layers, all real:
1. **MAF Durable Workflow orchestration** (`function_app.py` + `src/functions/workflows/invoice_p2p.py`) — single generator function representing one invoice end-to-end across 6 phase steps; HITL via `wait_for_external_event`; checkpointing automatic via Azure Durable Functions runtime; state persisted in Azurite.
2. **Per-phase MAF Pregel graphs** (`src/functions/graphs/*.py`) — real `WorkflowBuilder` + `Executor` graphs; each phase has a deterministic backbone with agent executors only where reasoning is required, and validators between agent and downstream steps.
3. **GHCP SDK Python sessions** (`src/functions/graphs/executors/agents/*.py` via `agent-framework-github-copilot`) — ephemeral sessions inside agent executor nodes, each loading one of 9 `finance-agent` skills.

The **Fleet Manager** (`src/server/services/fleet_manager_service.py`) is a separate always-on GHCP SDK session running inside FastAPI — not part of the durable orchestration. It consumes triage-filtered telemetry events, debounces them, and reasons over batches via `send_and_wait`, calling 5 MCP tools (the orchestration mirror, exception composer, etc.).

## Switching backends

The same React UI works with either backend (TS v1 or Python POC1):
```bash
# TS v1: cd ../control-plane && npm run dev:server
# Python POC1: this repo
# Set in control-plane/.env.local:
VITE_API_BASE_URL=http://localhost:3001
```

Both back ends listen on port 3001. Pick one to run at a time.

## Stop

Ctrl-C all processes. FastAPI + Fleet Manager + simulator state is in-memory (lost on restart). Durable Workflow state persists in Azurite (`./azurite-data/` directory; delete to reset).

## Known limitations

- HTTP-triggered orchestration starter requires `func start` running. If the Functions host is down, the simulator gracefully logs "failed to schedule" and the workflow appears in the store without an orchestration instance.
- `sendEventPostUri` cache in `durable_client.py` is process-local memory — fine for single-worker uvicorn; will need redis/db-backed cache for multi-worker.
- Activity functions in `src/functions/workflows/activities.py` are sync wrappers around `asyncio.run(...)` because Azure Durable Functions Python doesn't natively support async activities.
