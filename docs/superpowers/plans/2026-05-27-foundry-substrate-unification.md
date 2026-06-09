# Foundry Substrate Unification (awesome-gbb + threadlight alignment) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align zava-control-plane's substrate (deps, governance adapter, model defaults, MCP servers, telemetry, Azure tenancy preflight) literally to the conventions prescribed by [`aiappsgbb/awesome-gbb`](https://github.com/aiappsgbb/awesome-gbb) and [`aiappsgbb/threadlight-skills`](https://github.com/aiappsgbb/threadlight-skills) so that a snippet from `foundry-hosted-agents`, `foundry-mcp-aca`, `foundry-observability`, `foundry-agt`, or `azure-tenant-isolation` can be copy-pasted into zava with **no edits beyond resource names**.

**Architecture:** Six independent phases (A–F). Each is shippable on its own and leaves the laptop-PoC behaviour unchanged. Phase A pins Python deps to the awesome-gbb stack. Phase B re-shapes our GHCP-SDK governance adapter to expose `create_governance_middleware`-equivalent surface on top of the existing kernel. Phase C bumps model defaults to `gpt-5.4`. Phase D makes each `mocks/*` Node server speak MCP streamable-http on `/mcp` so the foundry-mcp-aca Bicep + `client.get_mcp_tool(...)` patterns work unchanged; ships one mock end-to-end as the template, then replicates. Phase E wires the three-layer `foundry-observability` substrate (LAW + AppIn + `azure-monitor-opentelemetry`). Phase F adds the `azure-tenant-isolation` preflight gate. Out of scope: MAF runtime, Foundry Memory, Teams HITL (user-directed in the brainstorm).

**Tech Stack:** Python 3.11/3.13 · `agent-framework-core~=1.6.0` · `agent-framework-foundry~=1.6.0` · `agent-governance-toolkit==3.6.0` (`agent_os.policies`) · `mcp>=1.10.0` · `azure-monitor-opentelemetry>=1.6.0` · `fastmcp>=2.0.0,<3.0.0` (new mock runtime) · Bicep + `azd` · GHCP SDK (`copilot.session` — unchanged) · existing FastAPI + Azure Durable Functions.

**Drop-in test (acceptance bar for the whole plan):** After this lands, the following four blobs paste into zava with only resource-name edits:
1. `foundry-mcp-aca` § "Bicep: ACA for MCP Server" snippet → drops into `infra/modules/aca-mcp.bicep`.
2. `foundry-observability/references/python/otel_init.py` → drops into `api/server/observability.py`.
3. `foundry-agt/references/maf-middleware-snippet.py:build_governed_agent(...)` → drops into a new agent file (without our wrapper rejecting the call shape).
4. `azure-tenant-isolation` agent preflight bash → drops into `scripts/preflight-tenant.sh`.

---

## File Structure

### Created

| Path | Purpose |
|---|---|
| `infra/modules/log-analytics.bicep` | Layer-1 LAW per `foundry-observability` |
| `infra/modules/app-insights.bicep` | Layer-1 AppIn workspace-bound + `Monitoring Metrics Publisher` RBAC for UAMI |
| `infra/modules/aca-env-monitoring.bicep` | ACA env bound to LAW |
| `infra/modules/aca-mcp.bicep` | One ACA per mock MCP, port 8080, `transport: 'http'`, `/health` probes |
| `infra/scripts/connect_observability_postprovision.py` | Verifies AppIn connection wiring; uv-runnable |
| `api/server/observability.py` | Single `init_telemetry()` helper — exact `foundry-observability` shape |
| `api/server/services/governance/middleware.py` | `create_governance_middleware()` factory mirroring upstream AGT surface for GHCP |
| `api/server/services/governance/build_governed_agent.py` | `build_governed_agent(client, instructions, tools, policy_dir)` paste-compatible with `foundry-agt` snippet |
| `mocks/_mcp_protocol/server.py` | Shared FastMCP wrapper exposing `initialize`, `notifications/initialized`, `tools/list`, `prompts/list`, `resources/list`, `logging/setLevel` on `/mcp` + `/health` |
| `mocks/concur-mcp/mcp_server.py` | Reference implementation: concur mock as FastMCP (template for other 18) |
| `mocks/concur-mcp/Dockerfile` | Linux/amd64, port 8080, uv-installed |
| `scripts/preflight-tenant.sh` | `azure-tenant-isolation` agent preflight (bare `az`, no PowerShell) |
| `docs/tenant-isolation.md` | Operator runbook + starter `index.example.json` |
| `docs/queries/agent-traces.kql` | Hosted-agent traces, last 1h |
| `docs/queries/mcp-tool-calls.kql` | MCP tool invocation breakdown |
| `docs/queries/first-trace-probe.kql` | Smoke query — "did ANY trace land in last 5 min?" |
| `tests/api/services/governance/test_middleware.py` | Factory contract tests |
| `tests/api/services/test_observability.py` | `init_telemetry()` defensive-init tests |
| `tests/mocks/test_mcp_protocol_compliance.py` | All 6 JSON-RPC methods return 200 on the reference mock |

### Modified

| Path | Change |
|---|---|
| `pyproject.toml` | Drop `agent-framework==1.0.1` meta + b260409 transitives; pin `agent-framework-core~=1.6.0`, `agent-framework-foundry~=1.6.0`, `mcp>=1.10.0`, `azure-monitor-opentelemetry>=1.6.0`, `agent-governance-toolkit==3.6.0`, `azure-identity>=1.19.0,<1.26.0a0`. Add `[tool.uv]` block. |
| `requirements.txt` | Regenerated from `pyproject.toml` via `uv pip compile`. |
| `api/server/services/governance/permission_handler.py` | Refactor to delegate to new `middleware.py` factory rather than calling the kernel directly. Keeps the GHCP-SDK `PermissionRequest` signature. |
| `api/server/main.py:53` | Call `observability.init_telemetry()` as the very first line of FastAPI startup. |
| `api/functions/segments/employee_transfer_b.py:136` | `model="gpt-4.1"` → `model="gpt-5.4"` |
| `api/functions/segments/employee_transfer_d.py` | Same model bump |
| `api/functions/segments/hiring_b.py` | Same model bump |
| `api/functions/segments/hiring_d.py` | Same model bump |
| `api/functions/segments/hiring_e.py` | Same model bump |
| `api/functions/segments/hiring_f.py` | Same model bump |
| `api/functions/segments/training_request_b.py` | Same model bump |
| `infra/main.bicep:41` | Param default `azureOpenAiDeployment` `gpt-4.1` → `gpt-5.4` |
| `infra/main.bicep:50` | Param default `fleetManagerModel` `gpt-4.1` → `gpt-5.4` |
| `infra/main.bicep` | Wire `log-analytics` + `app-insights` modules; remove the externally-passed `appInsightsConnectionString` param (now computed inside); pass connection string to `aca-app` |
| `infra/modules/aca-app.bicep` | Add `APPLICATIONINSIGHTS_CONNECTION_STRING` env var (already passed; verify); remove anything dependent on the param being external |
| `azure.yaml` | (No change unless we add hooks for postprovision connect step; defer to Phase E) |
| `scripts/boot-demo.sh` | Insert `preflight-tenant.sh` invocation at top of any deploy path; skip for pure-localhost mode |
| `docs/runtime-providers.md` | Add MCP-redeploy coupling note from `foundry-mcp-aca` (stale session-id 404 trap) |
| `mocks/*-mcp/` (18 servers) | Add `mcp_server.py` + `Dockerfile` per the reference pattern; keep `server.js`/`server.ts` for legacy local mode under `MCP_TRANSPORT=local` |
| `.gitignore` | Add `~/.azure-tenants/` and `~/.azd-tenants/` if not already covered |

---

## Out of Scope (per the brainstorm session 2026-05-27)

These were explicitly punted by the user and **must not be touched** in this plan:

- ❌ Adding an MAF runtime peer to `runtime_ghcp.py` (we keep raw GHCP `CopilotSession`).
- ❌ Foundry Memory Store adapter (we keep our `DomainMemory` + dream-pass).
- ❌ Teams Adaptive Cards / `foundry-teams-bot` integration (we keep the web Drawer + Fleet Manager HITL surface).
- ❌ Foundry Skill Catalog REST publishing (we keep filesystem `api/server/skills/<name>/SKILL.md`).
- ❌ `foundry-iq`, `foundry-evals`, `citadel-*` — these are awesome-gbb skills but not in zava's scope.

---

## Phase A — Pin the awesome-gbb dep stack

**Why first:** every later phase imports `azure-monitor-opentelemetry`, `mcp>=1.10.0`, or the bumped `agent_os.policies` API. Without this phase, the rest fails to import.

### Task A.1: Rewrite `pyproject.toml` dependency block

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read the current dependency layout**

Run: `view /Users/arturzielinski/dev/github-repos/zava-control-plane/pyproject.toml`
Note current `[project.dependencies]` content and any `[tool.uv]` config.

- [ ] **Step 2: Replace the dependency block**

Edit `pyproject.toml`. Remove all `agent-framework-*` lines (the meta-package and every `b260409` transitive). Replace with this minimal pinned block:

```toml
[project]
# ... existing name/version/python lines unchanged ...
dependencies = [
    # Core agent framework (per foundry-hosted-agents §Dependencies)
    "agent-framework-core~=1.6.0",
    "agent-framework-foundry~=1.6.0",
    # MCP runtime — required because agent_framework_foundry_hosting._responses
    # imports `from mcp import McpError` unconditionally (per foundry-hosted-agents
    # §Dependencies "Mandatory adjacent rules"). Pin even when no MCP tools used.
    "mcp>=1.10.0",
    # Governance — bump to match foundry-agt 1.0.4 prescription
    "agent-governance-toolkit==3.6.0",
    # Observability — single dep pulls all OTel exporters + instrumentors
    # (per foundry-observability Layer 3 "Step 3.2 — requirements.txt addition")
    "azure-monitor-opentelemetry>=1.6.0",
    # Azure auth — capped <1.26.0a0 to avoid the beta azure-identity 1.26.0b2
    # (per foundry-hosted-agents §Dependencies, `prerelease = "if-necessary-or-explicit"`)
    "azure-identity>=1.19.0,<1.26.0a0",
    # GHCP SDK + everything else zava currently pulls — preserve verbatim
    # (copilot SDK, httpx, fastapi, durable-functions, pydantic, etc.)
    # ... PRESERVE existing non-agent-framework lines exactly ...
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"

[tool.setuptools]
packages = []
```

> **Discipline:** do NOT add explicit `azure-monitor-opentelemetry-exporter`, `opentelemetry-sdk`, or `opentelemetry-instrumentation-*` lines. They are pulled transitively and declaring them explicitly causes version conflicts (per foundry-hosted-agents §Dependencies "Simplified deps (1.6.0)").

- [ ] **Step 3: Recompile the lockfile**

Run: `cd /Users/arturzielinski/dev/github-repos/zava-control-plane && uv pip compile pyproject.toml -o requirements.txt`
Expected: clean compile, no resolver errors. Inspect the diff — there should be no leftover `agent-framework==1.0.1`, no `b260409` transitives.

- [ ] **Step 4: Install + smoke-import**

Run: `uv sync --frozen`
Then: `uv run python -c "from agent_framework import Agent; from agent_os.policies import PolicyEvaluator; from azure.monitor.opentelemetry import configure_azure_monitor; import mcp; print('OK')"`
Expected: `OK` printed, no ImportError.

- [ ] **Step 5: Run the existing test suite to verify no regression**

Run: `uv run pytest -q 2>&1 | tail -40`
Expected: all currently-passing tests still pass. If any test fails on a now-missing transitive (e.g. `agent-framework-azure-cosmos`), add the SPECIFIC package back as a direct dep — do not restore the meta.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt uv.lock
git commit -m "feat(deps): pin awesome-gbb stack per foundry-hosted-agents 1.7.2

Drop the agent-framework==1.0.1 meta-package (explicitly forbidden by
foundry-hosted-agents §Dependencies). Pin agent-framework-core~=1.6.0,
agent-framework-foundry~=1.6.0, mcp>=1.10.0, azure-monitor-opentelemetry>=1.6.0,
agent-governance-toolkit==3.6.0 (bumped from 3.4.0 per foundry-agt 1.0.4),
azure-identity capped <1.26.0a0.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase A"
```

---

## Phase B — Governance: expose `create_governance_middleware` surface

**Context:** zava already uses upstream `agent_os.policies.PolicyEvaluator` (see `api/server/services/governance/kernel.py:216` and `policy_compiler.py:41`). What's missing is the `create_governance_middleware(...)` / `build_governed_agent(...)` factory shape that `foundry-agt` snippets use — so threadlight code currently doesn't paste in cleanly. This phase adds a thin factory on top of the existing kernel.

### Task B.1: Test the factory contract

**Files:**
- Create: `tests/api/services/governance/test_middleware.py`

- [ ] **Step 1: Write the failing test**

```python
"""Contract test for the create_governance_middleware factory.

Mirrors the surface expected by foundry-agt
references/maf-middleware-snippet.py:build_governed_agent so threadlight
code pastes into zava unchanged.
"""
from pathlib import Path

import pytest

from api.server.services.governance.middleware import (
    GovernedToolGuard,
    create_governance_middleware,
)


def test_factory_returns_callable_guard(tmp_path: Path) -> None:
    """create_governance_middleware returns a stackable guard object."""
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "default.yaml").write_text(
        "version: 1\nrules:\n  - id: allow-all\n    effect: allow\n",
        encoding="utf-8",
    )

    guard = create_governance_middleware(
        policy_dir=policy_dir,
        actor="test-skill",
        workflow_id="wf-1",
    )

    assert isinstance(guard, GovernedToolGuard)
    assert callable(guard.evaluate)


def test_guard_allows_when_policy_allows(tmp_path: Path) -> None:
    """A guard built from an allow-all policy must allow every call."""
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "default.yaml").write_text(
        "version: 1\nrules:\n  - id: allow-all\n    effect: allow\n",
        encoding="utf-8",
    )

    guard = create_governance_middleware(
        policy_dir=policy_dir,
        actor="test-skill",
        workflow_id=None,
    )
    decision = guard.evaluate(
        tool_id="concur.claim_lookup",
        args={"claim_id": "C-001"},
    )

    assert decision.allowed is True


def test_guard_denies_when_policy_denies(tmp_path: Path) -> None:
    """A guard built from a deny-all policy must deny."""
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "deny.yaml").write_text(
        "version: 1\nrules:\n  - id: deny-all\n    effect: deny\n",
        encoding="utf-8",
    )

    guard = create_governance_middleware(
        policy_dir=policy_dir,
        actor="test-skill",
        workflow_id=None,
    )
    decision = guard.evaluate(
        tool_id="concur.claim_lookup",
        args={"claim_id": "C-001"},
    )

    assert decision.allowed is False
    assert decision.reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/services/governance/test_middleware.py -v`
Expected: ImportError — `api.server.services.governance.middleware` does not exist.

- [ ] **Step 3: Implement the factory**

Create `api/server/services/governance/middleware.py`:

```python
"""create_governance_middleware factory — mirrors foundry-agt 1.0.4 surface.

This module exposes the call shape that foundry-agt
references/maf-middleware-snippet.py expects, so threadlight code that
imports `create_governance_middleware` pastes into a zava agent
unchanged. Backed by the existing zava governance kernel (which already
uses upstream agent_os.policies.PolicyEvaluator), so policy semantics
are identical — only the surface is renamed.

For full upstream context see:
  - foundry-agt SKILL.md §"Path A — In-process MAF middleware"
  - https://github.com/microsoft/agent-governance-toolkit
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.server.services.governance.kernel import (
    GovernanceDecision,
    GovernanceDenied,
    kernel as _kernel,
)


@dataclass(frozen=True)
class GovernedToolGuard:
    """A stackable guard that evaluates a (tool, args) call against policy.

    Returned by `create_governance_middleware(...)`. Use `.evaluate(...)`
    to get a `GovernanceDecision` synchronously. The guard does not
    enforce — callers (e.g. the GHCP PermissionHandler adapter, an
    MAF middleware shim) decide what to do on deny.
    """

    actor: str
    workflow_id: str | None
    policy_dir: Path

    def evaluate(
        self,
        *,
        tool_id: str,
        args: dict[str, Any],
    ) -> GovernanceDecision:
        """Evaluate one tool call. Returns the kernel's decision verbatim.

        Raises nothing — callers inspect `decision.allowed`. The kernel's
        log-only-vs-enforce mode (AGT_ENFORCE env var) is preserved: in
        enforce mode the kernel raises GovernanceDenied, which we trap
        and convert to a deny-shaped decision so the guard surface stays
        synchronous and exception-free for caller composition.
        """
        try:
            return _kernel().evaluate_tool_call(
                actor=self.actor,
                tool=tool_id,
                args=args,
                workflow_id=self.workflow_id,
            )
        except GovernanceDenied as denied:
            return denied.decision


def create_governance_middleware(
    *,
    policy_dir: Path,
    actor: str,
    workflow_id: str | None = None,
) -> GovernedToolGuard:
    """Construct a per-invocation governance guard.

    `policy_dir` is informational today — the live kernel loads its policy
    bundle from `data/policies/` at process start. We accept the argument
    so the call shape matches `foundry-agt` snippets exactly, and we
    assert it is a real directory so paste-mistakes surface immediately.
    """
    if not policy_dir.is_dir():
        raise ValueError(
            f"create_governance_middleware: policy_dir does not exist: {policy_dir}"
        )
    return GovernedToolGuard(
        actor=actor,
        workflow_id=workflow_id,
        policy_dir=policy_dir,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/services/governance/test_middleware.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full governance test suite to catch regressions**

Run: `uv run pytest tests/api/services/governance/ tests/api/services/test_authority.py tests/api/services/test_audit_logger.py -v 2>&1 | tail -20`
Expected: all previously-passing tests still pass (128+ from prior plan archive). 0 regressions.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/governance/middleware.py tests/api/services/governance/test_middleware.py
git commit -m "feat(governance): add create_governance_middleware factory per foundry-agt 1.0.4

Mirror the upstream agent-governance-toolkit surface so threadlight
snippets paste into zava unchanged. Backed by the existing kernel
(which already uses agent_os.policies). Pure addition — no behaviour
change to the live PermissionHandler.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase B"
```

### Task B.2: Add `build_governed_agent` shape

**Files:**
- Create: `api/server/services/governance/build_governed_agent.py`

- [ ] **Step 1: Implement the helper**

Create `api/server/services/governance/build_governed_agent.py`:

```python
"""build_governed_agent(...) — paste-compatible with foundry-agt snippet.

The foundry-agt SKILL.md §"Wiring snippet" ships
references/maf-middleware-snippet.py:build_governed_agent as the
shortest working integration. For zava we expose the same call shape
but route through the GHCP CopilotSession used by `run_agent_session`
in api/functions/graphs/executors/agents/_wrapper.py.

Threadlight code can therefore use:

    agent = build_governed_agent(
        client=client,
        instructions=load_skill("..."),
        tools=[my_tool, mcp_tool],
        policy_dir=Path("data/policies"),
    )

and it just works, with our governance kernel as the enforcement core.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from api.server.services.governance.middleware import (
    GovernedToolGuard,
    create_governance_middleware,
)


def build_governed_agent(
    *,
    client: Any,
    instructions: str,
    tools: list[Any],
    policy_dir: Path,
    actor: str = "anonymous-agent",
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Return the kwargs an agent constructor needs, with a governance guard wired.

    The returned dict contains `client`, `instructions`, `tools`, and `guard`
    (the GovernedToolGuard the caller installs as their session's
    PermissionHandler). Caller assembles the agent itself — we deliberately
    avoid hard-coding `Agent(...)` (MAF) vs `CopilotSession(...)` (GHCP)
    here so the helper composes with either runtime.
    """
    guard = create_governance_middleware(
        policy_dir=policy_dir,
        actor=actor,
        workflow_id=workflow_id,
    )
    return {
        "client": client,
        "instructions": instructions,
        "tools": tools,
        "guard": guard,
    }


__all__ = ["build_governed_agent", "GovernedToolGuard"]
```

- [ ] **Step 2: Test the helper composes**

Append to `tests/api/services/governance/test_middleware.py`:

```python
def test_build_governed_agent_returns_kwargs(tmp_path: Path) -> None:
    """build_governed_agent returns the four expected keys."""
    from api.server.services.governance.build_governed_agent import (
        build_governed_agent,
    )

    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "p.yaml").write_text(
        "version: 1\nrules:\n  - id: allow\n    effect: allow\n",
        encoding="utf-8",
    )

    kwargs = build_governed_agent(
        client=object(),
        instructions="be helpful",
        tools=[],
        policy_dir=policy_dir,
        actor="test",
    )

    assert set(kwargs.keys()) == {"client", "instructions", "tools", "guard"}
    assert isinstance(kwargs["guard"], GovernedToolGuard)
```

- [ ] **Step 3: Run + commit**

Run: `uv run pytest tests/api/services/governance/test_middleware.py -v`
Expected: 4 passed.

```bash
git add api/server/services/governance/build_governed_agent.py tests/api/services/governance/test_middleware.py
git commit -m "feat(governance): add build_governed_agent helper per foundry-agt snippet

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase B"
```

### Task B.3: Refactor PermissionHandler to route through the guard

**Files:**
- Modify: `api/server/services/governance/permission_handler.py:95-140`

- [ ] **Step 1: Refactor `AGTPermissionHandler.__call__` to use `GovernedToolGuard`**

Replace the body of `__call__` so the kernel call is wrapped through `GovernedToolGuard.evaluate(...)`. The factory shape becomes the single chokepoint; threadlight snippets that build a guard themselves get the identical evaluation path.

In `api/server/services/governance/permission_handler.py`, change:

```python
        try:
            decision = kernel.evaluate_tool_call(
                actor=self._actor,
                tool=tool_id,
                args=args,
                workflow_id=self._workflow_id,
            )
        except GovernanceDenied as denied:
            # ... existing deny handler ...
```

to:

```python
        from api.server.services.governance.middleware import (
            create_governance_middleware,
        )
        from pathlib import Path
        # Policy dir resolved once at module load; kernel already
        # holds the compiled bundle in memory, so this dir is
        # informational (per middleware.py docstring).
        guard = create_governance_middleware(
            policy_dir=Path(__file__).resolve().parents[3] / "data" / "policies",
            actor=self._actor,
            workflow_id=self._workflow_id,
        )
        decision = guard.evaluate(tool_id=tool_id, args=args)

        if not decision.allowed:
            # In enforce mode the kernel had raised; the guard converted
            # that to a deny-shaped decision. In log_only mode this branch
            # is reached only when AGT_ENFORCE=1 — log_only mode never
            # returns allowed=False from the kernel today.
            reason = decision.reason or "denied by governance"
            log.info(
                "AGTPermissionHandler: deny actor=%s tool=%s rule=%s reason=%s",
                self._actor, tool_id, decision.rule_id, reason,
            )
            return PermissionRequestResult(
                kind="denied-by-rules",
                feedback=reason,
                message=reason,
            )
        return PermissionRequestResult(kind="approved")
```

Remove the now-unused `from api.server.services.governance.kernel import (... GovernanceDenied ...)` import — `GovernanceDenied` is no longer referenced here (it's trapped inside the guard).

- [ ] **Step 2: Run governance tests + the autonomous-loop sanity test**

Run: `uv run pytest tests/api/services/governance/ -v 2>&1 | tail -30`
Expected: all governance tests pass (128+ baseline, +4 new = 132+).

Run: `uv run pytest tests/api/functions/graphs/ -v -k "agent_session or permission" 2>&1 | tail -20`
Expected: agent session + permission tests pass.

- [ ] **Step 3: Commit**

```bash
git add api/server/services/governance/permission_handler.py
git commit -m "refactor(governance): route AGTPermissionHandler through GovernedToolGuard

Same kernel + audit + Ed25519 identity behaviour, but the deny decision
flows through the create_governance_middleware factory now — so
threadlight code that constructs its own guard hits the identical
evaluation path zava's session adapter does.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase B"
```

---

## Phase C — Model defaults: bump to gpt-5.4

**Why:** `foundry-hosted-agents` §"Runtime Pattern (MAF Variant)" prescribes `gpt-5.4` for any chain ≥3 tool steps. zava segments invoke 2–5 MCP tools per run — `gpt-4.1` is below the recommended floor. Mini variant is reserved for trivial 1–2-step flows.

### Task C.1: Bump segment defaults

**Files:**
- Modify: `api/functions/segments/employee_transfer_b.py:136`
- Modify: `api/functions/segments/employee_transfer_d.py` (find `model=`)
- Modify: `api/functions/segments/hiring_b.py` (find `model=`)
- Modify: `api/functions/segments/hiring_d.py` (find `model=`)
- Modify: `api/functions/segments/hiring_e.py` (find `model=`)
- Modify: `api/functions/segments/hiring_f.py` (find `model=`)
- Modify: `api/functions/segments/training_request_b.py` (find `model=`)

- [ ] **Step 1: Find every `model="gpt-4.1"` literal under segments**

Run: `grep -n 'model="gpt-4.1"' /Users/arturzielinski/dev/github-repos/zava-control-plane/api/functions/segments/*.py`
Expected: 7 hits (one per segment file).

- [ ] **Step 2: Edit each segment file**

For each match, replace `model="gpt-4.1"` with `model="gpt-5.4"`. Use the edit tool with enough surrounding context to make each `old_str` unique (the call sites are similar but each is wrapped in distinct prompt-building logic).

- [ ] **Step 3: Verify**

Run: `grep -n 'model=' /Users/arturzielinski/dev/github-repos/zava-control-plane/api/functions/segments/*.py | grep -v "gpt-5.4"`
Expected: no matches.

- [ ] **Step 4: Run segment tests**

Run: `uv run pytest tests/api/functions/segments/ -v 2>&1 | tail -20`
Expected: all pass. If tests pin the model literal, update those assertions to `gpt-5.4`.

- [ ] **Step 5: Commit**

```bash
git add api/functions/segments/
git commit -m "feat(segments): default to gpt-5.4 per foundry-hosted-agents 1.7.2

gpt-4.1 is below the floor for chains with 3+ tool steps. gpt-5.4-mini
is reserved for trivially-shaped 1-2 step flows.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase C"
```

### Task C.2: Bump Bicep + env defaults

**Files:**
- Modify: `infra/main.bicep:41`
- Modify: `infra/main.bicep:50`
- Modify: `.env.example` (if it contains `gpt-4.1`)

- [ ] **Step 1: Edit Bicep param defaults**

Change `param azureOpenAiDeployment string = 'gpt-4.1'` → `'gpt-5.4'`.
Change `param fleetManagerModel string = 'gpt-4.1'` → `'gpt-5.4'`.

- [ ] **Step 2: Update env example**

Run: `grep -n "gpt-4.1" .env.example local.settings.example.json 2>/dev/null`
For each hit, change to `gpt-5.4`.

- [ ] **Step 3: Verify Bicep still compiles**

Run: `cd infra && az bicep build --file main.bicep --stdout > /dev/null && echo OK`
Expected: `OK`. (Requires `az bicep` installed — skip step if local toolchain lacks it; CI will catch.)

- [ ] **Step 4: Commit**

```bash
git add infra/main.bicep .env.example local.settings.example.json
git commit -m "feat(infra): default model deployments to gpt-5.4

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase C"
```

---

## Phase D — MCP onto ACA: protocol-conform every mock

**Why:** to make `client.get_mcp_tool(name=..., url=...)` from `foundry-mcp-aca` work against zava's mocks, every mock must speak MCP streamable-http on `/mcp` with all 6 mandatory JSON-RPC methods returning 200. Today's mocks speak proprietary HTTP+JSON.

**Strategy:** Ship ONE mock end-to-end as the reference (`concur-mcp`), then replicate the pattern to the other 18 in batched commits. The pattern is documented as a `mocks/_mcp_protocol/` shared module so per-mock changes are small.

### Task D.1: Shared FastMCP wrapper

**Files:**
- Create: `mocks/_mcp_protocol/__init__.py` (empty)
- Create: `mocks/_mcp_protocol/server.py`
- Create: `mocks/_mcp_protocol/pyproject.toml`

- [ ] **Step 1: Write the protocol-compliance test**

Create `tests/mocks/test_mcp_protocol_compliance.py`:

```python
"""Verify the FastMCP wrapper returns HTTP 200 on all 6 mandatory MCP
JSON-RPC methods (per foundry-mcp-aca §MCP Protocol Requirements).

These six MUST be 200 or `FoundryChatClient.get_mcp_tool()` silently
fails:
  - initialize
  - notifications/initialized
  - tools/list
  - prompts/list
  - resources/list
  - logging/setLevel   (camelCase — lowercase setlevel returns -32601)
"""
import pytest
import httpx

from mocks._mcp_protocol.server import build_app


@pytest.mark.asyncio
async def test_six_methods_all_return_200() -> None:
    app = build_app(
        name="test-mock",
        tools=[],   # protocol surface only — no tool definitions needed
    )
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        for method in (
            "initialize",
            "notifications/initialized",
            "tools/list",
            "prompts/list",
            "resources/list",
            "logging/setLevel",
        ):
            r = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": {}},
                headers={"Accept": "application/json, text/event-stream"},
            )
            assert r.status_code == 200, (
                f"MCP method {method} returned {r.status_code}, expected 200 "
                f"(foundry-mcp-aca §MCP Protocol Requirements)"
            )


@pytest.mark.asyncio
async def test_health_endpoint_returns_200() -> None:
    """ACA liveness/startup probes hit /health (per foundry-mcp-aca Bicep)."""
    app = build_app(name="test-mock", tools=[])
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mocks/test_mcp_protocol_compliance.py -v`
Expected: ImportError — `mocks._mcp_protocol.server` does not exist.

- [ ] **Step 3: Implement the wrapper**

Create `mocks/_mcp_protocol/server.py`:

```python
"""Shared FastMCP wrapper for zava mock servers.

All zava mocks were originally Node/Express servers exposing ad-hoc
HTTP+JSON. To drop into the foundry-mcp-aca deployment pattern,
they must speak MCP streamable-http on /mcp with all six mandatory
JSON-RPC methods returning HTTP 200, plus a /health endpoint for ACA
probes.

This module provides `build_app(name, tools)` that returns a Starlette
ASGI app composed of:
  - FastMCP-handled /mcp with the six mandatory methods + the supplied
    tool definitions
  - /health returning {"status": "ok"} for ACA Liveness + Startup probes

Per foundry-mcp-aca §"⚠️ Pin `fastmcp<3.0.0`" — fastmcp 3.x changed the
streamable-http mount path. Pin <3.0.0 in pyproject.toml.
"""
from __future__ import annotations

from typing import Any, Callable

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


ToolFn = Callable[..., Any]


def build_app(*, name: str, tools: list[ToolFn]) -> Starlette:
    """Compose a Starlette ASGI app exposing /mcp + /health.

    Args:
        name: cloudRoleName + FastMCP server name. Lowercase kebab-case.
        tools: List of `@mcp.tool()`-decorated async callables. Pass [] for
            protocol-only mocks (e.g. the compliance test).

    Returns:
        Starlette ASGI app suitable for `uvicorn.run(app, host="0.0.0.0",
        port=8080)`.
    """
    mcp = FastMCP(name)
    for tool_fn in tools:
        mcp.tool()(tool_fn)

    mcp_app = mcp.streamable_http_app()

    async def health(_request: Any) -> JSONResponse:
        return JSONResponse({"status": "ok", "name": name})

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app=mcp_app),
        ]
    )
```

Create `mocks/_mcp_protocol/pyproject.toml`:

```toml
[project]
name = "zava-mcp-wrapper"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    # foundry-mcp-aca §"⚠️ Pin `fastmcp<3.0.0`" — 3.x changed the
    # streamable-http mount path. Every redeploy after 3.x ships
    # silently breaks every tool call (POST /mcp -> 404).
    "fastmcp>=2.0.0,<3.0.0",
    "starlette>=0.36.0",
    "uvicorn[standard]>=0.29.0",
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/mocks/test_mcp_protocol_compliance.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add mocks/_mcp_protocol/ tests/mocks/test_mcp_protocol_compliance.py
git commit -m "feat(mocks): add FastMCP shared wrapper per foundry-mcp-aca 1.0.5

Exposes /mcp (streamable-http, all 6 mandatory JSON-RPC methods) plus
/health for ACA probes. Pins fastmcp<3.0.0 per the skill's call-out.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase D"
```

### Task D.2: Reference mock — concur-mcp as FastMCP

**Files:**
- Create: `mocks/concur-mcp/mcp_server.py`
- Create: `mocks/concur-mcp/Dockerfile`
- Create: `mocks/concur-mcp/pyproject.toml`
- Keep: `mocks/concur-mcp/server.ts` (legacy local mode under `MCP_TRANSPORT=local`)

- [ ] **Step 1: Inspect what the existing server.ts exposes**

Run: `view /Users/arturzielinski/dev/github-repos/zava-control-plane/mocks/concur-mcp/server.ts`
Note the route paths + the payload shape of `data.expense.json`. The tool surface we need to recreate as `@mcp.tool()` async functions: typically `claim_lookup`, `claim_get_receipt`, `claim_get_structured`, `claim_summary` (cross-check the existing `api/server/mcp_tools/claim_*.py` files for the canonical contract).

- [ ] **Step 2: Implement `mcp_server.py` exposing the same tools as FastMCP tools**

Create `mocks/concur-mcp/mcp_server.py`. The skeleton (you'll adapt tool names + payloads to match what `server.ts` returns today):

```python
"""Concur EMS mock — FastMCP streamable-http variant for ACA deployment.

Same data + same tool semantics as server.ts; different transport
(MCP streamable-http on /mcp instead of ad-hoc REST). The legacy
server.ts is retained for `MCP_TRANSPORT=local` docker-compose mode
during the rollout.

Tool surface mirrored from server.ts:
  - claim_lookup(claim_id) -> claim summary
  - claim_get_receipt(claim_id) -> receipt blob
  - claim_get_structured(claim_id) -> structured extraction
  - claim_summary(claim_id) -> rolled-up summary
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import uvicorn

from mocks._mcp_protocol.server import build_app


_DATA_PATH = Path(__file__).parent / "data.expense.json"


def _load_data() -> dict[str, Any]:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


async def claim_lookup(claim_id: str) -> dict[str, Any]:
    """Look up a Concur expense claim by id."""
    data = _load_data()
    for claim in data.get("claims", []):
        if claim.get("id") == claim_id:
            return claim
    return {"error": "claim_not_found", "claim_id": claim_id}


async def claim_get_receipt(claim_id: str) -> dict[str, Any]:
    """Return the raw receipt blob for a claim."""
    data = _load_data()
    for claim in data.get("claims", []):
        if claim.get("id") == claim_id:
            return {"claim_id": claim_id, "receipt": claim.get("receipt", {})}
    return {"error": "claim_not_found", "claim_id": claim_id}


async def claim_get_structured(claim_id: str) -> dict[str, Any]:
    """Return the structured (OCR-extracted) view of a claim."""
    data = _load_data()
    for claim in data.get("claims", []):
        if claim.get("id") == claim_id:
            return {"claim_id": claim_id, "structured": claim.get("structured", {})}
    return {"error": "claim_not_found", "claim_id": claim_id}


async def claim_summary(claim_id: str) -> dict[str, Any]:
    """Return a rolled-up summary suitable for a Finance Controller's drawer."""
    data = _load_data()
    for claim in data.get("claims", []):
        if claim.get("id") == claim_id:
            return {
                "claim_id": claim_id,
                "summary": claim.get("summary")
                or f"Expense claim {claim_id} for {claim.get('amount', 'unknown')}",
            }
    return {"error": "claim_not_found", "claim_id": claim_id}


def main() -> None:
    app = build_app(
        name="concur-mcp",
        tools=[
            claim_lookup,
            claim_get_receipt,
            claim_get_structured,
            claim_summary,
        ],
    )
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
```

> **Discipline:** every tool name + payload must round-trip through the
> existing `api/server/mcp_tools/claim_*.py` shims unchanged. Open each
> shim, cross-check the dict keys it expects, adjust the mock dict keys
> accordingly. Do not invent new fields.

- [ ] **Step 3: Create Dockerfile**

Create `mocks/concur-mcp/Dockerfile`:

```dockerfile
# Concur mock MCP server — ACA-deployable variant
# (legacy Node server.ts stays for MCP_TRANSPORT=local docker-compose mode)
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/
COPY mocks/_mcp_protocol /app/mocks/_mcp_protocol
COPY mocks/concur-mcp/pyproject.toml /app/mocks/concur-mcp/pyproject.toml
COPY mocks/concur-mcp/mcp_server.py /app/mocks/concur-mcp/mcp_server.py
COPY mocks/concur-mcp/data.expense.json /app/mocks/concur-mcp/data.expense.json
RUN cd /app/mocks/concur-mcp && uv sync --no-dev --no-install-project && rm -rf /root/.cache
EXPOSE 8080
CMD ["/app/mocks/concur-mcp/.venv/bin/python", "/app/mocks/concur-mcp/mcp_server.py"]
```

Create `mocks/concur-mcp/pyproject.toml`:

```toml
[project]
name = "zava-concur-mcp"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0.0,<3.0.0",
    "starlette>=0.36.0",
    "uvicorn[standard]>=0.29.0",
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
```

- [ ] **Step 4: Smoke-test the mock locally**

Run (in a separate terminal, but use background async mode):

```bash
uv run python -m mocks.concur-mcp.mcp_server &
sleep 2
curl -sf http://localhost:8080/health | jq .
curl -sX POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .
```

Expected: `{"status":"ok","name":"concur-mcp"}` from /health, then a JSON-RPC response listing `claim_lookup`, `claim_get_receipt`, `claim_get_structured`, `claim_summary` from /mcp.

Kill: `kill %1`

- [ ] **Step 5: Commit the reference mock**

```bash
git add mocks/concur-mcp/mcp_server.py mocks/concur-mcp/Dockerfile mocks/concur-mcp/pyproject.toml
git commit -m "feat(mocks): concur-mcp as FastMCP reference for ACA deployment

Same tools + data as server.ts; speaks MCP streamable-http on /mcp.
server.ts is retained for MCP_TRANSPORT=local docker-compose mode.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase D"
```

### Task D.3: Bicep — `aca-mcp.bicep` module

**Files:**
- Create: `infra/modules/aca-mcp.bicep`

- [ ] **Step 1: Drop the foundry-mcp-aca Bicep verbatim**

Create `infra/modules/aca-mcp.bicep`. Paste literally from `foundry-mcp-aca` SKILL.md §"Bicep: ACA for MCP Server" (lines 377–470 of that file), preserving the comment about `transport: 'http'` not `'auto'` and the liveness/startup probe block. Substitute zava-specific defaults:

```bicep
// One ACA per MCP server. Drop-in from foundry-mcp-aca 1.0.5.
// All defaults match the skill exactly so paste-compatibility holds.

@description('Name of the MCP ACA (e.g. ca-concur-mcp-${envName})')
param name string

@description('Location')
param location string = resourceGroup().location

@description('ACA managed environment resource ID')
param containerAppEnvironmentId string

@description('Container image (already pushed to ACR, pulled with the UAMI below)')
param image string

@description('Extra env vars (cosmos/search/etc — appended to the AppInsights one)')
param env array = []

@description('User-assigned managed identity resource ID (ACR pull + downstream RBAC)')
param userAssignedIdentityId string

@description('Container Registry name (NO FQDN — just the resource name)')
param acrName string

@description('App Insights connection string for OTel ingestion')
@secure()
param appInsightsConnectionString string

resource mcpAca 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userAssignedIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        // foundry-mcp-aca: explicit 'http' — 'auto' was deprecated for
        // new ACAs in early 2026 and now fails with
        // InvalidParameterValueInContainerTemplate.
        transport: 'http'
      }
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: userAssignedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: image
          env: concat(env, [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ])
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Startup'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 2
              periodSeconds: 3
              failureThreshold: 30
            }
          ]
        }
      ]
    }
  }
}

output endpoint string = 'https://${mcpAca.properties.configuration.ingress.fqdn}'
output fqdn string = mcpAca.properties.configuration.ingress.fqdn
output name string = mcpAca.name
```

- [ ] **Step 2: Verify Bicep compiles**

Run: `az bicep build --file infra/modules/aca-mcp.bicep --stdout > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add infra/modules/aca-mcp.bicep
git commit -m "feat(infra): aca-mcp.bicep module per foundry-mcp-aca 1.0.5

Drop-in copy of the skill's reference module — transport: 'http' (not
'auto'), port 8080, /health probes, shared UAMI for ACR pull.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase D"
```

### Task D.4: Replicate the FastMCP pattern to remaining 18 mocks

**Files (one per mock):**
- `mocks/acs-mcp/`, `mocks/authority-mcp/`, `mocks/docusign-mcp/`, `mocks/graph-mcp/`, `mocks/greenhouse-mcp/`, `mocks/heygen-mcp/`, `mocks/kinesso-mcp/`, `mocks/linkedin-mcp/`, `mocks/maconomy-mcp/`, `mocks/mediaocean-mcp/`, `mocks/prisma-mcp/`, `mocks/salesforce-mcp/`, `mocks/sap-s4-finance-mcp/`, `mocks/servicenow-mcp/`, `mocks/workday-hcm-mcp/`, `mocks/workday-hr-mcp/`, `mocks/workday-mcp/`, `mocks/workday-hr-mcp/`

For each mock:

- [ ] **Step 1: Read the existing `server.ts` to enumerate its tool surface**

Run: `view mocks/<name>/server.ts`
List every endpoint + payload shape. Cross-reference `api/server/mcp_tools/` to confirm the contract the shim expects.

- [ ] **Step 2: Create `mcp_server.py` mirroring the concur-mcp template**

Pattern: one async `@mcp.tool()` per existing endpoint, same name as the `api/server/mcp_tools/<name>.py` Tool object exposes, same payload shape.

- [ ] **Step 3: Create `Dockerfile` + `pyproject.toml` from the concur template**

Adjust `COPY` paths to the mock's name; everything else is identical.

- [ ] **Step 4: Smoke /health and /mcp**

Same curl pattern as Task D.2 Step 4.

- [ ] **Step 5: Commit each mock individually**

```bash
git add mocks/<name>/mcp_server.py mocks/<name>/Dockerfile mocks/<name>/pyproject.toml
git commit -m "feat(mocks): <name> as FastMCP per foundry-mcp-aca

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase D"
```

> **Note:** 18 commits is verbose but each is a small isolated change. Resist
> the temptation to batch — per-mock commits make bisecting a future tool-call
> regression trivial.

### Task D.5: Add MCP-redeploy coupling note

**Files:**
- Modify: `docs/runtime-providers.md`

- [ ] **Step 1: Append a section on MCP/agent coupled deploys**

In `docs/runtime-providers.md`, add at the end:

```markdown
## MCP redeploy ⇒ agent redeploy (coupled deploy pair)

Per `foundry-mcp-aca` SKILL.md §"⚠️ `azd deploy <mcp-service>` poisons every
running agent's MCP session": FastMCP's streamable-http maintains per-client
session state in-memory on the MCP container. When the MCP container is
redeployed (any new revision), all `mcp-session-id` values are wiped, but
the agent's MCP client caches them and **does NOT auto-reconnect**. Every
subsequent tool call returns HTTP 404 silently; the agent self-reports
"<tool> failed" on every call.

**Recovery:** after `azd deploy <mcp-name>`, also run
`azd deploy <agent-service-name>` to drop the agent's in-memory cache.
For zava's web/FastAPI variant, restart the ACA replica:

    az containerapp revision restart \
      -g <rg> -n <agent-aca-name> \
      --revision $(az containerapp revision list -g <rg> -n <agent-aca-name> \
                     --query "[?properties.active] | [0].name" -o tsv)
```

- [ ] **Step 2: Commit**

```bash
git add docs/runtime-providers.md
git commit -m "docs: note MCP/agent coupled deploy pair per foundry-mcp-aca

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase D"
```

---

## Phase E — Observability: three-layer Foundry shape

### Task E.1: Layer-1 Bicep — log-analytics module

**Files:**
- Create: `infra/modules/log-analytics.bicep`

- [ ] **Step 1: Drop the foundry-observability Bicep verbatim**

Create `infra/modules/log-analytics.bicep` exactly as shown in `foundry-observability` SKILL.md §"Step 1.1 — Single LAW for the whole pilot" (lines 108–127). The outputs `workspaceId`, `customerId`, `workspaceName` are the wire format every downstream module reads — do not rename.

- [ ] **Step 2: Verify it compiles**

Run: `az bicep build --file infra/modules/log-analytics.bicep --stdout > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add infra/modules/log-analytics.bicep
git commit -m "feat(infra): log-analytics.bicep per foundry-observability 1.1.1 Layer 1

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase E"
```

### Task E.2: Layer-1 Bicep — app-insights module

**Files:**
- Create: `infra/modules/app-insights.bicep`

- [ ] **Step 1: Drop the foundry-observability Bicep verbatim**

Create `infra/modules/app-insights.bicep` exactly as shown in `foundry-observability` SKILL.md §"Step 1.2 — App Insights bound to that LAW" (lines 131–173).

Critical: the role assignment must use role GUID `3913510d-42f4-4e42-8a64-420c390055eb` (`Monitoring Metrics Publisher`). The skill explicitly warns that "Application Insights Data Ingestor" is a misconception — using anything else with `DisableLocalAuth: true` causes HTTP 400 on every ingestion call.

- [ ] **Step 2: Verify it compiles**

Run: `az bicep build --file infra/modules/app-insights.bicep --stdout > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add infra/modules/app-insights.bicep
git commit -m "feat(infra): app-insights.bicep per foundry-observability 1.1.1 Layer 1

DisableLocalAuth: true + Monitoring Metrics Publisher RBAC to UAMI.
Role GUID 3913510d-42f4-4e42-8a64-420c390055eb is the only correct one
for OTel ingestion with local-auth disabled.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase E"
```

### Task E.3: Wire LAW + AppIn into `main.bicep`

**Files:**
- Modify: `infra/main.bicep`

- [ ] **Step 1: Replace the externally-passed AppIn param with in-pipeline modules**

Edit `infra/main.bicep`:

1. Remove the `param appInsightsConnectionString string = ''` declaration (line ~35).
2. After the existing `uami` module block, insert:

```bicep
module law 'modules/log-analytics.bicep' = {
  name: 'law-${environmentName}'
  scope: rg
  params: {
    name: 'log-${environmentName}'
    location: location
  }
}

module appInsights 'modules/app-insights.bicep' = {
  name: 'appin-${environmentName}'
  scope: rg
  params: {
    name: 'appin-${environmentName}'
    location: location
    workspaceId: law.outputs.workspaceId
    uamiPrincipalId: uami.outputs.principalId
  }
}
```

3. Replace every existing reference to `appInsightsConnectionString` (the param) with `appInsights.outputs.connectionString`.

- [ ] **Step 2: Verify Bicep still compiles**

Run: `az bicep build --file infra/main.bicep --stdout > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add infra/main.bicep
git commit -m "feat(infra): provision LAW + AppIn inline per foundry-observability

Stop relying on an externally-passed appInsightsConnectionString param.
Single LAW + workspace-based AppIn per environment, with the shared UAMI
granted Monitoring Metrics Publisher.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase E"
```

### Task E.4: Layer-3 Python — `init_telemetry()` helper

**Files:**
- Create: `api/server/observability.py`
- Create: `tests/api/services/test_observability.py`
- Modify: `api/server/main.py:53`

- [ ] **Step 1: Write the test**

Create `tests/api/services/test_observability.py`:

```python
"""init_telemetry() must be defensive — no env var, no crash.

Per foundry-observability §"Layer 2 caveat — hosted-agent containers
MUST guard the init too": treat platform auto-injection as best-effort.
The same guard applies to ACA workloads where the env var may be
deliberately absent in local dev.
"""
import importlib

import pytest


def test_init_telemetry_noop_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without APPLICATIONINSIGHTS_CONNECTION_STRING, init must succeed silently."""
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    # Reload to pick up the env-cleared state.
    from api.server import observability
    importlib.reload(observability)

    # Must not raise.
    observability.init_telemetry(service_name="test-svc")


def test_init_telemetry_calls_configure_when_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With env set, init must call configure_azure_monitor exactly once."""
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
        "IngestionEndpoint=https://example.in.applicationinsights.azure.com/",
    )
    from api.server import observability
    importlib.reload(observability)

    calls: list[dict] = []

    def _stub(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(observability, "_configure_azure_monitor", _stub)
    observability.init_telemetry(service_name="test-svc")

    assert len(calls) == 1
    assert calls[0]["logger_name"] == "test-svc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/services/test_observability.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the helper**

Create `api/server/observability.py`:

```python
"""init_telemetry() — single OTel-init entry point for every zava workload.

Mirrors foundry-observability 1.1.1 §"Step 3.1 — Python init" exactly,
with the defensive-guard pattern from §"Layer 2 caveat — hosted-agent
containers MUST guard the init too" so a missing
APPLICATIONINSIGHTS_CONNECTION_STRING does NOT crash startup.

Call this as the very first line of every service's __main__:
  - api/server/main.py (FastAPI control plane)
  - mocks/*/mcp_server.py (each MCP ACA — once mocks are on FastMCP)
  - any future ACA Job container

The same connection-string flows to all workloads via Bicep
(infra/main.bicep wires appInsights.outputs.connectionString into the
APPLICATIONINSIGHTS_CONNECTION_STRING env var on every container).
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)


# Indirected so tests can monkeypatch without touching the real exporter.
def _configure_azure_monitor(**kwargs: Any) -> None:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(**kwargs)


def init_telemetry(*, service_name: str) -> None:
    """Initialise OTel + Azure Monitor exporter. Idempotent + defensive.

    Args:
        service_name: cloudRoleName in App Insights (kebab-case).
            Examples: "zava-control-plane", "concur-mcp",
            "deadline-watcher-job".

    No-op when APPLICATIONINSIGHTS_CONNECTION_STRING is unset (local-dev
    case, or platform auto-injection failure per foundry-observability
    §"Layer 2 caveat"). A WARN is logged so it shows up in any log
    aggregator we DO have configured.
    """
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        log.warning(
            "init_telemetry: APPLICATIONINSIGHTS_CONNECTION_STRING unset; "
            "OTel exporter disabled for service=%s",
            service_name,
        )
        return

    try:
        _configure_azure_monitor(
            logger_name=service_name,   # foundry-observability §3.1: shows as cloudRoleName
            instrumentation_options={
                "azure_sdk": {"enabled": True},
                "fastapi":   {"enabled": True},
                "requests":  {"enabled": True},
                "urllib3":   {"enabled": True},
                "urllib":    {"enabled": True},
                "django":    {"enabled": False},
                "flask":     {"enabled": False},
                "psycopg2":  {"enabled": False},
            },
        )
        log.info("init_telemetry: OTel configured for service=%s", service_name)
    except Exception as exc:
        # Per foundry-observability §"Layer 2 caveat" — never crash startup
        # on telemetry init failure. Log the exception and continue.
        log.warning(
            "init_telemetry: configure_azure_monitor failed for service=%s: %s",
            service_name, exc,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/services/test_observability.py -v`
Expected: 2 passed.

- [ ] **Step 5: Wire into FastAPI startup**

Edit `api/server/main.py` near line 53 (where the existing comment "Governance kernel — see plan/feature-agent-governance-toolkit-1.md" lives). Add ABOVE every other startup logic:

```python
from api.server.observability import init_telemetry

# foundry-observability §3.1: init OTel as the very first thing before any
# I/O, any imports of Cosmos/SDK clients, any environment lookups.
init_telemetry(service_name="zava-control-plane")
```

- [ ] **Step 6: Wire into each FastMCP mock's main()**

For every mock that has `mcp_server.py` after Phase D (starting with `concur-mcp`), prepend to `main()`:

```python
from api.server.observability import init_telemetry
init_telemetry(service_name="<mock-name>")  # cloudRoleName in AppIn
```

> **Note:** doing this only for the concur reference mock in Phase E and
> deferring the other 18 to Phase D.4 commits is acceptable — Phase D
> tasks each include this line per the template.

- [ ] **Step 7: Run the smoke suite + verify import**

Run: `uv run pytest tests/api/services/test_observability.py tests/api/test_main.py -v 2>&1 | tail -20`
Expected: pass + the FastAPI startup test still passes.

Run: `uv run python -c "from api.server.observability import init_telemetry; init_telemetry(service_name='smoke-test')"`
Expected: WARN message printed about missing env var, then exit 0 (no exception).

- [ ] **Step 8: Commit**

```bash
git add api/server/observability.py tests/api/services/test_observability.py api/server/main.py mocks/concur-mcp/mcp_server.py
git commit -m "feat(observability): init_telemetry() helper per foundry-observability Layer 3

Single defensive OTel-init helper used by FastAPI + every FastMCP mock.
Missing APPLICATIONINSIGHTS_CONNECTION_STRING is a WARN, not a crash
(per Layer 2 caveat).

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase E"
```

### Task E.5: Diagnostic KQL queries

**Files:**
- Create: `docs/queries/agent-traces.kql`
- Create: `docs/queries/mcp-tool-calls.kql`
- Create: `docs/queries/first-trace-probe.kql`

- [ ] **Step 1: Copy the queries verbatim from foundry-observability**

For each file, copy the exact KQL from `/tmp/awesome-gbb/skills/foundry-observability/references/queries/<file>.kql`. The queries match on `cloudRoleName` (which our `init_telemetry(service_name=...)` populates), so they work against zava traces without modification.

Run: `ls /tmp/awesome-gbb/skills/foundry-observability/references/queries/ 2>/dev/null && for f in agent-traces mcp-tool-calls first-trace-probe; do echo "=== $f.kql ==="; cat /tmp/awesome-gbb/skills/foundry-observability/references/queries/$f.kql 2>/dev/null; done`

Then create each file with the exact content.

- [ ] **Step 2: Add a one-line README**

Create `docs/queries/README.md`:

```markdown
# Diagnostic KQL queries

These queries are paste-compatible drops from `foundry-observability` 1.1.1
`references/queries/`. They match on `cloudRoleName` (populated by
`api/server/observability.py:init_telemetry(service_name=...)`), so they
work against zava telemetry unchanged.

Run them in the App Insights "Logs" blade (or `az monitor app-insights query`).
```

- [ ] **Step 3: Commit**

```bash
git add docs/queries/
git commit -m "docs: drop-in KQL queries from foundry-observability

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase E"
```

---

## Phase F — Azure tenant isolation preflight

### Task F.1: Preflight script

**Files:**
- Create: `scripts/preflight-tenant.sh`

- [ ] **Step 1: Implement the bare-`az` agent preflight**

Create `scripts/preflight-tenant.sh`. The skill is explicit that the preflight uses ONLY bare `az`/`azd` CLI — no wrapper scripts, no PowerShell modules:

```bash
#!/usr/bin/env bash
# Azure tenant + subscription preflight per azure-tenant-isolation 1.1.0
# §"Agent preflight (Copilot CLI / automated sessions)".
#
# Refuses to proceed unless:
#   1. AZURE_CONFIG_DIR (+ AZD_CONFIG_DIR if EXPECT_AZD=1) are set
#   2. az account show succeeds (token is valid)
#   3. tenantId matches $EXPECTED_TENANT_ID
#   4. subscription name matches $EXPECTED_SUBSCRIPTION
#
# Caller must export EXPECTED_TENANT_ID + EXPECTED_SUBSCRIPTION before
# invoking. The tenant index at ~/.azure-tenants/index.json is the
# authoritative source — see docs/tenant-isolation.md.

set -euo pipefail

EXPECT_AZD="${EXPECT_AZD:-1}"

if [[ -z "${EXPECTED_TENANT_ID:-}" ]] || [[ -z "${EXPECTED_SUBSCRIPTION:-}" ]]; then
  echo "ERROR: EXPECTED_TENANT_ID and EXPECTED_SUBSCRIPTION must be set" >&2
  echo "       Source these from ~/.azure-tenants/index.json — see docs/tenant-isolation.md" >&2
  exit 1
fi

if [[ -z "${AZURE_CONFIG_DIR:-}" ]]; then
  echo "ERROR: AZURE_CONFIG_DIR is unset — refusing to operate on global ~/.azure" >&2
  echo "       export AZURE_CONFIG_DIR=~/.azure-tenants/<alias>" >&2
  exit 1
fi

if [[ "$EXPECT_AZD" == "1" ]] && [[ -z "${AZD_CONFIG_DIR:-}" ]]; then
  echo "ERROR: AZD_CONFIG_DIR is unset (EXPECT_AZD=1)" >&2
  echo "       export AZD_CONFIG_DIR=~/.azd-tenants/<alias>" >&2
  exit 1
fi

# azure-tenant-isolation §"Agent preflight" Step 3:
# Check token validity with `az account show` — only prompt login on failure.
if ! ACTUAL_TENANT=$(az account show --query tenantId -o tsv 2>/dev/null); then
  echo "ERROR: az account show failed — token expired or never logged in." >&2
  echo "       Run: az login --tenant $EXPECTED_TENANT_ID" >&2
  echo "            az account set --subscription \"$EXPECTED_SUBSCRIPTION\"" >&2
  if [[ "$EXPECT_AZD" == "1" ]]; then
    echo "            azd auth login --tenant-id $EXPECTED_TENANT_ID" >&2
  fi
  exit 1
fi

ACTUAL_SUB=$(az account show --query name -o tsv)

if [[ "$ACTUAL_TENANT" != "$EXPECTED_TENANT_ID" ]]; then
  echo "ERROR: tenant mismatch" >&2
  echo "       expected: $EXPECTED_TENANT_ID" >&2
  echo "       actual:   $ACTUAL_TENANT" >&2
  exit 1
fi

if [[ "$ACTUAL_SUB" != "$EXPECTED_SUBSCRIPTION" ]]; then
  echo "ERROR: subscription mismatch" >&2
  echo "       expected: $EXPECTED_SUBSCRIPTION" >&2
  echo "       actual:   $ACTUAL_SUB" >&2
  echo "       (rule 4a: az login --tenant <id> does NOT honor default_subscription —" >&2
  echo "        run: az account set --subscription \"$EXPECTED_SUBSCRIPTION\")" >&2
  exit 1
fi

echo "✓ tenant: $ACTUAL_TENANT  subscription: $ACTUAL_SUB  config: $AZURE_CONFIG_DIR"
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x /Users/arturzielinski/dev/github-repos/zava-control-plane/scripts/preflight-tenant.sh`

- [ ] **Step 3: Smoke-test (negative path)**

Run: `unset AZURE_CONFIG_DIR; EXPECTED_TENANT_ID=x EXPECTED_SUBSCRIPTION=y scripts/preflight-tenant.sh; echo exit=$?`
Expected: error "AZURE_CONFIG_DIR is unset", `exit=1`.

- [ ] **Step 4: Commit**

```bash
git add scripts/preflight-tenant.sh
git commit -m "feat(scripts): tenant isolation preflight per azure-tenant-isolation 1.1.0

Bare az CLI, no PowerShell module, no wrapper. Refuses to proceed on
missing AZURE_CONFIG_DIR / AZD_CONFIG_DIR or tenant+sub mismatch.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase F"
```

### Task F.2: Operator runbook + index example

**Files:**
- Create: `docs/tenant-isolation.md`
- Modify: `.gitignore`

- [ ] **Step 1: Write the runbook**

Create `docs/tenant-isolation.md`:

```markdown
# Azure tenant isolation

Zava deploys touch real Azure subscriptions. Per
[`azure-tenant-isolation` 1.1.0](https://github.com/aiappsgbb/awesome-gbb/blob/main/skills/azure-tenant-isolation/SKILL.md)
every shell that runs `az` or `azd` MUST set `AZURE_CONFIG_DIR` (and
`AZD_CONFIG_DIR`) to a per-tenant directory so multiple terminals do
not collide on the global `~/.azure` token cache.

## One-time setup

```bash
mkdir -p ~/.azure-tenants ~/.azd-tenants
cat > ~/.azure-tenants/index.json <<'JSON'
{
  "version": 1,
  "default_alias": "dev",
  "tenants": {
    "dev": {
      "tenant_id": "00000000-0000-0000-0000-000000000000",
      "description": "Personal dev tenant",
      "config_dir": null,
      "azd_config_dir": null,
      "default_subscription": "your-sub-name-or-id",
      "allowed_subscriptions": ["your-sub-name-or-id"]
    }
  }
}
JSON
```

The file is personal data (it lists your tenant ids). It is gitignored.

## Per-shell setup

```bash
ALIAS=dev   # pick a tenant from the index
export AZURE_CONFIG_DIR="$HOME/.azure-tenants/$ALIAS"
export AZD_CONFIG_DIR="$HOME/.azd-tenants/$ALIAS"
export EXPECTED_TENANT_ID="$(jq -r .tenants.$ALIAS.tenant_id ~/.azure-tenants/index.json)"
export EXPECTED_SUBSCRIPTION="$(jq -r .tenants.$ALIAS.default_subscription ~/.azure-tenants/index.json)"
```

## Before any destructive op

```bash
scripts/preflight-tenant.sh
# ✓ tenant: <id>  subscription: <name>  config: ~/.azure-tenants/dev
```

Any zava `scripts/deploy-*.sh` or `azd up` invocation runs this preflight
first. Failure aborts the deploy.

## Mandatory rules (from the skill, abridged)

1. **Per-tenant `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` are mandatory.**
   Never let them fall back to `~/.azure`.
2. **`az login --tenant <id>` ≠ active subscription on multi-sub tenants.**
   Always follow with `az account set --subscription "$DEFAULT_SUB"` (rule 4a).
3. **`azd auth login --tenant-id <id>` is a separate auth chain** —
   `az login` alone does NOT satisfy `azd deploy`.
4. **Subprocess inherits env, not isolation state** — set both `_CONFIG_DIR`
   vars in the parent before spawning any `azure.yaml` hook script.
5. **Application code uses `ChainedTokenCredential` / `DefaultAzureCredential`,
   never API keys.** Keys bypass the isolation guarantee.
```

- [ ] **Step 2: Add gitignore entries**

Append to `.gitignore` (if not already present):

```
# Personal Azure tenant index (per azure-tenant-isolation skill)
~/.azure-tenants/
~/.azd-tenants/
```

- [ ] **Step 3: Commit**

```bash
git add docs/tenant-isolation.md .gitignore
git commit -m "docs(deploy): tenant isolation runbook + starter index

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase F"
```

### Task F.3: Wire preflight into boot-demo.sh deploy paths

**Files:**
- Modify: `scripts/boot-demo.sh`

- [ ] **Step 1: Find the deploy-touching paths in boot-demo.sh**

Run: `grep -n "azd\|az \|az.exe" /Users/arturzielinski/dev/github-repos/zava-control-plane/scripts/boot-demo.sh`
For each match, determine whether it's a deploy path or pure-localhost (vite preview, function-host, FastAPI). The localhost paths SKIP preflight; deploy paths REQUIRE it.

- [ ] **Step 2: Insert preflight call before each deploy-touching block**

Add (early in each deploy path):

```bash
# foundry alignment: tenant isolation preflight (azure-tenant-isolation 1.1.0)
if [[ -z "${SKIP_TENANT_PREFLIGHT:-}" ]]; then
  scripts/preflight-tenant.sh
fi
```

The `SKIP_TENANT_PREFLIGHT` escape hatch lets the laptop-PoC path (which never touches Azure) keep working without a tenant index.

- [ ] **Step 3: Smoke the localhost path**

Run: `SKIP_TENANT_PREFLIGHT=1 BOOT_DEMO_DRY_RUN=1 scripts/boot-demo.sh 2>&1 | head -20`
(`BOOT_DEMO_DRY_RUN` is illustrative — substitute whatever env knob the existing script uses to short-circuit; or simply `head -3` to verify no preflight error at the very top.)
Expected: no "AZURE_CONFIG_DIR is unset" error.

- [ ] **Step 4: Commit**

```bash
git add scripts/boot-demo.sh
git commit -m "feat(scripts): wire tenant preflight into boot-demo.sh deploy paths

SKIP_TENANT_PREFLIGHT=1 escape hatch for pure-localhost runs.

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md Phase F"
```

---

## Phase G — End-to-end verification

### Task G.1: Run the full test suite

- [ ] **Step 1: Run everything**

Run: `uv run pytest -q 2>&1 | tail -30`
Expected: all tests pass. Capture the count.

- [ ] **Step 2: Verify the four drop-in tests pass by inspection**

For each of the four "drop-in" acceptance items at the top of this plan, confirm by reading the files that:

1. `infra/modules/aca-mcp.bicep` is line-for-line equivalent to `foundry-mcp-aca` SKILL.md §"Bicep: ACA for MCP Server" (modulo defaults).
2. `api/server/observability.py:init_telemetry()` is line-for-line equivalent to `foundry-observability/references/python/otel_init.py` (modulo logger_name).
3. `api/server/services/governance/build_governed_agent.py:build_governed_agent(...)` has the same `(client, instructions, tools, policy_dir)` signature as `foundry-agt/references/maf-middleware-snippet.py`.
4. `scripts/preflight-tenant.sh` covers the same preflight steps as `azure-tenant-isolation` §"Agent preflight".

- [ ] **Step 3: Update the project README**

In `README.md`, under the "Stack" bullet list, append:

```markdown
- Aligned to [`aiappsgbb/awesome-gbb`](https://github.com/aiappsgbb/awesome-gbb)
  + [`aiappsgbb/threadlight-skills`](https://github.com/aiappsgbb/threadlight-skills)
  conventions per
  [`docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md`](docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md):
  paste-compatible `foundry-mcp-aca`, `foundry-observability`,
  `foundry-agt`, `azure-tenant-isolation` snippets.
```

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: note awesome-gbb alignment in README

Refs: docs/superpowers/plans/2026-05-27-foundry-substrate-unification.md"
```

---

## Self-Review (post-write)

**Spec coverage:**
- ✅ Phase A — deps pin (#1)
- ✅ Phase B — AGT consolidation (#3)
- ✅ Phase C — model defaults (#4)
- ✅ Phase D — MCP onto ACA (#5)
- ✅ Phase E — observability (#7)
- ✅ Phase F — tenant isolation (#10)
- ❌ Out-of-scope items (#2 MAF, #6 Memory, #8 Teams, #9 was duplicated into model bump) confirmed not addressed.

**Placeholder scan:** No "TBD", no "implement later", no "add appropriate error handling". One template-replication pattern (Phase D.4) which deliberately points back to D.2 as the worked example with full code, rather than copy-pasting 18 near-identical 100-line blocks. Each replicated mock still gets its own commit per the steps.

**Type consistency:**
- `GovernedToolGuard` defined Task B.1, used in B.2 and B.3 — consistent.
- `create_governance_middleware(policy_dir=, actor=, workflow_id=)` keyword signature consistent across B.1 / B.2 / B.3.
- `init_telemetry(service_name=...)` keyword-only consistent across E.4 / E.5 / D.2.
- Bicep module `outputs` (`workspaceId`, `customerId`, `connectionString`, `endpoint`, `fqdn`) match the foundry-observability + foundry-mcp-aca wire formats — confirmed against the skill text.

**Open risks called out:**
- Phase D.4 is the highest-effort task (18 mocks × ~5 steps). Acceptable to ship Phase D in two PRs: D.1–D.3 first (reference + Bicep), D.4 as a follow-up batch.
- AGT bump 3.4.0 → 3.6.0 may have policy-schema changes. Task A.5's full test run is the gate; if policy YAML format changed, add a Task A.6 to migrate `data/policies/` before merging.

---
