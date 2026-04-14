# WPP Control Plane Python POC1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python implementation of POC1 (Finance Procure-to-Pay) using Microsoft's Durable Agents pattern (MAF + Durable Task Framework) with GHCP SDK Python inside agent executors, wired into the existing React Control Plane UI in 2 days.

**Architecture:** Greenfield Python backend at `c:\dev\ghcp sdk stuff\control-plane-py\`. Single MAF `DurableWorkflow` per invoice with 6 phase steps; each step builds and executes a per-phase MAF Pregel graph of typed executors (deterministic + agent + validator). Hosted by Azure Functions runtime locally with Azurite for state. FastAPI server exposes the same `/api/*` shape the React UI already consumes; new endpoints `/api/workflows/:id/orchestration` and `/api/stream/orchestration` power two new UI surfaces.

**Tech Stack:** Python 3.11+, FastAPI + Uvicorn, MAF Python (Durable Workflows + workflow graphs), GHCP SDK Python, Azure Functions Core Tools 4 + Azurite, pytest + pytest-asyncio, uv (package manager), Pydantic v2.

**Reference:** [docs/superpowers/specs/2026-04-13-wpp-control-plane-py-poc1-design.md](../specs/2026-04-13-wpp-control-plane-py-poc1-design.md)

**Working dir:** `c:\dev\ghcp sdk stuff\control-plane-py\`

**Constraints carried from v1 (apply to ALL tasks):**
- DO NOT git commit anything. The user runs commits separately.
- Stay on `main` branch.
- Windows + bash. Forward slashes in paths.
- Mock MCP servers in `c:\dev\ghcp sdk stuff\control-plane\mocks\` are reused as-is (HTTP, language-agnostic, ports 4101–4104). Don't reimplement.
- TS v1 at `c:\dev\ghcp sdk stuff\control-plane\` is untouched.
- Auth: `gh auth token` from the user's personal Copilot license. Do not require Azure credentials.

**Phases:**
- Phase 0 — Scaffold + risk spike (0.1, 0.2)
- Phase 1 — Shared types + events (1.1, 1.2)
- Phase 2 — Core services (2.1, 2.2, 2.3, 2.4)
- Phase 3 — FastAPI server skeleton (3.1, 3.2, 3.3)
- Phase 4 — 10 SKILL.md files (4.1)
- Phase 5 — Fleet Manager Python port (5.1, 5.2, 5.3)
- Phase 6 — Per-phase deterministic executors (6.1–6.5)
- Phase 7 — Per-phase agent executors (7.1, 7.2, 7.3)
- Phase 8 — MAF Pregel graphs (8.1–8.6)
- Phase 9 — InvoiceP2PWorkflow Durable Workflow (9.1, 9.2)
- Phase 10 — Simulator + HITL signal (10.1, 10.2)
- Phase 11 — UI: Orchestration tab + right-rail feed (11.1, 11.2)
- Phase 12 — Demo polish + integration check (12.1, 12.2)

Cut order if time runs short (matches spec §12): right-rail Orchestration tab → Reconciliation as Hybrid (make deterministic) → Sub-agent moment in Intake → hero shot #11 → hero shot #12.

---

## Phase 0 — Scaffold + risk spike

### Task 0.1: Scaffold the Python workspace

**Files:**
- Create: `control-plane-py/pyproject.toml`
- Create: `control-plane-py/.env.example`
- Create: `control-plane-py/.gitignore`
- Create: `control-plane-py/docker-compose.yml`
- Create: `control-plane-py/host.json`
- Create: `control-plane-py/local.settings.json.example`
- Create: `control-plane-py/Makefile`
- Create: `control-plane-py/README.md` (placeholder, fleshed out in Phase 12)

- [ ] **Step 1: Create directories**

```bash
mkdir -p "c:/dev/ghcp sdk stuff/control-plane-py"
cd "c:/dev/ghcp sdk stuff/control-plane-py"
mkdir -p src/server/routes src/server/services src/server/mcp_tools src/server/skills src/server/fixtures
mkdir -p src/shared
mkdir -p src/functions/workflows src/functions/graphs/executors/deterministic src/functions/graphs/executors/agents src/functions/graphs/executors/validators
mkdir -p spike tests/unit
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "wpp-control-plane-py"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "httpx>=0.27",
  "sse-starlette>=2.1",
  "pyyaml>=6.0",
  "python-dotenv>=1.0",
  "nanoid>=2.0",
  "azure-functions>=1.21",
  "azure-functions-durable>=1.2",
  "agent-framework",
  "copilot-sdk"
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-mock>=3.14",
  "ruff>=0.7"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 110
target-version = "py311"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Note:** package names `agent-framework` and `copilot-sdk` are best-guesses. The Phase 0.2 spike resolves the actual names. If `uv sync` fails on either, leave them and report — the spike fixes it.

- [ ] **Step 3: Write `.env.example`**

```
PORT=3001
FUNCTIONS_HOST=http://localhost:7071
AZURITE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEEcrn8gNXBNHZTpaKE9LXVUcXg/p4axyW3PYsoGTcJ2VVQpRzD5pSlUL/RcQfA==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;
WORKDAY_MCP_URL=http://localhost:4101
D365_MCP_URL=http://localhost:4102
MACONOMY_MCP_URL=http://localhost:4103
PAYMENT_MCP_URL=http://localhost:4104
FLEET_MANAGER_MODEL=gpt-4.1
FLEET_MANAGER_MAX_TOKENS=2000
SIMULATOR_TARGET_WORKFLOWS=30
```

- [ ] **Step 4: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
.env.local
local.settings.json
.pytest_cache/
.ruff_cache/
azurite-data/
```

- [ ] **Step 5: Write `docker-compose.yml`**

```yaml
services:
  azurite:
    image: mcr.microsoft.com/azure-storage/azurite:latest
    container_name: cp-py-azurite
    ports:
      - "10000:10000"
      - "10001:10001"
      - "10002:10002"
    volumes:
      - ./azurite-data:/data
    command: "azurite --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0 --location /data"
```

- [ ] **Step 6: Write `host.json` and `local.settings.json.example`**

`host.json`:
```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": { "samplingSettings": { "isEnabled": false } }
  },
  "extensions": {
    "durableTask": {
      "hubName": "InvoiceP2PHub"
    }
  }
}
```

`local.settings.json.example`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEEcrn8gNXBNHZTpaKE9LXVUcXg/p4axyW3PYsoGTcJ2VVQpRzD5pSlUL/RcQfA==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "PYTHON_ISOLATE_WORKER_DEPENDENCIES": "1",
    "FASTAPI_WEBHOOK_URL": "http://localhost:3001/internal/durable-event"
  }
}
```

- [ ] **Step 7: Write `Makefile`**

```makefile
.PHONY: install dev mcp server functions test clean azurite-up azurite-down

install:
	uv sync

azurite-up:
	docker compose up -d azurite

azurite-down:
	docker compose down

mcp:
	cd "../control-plane" && npm run dev:mcp

server:
	uv run uvicorn src.server.main:app --port 3001 --reload

functions:
	cd src/functions && func start --port 7071

dev: azurite-up
	@echo "Start in 3 terminals: 'make mcp' / 'make server' / 'make functions'"

test:
	uv run pytest -v

clean:
	docker compose down -v
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache azurite-data
```

- [ ] **Step 8: Placeholder `README.md`**

```markdown
# WPP Control Plane Python POC1

Python implementation of POC1 using MAF Durable Agents + GHCP SDK.

Quickstart will be filled out in Phase 12.

See [design spec](../docs/superpowers/specs/2026-04-13-wpp-control-plane-py-poc1-design.md).
```

- [ ] **Step 9: Install + verify**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv not installed
uv sync
```

Expected: most deps install. `agent-framework` and `copilot-sdk` may fail — note the exact error and proceed to Phase 0.2 spike.

- [ ] **Step 10: DO NOT commit.** Phase 0.2 will resolve package names.

---

### Task 0.2: Day-1 spike — discover MAF Durable Agents + GHCP SDK Python APIs

This is the de-risking step. Same pattern as v1 Phase 0.2 spike but for two SDKs at once.

**Files:**
- Create: `control-plane-py/spike/maf_durable_spike.py`
- Create: `control-plane-py/spike/copilot_sdk_spike.py`
- Create: `control-plane-py/spike/MAF-DURABLE-NOTES.md`

#### Step 1: Resolve package names

```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
# Search PyPI for likely package names
uv pip search "agent framework" 2>/dev/null || echo "no search"
# Best-known candidates as of 2026-04:
#   - microsoft-agent-framework
#   - azure-ai-agent-framework
# For copilot SDK Python:
#   - github-copilot-sdk
#   - copilot-sdk
# Install whichever resolves
uv add microsoft-agent-framework || uv add azure-ai-agent-framework || uv add agent-framework
uv add github-copilot-sdk || uv add copilot-sdk
```

If installation fails for any candidate, document the exact error in `MAF-DURABLE-NOTES.md` §1 and try the next name. Update `pyproject.toml` to the actual installed names. If NONE work, report BLOCKED.

#### Step 2: Write the GHCP SDK Python spike

```python
# control-plane-py/spike/copilot_sdk_spike.py
"""Discover the Python @github/copilot-sdk equivalent's API surface.

Goal: prove that
  - we can construct a client using `gh auth token`
  - we can create a session, send messages programmatically
  - we can register a tool and observe its invocation
"""
import asyncio
import subprocess

# IMPORT WHATEVER THE PACKAGE TURNED OUT TO BE
# Examples to try:
#   from copilot_sdk import CopilotClient, define_tool
#   from github_copilot_sdk import CopilotClient, define_tool
#   from copilot_sdk_python import ...

# Replace these imports based on what installed successfully.
try:
    from copilot_sdk import CopilotClient, define_tool  # type: ignore
except ImportError:
    from github_copilot_sdk import CopilotClient, define_tool  # type: ignore


def gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


async def main():
    print("=== GHCP SDK Python SPIKE ===")
    client = CopilotClient(github_token=gh_token())
    print(f"[client] type={type(client).__name__}")

    ping_tool = define_tool(
        "ping",
        description="Echoes a message back",
        # PARAMETER SCHEMA — discover what shape the SDK wants. Try in order:
        #   - Pydantic model
        #   - {"type": "object", "properties": {...}}
        #   - dataclass
        parameters={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
        handler=lambda args: {"echoed": args["msg"]},
    )

    session = await client.create_session(
        model="gpt-4.1",
        system_prompt="When asked, call the ping tool. Otherwise be brief.",
        tools=[ping_tool],
    )
    print(f"[session] id={getattr(session, 'id', '?')}")

    # Test 1: programmatic message
    r1 = await session.send_message("Say hello to Alice.")
    print(f"[R1] {getattr(r1, 'content', r1)}")

    # Test 2: session retains context
    r2 = await session.send_message("What's the name I just told you?")
    print(f"[R2] {getattr(r2, 'content', r2)}")

    # Test 3: tool invocation observation
    # Wire up event observers BEFORE sending. Try .on(...) / .subscribe(...) / etc.
    events = []
    if hasattr(session, "on"):
        session.on("tool.execution_start", lambda e: events.append(("start", e)))
        session.on("tool.execution_complete", lambda e: events.append(("complete", e)))
    r3 = await session.send_message("Call the ping tool with msg='hello'.")
    print(f"[R3] {getattr(r3, 'content', r3)}")
    print(f"[events] {events}")

    await session.close() if hasattr(session, "close") else None


if __name__ == "__main__":
    asyncio.run(main())
```

Run:
```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
uv run python spike/copilot_sdk_spike.py
```

If imports/methods don't match, inspect installed package's `.pyi`/`.py` files in `.venv/lib/python*/site-packages/` and adapt names. Document what worked.

**Acceptance:** R1 returns a greeting, R2 references "Alice" (proves context), R3 contains "hello" and `events` shows tool start+complete.

#### Step 3: Write the MAF Durable Workflow spike

```python
# control-plane-py/spike/maf_durable_spike.py
"""Discover the MAF Durable Agents (DurableWorkflow) API.

Goal: prove that
  - we can declare a DurableWorkflow with multiple steps
  - the workflow runs locally via the durable runtime  - we can pause via wait_for_external_event and resume via raise_event
  - workflow steps can call regular Python coroutines (later: graphs)
"""
import asyncio

# IMPORT — try candidates:
#   from agent_framework.workflows.durable import DurableWorkflow, workflow_step
#   from microsoft.agent_framework.durable import ...
#   from azure.ai.agent_framework.workflows.durable import ...
try:
    from agent_framework.workflows.durable import DurableWorkflow, workflow_step  # type: ignore
except ImportError:
    from microsoft_agent_framework.durable import DurableWorkflow, workflow_step  # type: ignore


class HelloWorkflow(DurableWorkflow):
    @workflow_step
    async def step_one(self, ctx, name: str) -> str:
        return f"hello {name}"

    @workflow_step
    async def step_two(self, ctx, greeting: str) -> str:
        # Pause for external signal
        decision = await ctx.wait_for_external_event("approve_greeting")
        return f"{greeting} (approved: {decision})"

    async def run(self, ctx, name: str) -> str:
        a = await self.step_one(ctx, name)
        b = await self.step_two(ctx, a)
        return b


async def main():
    print("=== MAF Durable Agents SPIKE ===")
    # IMPORT runtime client too:
    #   from agent_framework.workflows.durable import DurableRuntimeClient
    from agent_framework.workflows.durable import DurableRuntimeClient  # type: ignore

    client = DurableRuntimeClient.from_environment()
    workflow = HelloWorkflow()

    instance_id = await client.start_new(workflow, input="Alice")
    print(f"[start] instance_id={instance_id}")

    # Poll status until suspended
    for _ in range(60):
        status = await client.get_status(instance_id)
        print(f"[status] {status}")
        if str(status).lower().startswith("suspend"):
            break
        await asyncio.sleep(1)

    # Raise the awaited event
    await client.raise_event(instance_id, "approve_greeting", "yes")
    print("[raise_event] sent")

    # Wait for completion
    for _ in range(30):
        status = await client.get_status(instance_id)
        if "complet" in str(status).lower() or "fail" in str(status).lower():
            print(f"[final] {status}")
            output = await client.get_output(instance_id)
            print(f"[output] {output}")
            break
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
```

Pre-run setup:
```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
docker compose up -d azurite      # storage backend
# Start Functions host that loads the workflow
cp local.settings.json.example local.settings.json
cd src/functions
# Minimal function_app.py registers the workflow with the runtime; the spike
# may need a temporary registration. If MAF supports standalone runtime mode
# without Functions, prefer that.
```

Run the spike. If it requires a Functions host, write a minimal `src/functions/function_app.py`:
```python
import azure.functions as func

app = func.FunctionApp()
# Register the spike workflow if needed; depends on MAF runtime hosting model.
```

Then `func start --port 7071` in a separate terminal, run the spike from another.

**Acceptance:** workflow starts, status reaches "Suspended" after step_one, raise_event resumes step_two, final output is `"hello Alice (approved: yes)"`.

If the API surface is different from the spike's assumption (e.g., `DurableRuntimeClient` doesn't exist, or `wait_for_external_event` is `wait_for_event`), adapt and document the actual names.

#### Step 4: Document findings

Write `spike/MAF-DURABLE-NOTES.md` with these sections (mirrors v1 SPIKE-NOTES structure):

1. **Resolved package names** — actual `pyproject.toml` deps that installed
2. **GHCP SDK Python API** — class names, session methods, tool registration shape, event subscription pattern, the `gh auth token` integration
3. **MAF Durable Workflow API** — `DurableWorkflow` superclass + step decorator name, `wait_for_external_event` exact signature, `raise_event` client method, hosting model (Functions-required or standalone)
4. **MAF Pregel graph API** — class names for workflow graphs (used in Phase 8). If not yet exercised, leave a TODO with import paths to investigate
5. **Hosting model** — does MAF runtime require Azure Functions host? If yes, what registration pattern? If MAF can run standalone, prefer that
6. **What does NOT work** — anything tried that failed, with errors

#### Step 5: DO NOT commit. Report results.

**Acceptance for Task 0.2 overall:**
- [ ] Both spikes run end-to-end
- [ ] `MAF-DURABLE-NOTES.md` documents the actual API surface
- [ ] `pyproject.toml` updated with resolved package names

**If spike fails:** report BLOCKED with specific package/API issues. Fallback options to discuss with controller before proceeding:
- Use the manual-integration pattern (DF orchestrator function + MAF graphs as activities) — spec §11 risk #1 names this as fallback
- Use a different MAF runtime hosting (e.g., direct in-process if Functions host is heavy)

---

## Phase 1 — Shared types + events

### Task 1.1: Pydantic types

**Files:**
- Create: `control-plane-py/src/shared/types.py`
- Create: `control-plane-py/tests/unit/test_types.py`

- [ ] **Step 1: Write failing test**

```python
# control-plane-py/tests/unit/test_types.py
from src.shared.types import next_phase, PHASE_ORDER


def test_next_phase_returns_next():
    assert next_phase("Intake") == "Validation"
    assert next_phase("Approval") == "Payment"


def test_next_phase_returns_none_at_end():
    assert next_phase("Reconciliation") is None


def test_phase_order_is_six():
    assert len(PHASE_ORDER) == 6
```

- [ ] **Step 2: Run, expect FAIL**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
uv run pytest tests/unit/test_types.py -v
```

- [ ] **Step 3: Implement `types.py`**

```python
# control-plane-py/src/shared/types.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

PhaseName = Literal["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"]

PHASE_ORDER: list[PhaseName] = [
    "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
]

WorkflowStatus = Literal["in_progress", "awaiting_hitl", "completed", "failed"]
Severity = Literal["critical", "high", "medium"]
ExceptionCategory = Literal[
    "duplicate-invoice", "po-mismatch", "threshold-exceeded",
    "sanctions-flag", "compliance", "payment-timeout", "validator-blocked"
]


class Vendor(BaseModel):
    id: str
    name: str
    country: str


class InvoiceLineItem(BaseModel):
    description: str
    qty: float
    unit_price: float


class InvoiceData(BaseModel):
    number: str
    amount: float
    currency: str
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    po_ref: str


class ToolCall(BaseModel):
    tool: str
    args_preview: str
    ms: int
    ok: bool


class ActionLedgerEntry(BaseModel):
    workflow_id: str
    timestamp: float
    actor_kind: Literal["agent", "human"]
    actor_id: str
    action: str
    revocable: bool
    details: dict


class Workflow(BaseModel):
    id: str
    type: Literal["invoice-p2p"] = "invoice-p2p"
    status: WorkflowStatus = "in_progress"
    current_phase: PhaseName = "Intake"
    created_at: float
    sla_due_at: float
    vendor: Vendor
    invoice: InvoiceData
    jurisdiction: str
    agency: str
    active_exception_id: str | None = None
    action_ledger: list[ActionLedgerEntry] = Field(default_factory=list)
    tokens_spent: int = 0
    cost_usd: float = 0.0
    orchestration_instance_id: str | None = None


class Phase(BaseModel):
    workflow_id: str
    name: PhaseName
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    started_at: float | None = None
    completed_at: float | None = None
    agent_id: Literal["finance-agent"] = "finance-agent"
    tool_calls: list[ToolCall] = Field(default_factory=list)
    span_ids: list[str] = Field(default_factory=list)


class OtelSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_ms: float
    end_ms: float
    attributes: dict
    status: Literal["ok", "error"] = "ok"


class ExceptionOption(BaseModel):
    label: str
    action: str
    non_revocable: bool = False


class PolicyRef(BaseModel):
    title: str
    snippet: str
    source: str


class Exception_(BaseModel):
    id: str
    workflow_id: str
    composed_by: Literal["fleet-manager", "guardrail", "simulator-injected", "validator"]
    severity: Severity
    category: ExceptionCategory
    summary: str
    recommendation: str
    options: list[ExceptionOption] = Field(default_factory=list)
    related_policy_refs: list[PolicyRef] = Field(default_factory=list)
    bulk_candidate_ids: list[str] | None = None
    confidence: float = 0.8
    created_at: float
    resolved_at: float | None = None
    resolved_by: str | None = None


class SkillAmplification(BaseModel):
    id: str
    workflow_id: str
    policy_context: list[PolicyRef] = Field(default_factory=list)
    precedents: list[dict] = Field(default_factory=list)
    recommended_approach: str
    created_at: float


class AutonomyPolicy(BaseModel):
    id: str
    description: str
    current_value: float | str | bool
    git_sha: str
    author: str
    updated_at: float


def next_phase(p: PhaseName) -> PhaseName | None:
    i = PHASE_ORDER.index(p) if p in PHASE_ORDER else -1
    if i < 0 or i >= len(PHASE_ORDER) - 1:
        return None
    return PHASE_ORDER[i + 1]
```

**Note:** `Exception` is a Python builtin so we use `Exception_` (or `WorkflowException`). Pick one and use consistently. Use `Exception_` for minimal renaming.

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest tests/unit/test_types.py -v
```

- [ ] **Step 5: DO NOT commit.**

---

### Task 1.2: Event taxonomy

**Files:**
- Create: `control-plane-py/src/shared/events.py`
- Create: `control-plane-py/tests/unit/test_events.py`

- [ ] **Step 1: Test FIRST**

```python
# control-plane-py/tests/unit/test_events.py
from src.shared.events import wakes_fleet_manager, WAKE_TYPES, FleetEvent


def test_wakes_on_exception_detected():
    e = FleetEvent(type="workflow.exception.detected", workflow_id="A", category="duplicate-invoice", severity="high")
    assert wakes_fleet_manager(e) is True


def test_does_not_wake_on_phase_started():
    e = FleetEvent(type="workflow.phase.started", workflow_id="A", phase="Intake")
    assert wakes_fleet_manager(e) is False


def test_wake_set_size():
    assert len(WAKE_TYPES) == 6
```

- [ ] **Step 2: Implement**

```python
# control-plane-py/src/shared/events.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict

# Discriminated union via Pydantic with `type` field. We use a single Pydantic model with optional
# fields rather than a true union, for ergonomics. Producers ensure correct fields per type.

FleetEventType = Literal[
    "workflow.started",
    "workflow.phase.started",
    "workflow.phase.completed",
    "workflow.phase.failed",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "workflow.resolved",
    "otel.span.emitted",
    "fleet.anomaly.detected",
    "fleet.tick",
    "fleet.overload",
    # Durable Workflow events (new in py POC1)
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "durable.validator.blocked",
    "durable.suspended",
    "durable.resumed",
    "durable.workflow.completed",
]


class FleetEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: FleetEventType
    workflow_id: str | None = None
    # All other fields permitted via extra="allow"


WAKE_TYPES: frozenset[FleetEventType] = frozenset({
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "fleet.anomaly.detected",
    "fleet.tick",
})


def wakes_fleet_manager(e: FleetEvent) -> bool:
    return e.type in WAKE_TYPES
```

- [ ] **Step 3: Run, expect PASS**

```bash
uv run pytest tests/unit/test_events.py -v
```

- [ ] **Step 4: DO NOT commit.**

---

## Phase 2 — Core services

### Task 2.1: EventBus (asyncio)

**Files:**
- Create: `control-plane-py/src/server/services/event_bus.py`
- Create: `control-plane-py/tests/unit/test_event_bus.py`

- [ ] **Step 1: Test FIRST**

```python
# control-plane-py/tests/unit/test_event_bus.py
import pytest
from src.server.services.event_bus import EventBus
from src.shared.events import FleetEvent


@pytest.mark.asyncio
async def test_delivers_to_subscriber():
    bus = EventBus()
    received = []
    bus.on("workflow.started", lambda e: received.append(e))
    bus.emit(FleetEvent(type="workflow.started", workflow_id="A"))
    assert len(received) == 1
    assert received[0].workflow_id == "A"


@pytest.mark.asyncio
async def test_on_any_receives_all():
    bus = EventBus()
    received = []
    bus.on_any(lambda e: received.append(e))
    bus.emit(FleetEvent(type="fleet.tick"))
    assert len(received) == 1


@pytest.mark.asyncio
async def test_unsubscribe_works():
    bus = EventBus()
    received = []
    handler = lambda e: received.append(e)
    off = bus.on("workflow.started", handler)
    off()
    bus.emit(FleetEvent(type="workflow.started", workflow_id="A"))
    assert len(received) == 0
```

- [ ] **Step 2: Implement**

```python
# control-plane-py/src/server/services/event_bus.py
from __future__ import annotations
from collections import defaultdict
from typing import Callable
from src.shared.events import FleetEvent, FleetEventType

Handler = Callable[[FleetEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._typed: dict[str, list[Handler]] = defaultdict(list)
        self._any: list[Handler] = []

    def on(self, event_type: FleetEventType, handler: Handler) -> Callable[[], None]:
        self._typed[event_type].append(handler)
        def off() -> None:
            try:
                self._typed[event_type].remove(handler)
            except ValueError:
                pass
        return off

    def on_any(self, handler: Handler) -> Callable[[], None]:
        self._any.append(handler)
        def off() -> None:
            try:
                self._any.remove(handler)
            except ValueError:
                pass
        return off

    def emit(self, event: FleetEvent) -> None:
        for h in list(self._typed.get(event.type, [])):
            try:
                h(event)
            except Exception:
                pass
        for h in list(self._any):
            try:
                h(event)
            except Exception:
                pass
```

- [ ] **Step 3: Run, PASS, no commit.**

---

### Task 2.2: StateStore

**Files:**
- Create: `control-plane-py/src/server/services/state_store.py`
- Create: `control-plane-py/tests/unit/test_state_store.py`

- [ ] **Step 1: Test FIRST**

```python
# control-plane-py/tests/unit/test_state_store.py
import time
from src.server.services.state_store import StateStore
from src.shared.types import Workflow, Vendor, InvoiceData, ActionLedgerEntry


def mk_workflow(id: str, **overrides) -> Workflow:
    base = dict(
        id=id, created_at=time.time(), sla_due_at=time.time() + 3600,
        vendor=Vendor(id="V-001", name="Acme", country="US"),
        invoice=InvoiceData(number="INV-001", amount=1000, currency="USD", po_ref="PO-10001"),
        jurisdiction="US-CA", agency="Ogilvy-US",
    )
    base.update(overrides)
    return Workflow(**base)


def test_upsert_and_get():
    s = StateStore()
    s.upsert_workflow(mk_workflow("A"))
    assert s.get_workflow("A").id == "A"


def test_list_with_filters():
    s = StateStore()
    s.upsert_workflow(mk_workflow("A", status="awaiting_hitl"))
    s.upsert_workflow(mk_workflow("B", status="completed"))
    awaiting = s.list_workflows(status="awaiting_hitl")
    assert len(awaiting) == 1
    assert awaiting[0].id == "A"


def test_append_ledger():
    s = StateStore()
    s.upsert_workflow(mk_workflow("A"))
    s.append_ledger("A", ActionLedgerEntry(
        workflow_id="A", timestamp=1, actor_kind="agent",
        actor_id="finance-agent", action="intake.started",
        revocable=True, details={}
    ))
    assert len(s.get_workflow("A").action_ledger) == 1
```

- [ ] **Step 2: Implement**

```python
# control-plane-py/src/server/services/state_store.py
from __future__ import annotations
from src.shared.types import (
    Workflow, Phase, OtelSpan, Exception_ as Exception, ActionLedgerEntry,
    AutonomyPolicy, SkillAmplification
)


class StateStore:
    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._phases: dict[str, list[Phase]] = {}
        self._spans: dict[str, list[OtelSpan]] = {}
        self._exceptions: dict[str, Exception] = {}
        self._policies: dict[str, AutonomyPolicy] = {}
        self._amplifications: dict[str, list[SkillAmplification]] = {}

    def upsert_workflow(self, w: Workflow) -> None:
        self._workflows[w.id] = w

    def get_workflow(self, id: str) -> Workflow | None:
        return self._workflows.get(id)

    def list_workflows(
        self,
        status: str | None = None,
        phase: str | None = None,
        agency: str | None = None,
        has_exception: bool | None = None,
    ) -> list[Workflow]:
        out = []
        for w in self._workflows.values():
            if status is not None and w.status != status: continue
            if phase is not None and w.current_phase != phase: continue
            if agency is not None and w.agency != agency: continue
            if has_exception is not None:
                if has_exception != bool(w.active_exception_id): continue
            out.append(w)
        return out

    def append_phase(self, workflow_id: str, p: Phase) -> None:
        self._phases.setdefault(workflow_id, []).append(p)

    def update_phase(self, workflow_id: str, name: str, **patch) -> None:
        for p in self._phases.get(workflow_id, []):
            if p.name == name:
                for k, v in patch.items():
                    setattr(p, k, v)
                return

    def get_phases(self, workflow_id: str) -> list[Phase]:
        return self._phases.get(workflow_id, [])

    def append_span(self, s: OtelSpan) -> None:
        wid = s.attributes.get("workflow.id")
        if wid:
            self._spans.setdefault(wid, []).append(s)

    def get_spans(self, workflow_id: str) -> list[OtelSpan]:
        return self._spans.get(workflow_id, [])

    def upsert_exception(self, e: Exception) -> None:
        self._exceptions[e.id] = e
        w = self._workflows.get(e.workflow_id)
        if w and not e.resolved_at:
            w.active_exception_id = e.id

    def get_exception(self, id: str) -> Exception | None:
        return self._exceptions.get(id)

    def list_exceptions(self, include_resolved: bool = False) -> list[Exception]:
        return [e for e in self._exceptions.values() if include_resolved or not e.resolved_at]

    def resolve_exception(self, id: str, resolved_by: str) -> None:
        import time as _time
        e = self._exceptions.get(id)
        if not e: return
        e.resolved_at = _time.time()
        e.resolved_by = resolved_by
        w = self._workflows.get(e.workflow_id)
        if w and w.active_exception_id == id:
            w.active_exception_id = None

    def append_ledger(self, workflow_id: str, entry: ActionLedgerEntry) -> None:
        w = self._workflows.get(workflow_id)
        if w:
            w.action_ledger.append(entry)

    def upsert_policy(self, p: AutonomyPolicy) -> None:
        self._policies[p.id] = p

    def list_policies(self) -> list[AutonomyPolicy]:
        return list(self._policies.values())

    def append_amplification(self, workflow_id: str, a: SkillAmplification) -> None:
        self._amplifications.setdefault(workflow_id, []).append(a)

    def get_amplifications(self, workflow_id: str) -> list[SkillAmplification]:
        return self._amplifications.get(workflow_id, [])
```

- [ ] **Step 3: Run, PASS, no commit.**

---

### Task 2.3: Triage

**Files:**
- Create: `control-plane-py/src/server/services/triage.py`
- Create: `control-plane-py/tests/unit/test_triage.py`

- [ ] **Step 1: Test FIRST**

```python
# control-plane-py/tests/unit/test_triage.py
import time
from src.server.services.triage import Triage
from src.shared.events import FleetEvent


def test_does_not_wake_on_phase_started():
    t = Triage()
    e = FleetEvent(type="workflow.phase.started", workflow_id="A", phase="Intake")
    assert t.should_wake(e) is False


def test_wakes_on_exception_detected():
    t = Triage()
    e = FleetEvent(type="workflow.exception.detected", workflow_id="A", category="duplicate-invoice", severity="high")
    assert t.should_wake(e) is True


def test_detects_anomaly_on_3_dups_in_60s():
    t = Triage()
    now = time.time()
    for i in range(3):
        e = FleetEvent(type="workflow.exception.detected", workflow_id=f"W-{i}", category="duplicate-invoice", severity="high")
        t.observe(e, now=now + i)
    a = t.detect_anomaly(now=now + 3)
    assert a is not None
    assert a["pattern"] == "duplicate-burst"
```

- [ ] **Step 2: Implement**

```python
# control-plane-py/src/server/services/triage.py
from __future__ import annotations
import time
from src.shared.events import FleetEvent, wakes_fleet_manager


class Triage:
    def __init__(self) -> None:
        self._recent_dups: list[tuple[str, float]] = []

    def should_wake(self, e: FleetEvent) -> bool:
        return wakes_fleet_manager(e)

    def observe(self, e: FleetEvent, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if e.type == "workflow.exception.detected" and getattr(e, "category", None) == "duplicate-invoice":
            self._recent_dups.append((e.workflow_id or "", now))
            self._recent_dups = [(w, t) for w, t in self._recent_dups if now - t <= 60]

    def detect_anomaly(self, now: float | None = None) -> dict | None:
        now = now if now is not None else time.time()
        dups = [(w, t) for w, t in self._recent_dups if now - t <= 60]
        if len(dups) >= 3:
            return {"pattern": "duplicate-burst", "workflow_ids": [w for w, _ in dups]}
        return None
```

- [ ] **Step 3: Run, PASS, no commit.**

---

### Task 2.4: AuditLogger

**Files:**
- Create: `control-plane-py/src/server/services/audit_logger.py`

- [ ] **Step 1: Implement (no test — too trivial)**

```python
# control-plane-py/src/server/services/audit_logger.py
from __future__ import annotations
import time as _time
from typing import Any


class AuditLogger:
    def __init__(self) -> None:
        self._entries: list[dict] = []

    def log(self, action: str, details: Any) -> None:
        self._entries.append({"action": action, "details": details, "timestamp": _time.time()})

    def list(self) -> list[dict]:
        return list(self._entries)
```

- [ ] **Step 2: No commit.**

---

## Phase 3 — FastAPI server skeleton

### Task 3.1: FastAPI main + lifespan

**Files:**
- Create: `control-plane-py/src/server/main.py`
- Create: `control-plane-py/src/server/__init__.py`
- Create: `control-plane-py/src/__init__.py`
- Create: `control-plane-py/src/shared/__init__.py`
- Create: `control-plane-py/src/server/services/__init__.py`

- [ ] **Step 1: Empty `__init__.py` files** in all four package locations above.

- [ ] **Step 2: Write `main.py`**

```python
# control-plane-py/src/server/main.py
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.server.services.event_bus import EventBus
from src.server.services.state_store import StateStore
from src.server.services.audit_logger import AuditLogger

load_dotenv()


class AppState:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.store = StateStore()
        self.audit = AuditLogger()


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup placeholder — Phase 5 wires Fleet Manager, Phase 10 wires simulator
    yield
    # Shutdown


app = FastAPI(title="WPP Control Plane (Python POC1)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}


# Routes will be wired in Task 3.3
```

- [ ] **Step 3: Smoke test**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
uv run uvicorn src.server.main:app --port 3001 &
SRV=$!
sleep 3
curl -s http://localhost:3001/api/health
echo
kill $SRV
```

Expected: `{"ok":true}`.

- [ ] **Step 4: No commit.**

---

### Task 3.2: SSE hub + stream routes

**Files:**
- Create: `control-plane-py/src/server/services/sse_hub.py`
- Create: `control-plane-py/src/server/routes/__init__.py`
- Create: `control-plane-py/src/server/routes/stream.py`

- [ ] **Step 1: Implement SSE hub**

```python
# control-plane-py/src/server/services/sse_hub.py
from __future__ import annotations
import asyncio
import json
from typing import Any, AsyncIterator, Literal

Topic = Literal["fleet", "fleet-manager", "orchestration"]


class SSEHub:
    def __init__(self) -> None:
        self._queues: dict[Topic, set[asyncio.Queue]] = {"fleet": set(), "fleet-manager": set(), "orchestration": set()}

    def subscribe(self, topic: Topic) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._queues[topic].add(q)
        return q

    def unsubscribe(self, topic: Topic, q: asyncio.Queue) -> None:
        self._queues[topic].discard(q)

    def broadcast(self, topic: Topic, data: Any) -> None:
        payload = json.dumps(data, default=str)
        for q in list(self._queues[topic]):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def stream(self, topic: Topic) -> AsyncIterator[str]:
        q = self.subscribe(topic)
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        finally:
            self.unsubscribe(topic, q)
```

- [ ] **Step 2: Stream routes**

```python
# control-plane-py/src/server/routes/stream.py
from __future__ import annotations
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from src.server.main import app_state

router = APIRouter(prefix="/api/stream")


@router.get("/fleet")
async def stream_fleet():
    return EventSourceResponse(app_state.hub.stream("fleet"))


@router.get("/fleet-manager")
async def stream_fleet_manager():
    return EventSourceResponse(app_state.hub.stream("fleet-manager"))


@router.get("/orchestration")
async def stream_orchestration():
    return EventSourceResponse(app_state.hub.stream("orchestration"))
```

- [ ] **Step 3: Update `main.py` to add `hub` to AppState and mount router**

In `main.py`, add:
```python
from src.server.services.sse_hub import SSEHub
# Inside AppState.__init__:
self.hub = SSEHub()
# After app creation:
from src.server.routes.stream import router as stream_router
app.include_router(stream_router)
# Wire bus -> hub fan-out (every event broadcast on "fleet" topic)
app_state.bus.on_any(lambda e: app_state.hub.broadcast("fleet", e.model_dump()))
```

- [ ] **Step 4: Smoke test SSE**

```bash
uv run uvicorn src.server.main:app --port 3001 &
SRV=$!
sleep 3
# Just verify endpoint responds with text/event-stream
curl -s -I http://localhost:3001/api/stream/fleet | head -3
kill $SRV
```

Expected: `HTTP/1.1 200 OK`, `content-type: text/event-stream`.

- [ ] **Step 5: No commit.**

---

### Task 3.3: REST routes (workflows, exceptions, policy, simulator, audit, evals, orchestration)

**Files:**
- Create: `control-plane-py/src/server/routes/workflows.py`
- Create: `control-plane-py/src/server/routes/exceptions.py`
- Create: `control-plane-py/src/server/routes/policy.py`
- Create: `control-plane-py/src/server/routes/simulator.py`
- Create: `control-plane-py/src/server/routes/audit.py`
- Create: `control-plane-py/src/server/routes/evals.py`
- Create: `control-plane-py/src/server/routes/orchestration.py`
- Create: `control-plane-py/src/server/routes/internal_durable_event.py`
- Modify: `control-plane-py/src/server/main.py` (mount all routers)
- Create: `control-plane-py/src/server/fixtures/` (copy from v1)
- Create: `control-plane-py/src/shared/policies.yaml` (copy from v1)

- [ ] **Step 1: Copy fixtures + policies.yaml from v1**

```bash
cp "c:/dev/ghcp sdk stuff/control-plane/src/server/fixtures/vendors.json" "c:/dev/ghcp sdk stuff/control-plane-py/src/server/fixtures/"
cp "c:/dev/ghcp sdk stuff/control-plane/src/server/fixtures/purchase-orders.json" "c:/dev/ghcp sdk stuff/control-plane-py/src/server/fixtures/"
cp "c:/dev/ghcp sdk stuff/control-plane/src/server/fixtures/agencies.json" "c:/dev/ghcp sdk stuff/control-plane-py/src/server/fixtures/"
cp "c:/dev/ghcp sdk stuff/control-plane/src/server/fixtures/policy-refs.json" "c:/dev/ghcp sdk stuff/control-plane-py/src/server/fixtures/"
cp "c:/dev/ghcp sdk stuff/control-plane/src/shared/policies.yaml" "c:/dev/ghcp sdk stuff/control-plane-py/src/shared/"
```

- [ ] **Step 2: Workflows route**

```python
# control-plane-py/src/server/routes/workflows.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from src.server.main import app_state

router = APIRouter(prefix="/api/workflows")


@router.get("/")
async def list_workflows(status: str | None = None, phase: str | None = None, agency: str | None = None, has_exception: bool | None = None):
    items = app_state.store.list_workflows(status=status, phase=phase, agency=agency, has_exception=has_exception)
    return [w.model_dump() for w in items]


@router.get("/{id}")
async def get_workflow(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    active = app_state.store.get_exception(w.active_exception_id) if w.active_exception_id else None
    return {
        "workflow": w.model_dump(),
        "phases": [p.model_dump() for p in app_state.store.get_phases(id)],
        "spans": [s.model_dump() for s in app_state.store.get_spans(id)],
        "amplifications": [a.model_dump() for a in app_state.store.get_amplifications(id)],
        "active_exception": active.model_dump() if active else None,
    }
```

- [ ] **Step 3: Exceptions route**

```python
# control-plane-py/src/server/routes/exceptions.py
from __future__ import annotations
import time
from fastapi import APIRouter
from pydantic import BaseModel
from src.server.main import app_state
from src.shared.types import ActionLedgerEntry

router = APIRouter(prefix="/api/exceptions")


class BulkResolveBody(BaseModel):
    exception_ids: list[str]
    resolution: str
    resolved_by: str


@router.get("/")
async def list_exceptions(include_resolved: bool = False):
    return [e.model_dump() for e in app_state.store.list_exceptions(include_resolved=include_resolved)]


@router.post("/bulk-resolve")
async def bulk_resolve(body: BulkResolveBody):
    resolved = 0
    for id in body.exception_ids:
        exc = app_state.store.get_exception(id)
        if not exc: continue
        app_state.store.resolve_exception(id, body.resolved_by)
        w = app_state.store.get_workflow(exc.workflow_id)
        if w and w.status == "awaiting_hitl":
            w.status = "in_progress"
            w.action_ledger.append(ActionLedgerEntry(
                workflow_id=w.id, timestamp=time.time(),
                actor_kind="human", actor_id=body.resolved_by,
                action=f"bulk-resolve:{body.resolution}",
                revocable=False, details={"exception_id": id}
            ))
        resolved += 1
    # Phase 10 will add: signal MAF runtime via raise_event for the Approval-step HITL case
    return {"resolved": resolved}
```

- [ ] **Step 4: Policy route**

```python
# control-plane-py/src/server/routes/policy.py
from __future__ import annotations
import time
from pathlib import Path
import yaml
from fastapi import APIRouter
from pydantic import BaseModel
from src.server.main import app_state
from src.shared.types import AutonomyPolicy

router = APIRouter(prefix="/api/policy")

_change_requests: list[dict] = []


def _load_policies() -> None:
    path = Path(__file__).resolve().parents[2] / "shared" / "policies.yaml"
    data = yaml.safe_load(path.read_text())
    for p in data["policies"]:
        app_state.store.upsert_policy(AutonomyPolicy(
            id=p["id"], description=p["description"], current_value=p["value"],
            git_sha=p["gitSha"], author=p["author"],
            updated_at=time.mktime(time.strptime(p["updatedAt"], "%Y-%m-%dT%H:%M:%SZ")),
        ))


_load_policies()


class DryRunBody(BaseModel):
    policy_id: str
    proposed_value: float | str | bool
    scope_days: int = 7


class ProposeChangeBody(BaseModel):
    policy_id: str
    proposed_value: float | str | bool
    rationale: str
    proposed_by: str


@router.get("/")
async def list_policies():
    return [p.model_dump() for p in app_state.store.list_policies()]


@router.post("/dry-run")
async def dry_run(body: DryRunBody):
    cutoff = time.time() - body.scope_days * 86400
    completed = [w for w in app_state.store.list_workflows() if w.status == "completed" and w.created_at >= cutoff]
    would_be_different = 0
    impacted = []
    if body.policy_id == "invoice-p2p.approval.auto_threshold":
        threshold = float(body.proposed_value)
        for w in completed:
            if w.invoice.amount <= threshold:
                would_be_different += 1
                impacted.append(w.id)
    return {
        "scope_days": body.scope_days,
        "total_evaluated": len(completed),
        "would_be_different": would_be_different,
        "impacted_workflow_ids": impacted[:20],
    }


@router.post("/propose-change")
async def propose_change(body: ProposeChangeBody):
    id = f"CR-{int(time.time())}"
    _change_requests.append({"id": id, **body.model_dump(), "created_at": time.time()})
    return {"id": id}


@router.get("/change-requests")
async def list_change_requests():
    return _change_requests
```

- [ ] **Step 5: Simulator + audit + evals + orchestration + internal_durable_event routes**

`simulator.py`:
```python
# control-plane-py/src/server/routes/simulator.py
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/simulator")


class InjectBody(BaseModel):
    scenario: str | None = None


@router.post("/inject")
async def inject(body: InjectBody):
    # Phase 10 wires this to the MAF durable client to start an InvoiceP2PWorkflow
    from src.server.services import simulator_orchestrator  # lazy to avoid cycles
    workflow_id = await simulator_orchestrator.spawn_workflow(scenario=body.scenario)
    return {"workflow_id": workflow_id}
```

`audit.py`:
```python
# control-plane-py/src/server/routes/audit.py
from __future__ import annotations
from fastapi import APIRouter
from src.server.main import app_state

router = APIRouter(prefix="/api/audit")


@router.get("/")
async def list_audit():
    return app_state.audit.list()
```

`evals.py`:
```python
# control-plane-py/src/server/routes/evals.py
from __future__ import annotations
import time, random
from fastapi import APIRouter
from src.server.main import app_state

router = APIRouter(prefix="/api/evals")

# Stub: returns synthetic samples (per spec §6.6 — labelled in UI as synthetic for honesty)
_evals: list[dict] = []


@router.get("/")
async def list_evals():
    completed = [w for w in app_state.store.list_workflows() if w.status == "completed"]
    if completed and (not _evals or _evals[-1]["ran_at"] < time.time() - 5):
        pick = random.choice(completed)
        _evals.append({
            "id": f"EVAL-{int(time.time()*1000)}",
            "workflow_id": pick.id,
            "ran_at": time.time(),
            "task_adherence": 0.85 + random.random() * 0.15,
            "safety": 0.95 + random.random() * 0.05,
            "tool_accuracy": 0.88 + random.random() * 0.12,
        })
    return list(reversed(_evals[-50:]))
```

`orchestration.py`:
```python
# control-plane-py/src/server/routes/orchestration.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from src.server.main import app_state

router = APIRouter(prefix="/api/workflows")


@router.get("/{id}/orchestration")
async def get_orchestration(id: str):
    w = app_state.store.get_workflow(id)
    if not w:
        raise HTTPException(404)
    # Phase 9 fills this from the durable runtime; for now, return the locally-tracked
    # step + executor history captured from /internal/durable-event webhooks.
    history = app_state.orchestration_history.get(id, [])
    return {
        "instance_id": w.orchestration_instance_id,
        "status": w.status,
        "history": history,
    }
```

`internal_durable_event.py`:
```python
# control-plane-py/src/server/routes/internal_durable_event.py
from __future__ import annotations
import time
from fastapi import APIRouter
from pydantic import BaseModel
from src.server.main import app_state
from src.shared.events import FleetEvent

router = APIRouter(prefix="/internal")


class DurableEventBody(BaseModel):
    workflow_id: str
    instance_id: str | None = None
    kind: str  # workflow.started, step.started, step.completed, executor.invoked, validator.blocked, suspended, resumed, workflow.completed
    payload: dict


@router.post("/durable-event")
async def receive_durable_event(body: DurableEventBody):
    # Append to orchestration history
    app_state.orchestration_history.setdefault(body.workflow_id, []).append({
        "kind": body.kind, "payload": body.payload, "at": time.time()
    })
    # Fan to UI via SSE
    app_state.hub.broadcast("orchestration", {
        "kind": body.kind, "workflow_id": body.workflow_id, "payload": body.payload
    })
    # Translate selected events into FleetEvents (so the workflow appears in dashboards / triggers FM)
    if body.kind == "workflow.started":
        app_state.bus.emit(FleetEvent(type="workflow.started", workflow_id=body.workflow_id))
    elif body.kind == "step.started":
        app_state.bus.emit(FleetEvent(type="workflow.phase.started", workflow_id=body.workflow_id, phase=body.payload.get("step")))
    elif body.kind == "step.completed":
        app_state.bus.emit(FleetEvent(type="workflow.phase.completed", workflow_id=body.workflow_id, phase=body.payload.get("step"), durationMs=body.payload.get("duration_ms", 0)))
    elif body.kind == "validator.blocked":
        app_state.bus.emit(FleetEvent(type="workflow.exception.detected", workflow_id=body.workflow_id, category="validator-blocked", severity="high"))
    elif body.kind == "suspended":
        app_state.bus.emit(FleetEvent(type="workflow.hitl.requested", workflow_id=body.workflow_id, reason=body.payload.get("reason", "approval")))
    elif body.kind == "workflow.completed":
        app_state.bus.emit(FleetEvent(type="workflow.resolved", workflow_id=body.workflow_id, resolution="completed"))
    return {"received": True}
```

- [ ] **Step 6: Wire all routes + add `orchestration_history` to AppState**

In `main.py`, extend `AppState.__init__`:
```python
self.orchestration_history: dict[str, list[dict]] = {}
```

After the SSE include, mount all the new routers:
```python
from src.server.routes.workflows import router as workflows_router
from src.server.routes.exceptions import router as exceptions_router
from src.server.routes.policy import router as policy_router
from src.server.routes.simulator import router as simulator_router
from src.server.routes.audit import router as audit_router
from src.server.routes.evals import router as evals_router
from src.server.routes.orchestration import router as orchestration_router
from src.server.routes.internal_durable_event import router as durable_event_router

for r in (workflows_router, exceptions_router, policy_router, simulator_router, audit_router, evals_router, orchestration_router, durable_event_router):
    app.include_router(r)
```

- [ ] **Step 7: Smoke test all routes**

```bash
uv run uvicorn src.server.main:app --port 3001 &
SRV=$!
sleep 3
curl -s http://localhost:3001/api/health
echo
curl -s http://localhost:3001/api/workflows | head -c 50
echo
curl -s http://localhost:3001/api/exceptions | head -c 50
echo
curl -s http://localhost:3001/api/policy | head -c 200
echo
kill $SRV
```

Expected: `{"ok":true}`, `[]`, `[]`, list of 3 policies.

- [ ] **Step 8: No commit.**

---

## Phase 4 — 10 SKILL.md files

### Task 4.1: Author all 10 SKILL files

**Files:**
- Copy from v1: `control-plane-py/src/server/skills/fleet-manager.skill.md` (lift verbatim from `c:\dev\ghcp sdk stuff\control-plane\src\server\skills\fleet-manager.skill.md`)
- Create 9 new: `control-plane-py/src/server/skills/{field_extractor,line_item_extractor,anomaly_flagger,invoice_classifier,gl_coder,cost_centre_assigner,exception_classifier,root_cause_explainer,resolution_recommender}.skill.md`

- [ ] **Step 1: Copy fleet-manager.skill.md from v1**

```bash
cp "c:/dev/ghcp sdk stuff/control-plane/src/server/skills/fleet-manager.skill.md" "c:/dev/ghcp sdk stuff/control-plane-py/src/server/skills/"
```

- [ ] **Step 2: Write each of the 9 finance skills**

Each follows the same shape — frontmatter + role + steps. Authoritative content:

`field_extractor.skill.md`:
```markdown
---
name: field-extractor
description: Extract structured invoice fields from raw OCR/parsed input. Flag low-confidence fields for sub-agent reasoning.
allowed-tools: workday.getVendor, d365.parseInvoice
---
You are the Invoice Field Extractor for the WPP Finance P2P workflow. Given a raw parsed invoice payload, return a structured JSON object with: vendor_id, invoice_number, amount, currency, po_ref, line_items[]. For any field you are below 0.8 confidence on, set its value to {"value": <best guess>, "confidence": <float>, "needs_subagent": true}. Be terse — return only the JSON.
```

`line_item_extractor.skill.md`:
```markdown
---
name: line-item-extractor
description: Parse line items from a multi-line invoice payload.
allowed-tools: d365.parseInvoice
---
You parse invoice line items. Given the raw line item region, return a JSON array of {description, qty, unit_price}. Validate that each line has positive qty and price. If a line is malformed, omit it and add a "skipped" entry to your output explaining why.
```

`anomaly_flagger.skill.md`:
```markdown
---
name: anomaly-flagger
description: Flag suspicious invoice patterns (vendor mismatch, unusual amounts, unexpected GL codes).
allowed-tools: workday.getVendor
---
You assess whether the extracted invoice is anomalous given vendor history and typical patterns. Return a JSON object: {is_anomalous: bool, signals: [list of short reasons]}. Flag if amount is >3σ from vendor history (assume σ=0.3*mean for demo), if PO is closed, if currency mismatch.
```

`invoice_classifier.skill.md`:
```markdown
---
name: invoice-classifier
description: Categorise an invoice as media-production / talent-fees / post-production / other.
allowed-tools: workday.getVendor
---
You classify invoices into one of four categories: media-production, talent-fees, post-production, other. Use the vendor name, invoice description, and line items as signals. Return JSON: {category: <one of four>, rationale: <one short sentence>}.
```

`gl_coder.skill.md`:
```markdown
---
name: gl-coder
description: Pick the correct GL account for an invoice given category, vendor history, and active GL list.
allowed-tools: d365.matchPO, d365.postGLEntry
---
You select the GL account for an invoice. Given the category, vendor, and the list of active GLs, choose the best match. Map: media-production → GL-5000, talent-fees → GL-5100, post-production → GL-5200. If category is "other", choose GL-5000 as fallback. Return JSON: {gl_account_id: <id>, confidence: <float>}.

IMPORTANT: For a workflow whose vendor name contains "DEMO_FAIL", deliberately choose GL-9999 (an inactive code) — this is the scripted bounded-probabilism case for the demo.
```

`cost_centre_assigner.skill.md`:
```markdown
---
name: cost-centre-assigner
description: Assign the cost centre for an invoice given agency, project, and vendor.
allowed-tools: workday.getCostCentre
---
You assign cost centres. Map agencies to default cost centres: Ogilvy-US → CC-001, GroupM-US → CC-002, Wunderman-US → CC-003. Return JSON: {cost_centre_id: <id>, rationale: <short reason>}.
```

`exception_classifier.skill.md`:
```markdown
---
name: exception-classifier
description: Classify an unmatched bank statement item into a known taxonomy.
allowed-tools: payment.reconcileStatement
---
You classify reconciliation exceptions into one of: timing-difference, amount-mismatch, missing-payment, duplicate-payment, fraud-suspect. Return JSON: {classification: <one of five>, confidence: <float>}.
```

`root_cause_explainer.skill.md`:
```markdown
---
name: root-cause-explainer
description: Propose a root cause explanation for an unmatched bank statement item.
allowed-tools: payment.reconcileStatement
---
Given an unmatched bank statement item and its classification, propose a brief root cause. Output JSON: {root_cause: <one short paragraph>}.
```

`resolution_recommender.skill.md`:
```markdown
---
name: resolution-recommender
description: Recommend an action for a classified reconciliation exception.
allowed-tools: payment.reconcileStatement
---
Given a classified reconciliation exception with proposed root cause, recommend an action. Choose from: write-off, escalate-to-controller, retry-payment, request-vendor-clarification. Output JSON: {action: <one of four>, justification: <short sentence>}.
```

- [ ] **Step 3: No commit.**

---

## Phase 5 — Fleet Manager Python port

### Task 5.1: Fleet Manager MCP tools (5 tools)

**Files:**
- Create: `control-plane-py/src/server/mcp_tools/__init__.py`
- Create: `control-plane-py/src/server/mcp_tools/query_fleet.py`
- Create: `control-plane-py/src/server/mcp_tools/query_traces.py`
- Create: `control-plane-py/src/server/mcp_tools/compose_exception.py`
- Create: `control-plane-py/src/server/mcp_tools/propose_skill_amp.py`
- Create: `control-plane-py/src/server/mcp_tools/dry_run_policy.py`

**Tool registration shape:** discovered in Phase 0.2 spike. Apply the same pattern across all 5 tools. The example below assumes `define_tool(name, description=..., parameters=..., handler=...)` returning an opaque object that the GHCP SDK accepts. Adapt to actual API.

- [ ] **Step 1: `query_fleet.py`**

```python
# control-plane-py/src/server/mcp_tools/query_fleet.py
from __future__ import annotations
from copilot_sdk import define_tool  # adapt import per spike
from src.server.services.state_store import StateStore


def query_fleet_tool(store: StateStore):
    async def handler(args: dict) -> dict:
        items = store.list_workflows(
            phase=args.get("phase"),
            agency=args.get("agency"),
            has_exception=args.get("has_exception"),
        )
        excs = store.list_exceptions()
        by_phase: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for w in items:
            by_phase[w.current_phase] = by_phase.get(w.current_phase, 0) + 1
            by_status[w.status] = by_status.get(w.status, 0) + 1
        return {
            "total": len(items),
            "by_phase": by_phase,
            "by_status": by_status,
            "open_exception_count": len(excs),
            "recent_exceptions": [
                {"id": e.id, "workflow_id": e.workflow_id, "category": e.category, "severity": e.severity}
                for e in excs[-5:]
            ],
        }
    return define_tool(
        "query-fleet",
        description="Aggregated fleet state.",
        parameters={"type": "object", "properties": {
            "phase": {"type": "string"}, "agency": {"type": "string"}, "has_exception": {"type": "boolean"}
        }},
        handler=handler,
    )
```

- [ ] **Step 2: `query_traces.py`**

```python
# control-plane-py/src/server/mcp_tools/query_traces.py
from __future__ import annotations
from copilot_sdk import define_tool
from src.server.services.state_store import StateStore


def query_traces_tool(store: StateStore):
    async def handler(args: dict) -> list:
        wid = args["workflow_id"]
        spans = store.get_spans(wid)
        if "phase" in args:
            spans = [s for s in spans if s.attributes.get("workflow.phase") == args["phase"]]
        return [s.model_dump() for s in spans]
    return define_tool(
        "query-traces",
        description="OTEL spans for a workflow.",
        parameters={"type": "object",
                    "properties": {"workflow_id": {"type": "string"}, "phase": {"type": "string"}},
                    "required": ["workflow_id"]},
        handler=handler,
    )
```

- [ ] **Step 3: `compose_exception.py` (hook-gated)**

```python
# control-plane-py/src/server/mcp_tools/compose_exception.py
from __future__ import annotations
import time
from nanoid import generate as nanoid
from copilot_sdk import define_tool
from src.server.services.state_store import StateStore
from src.server.services.audit_logger import AuditLogger
from src.shared.types import Exception_ as Exception, ExceptionOption


def compose_exception_tool(store: StateStore, audit: AuditLogger):
    async def handler(args: dict) -> dict:
        # Hook-gated non-revocable action: pre-audit BEFORE write.
        audit.log("compose-exception.pre", {"workflow_id": args["workflow_id"]})
        e = Exception(
            id=f"EXC-{nanoid(size=8)}",
            workflow_id=args["workflow_id"],
            composed_by="fleet-manager",
            severity=args["severity"],
            category=args["category"],
            summary=args["summary"],
            recommendation=args["recommendation"],
            options=[ExceptionOption(**o) for o in args.get("options", [
                {"label": "Approve", "action": "approve", "non_revocable": False},
                {"label": "Reject", "action": "reject", "non_revocable": False},
            ])],
            related_policy_refs=args.get("related_policy_refs", []),
            bulk_candidate_ids=args.get("bulk_candidate_ids"),
            confidence=args.get("confidence", 0.8),
            created_at=time.time(),
        )
        store.upsert_exception(e)
        audit.log("compose-exception.emitted", {"exception_id": e.id, "workflow_id": e.workflow_id})
        return {"exception_id": e.id}
    return define_tool(
        "compose-exception",
        description="Write an exception to the queue.",
        parameters={"type": "object", "properties": {
            "workflow_id": {"type": "string"},
            "severity": {"type": "string", "enum": ["critical", "high", "medium"]},
            "category": {"type": "string"},
            "summary": {"type": "string"},
            "recommendation": {"type": "string"},
            "options": {"type": "array"},
            "related_policy_refs": {"type": "array"},
            "bulk_candidate_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        }, "required": ["workflow_id", "severity", "category", "summary", "recommendation"]},
        handler=handler,
    )
```

- [ ] **Step 4: `propose_skill_amp.py`**

```python
# control-plane-py/src/server/mcp_tools/propose_skill_amp.py
from __future__ import annotations
import time
from nanoid import generate as nanoid
from copilot_sdk import define_tool
from src.server.services.state_store import StateStore
from src.shared.types import SkillAmplification


def propose_skill_amp_tool(store: StateStore):
    async def handler(args: dict) -> dict:
        a = SkillAmplification(
            id=f"AMP-{nanoid(size=8)}",
            workflow_id=args["workflow_id"],
            policy_context=args.get("policy_context", []),
            precedents=args.get("precedents", []),
            recommended_approach=args["recommended_approach"],
            created_at=time.time(),
        )
        store.append_amplification(args["workflow_id"], a)
        return {"amplification_id": a.id}
    return define_tool(
        "propose-skill-amplification",
        description="Emit a coach card for an operator.",
        parameters={"type": "object", "properties": {
            "workflow_id": {"type": "string"},
            "policy_context": {"type": "array"},
            "precedents": {"type": "array"},
            "recommended_approach": {"type": "string"},
        }, "required": ["workflow_id", "recommended_approach"]},
        handler=handler,
    )
```

- [ ] **Step 5: `dry_run_policy.py`**

Reuse the route's logic by calling into a shared function. Extract first:

```python
# control-plane-py/src/server/mcp_tools/dry_run_policy.py
from __future__ import annotations
import time
from copilot_sdk import define_tool
from src.server.services.state_store import StateStore


def dry_run_policy_impl(store: StateStore, policy_id: str, proposed_value, scope_days: int = 7) -> dict:
    cutoff = time.time() - scope_days * 86400
    completed = [w for w in store.list_workflows() if w.status == "completed" and w.created_at >= cutoff]
    would_be_different = 0
    impacted = []
    if policy_id == "invoice-p2p.approval.auto_threshold":
        threshold = float(proposed_value)
        for w in completed:
            if w.invoice.amount <= threshold:
                would_be_different += 1
                impacted.append(w.id)
    return {
        "scope_days": scope_days,
        "total_evaluated": len(completed),
        "would_be_different": would_be_different,
        "impacted_workflow_ids": impacted[:20],
    }


def dry_run_policy_tool(store: StateStore):
    async def handler(args: dict) -> dict:
        return dry_run_policy_impl(store, args["policy_id"], args["proposed_value"], args.get("scope_days", 7))
    return define_tool(
        "dry-run-policy",
        description="Simulate a policy value change against completed workflows.",
        parameters={"type": "object", "properties": {
            "policy_id": {"type": "string"},
            "proposed_value": {},
            "scope_days": {"type": "number"}
        }, "required": ["policy_id", "proposed_value"]},
        handler=handler,
    )
```

Then update `policy.py` route's `/dry-run` endpoint to call `dry_run_policy_impl` directly to avoid code duplication.

- [ ] **Step 6: Tools index**

```python
# control-plane-py/src/server/mcp_tools/__init__.py
from .query_fleet import query_fleet_tool
from .query_traces import query_traces_tool
from .compose_exception import compose_exception_tool
from .propose_skill_amp import propose_skill_amp_tool
from .dry_run_policy import dry_run_policy_tool


def build_fleet_manager_tools(store, audit):
    return [
        query_fleet_tool(store),
        query_traces_tool(store),
        compose_exception_tool(store, audit),
        propose_skill_amp_tool(store),
        dry_run_policy_tool(store),
    ]
```

- [ ] **Step 7: No commit.**

---

### Task 5.2: FleetManagerQueue

**Files:**
- Create: `control-plane-py/src/server/services/fleet_manager_queue.py`
- Create: `control-plane-py/tests/unit/test_fleet_manager_queue.py`

- [ ] **Step 1: Test FIRST**

```python
# control-plane-py/tests/unit/test_fleet_manager_queue.py
import asyncio
import pytest
from src.server.services.fleet_manager_queue import FleetManagerQueue, QueueEntry


@pytest.mark.asyncio
async def test_debounces_per_workflow():
    calls = []
    async def proc(batch):
        calls.append(list(batch))
    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id="A", reason="x"))
    q.enqueue(QueueEntry(workflow_id="A", reason="y"))
    q.enqueue(QueueEntry(workflow_id="A", reason="z"))
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    assert len(calls[0]) == 1


@pytest.mark.asyncio
async def test_batches_multiple_workflows():
    calls = []
    async def proc(batch):
        calls.append(list(batch))
    q = FleetManagerQueue(proc, debounce_ms=100)
    q.enqueue(QueueEntry(workflow_id="A", reason="x"))
    q.enqueue(QueueEntry(workflow_id="B", reason="x"))
    q.enqueue(QueueEntry(workflow_id="C", reason="x"))
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    assert sorted(e.workflow_id for e in calls[0]) == ["A", "B", "C"]
```

- [ ] **Step 2: Implement**

```python
# control-plane-py/src/server/services/fleet_manager_queue.py
from __future__ import annotations
import asyncio
from typing import Awaitable, Callable
from pydantic import BaseModel


class QueueEntry(BaseModel):
    workflow_id: str
    reason: str


class FleetManagerQueue:
    def __init__(self, processor: Callable[[list[QueueEntry]], Awaitable[None]], debounce_ms: int = 2000):
        self._processor = processor
        self._debounce = debounce_ms / 1000.0
        self._pending: dict[str, QueueEntry] = {}
        self._task: asyncio.Task | None = None
        self._flushing = False

    def enqueue(self, entry: QueueEntry) -> None:
        self._pending[entry.workflow_id] = entry
        if not self._task or self._task.done():
            self._task = asyncio.get_event_loop().create_task(self._wait_and_flush())

    def depth(self) -> int:
        return len(self._pending)

    async def _wait_and_flush(self) -> None:
        await asyncio.sleep(self._debounce)
        if self._flushing:
            return
        self._flushing = True
        try:
            batch = list(self._pending.values())
            self._pending.clear()
            if batch:
                await self._processor(batch)
        finally:
            self._flushing = False
```

- [ ] **Step 3: Run, PASS, no commit.**

---

### Task 5.3: FleetManagerService — Python port

**Files:**
- Create: `control-plane-py/src/server/services/fleet_manager_service.py`

- [ ] **Step 1: Implement**

```python
# control-plane-py/src/server/services/fleet_manager_service.py
"""
Python port of v1's FleetManagerService.

API names below assume the Phase 0.2 GHCP SDK Python spike's findings.
If the spike showed different method names, update this file accordingly.
"""
from __future__ import annotations
import subprocess
import asyncio
import time
from pathlib import Path
from typing import Callable
from copilot_sdk import CopilotClient  # adapt per spike
from src.server.services.event_bus import EventBus
from src.server.services.state_store import StateStore
from src.server.services.audit_logger import AuditLogger
from src.server.services.fleet_manager_queue import FleetManagerQueue, QueueEntry
from src.server.services.triage import Triage
from src.server.mcp_tools import build_fleet_manager_tools


def gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


class FleetManagerService:
    def __init__(self, *, bus: EventBus, store: StateStore, audit: AuditLogger,
                 model: str = "gpt-4.1", max_tokens: int = 2000,
                 on_live: Callable[[dict], None] | None = None):
        self._bus = bus
        self._store = store
        self._audit = audit
        self._model = model
        self._max_tokens = max_tokens
        self._on_live = on_live or (lambda e: None)
        self._client: CopilotClient | None = None
        self._session = None
        self._triage = Triage()
        self._queue = FleetManagerQueue(self._process_batch, debounce_ms=2000)
        self._tick_task: asyncio.Task | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        try:
            token = gh_token()
        except Exception as ex:
            print(f"[fleet-manager] gh auth token failed: {ex}; not starting")
            return

        self._client = CopilotClient(github_token=token)
        skill_path = Path(__file__).resolve().parents[1] / "skills" / "fleet-manager.skill.md"
        system_prompt = skill_path.read_text()
        tools = build_fleet_manager_tools(self._store, self._audit)

        self._session = await self._client.create_session(
            model=self._model,
            system_prompt=system_prompt,
            tools=tools,
        )

        # Tool-call event subscription per spike findings
        if hasattr(self._session, "on"):
            self._session.on("tool.execution_start", lambda e: self._on_live({
                "kind": "tool_call",
                "timestamp": time.time(),
                "data": {"stage": "start", "name": getattr(e, "tool_name", None) or e.get("toolName"), "args": getattr(e, "arguments", None)}
            }))
            self._session.on("tool.execution_complete", lambda e: self._on_live({
                "kind": "tool_call",
                "timestamp": time.time(),
                "data": {"stage": "complete", "result": getattr(e, "result", None)}
            }))

        self._bus.on_any(self._observe)
        self._tick_task = asyncio.create_task(self._tick_loop())
        self._started = True
        self._on_live({"kind": "idle", "timestamp": time.time()})

    def _observe(self, event) -> None:
        self._triage.observe(event)
        anomaly = self._triage.detect_anomaly()
        if anomaly:
            from src.shared.events import FleetEvent
            self._bus.emit(FleetEvent(type="fleet.anomaly.detected", pattern=anomaly["pattern"], workflow_ids=anomaly["workflow_ids"]))
        if self._triage.should_wake(event) and event.workflow_id:
            self._queue.enqueue(QueueEntry(workflow_id=event.workflow_id, reason=event.type))
            self._on_live({
                "kind": "wakeup", "timestamp": time.time(),
                "data": {"workflow_id": event.workflow_id, "reason": event.type}
            })

    async def _tick_loop(self) -> None:
        from src.shared.events import FleetEvent
        while True:
            await asyncio.sleep(30)
            self._bus.emit(FleetEvent(type="fleet.tick", timestamp=time.time()))

    async def _process_batch(self, batch: list[QueueEntry]) -> None:
        if self._queue.depth() > 20:
            from src.shared.events import FleetEvent
            self._bus.emit(FleetEvent(type="fleet.overload", queue_depth=self._queue.depth()))
        self._on_live({
            "kind": "reasoning_start", "timestamp": time.time(),
            "data": {"batch_size": len(batch), "workflow_ids": [b.workflow_id for b in batch]}
        })
        prompt_lines = [f"- workflow={b.workflow_id} reason={b.reason}" for b in batch]
        prompt = "Triggering events:\n" + "\n".join(prompt_lines) + "\n\nFollow the SKILL instructions. Call tools as needed. Prefer bulk grouping."
        try:
            r = await self._session.send_message(prompt)  # adapt per spike
            preview = (getattr(r, "content", None) or str(r))[:200]
            self._on_live({"kind": "reasoning_done", "timestamp": time.time(), "data": {"preview": preview}})
        except Exception as ex:
            self._on_live({"kind": "error", "timestamp": time.time(), "data": {"message": str(ex)}})
```

- [ ] **Step 2: Wire into `main.py` lifespan**

In `main.py`:
```python
from src.server.services.fleet_manager_service import FleetManagerService

# After AppState init:
def _on_live(ev):
    app_state.hub.broadcast("fleet-manager", ev)

app_state.fm = FleetManagerService(
    bus=app_state.bus, store=app_state.store, audit=app_state.audit,
    on_live=_on_live,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await app_state.fm.start()
    yield
```

- [ ] **Step 3: Smoke test (server boots, FM tries to start, gh auth token used)**

```bash
uv run uvicorn src.server.main:app --port 3001 &
SRV=$!
sleep 8
curl -s http://localhost:3001/api/health
kill $SRV
```

Expected: server logs include either "Fleet Manager started" or a graceful warning about gh auth/SDK.

- [ ] **Step 4: No commit.**

---

## Phase 6 — Per-phase deterministic executors

Each per-phase MAF graph (Phase 8) is composed of executors. Phase 6 builds the deterministic ones; Phase 7 builds the agent ones; Phase 8 wires them into Pregel graphs.

**Per-executor file convention:** each executor is one Python file in `src/functions/graphs/executors/{deterministic,validators}/`. Each exports an async function `execute(context, input) -> output`. The Pregel graph (Phase 8) wires them as nodes.

### Task 6.1: Deterministic node helpers

**Files:**
- Create: `control-plane-py/src/functions/__init__.py`
- Create: `control-plane-py/src/functions/graphs/__init__.py`
- Create: `control-plane-py/src/functions/graphs/_common.py`
- Create: `control-plane-py/src/functions/graphs/executors/__init__.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/__init__.py`
- Create: `control-plane-py/src/functions/graphs/executors/validators/__init__.py`

- [ ] **Step 1: Empty `__init__.py` files.**

- [ ] **Step 2: Helpers**

```python
# control-plane-py/src/functions/graphs/_common.py
from __future__ import annotations
import os
import time
import httpx


WORKDAY_URL = os.getenv("WORKDAY_MCP_URL", "http://localhost:4101")
D365_URL = os.getenv("D365_MCP_URL", "http://localhost:4102")
MACONOMY_URL = os.getenv("MACONOMY_MCP_URL", "http://localhost:4103")
PAYMENT_URL = os.getenv("PAYMENT_MCP_URL", "http://localhost:4104")


async def call_mcp(base_url: str, tool: str, args: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{base_url}/mcp/call/{tool}", json=args, timeout=10)
        r.raise_for_status()
        return r.json()


def now_ms() -> int:
    return int(time.time() * 1000)
```

- [ ] **Step 3: No commit.**

---

### Task 6.2: Intake deterministic executors + validators

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/doc_intelligence_extract.py`
- Create: `control-plane-py/src/functions/graphs/executors/validators/validate_required_fields.py`
- Create: `control-plane-py/src/functions/graphs/executors/validators/validate_amount_consistency.py`

- [ ] **Step 1: doc_intelligence_extract (stub)**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/doc_intelligence_extract.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    """Stub: in production this calls Azure Document Intelligence. Here, return the seed
    invoice payload as if it had been OCR'd."""
    invoice = input["invoice"]
    return {
        "raw_text": f"INVOICE {invoice['number']} FROM {input['vendor']['name']} TOTAL {invoice['amount']}",
        "structure": {
            "vendor_id": input["vendor"]["id"],
            "amount": invoice["amount"],
            "po_ref": invoice["po_ref"],
            "currency": invoice["currency"],
            "line_items": invoice.get("line_items", []),
        },
    }
```

- [ ] **Step 2: validate_required_fields**

```python
# control-plane-py/src/functions/graphs/executors/validators/validate_required_fields.py
from __future__ import annotations

REQUIRED = {"vendor_id", "amount", "po_ref", "currency"}


async def execute(input: dict) -> dict:
    fields = input.get("extracted", {})
    missing = [r for r in REQUIRED if not fields.get(r)]
    return {"ok": len(missing) == 0, "missing": missing, "extracted": fields}
```

- [ ] **Step 3: validate_amount_consistency**

```python
# control-plane-py/src/functions/graphs/executors/validators/validate_amount_consistency.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    extracted = input["extracted"]
    line_items = extracted.get("line_items", [])
    if not line_items:
        return {"ok": True, "extracted": extracted}
    line_sum = sum(li.get("qty", 1) * li.get("unit_price", 0) for li in line_items)
    diff = abs(line_sum - extracted["amount"])
    tolerance = max(extracted["amount"] * 0.01, 1.0)
    return {"ok": diff <= tolerance, "line_sum": line_sum, "diff": diff, "extracted": extracted}
```

- [ ] **Step 4: No commit.**

---

### Task 6.3: Routing deterministic executors + validators

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/lookup_vendor_context.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/lookup_active_gls.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/lookup_cost_centre_policy.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/record_decision.py`
- Create: `control-plane-py/src/functions/graphs/executors/validators/validate_gl_active.py`
- Create: `control-plane-py/src/functions/graphs/executors/validators/validate_threshold_authority.py`

- [ ] **Step 1: lookup_vendor_context**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/lookup_vendor_context.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, WORKDAY_URL


async def execute(input: dict) -> dict:
    vendor_id = input["vendor"]["id"]
    v = await call_mcp(WORKDAY_URL, "getVendor", {"vendorId": vendor_id})
    return {"vendor": v}
```

- [ ] **Step 2: lookup_active_gls**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/lookup_active_gls.py
from __future__ import annotations

# Hardcoded for v1 — the d365 mock doesn't expose a list endpoint; we use the
# known active set. The bounded-probabilism demo case picks GL-9999 which is NOT in this set.
ACTIVE_GLS = ["GL-5000", "GL-5100", "GL-5200"]


async def execute(input: dict) -> dict:
    return {"active_gls": ACTIVE_GLS}
```

- [ ] **Step 3: lookup_cost_centre_policy**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/lookup_cost_centre_policy.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, WORKDAY_URL


async def execute(input: dict) -> dict:
    cc = await call_mcp(WORKDAY_URL, "getCostCentre", {"costCentreId": "CC-001"})
    return {"cost_centre_policy": cc}
```

- [ ] **Step 4: record_decision**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/record_decision.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, D365_URL


async def execute(input: dict) -> dict:
    workflow_id = input["workflow_id"]
    gl = input["gl_decision"]["gl_account_id"]
    cc = input["cost_centre_decision"]["cost_centre_id"]
    res = await call_mcp(D365_URL, "postGLEntry", {"glAccountId": gl, "amount": input["invoice"]["amount"], "workflowId": workflow_id})
    return {"posted": res, "cost_centre_id": cc}
```

- [ ] **Step 5: validate_gl_active**

```python
# control-plane-py/src/functions/graphs/executors/validators/validate_gl_active.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    gl = input["gl_decision"]["gl_account_id"]
    active = input["active_gls"]
    return {"ok": gl in active, "blocked_reason": None if gl in active else f"GL {gl} not in active set"}
```

- [ ] **Step 6: validate_threshold_authority**

```python
# control-plane-py/src/functions/graphs/executors/validators/validate_threshold_authority.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    amount = input["invoice"]["amount"]
    # Trivial check: above 50000 requires CFO chain (not enforced here in v1).
    return {"ok": True, "requires_cfo": amount > 50000}
```

- [ ] **Step 7: No commit.**

---

### Task 6.4: Approval, Payment deterministic executors

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/load_authority_policy.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/apply_threshold_routing.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/generate_payment_file.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/submit_payment.py`

- [ ] **Step 1: Authority + threshold**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/load_authority_policy.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    return {"auto_threshold": 5000.0, "cfo_threshold": 25000.0}
```

```python
# control-plane-py/src/functions/graphs/executors/deterministic/apply_threshold_routing.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    amount = input["invoice"]["amount"]
    policy = input["policy"]
    if amount <= policy["auto_threshold"]:
        return {"requires_hitl": False, "decision": "auto-approved"}
    return {"requires_hitl": True, "reason": f"amount {amount} > auto threshold {policy['auto_threshold']}"}
```

- [ ] **Step 2: Payment**

```python
# control-plane-py/src/functions/graphs/executors/deterministic/generate_payment_file.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, PAYMENT_URL


async def execute(input: dict) -> dict:
    workflow_id = input["workflow_id"]
    amount = input["invoice"]["amount"]
    res = await call_mcp(PAYMENT_URL, "createPaymentFile", {"workflowId": workflow_id, "amount": amount})
    return {"payment_file": res}
```

```python
# control-plane-py/src/functions/graphs/executors/deterministic/submit_payment.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, PAYMENT_URL


async def execute(input: dict) -> dict:
    """Hook-gated non-revocable action: refuse if no human approval entry on the action ledger."""
    ledger = input.get("action_ledger", [])
    has_human_approval = any(le.get("actor_kind") == "human" and "approve" in le.get("action", "").lower() for le in ledger)
    if input.get("requires_hitl") and not has_human_approval:
        return {"ok": False, "blocked": "requires human approval"}
    file_id = input["payment_file"]["paymentFileId"]
    res = await call_mcp(PAYMENT_URL, "submitPayment", {"paymentFileId": file_id, "simulateTimeout": False})
    return {"ok": True, "result": res}
```

- [ ] **Step 3: No commit.**

---

### Task 6.5: Validation + Reconciliation deterministic executors

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/three_way_match.py`
- Create: `control-plane-py/src/functions/graphs/executors/deterministic/bank_statement_match.py`
- Create: `control-plane-py/src/functions/graphs/executors/validators/validate_recommendation_authority.py`

```python
# control-plane-py/src/functions/graphs/executors/deterministic/three_way_match.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, D365_URL


async def execute(input: dict) -> dict:
    invoice = input["invoice"]
    res = await call_mcp(D365_URL, "matchPO", {"invoiceAmount": invoice["amount"], "poId": invoice["po_ref"]})
    return {"match": res}
```

```python
# control-plane-py/src/functions/graphs/executors/deterministic/bank_statement_match.py
from __future__ import annotations
from src.functions.graphs._common import call_mcp, PAYMENT_URL


async def execute(input: dict) -> dict:
    res = await call_mcp(PAYMENT_URL, "reconcileStatement", {"statementId": "STMT-2026-04-10"})
    return {"reconciliation": res, "unmatched_items": []}  # demo: zero unmatched (recon agents skip)
```

```python
# control-plane-py/src/functions/graphs/executors/validators/validate_recommendation_authority.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    rec = input.get("resolution_recommendation", {}).get("action")
    return {"ok": rec in {"write-off", "escalate-to-controller", "retry-payment", "request-vendor-clarification"}}
```

- [ ] **Step 1: Write all three files.**
- [ ] **Step 2: No commit.**

---

## Phase 7 — Per-phase agent executors

### Task 7.1: Agent executor wrapper

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/agents/_wrapper.py`

This is the shared pattern that each agent executor uses: load a SKILL.md, instantiate a finance-agent GHCP SDK session, run the prompt, parse the JSON result, return.

```python
# control-plane-py/src/functions/graphs/executors/agents/_wrapper.py
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from copilot_sdk import CopilotClient  # adapt per spike


_client: CopilotClient | None = None


def _gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def _get_client() -> CopilotClient:
    global _client
    if _client is None:
        _client = CopilotClient(github_token=_gh_token())
    return _client


def _skill_path(name: str) -> Path:
    return Path(__file__).resolve().parents[4] / "server" / "skills" / f"{name}.skill.md"


async def run_agent_skill(skill_name: str, prompt: str, model: str = "gpt-4.1") -> dict:
    """Run a single ephemeral GHCP SDK session loading the named skill, return parsed JSON output."""
    skill_text = _skill_path(skill_name).read_text()
    client = _get_client()
    session = await client.create_session(
        model=model,
        system_prompt=skill_text,
    )
    response = await session.send_message(prompt)
    text = getattr(response, "content", None) or str(response)
    # Extract first JSON object from the response
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}
```

- [ ] **Step 1: Write the wrapper.**
- [ ] **Step 2: No commit.**

---

### Task 7.2: Intake agent executors (with sub-agent moment)

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_field_extractor.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_line_item_extractor.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_anomaly_flagger.py`

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_field_extractor.py
from __future__ import annotations
import json
from .  _wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    raw = input["raw_text"]
    structure = input["structure"]
    prompt = f"Raw invoice payload:\n{raw}\n\nStructure hints:\n{json.dumps(structure)}\n\nReturn the structured fields as JSON per your role."
    extracted = await run_agent_skill("field_extractor", prompt)

    # Sub-agent delegation: for any field marked needs_subagent, spawn a sub-session
    # focused on just that field. This is the Rich moment for the demo.
    if isinstance(extracted, dict):
        for field, value in list(extracted.items()):
            if isinstance(value, dict) and value.get("needs_subagent"):
                sub_prompt = f"Resolve the value of field '{field}' from this invoice context: {raw}. Best guess so far: {value.get('value')}. Confidence: {value.get('confidence')}. Return JSON with just {{\"value\": <resolved>, \"confidence\": <float>}}."
                sub_result = await run_agent_skill("field_extractor", sub_prompt)
                extracted[field] = sub_result.get("value", value.get("value"))

    return {"extracted": extracted}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_line_item_extractor.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    extracted = input["extracted"]
    line_items_hint = extracted.get("line_items", [])
    prompt = f"Line items region:\n{json.dumps(line_items_hint)}\n\nReturn parsed line items per your role."
    result = await run_agent_skill("line_item_extractor", prompt)
    if isinstance(result, list):
        extracted["line_items"] = result
    elif isinstance(result, dict) and "line_items" in result:
        extracted["line_items"] = result["line_items"]
    return {"extracted": extracted}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_anomaly_flagger.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    extracted = input["extracted"]
    vendor = input["vendor"]
    prompt = f"Vendor:\n{json.dumps(vendor)}\n\nExtracted invoice:\n{json.dumps(extracted)}\n\nAssess anomalies per your role."
    result = await run_agent_skill("anomaly_flagger", prompt)
    return {"anomaly": result, "extracted": extracted}
```

- [ ] **Step 1: Write all three.**
- [ ] **Step 2: No commit.**

---

### Task 7.3: Routing + Reconciliation agent executors

**Files:**
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_invoice_classifier.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_gl_coder.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_cost_centre_assigner.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_exception_classifier.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_root_cause_explainer.py`
- Create: `control-plane-py/src/functions/graphs/executors/agents/agent_resolution_recommender.py`

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_invoice_classifier.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    prompt = f"Vendor: {json.dumps(input['vendor'])}\nInvoice: {json.dumps(input['invoice'])}\n\nClassify per your role."
    return {"classification": await run_agent_skill("invoice_classifier", prompt)}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_gl_coder.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    classification = input["classification"]["category"]
    vendor = input["vendor"]
    active_gls = input["active_gls"]
    prompt = f"Category: {classification}\nVendor: {json.dumps(vendor)}\nActive GLs: {active_gls}\n\nPick GL per your role."
    return {"gl_decision": await run_agent_skill("gl_coder", prompt)}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_cost_centre_assigner.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    prompt = f"Agency: {input['agency']}\nVendor: {json.dumps(input['vendor'])}\n\nAssign cost centre per your role."
    return {"cost_centre_decision": await run_agent_skill("cost_centre_assigner", prompt)}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_exception_classifier.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    prompt = f"Unmatched item: {json.dumps(item)}\n\nClassify per your role."
    return {"exception_classification": await run_agent_skill("exception_classifier", prompt)}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_root_cause_explainer.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    classification = input["exception_classification"]
    prompt = f"Item: {json.dumps(item)}\nClassification: {json.dumps(classification)}\n\nExplain root cause per your role."
    return {"root_cause": await run_agent_skill("root_cause_explainer", prompt)}
```

```python
# control-plane-py/src/functions/graphs/executors/agents/agent_resolution_recommender.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    classification = input["exception_classification"]
    root_cause = input["root_cause"]
    prompt = f"Item: {json.dumps(item)}\nClassification: {json.dumps(classification)}\nRoot cause: {json.dumps(root_cause)}\n\nRecommend per your role."
    return {"resolution_recommendation": await run_agent_skill("resolution_recommender", prompt)}
```

- [ ] **Step 1: Write all six.**
- [ ] **Step 2: No commit.**

---

## Phase 8 — MAF Pregel graphs

Each per-phase graph wires its executors in the order described in the spec. The MAF Pregel API discovered in Phase 0.2 spike is used here. If MAF supports declarative graph composition (e.g. `Graph().add_node().add_edge()`), use that; otherwise fall back to a simple sequential async runner that follows the same pattern.

**Common shape** — each per-phase module exports `async def run(workflow_payload: dict) -> dict`. Inside, it composes its executors and emits durable events to FastAPI via the shared webhook helper.

### Task 8.1: Webhook helper for graph events

**Files:**
- Create: `control-plane-py/src/functions/webhook.py`

```python
# control-plane-py/src/functions/webhook.py
from __future__ import annotations
import os
import httpx


WEBHOOK_URL = os.getenv("FASTAPI_WEBHOOK_URL", "http://localhost:3001/internal/durable-event")


async def emit(workflow_id: str, instance_id: str | None, kind: str, payload: dict) -> None:
    body = {"workflow_id": workflow_id, "instance_id": instance_id, "kind": kind, "payload": payload}
    try:
        async with httpx.AsyncClient() as c:
            await c.post(WEBHOOK_URL, json=body, timeout=5)
    except Exception:
        pass  # webhook failures are logged but don't break the workflow
```

- [ ] **Step 1: Write file. No commit.**

---

### Task 8.2: Intake graph

**Files:**
- Create: `control-plane-py/src/functions/graphs/intake.py`

```python
# control-plane-py/src/functions/graphs/intake.py
from __future__ import annotations
import time
from src.functions.webhook import emit
from src.functions.graphs.executors.deterministic import doc_intelligence_extract
from src.functions.graphs.executors.agents import agent_field_extractor, agent_line_item_extractor, agent_anomaly_flagger
from src.functions.graphs.executors.validators import validate_required_fields, validate_amount_consistency


async def run(workflow_payload: dict) -> dict:
    wid = workflow_payload["workflow_id"]
    iid = workflow_payload.get("instance_id")
    inv = workflow_payload["invoice"]
    vendor = workflow_payload["vendor"]

    async def step(name: str, etype: str, fn, payload):
        t0 = time.time()
        await emit(wid, iid, "executor.invoked", {"name": name, "type": etype, "stage": "start"})
        result = await fn(payload)
        await emit(wid, iid, "executor.invoked", {"name": name, "type": etype, "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})
        return result

    extracted_raw = await step("doc_intelligence_extract", "deterministic", doc_intelligence_extract.execute, workflow_payload)
    field_input = {**workflow_payload, **extracted_raw}
    field_result = await step("agent_field_extractor", "agent", agent_field_extractor.execute, field_input)
    li_result = await step("agent_line_item_extractor", "agent", agent_line_item_extractor.execute, {**workflow_payload, **field_result})
    valid_required = await step("validate_required_fields", "validator", validate_required_fields.execute, li_result)
    if not valid_required["ok"]:
        await emit(wid, iid, "validator.blocked", {"name": "validate_required_fields", "missing": valid_required["missing"]})
        return {"ok": False, "blocked_at": "validate_required_fields"}
    anomaly_result = await step("agent_anomaly_flagger", "agent", agent_anomaly_flagger.execute, {**workflow_payload, **valid_required})
    valid_consistency = await step("validate_amount_consistency", "validator", validate_amount_consistency.execute, anomaly_result)
    if not valid_consistency["ok"]:
        await emit(wid, iid, "validator.blocked", {"name": "validate_amount_consistency", "diff": valid_consistency.get("diff")})
        return {"ok": False, "blocked_at": "validate_amount_consistency"}
    return {"ok": True, "extracted": valid_consistency["extracted"], "anomaly": anomaly_result.get("anomaly")}
```

- [ ] **Step 1: Write file. No commit.**

---

### Task 8.3: Validation graph (deterministic)

**Files:**
- Create: `control-plane-py/src/functions/graphs/validation.py`

```python
# control-plane-py/src/functions/graphs/validation.py
from __future__ import annotations
import time
from src.functions.webhook import emit
from src.functions.graphs.executors.deterministic import three_way_match


async def run(workflow_payload: dict) -> dict:
    wid = workflow_payload["workflow_id"]
    iid = workflow_payload.get("instance_id")
    t0 = time.time()
    await emit(wid, iid, "executor.invoked", {"name": "three_way_match", "type": "deterministic", "stage": "start"})
    result = await three_way_match.execute(workflow_payload)
    await emit(wid, iid, "executor.invoked", {"name": "three_way_match", "type": "deterministic", "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})
    return {"ok": True, "match": result["match"]}
```

- [ ] **Step 1: Write file. No commit.**

---

### Task 8.4: Routing graph (with deliberate fail)

**Files:**
- Create: `control-plane-py/src/functions/graphs/routing.py`

```python
# control-plane-py/src/functions/graphs/routing.py
from __future__ import annotations
import asyncio
import time
from src.functions.webhook import emit
from src.functions.graphs.executors.deterministic import (
    lookup_vendor_context, lookup_active_gls, lookup_cost_centre_policy, record_decision
)
from src.functions.graphs.executors.agents import (
    agent_invoice_classifier, agent_gl_coder, agent_cost_centre_assigner
)
from src.functions.graphs.executors.validators import validate_gl_active, validate_threshold_authority


async def run(workflow_payload: dict) -> dict:
    wid = workflow_payload["workflow_id"]
    iid = workflow_payload.get("instance_id")

    async def step(name: str, etype: str, fn, payload):
        t0 = time.time()
        await emit(wid, iid, "executor.invoked", {"name": name, "type": etype, "stage": "start"})
        r = await fn(payload)
        await emit(wid, iid, "executor.invoked", {"name": name, "type": etype, "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})
        return r

    # Parallel deterministic fan-out
    vc, ag, cp = await asyncio.gather(
        step("lookup_vendor_context", "deterministic", lookup_vendor_context.execute, workflow_payload),
        step("lookup_active_gls", "deterministic", lookup_active_gls.execute, workflow_payload),
        step("lookup_cost_centre_policy", "deterministic", lookup_cost_centre_policy.execute, workflow_payload),
    )
    payload2 = {**workflow_payload, **vc, **ag, **cp}

    classified = await step("agent_invoice_classifier", "agent", agent_invoice_classifier.execute, payload2)
    payload3 = {**payload2, **classified}
    gl = await step("agent_gl_coder", "agent", agent_gl_coder.execute, payload3)
    payload4 = {**payload3, **gl}
    cc = await step("agent_cost_centre_assigner", "agent", agent_cost_centre_assigner.execute, payload4)
    payload5 = {**payload4, **cc}

    v_gl = await step("validate_gl_active", "validator", validate_gl_active.execute, payload5)
    if not v_gl["ok"]:
        await emit(wid, iid, "validator.blocked", {"name": "validate_gl_active", "reason": v_gl["blocked_reason"]})
        return {"ok": False, "blocked_at": "validate_gl_active", "details": v_gl["blocked_reason"]}

    v_thr = await step("validate_threshold_authority", "validator", validate_threshold_authority.execute, payload5)
    if not v_thr["ok"]:
        await emit(wid, iid, "validator.blocked", {"name": "validate_threshold_authority"})
        return {"ok": False, "blocked_at": "validate_threshold_authority"}

    posted = await step("record_decision", "deterministic", record_decision.execute, payload5)
    return {"ok": True, "gl": gl["gl_decision"], "cost_centre": cc["cost_centre_decision"], "posted": posted}
```

- [ ] **Step 1: Write file. No commit.**

---

### Task 8.5: Approval, Payment graphs

**Files:**
- Create: `control-plane-py/src/functions/graphs/approval.py`
- Create: `control-plane-py/src/functions/graphs/payment.py`

```python
# control-plane-py/src/functions/graphs/approval.py
from __future__ import annotations
import time
from src.functions.webhook import emit
from src.functions.graphs.executors.deterministic import load_authority_policy, apply_threshold_routing


async def run(workflow_payload: dict) -> dict:
    """Returns {"requires_hitl": bool, "reason": str | None, "decision": str | None}.
    The InvoiceP2PWorkflow handles the HITL wait at workflow level."""
    wid = workflow_payload["workflow_id"]
    iid = workflow_payload.get("instance_id")

    t0 = time.time()
    await emit(wid, iid, "executor.invoked", {"name": "load_authority_policy", "type": "deterministic", "stage": "start"})
    pol = await load_authority_policy.execute(workflow_payload)
    await emit(wid, iid, "executor.invoked", {"name": "load_authority_policy", "type": "deterministic", "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})

    t0 = time.time()
    await emit(wid, iid, "executor.invoked", {"name": "apply_threshold_routing", "type": "deterministic", "stage": "start"})
    routed = await apply_threshold_routing.execute({**workflow_payload, "policy": pol})
    await emit(wid, iid, "executor.invoked", {"name": "apply_threshold_routing", "type": "deterministic", "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})

    return routed
```

```python
# control-plane-py/src/functions/graphs/payment.py
from __future__ import annotations
import time
from src.functions.webhook import emit
from src.functions.graphs.executors.deterministic import generate_payment_file, submit_payment


async def run(workflow_payload: dict) -> dict:
    wid = workflow_payload["workflow_id"]
    iid = workflow_payload.get("instance_id")

    async def step(name: str, fn, payload):
        t0 = time.time()
        await emit(wid, iid, "executor.invoked", {"name": name, "type": "deterministic", "stage": "start"})
        r = await fn(payload)
        await emit(wid, iid, "executor.invoked", {"name": name, "type": "deterministic", "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})
        return r

    file_result = await step("generate_payment_file", generate_payment_file.execute, workflow_payload)
    submit = await step("submit_payment", submit_payment.execute, {**workflow_payload, **file_result})
    if not submit["ok"]:
        return {"ok": False, "blocked": submit.get("blocked")}
    return {"ok": True, "result": submit["result"]}
```

- [ ] **Step 1: Write both files. No commit.**

---

### Task 8.6: Reconciliation graph

**Files:**
- Create: `control-plane-py/src/functions/graphs/reconciliation.py`

```python
# control-plane-py/src/functions/graphs/reconciliation.py
from __future__ import annotations
import time
from src.functions.webhook import emit
from src.functions.graphs.executors.deterministic import bank_statement_match
from src.functions.graphs.executors.agents import (
    agent_exception_classifier, agent_root_cause_explainer, agent_resolution_recommender
)
from src.functions.graphs.executors.validators import validate_recommendation_authority


async def run(workflow_payload: dict) -> dict:
    wid = workflow_payload["workflow_id"]
    iid = workflow_payload.get("instance_id")

    async def step(name: str, etype: str, fn, payload):
        t0 = time.time()
        await emit(wid, iid, "executor.invoked", {"name": name, "type": etype, "stage": "start"})
        r = await fn(payload)
        await emit(wid, iid, "executor.invoked", {"name": name, "type": etype, "stage": "complete", "duration_ms": int((time.time() - t0) * 1000)})
        return r

    match = await step("bank_statement_match", "deterministic", bank_statement_match.execute, workflow_payload)
    unmatched = match.get("unmatched_items", [])
    if not unmatched:
        return {"ok": True, "reconciled": True, "agent_classifications": []}

    classifications = []
    for item in unmatched:
        ctx = {**workflow_payload, "unmatched_item": item}
        cls = await step("agent_exception_classifier", "agent", agent_exception_classifier.execute, ctx)
        ctx2 = {**ctx, **cls}
        rc = await step("agent_root_cause_explainer", "agent", agent_root_cause_explainer.execute, ctx2)
        ctx3 = {**ctx2, **rc}
        rec = await step("agent_resolution_recommender", "agent", agent_resolution_recommender.execute, ctx3)
        ctx4 = {**ctx3, **rec}
        v = await step("validate_recommendation_authority", "validator", validate_recommendation_authority.execute, ctx4)
        if not v["ok"]:
            await emit(wid, iid, "validator.blocked", {"name": "validate_recommendation_authority", "item": item})
            classifications.append({"item": item, "blocked": True})
        else:
            classifications.append({"item": item, "decision": rec})

    return {"ok": True, "reconciled": True, "agent_classifications": classifications}
```

- [ ] **Step 1: Write file. No commit.**

---

## Phase 9 — InvoiceP2PWorkflow Durable Workflow

### Task 9.1: The Durable Workflow

**Files:**
- Create: `control-plane-py/src/functions/workflows/__init__.py`
- Create: `control-plane-py/src/functions/workflows/invoice_p2p.py`

> **NOTE:** The MAF Durable Workflow API names below are placeholders. The Phase 0.2 spike (`spike/MAF-DURABLE-NOTES.md`) provides the actual class/decorator names. Adapt the imports and signatures.

```python
# control-plane-py/src/functions/workflows/invoice_p2p.py
"""
The single MAF Durable Workflow representing one POC1 invoice-P2P process.

Adapt the import + base class + decorator names per the Phase 0.2 spike.
"""
from __future__ import annotations
import time
from agent_framework.workflows.durable import DurableWorkflow, workflow_step  # adapt per spike

from src.functions.webhook import emit
from src.functions.graphs import intake, validation, routing, approval, payment, reconciliation


class InvoiceP2PWorkflow(DurableWorkflow):

    @workflow_step
    async def step_intake(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "step.started", {"step": "Intake"})
        t0 = time.time()
        result = await intake.run({**payload, "instance_id": ctx.instance_id})
        await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Intake", "duration_ms": int((time.time() - t0) * 1000), "ok": result["ok"]})
        return result

    @workflow_step
    async def step_validation(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "step.started", {"step": "Validation"})
        t0 = time.time()
        result = await validation.run({**payload, "instance_id": ctx.instance_id})
        await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Validation", "duration_ms": int((time.time() - t0) * 1000), "ok": result["ok"]})
        return result

    @workflow_step
    async def step_routing(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "step.started", {"step": "Routing"})
        t0 = time.time()
        result = await routing.run({**payload, "instance_id": ctx.instance_id})
        await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Routing", "duration_ms": int((time.time() - t0) * 1000), "ok": result["ok"]})
        return result

    @workflow_step
    async def step_approval(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "step.started", {"step": "Approval"})
        t0 = time.time()
        result = await approval.run({**payload, "instance_id": ctx.instance_id})
        if result.get("requires_hitl"):
            await emit(payload["workflow_id"], ctx.instance_id, "suspended", {"reason": result.get("reason", "approval_required")})
            decision = await ctx.wait_for_external_event("approval_decision")
            await emit(payload["workflow_id"], ctx.instance_id, "resumed", {"decision": decision})
            await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Approval", "duration_ms": int((time.time() - t0) * 1000), "ok": True, "decision": decision})
            return {"ok": True, "decision": decision, "via_hitl": True}
        await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Approval", "duration_ms": int((time.time() - t0) * 1000), "ok": True})
        return result

    @workflow_step
    async def step_payment(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "step.started", {"step": "Payment"})
        t0 = time.time()
        result = await payment.run({**payload, "instance_id": ctx.instance_id})
        await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Payment", "duration_ms": int((time.time() - t0) * 1000), "ok": result["ok"]})
        return result

    @workflow_step
    async def step_reconciliation(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "step.started", {"step": "Reconciliation"})
        t0 = time.time()
        result = await reconciliation.run({**payload, "instance_id": ctx.instance_id})
        await emit(payload["workflow_id"], ctx.instance_id, "step.completed", {"step": "Reconciliation", "duration_ms": int((time.time() - t0) * 1000), "ok": result["ok"]})
        return result

    async def run(self, ctx, payload: dict) -> dict:
        await emit(payload["workflow_id"], ctx.instance_id, "workflow.started", {})
        intake = await self.step_intake(ctx, payload)
        validation = await self.step_validation(ctx, {**payload, "intake": intake})
        routing = await self.step_routing(ctx, {**payload, "intake": intake, "validation": validation})
        approval = await self.step_approval(ctx, {**payload, "intake": intake, "validation": validation, "routing": routing})
        payment = await self.step_payment(ctx, {**payload, "approval": approval, "routing": routing})
        recon = await self.step_reconciliation(ctx, {**payload, "payment": payment})
        await emit(payload["workflow_id"], ctx.instance_id, "workflow.completed", {})
        return {
            "intake": intake, "validation": validation, "routing": routing,
            "approval": approval, "payment": payment, "reconciliation": recon
        }
```

- [ ] **Step 1: Write file. Adapt imports per spike.**
- [ ] **Step 2: No commit.**

---

### Task 9.2: function_app.py — register the workflow

**Files:**
- Create: `control-plane-py/src/functions/function_app.py`

```python
# control-plane-py/src/functions/function_app.py
"""
Azure Functions app registering the MAF durable runtime + workflow.

The exact registration pattern depends on Phase 0.2 spike findings on how MAF
hosts inside Functions. Two likely shapes:

A) MAF auto-discovers DurableWorkflow subclasses on import.
B) Manual registration: `app.register_workflow(InvoiceP2PWorkflow)`.

Use whichever the spike found.
"""
import azure.functions as func
from src.functions.workflows.invoice_p2p import InvoiceP2PWorkflow

app = func.FunctionApp()

# Pattern B example:
# from agent_framework.workflows.durable import register_with_functions
# register_with_functions(app, InvoiceP2PWorkflow)
```

- [ ] **Step 1: Write file (adapt registration per spike).**
- [ ] **Step 2: Smoke test — Functions host loads without errors**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane-py"
docker compose up -d azurite
cp local.settings.json.example local.settings.json
cd src/functions
func start --port 7071 &
FN=$!
sleep 10
curl -s http://localhost:7071/admin/host/status 2>/dev/null || echo "no admin endpoint"
kill $FN
```

Expected: Functions host starts. Workflow registered. No "module not found" errors.

If errors: revisit the registration pattern, consult Phase 0.2 spike notes.

- [ ] **Step 3: No commit.**

---

## Phase 10 — Simulator + HITL signal

### Task 10.1: Durable runtime client wrapper

**Files:**
- Create: `control-plane-py/src/server/services/durable_client.py`

```python
# control-plane-py/src/server/services/durable_client.py
"""
Wrapper around the MAF durable runtime client.

Adapt class names per Phase 0.2 spike findings.
"""
from __future__ import annotations
from agent_framework.workflows.durable import DurableRuntimeClient  # adapt per spike

_client: DurableRuntimeClient | None = None


def get_client() -> DurableRuntimeClient:
    global _client
    if _client is None:
        _client = DurableRuntimeClient.from_environment()
    return _client


async def start_workflow(workflow_class, payload: dict) -> str:
    return await get_client().start_new(workflow_class, input=payload)


async def raise_event(instance_id: str, event_name: str, payload) -> None:
    await get_client().raise_event(instance_id, event_name, payload)


async def get_status(instance_id: str) -> str:
    return await get_client().get_status(instance_id)
```

- [ ] **Step 1: Write file. Adapt per spike.**
- [ ] **Step 2: No commit.**

---

### Task 10.2: Simulator orchestrator + bulk-resolve hook

**Files:**
- Create: `control-plane-py/src/server/services/simulator_orchestrator.py`
- Create: `control-plane-py/src/server/services/synthetic_data.py`
- Modify: `control-plane-py/src/server/routes/exceptions.py` — wire raise_event in bulk-resolve

```python
# control-plane-py/src/server/services/synthetic_data.py
from __future__ import annotations
import json
import random
import time
from pathlib import Path
from src.shared.types import Workflow, Vendor, InvoiceData, InvoiceLineItem


_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load_json(name: str) -> list:
    with open(_FIXTURES / name) as f:
        return json.load(f)


VENDORS = _load_json("vendors.json")
PURCHASE_ORDERS = _load_json("purchase-orders.json")
AGENCIES = _load_json("agencies.json")


def build_workflow(workflow_id: str, force_demo_fail: bool = False) -> Workflow:
    vendor_data = random.choice(VENDORS)
    if force_demo_fail:
        vendor_data = {**vendor_data, "name": vendor_data["name"] + " DEMO_FAIL"}
    po = random.choice(PURCHASE_ORDERS)
    agency = random.choice(AGENCIES)
    now = time.time()
    line_count = po.get("lineCount", 1)
    return Workflow(
        id=workflow_id,
        created_at=now,
        sla_due_at=now + (1 + random.random() * 4) * 3600,
        vendor=Vendor(id=vendor_data["id"], name=vendor_data["name"], country=vendor_data["country"]),
        invoice=InvoiceData(
            number=f"INV-{random.randint(100000, 999999)}",
            amount=round(po["amount"] * (0.98 + random.random() * 0.05), 2),
            currency=po["currency"],
            line_items=[InvoiceLineItem(description=f"Line {i+1}", qty=1, unit_price=po["amount"]/line_count) for i in range(line_count)],
            po_ref=po["id"],
        ),
        jurisdiction=f"{vendor_data['country']}-CA",
        agency=agency["id"],
    )
```

```python
# control-plane-py/src/server/services/simulator_orchestrator.py
from __future__ import annotations
import asyncio
import os
import random
from src.server.main import app_state
from src.server.services.durable_client import start_workflow
from src.server.services.synthetic_data import build_workflow
from src.functions.workflows.invoice_p2p import InvoiceP2PWorkflow

_seq = 0


async def spawn_workflow(scenario: str | None = None) -> str:
    """Create a new invoice workflow and start its DurableWorkflow instance."""
    global _seq
    _seq += 1
    wid = f"INV-{_seq:04d}"
    force_fail = scenario == "demo-fail"
    w = build_workflow(wid, force_demo_fail=force_fail)
    app_state.store.upsert_workflow(w)
    payload = {
        "workflow_id": w.id,
        "vendor": w.vendor.model_dump(),
        "invoice": w.invoice.model_dump(),
        "agency": w.agency,
        "jurisdiction": w.jurisdiction,
    }
    instance_id = await start_workflow(InvoiceP2PWorkflow, payload)
    w.orchestration_instance_id = instance_id
    app_state.store.upsert_workflow(w)
    return wid


async def ramp_loop() -> None:
    """Background coroutine: spawn workflows until target, then steady-state."""
    target = int(os.getenv("SIMULATOR_TARGET_WORKFLOWS", "30"))
    ramp_ms = 90_000
    delay_per = ramp_ms / target / 1000
    for _ in range(target):
        try:
            await spawn_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(delay_per)
    while True:
        try:
            await spawn_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(3 + random.random() * 5)
```

Update `main.py` lifespan to start the ramp:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await app_state.fm.start()
    asyncio.create_task(simulator_orchestrator.ramp_loop())
    yield
```
(Add the import at top of main.py: `from src.server.services import simulator_orchestrator`.)

Update `exceptions.py` `bulk_resolve` to call `raise_event` for HITL-paused workflows:

```python
# inside bulk_resolve, after w.status = "in_progress":
if w and w.orchestration_instance_id and w.current_phase == "Approval":
    from src.server.services.durable_client import raise_event
    await raise_event(w.orchestration_instance_id, "approval_decision", body.resolution)
```

- [ ] **Step 1: Write all files + edits.**
- [ ] **Step 2: Smoke test — server boots, spawns workflows, hits Functions runtime**

```bash
# Three terminals (or background)
docker compose up -d azurite
cd src/functions && func start --port 7071 &
cd ../.. && uv run uvicorn src.server.main:app --port 3001 &
cd ../control-plane && npm run dev:mcp &
sleep 15
curl -s http://localhost:3001/api/workflows | head -c 200
echo
curl -s http://localhost:3001/api/health
```

Expected: workflows list populates within ~30s.

- [ ] **Step 3: No commit.**

---

## Phase 11 — UI: Orchestration tab + right-rail feed

### Task 11.1: Backend env switch in React UI

**Files:**
- Modify: `c:\dev\ghcp sdk stuff\control-plane\.env.example` (add `VITE_API_BASE_URL=`)
- Modify: `c:\dev\ghcp sdk stuff\control-plane\vite.config.ts` (proxy uses env when set)

- [ ] **Step 1: Update vite.config.ts proxy**

```typescript
// c:/dev/ghcp sdk stuff/control-plane/vite.config.ts
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3001";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
        "/internal": apiTarget,
      }
    },
    resolve: {
      alias: {
        "@shared": path.resolve(__dirname, "src/shared"),
        "@client": path.resolve(__dirname, "src/client")
      }
    }
  };
});
```

- [ ] **Step 2: Add `.env.example` line**

Append `VITE_API_BASE_URL=http://localhost:3001  # set this to switch to Python backend (same port)` to `.env.example`.

- [ ] **Step 3: No commit.**

---

### Task 11.2: New UI surfaces (Orchestration tab + right-rail feed)

**Files:**
- Modify: `c:\dev\ghcp sdk stuff\control-plane\src\client\routes\WorkflowDetail.tsx` (add Orchestration tab)
- Create: `c:\dev\ghcp sdk stuff\control-plane\src\client\components\OrchestrationView.tsx`
- Create: `c:\dev\ghcp sdk stuff\control-plane\src\client\hooks\useOrchestrationStream.ts`
- Modify: `c:\dev\ghcp sdk stuff\control-plane\src\client\components\FleetManagerRail.tsx` (add tabs)

- [ ] **Step 1: useOrchestrationStream hook**

```typescript
// c:/dev/ghcp sdk stuff/control-plane/src/client/hooks/useOrchestrationStream.ts
import { useCallback, useRef, useState } from "react";
import { useSSE } from "./useSSE";

export interface OrchestrationEvent {
  kind: string;        // workflow.started | step.started | executor.invoked | validator.blocked | suspended | resumed | workflow.completed
  workflow_id: string;
  payload: { name?: string; type?: string; stage?: string; step?: string; reason?: string; duration_ms?: number; [k: string]: unknown };
}

export function useOrchestrationStream(max = 100) {
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);
  const ref = useRef<OrchestrationEvent[]>([]);
  useSSE<OrchestrationEvent>("/api/stream/orchestration", useCallback((e) => {
    ref.current = [e, ...ref.current].slice(0, max);
    setEvents(ref.current.slice());
  }, [max]));
  return events;
}
```

- [ ] **Step 2: OrchestrationView component**

```tsx
// c:/dev/ghcp sdk stuff/control-plane/src/client/components/OrchestrationView.tsx
import { useEffect, useState } from "react";

interface HistoryEntry {
  kind: string;
  payload: { name?: string; type?: string; stage?: string; step?: string; duration_ms?: number; reason?: string; [k: string]: unknown };
  at: number;
}

interface OrchestrationData {
  instance_id: string | null;
  status: string;
  history: HistoryEntry[];
}

const stepNames = ["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"] as const;

const exTypeIcon = (t: string | undefined) => {
  if (t === "agent") return <span className="text-purple-300">[agt]</span>;
  if (t === "validator") return <span className="text-amber-300">[val]</span>;
  if (t === "deterministic") return <span className="text-slate-400">[det]</span>;
  return <span className="text-slate-500">[ ?]</span>;
};

export default function OrchestrationView({ workflowId }: { workflowId: string }) {
  const [data, setData] = useState<OrchestrationData | null>(null);

  useEffect(() => {
    const tick = () => void fetch(`/api/workflows/${workflowId}/orchestration`).then(r => r.json()).then(setData);
    tick();
    const i = setInterval(tick, 1500);
    return () => clearInterval(i);
  }, [workflowId]);

  if (!data) return <div className="text-xs text-slate-500">loading orchestration…</div>;

  const stepsCompleted = stepNames.map(name => ({
    name,
    started: data.history.find(h => h.kind === "step.started" && h.payload.step === name),
    completed: data.history.find(h => h.kind === "step.completed" && h.payload.step === name),
    suspended: data.history.find(h => h.kind === "suspended" && data.history.find(s => s.kind === "step.started" && s.at <= h.at && s.payload.step === name)),
    executors: data.history.filter(h => h.kind === "executor.invoked" && h.payload.stage === "complete"
      && (() => {
        const stepStart = data.history.find(s => s.kind === "step.started" && s.payload.step === name);
        const stepEnd = data.history.find(s => s.kind === "step.completed" && s.payload.step === name);
        if (!stepStart) return false;
        if (stepEnd && h.at > stepEnd.at) return false;
        return h.at >= stepStart.at;
      })()),
    blocked: data.history.find(h => h.kind === "validator.blocked"
      && (() => {
        const stepStart = data.history.find(s => s.kind === "step.started" && s.payload.step === name);
        const stepEnd = data.history.find(s => s.kind === "step.completed" && s.payload.step === name);
        if (!stepStart) return false;
        if (stepEnd && h.at > stepEnd.at) return false;
        return h.at >= stepStart.at;
      })()),
  }));

  return (
    <div className="space-y-3 text-xs">
      <div className="border border-slate-800 rounded p-3 bg-slate-900/30">
        <div>Durable Workflow: <span className="text-slate-200">InvoiceP2PWorkflow</span></div>
        <div>instance: <span className="text-slate-300 font-mono">{data.instance_id || "—"}</span></div>
        <div>status: <span className="text-slate-200">{data.status}</span></div>
      </div>
      <div className="space-y-2">
        {stepsCompleted.map(s => (
          <div key={s.name} className="border border-slate-800 rounded bg-slate-900/30">
            <div className="px-3 py-1.5 flex items-center gap-2">
              <div className="w-32 text-slate-200">{s.name}</div>
              {s.completed ? <div className="text-emerald-400">✓ completed</div>
                : s.blocked ? <div className="text-red-400">✗ blocked</div>
                : s.suspended ? <div className="text-amber-400">⏸ suspended</div>
                : s.started ? <div className="text-blue-400">running</div>
                : <div className="text-slate-500">not started</div>}
              {s.completed && <div className="text-slate-500 ml-auto">{s.completed.payload.duration_ms} ms</div>}
            </div>
            {(s.executors.length > 0 || s.blocked) && (
              <div className="border-t border-slate-800 px-3 py-2 space-y-0.5">
                {s.executors.map((e, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    {exTypeIcon(e.payload.type)}
                    <span className="text-slate-300 font-mono">{e.payload.name}</span>
                    <span className="text-slate-500 ml-auto">{e.payload.duration_ms} ms</span>
                  </div>
                ))}
                {s.blocked && (
                  <div className="text-red-400 mt-1">↳ {s.blocked.payload.name as string} blocked: {String(s.blocked.payload.reason || "")} → routed to Fleet Manager</div>
                )}
                {s.suspended && (
                  <div className="text-amber-300 mt-1">↳ awaiting `approval_decision` (zero compute)</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add Orchestration tab to WorkflowDetail**

In `WorkflowDetail.tsx`, change the tabs constant:
```tsx
const tabs = ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Orchestration"] as const;
```

And add a render branch:
```tsx
{tab === "Orchestration" && <OrchestrationView workflowId={id!} />}
```

Add the import: `import OrchestrationView from "../components/OrchestrationView";`

- [ ] **Step 4: Add Orchestration tab to FleetManagerRail**

Modify `FleetManagerRail.tsx`:

```tsx
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { useOrchestrationStream } from "../hooks/useOrchestrationStream";
import { useState } from "react";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";

const fmIconFor = (kind: string) => {
  switch (kind) {
    case "wakeup": return <Activity size={14} className="text-amber-400" />;
    case "reasoning_start": return <Loader2 size={14} className="text-blue-400 animate-spin" />;
    case "tool_call": return <Wrench size={14} className="text-purple-300" />;
    case "reasoning_done": return <CheckCircle2 size={14} className="text-emerald-400" />;
    case "error": return <AlertCircle size={14} className="text-red-400" />;
    default: return <Activity size={14} className="text-slate-400" />;
  }
};

const orchTypeIcon = (t: string | undefined) => {
  if (t === "agent") return <span className="text-purple-300 text-[10px] font-mono">[agt]</span>;
  if (t === "validator") return <span className="text-amber-300 text-[10px] font-mono">[val]</span>;
  if (t === "deterministic") return <span className="text-slate-400 text-[10px] font-mono">[det]</span>;
  return <span className="text-slate-500 text-[10px] font-mono">[stp]</span>;
};

export default function FleetManagerRail() {
  const fmEvents = useFleetManagerStream();
  const orchEvents = useOrchestrationStream();
  const [tab, setTab] = useState<"fm" | "orch">("fm");

  return (
    <div className="p-3 space-y-2">
      <div className="flex gap-1 border-b border-slate-800 mb-1">
        <button onClick={() => setTab("fm")}
          className={`text-[11px] px-2 py-1 ${tab === "fm" ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`}>
          Fleet Manager
        </button>
        <button onClick={() => setTab("orch")}
          className={`text-[11px] px-2 py-1 ${tab === "orch" ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`}>
          Orchestration
        </button>
      </div>
      {tab === "fm" && (
        <div className="space-y-1.5">
          <div className="text-[11px] text-slate-500">GHCP SDK session · {fmEvents.length} recent events</div>
          {fmEvents.length === 0 && <div className="text-xs text-slate-500">idle</div>}
          {fmEvents.map((e, i) => (
            <div key={i} className="flex gap-2 text-xs border border-slate-800 rounded p-2">
              {fmIconFor(e.kind)}
              <div className="flex-1 min-w-0">
                <div className="text-slate-200 font-medium truncate">{e.kind}</div>
                <div className="text-[11px] text-slate-500 truncate">{e.data ? JSON.stringify(e.data).slice(0, 160) : ""}</div>
              </div>
              <div className="text-[10px] text-slate-600 whitespace-nowrap">{new Date(e.timestamp).toLocaleTimeString()}</div>
            </div>
          ))}
        </div>
      )}
      {tab === "orch" && (
        <div className="space-y-1">
          <div className="text-[11px] text-slate-500">MAF Durable Workflows · {orchEvents.length} recent events</div>
          {orchEvents.length === 0 && <div className="text-xs text-slate-500">idle</div>}
          {orchEvents.map((e, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] border border-slate-800 rounded px-2 py-1">
              {orchTypeIcon(e.payload.type)}
              <span className="text-slate-300 font-mono truncate">{e.workflow_id}</span>
              <span className="text-slate-200 truncate flex-1">
                {e.kind === "executor.invoked" ? `${e.payload.name} (${e.payload.stage})`
                  : e.kind.startsWith("step.") ? `step:${e.payload.step} ${e.kind.split(".")[1]}`
                  : e.kind.startsWith("workflow.") ? `workflow ${e.kind.split(".")[1]}`
                  : e.kind === "validator.blocked" ? `${e.payload.name} BLOCKED`
                  : e.kind}
              </span>
              {e.payload.duration_ms && <span className="text-slate-500">{e.payload.duration_ms} ms</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Smoke test the UI**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
echo "VITE_API_BASE_URL=http://localhost:3001" > .env.local
npm run dev:client &
sleep 5
# Open http://localhost:5173 and verify:
# - Fleet Dashboard loads (workflows from Python backend)
# - Click any workflow card → Workflow Detail shows the new "Orchestration" tab
# - Right rail shows tab strip [Fleet Manager] [Orchestration]
```

- [ ] **Step 6: No commit.**

---

## Phase 12 — Demo polish + integration check

### Task 12.1: Scripted bounded-probabilism demo case

**Files:**
- Modify: `control-plane-py/src/server/routes/simulator.py` (already accepts scenario; spawn with scenario="demo-fail")

The `agent_gl_coder` skill has the rule "for vendor name containing DEMO_FAIL, choose GL-9999". The synthetic data builder appends "DEMO_FAIL" when scenario is "demo-fail". `validate_gl_active` will then block.

- [ ] **Step 1: Verify the chain works end-to-end**

```bash
# Ensure all three services are running + UI
curl -s -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
sleep 30
curl -s http://localhost:3001/api/exceptions | head -c 500
```

Expected: at least one exception with category "validator-blocked" appears.

- [ ] **Step 2: No commit.**

---

### Task 12.2: README + demo script + final integration check

**Files:**
- Replace: `control-plane-py/README.md` (full quickstart)
- Create: `control-plane-py/docs/demo-script.md`

```markdown
# WPP Control Plane — Python POC1 (MAF Durable Agents)

End-to-end POC1 (Finance P2P) implementation using Microsoft's Durable Agents pattern (MAF + Durable Task Framework) with GHCP SDK Python inside agent executors.

## Quickstart

```bash
# 1. Install
gh auth login                          # if not authenticated; needs Copilot license
uv sync
cp .env.example .env

# 2. Start storage
docker compose up -d azurite

# 3. Mock MCPs (TS, from v1)
cd ../control-plane && npm run dev:mcp

# 4. Functions host (MAF runtime)
cd src/functions && func start --port 7071

# 5. FastAPI server
uv run uvicorn src.server.main:app --port 3001 --reload

# 6. UI (uses Python backend via VITE_API_BASE_URL)
cd ../control-plane
echo "VITE_API_BASE_URL=http://localhost:3001" > .env.local
npm run dev:client
```

UI: http://localhost:5173

## Inject scenarios

```bash
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{}'                       # normal
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'  # bounded-probabilism: gl_coder picks inactive GL → validator blocks
```

## Architecture
See [design spec](../docs/superpowers/specs/2026-04-13-wpp-control-plane-py-poc1-design.md).

Three layers:
1. **MAF Durable Workflow** (InvoiceP2PWorkflow) — one instance per invoice, 6 phase steps, native HITL via `wait_for_external_event`
2. **Per-phase MAF Pregel graphs** — typed executors: deterministic + agent + validator
3. **GHCP SDK Python sessions** inside agent executors, each loading one of 9 finance-agent skills (the Fleet Manager is a 10th skill on a separate agent identity)

## Switching back to TS v1

```bash
# in control-plane/.env.local
VITE_API_BASE_URL=http://localhost:3001
# Then run TS v1 backend at the same port: cd ../control-plane && npm run dev:server
```

## Stop

Ctrl-C all processes. State is in-memory in FastAPI. Durable workflow state persists in Azurite (delete `azurite-data/` for a clean slate).
```

```markdown
# control-plane-py/docs/demo-script.md
# Python POC1 Demo Script

Add 6 new hero shots on top of the v1 set.

## Pre-flight
1. `make azurite-up`
2. Start TS mock MCPs
3. Start `func start --port 7071` (MAF host)
4. Start `uvicorn src.server.main:app --port 3001`
5. Start UI with `VITE_API_BASE_URL=http://localhost:3001`
6. Wait until 10+ workflows visible on Fleet Dashboard

## New shot list

7. Workflow Detail → Orchestration tab showing DF/MAF history mid-Routing phase
8. Same view zoomed: 3 agent executors visible (`agent_invoice_classifier`, `agent_gl_coder`, `agent_cost_centre_assigner`) with skill names + 2 validators
9. Inject demo-fail: `curl -X POST http://localhost:3001/api/simulator/inject -d '{"scenario":"demo-fail"}'`. Wait for the validator-blocked screenshot
10. Right rail Orchestration tab during a busy moment
11. Azure Storage Explorer (or `az storage table query --table InvoiceP2PHubInstances --connection-string $AZURITE_CONNECTION_STRING`) showing the persisted orchestration row
12. Workflow Detail Orchestration tab when a HITL workflow is suspended awaiting approval (inject normal workflows; one will hit the threshold and pause)
```

- [ ] **Step 1: Write both files.**

- [ ] **Step 2: Final integration check**

```bash
# Full stack up
make azurite-up
# Three terminals:
cd src/functions && func start --port 7071 &
uv run uvicorn src.server.main:app --port 3001 --reload &
cd ../control-plane && npm run dev:mcp &
sleep 25
# Inject regular + demo-fail
for i in 1 2 3; do curl -s -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{}'; echo; done
curl -s -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
sleep 60
# Verify
echo "=== WORKFLOWS ==="
curl -s http://localhost:3001/api/workflows | python -c "import sys,json; d=json.load(sys.stdin); print(f'count={len(d)}'); st={}; [(st.update({w[\"status\"]: st.get(w[\"status\"],0)+1})) for w in d]; print(f'status={st}')"
echo "=== EXCEPTIONS ==="
curl -s http://localhost:3001/api/exceptions
echo "=== ORCHESTRATION HISTORY (first workflow) ==="
W1=$(curl -s http://localhost:3001/api/workflows | python -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -s "http://localhost:3001/api/workflows/$W1/orchestration" | head -c 1000
```

Expected:
- workflows show statuses including completed, awaiting_hitl, in_progress
- at least one exception (the demo-fail)
- orchestration history for the first workflow shows step.started/completed entries
- UI shows the Orchestration tab populated for any workflow you click

- [ ] **Step 3: No commit.**

---

## Self-review checklist

- [ ] **Spec coverage:** every solution.md §14 phase has a graph (Phase 8). Every MAF executor type (det/agent/validator) is implemented (Phases 6 + 7). All 10 skills are written (Phase 4). All 12 hero shots are achievable (6 inherited from v1 still work; 6 new shot moments confirmed in §8 of spec — Workflow Detail Orchestration tab, validator-blocked, right-rail orch tab, Azurite/storage view, HITL suspension, demo-fail flow).

- [ ] **Placeholder scan:** `grep -E "TBD|TODO|FIXME|XXX|implement later" docs/superpowers/plans/2026-04-13-wpp-control-plane-py-poc1.md` returns nothing.

- [ ] **Type consistency:** `Workflow.id`, `Workflow.orchestration_instance_id`, `Phase.name`, `Exception_.id`, `FleetEvent.type`, executor `execute(input) -> output` shape — all consistent across phases.

- [ ] **API shape consistency:** route definitions in Phase 3 match consumer code paths in Phase 11 (`/api/workflows/:id/orchestration`, `/api/stream/orchestration`, `/api/exceptions/bulk-resolve`, `/api/policy/dry-run`).

- [ ] **Spike outputs feed Phase 5+, 9+, 10:** `MAF-DURABLE-NOTES.md` is the source of truth for `DurableWorkflow` superclass, `wait_for_external_event` signature, and `DurableRuntimeClient` API. Phases 5, 9, 10 explicitly say "adapt per spike".

- [ ] **Cut list integrity:** Right-rail Orchestration tab (11.2 step 4) → Reconciliation as Hybrid (Phase 7.3 + 8.6) → Sub-agent moment in Intake (7.2's `agent_field_extractor` sub-agent block) → hero shot #11 (Phase 12.2) → hero shot #12 (Phase 12.2) — each is independently dropable without breaking prior phases.
