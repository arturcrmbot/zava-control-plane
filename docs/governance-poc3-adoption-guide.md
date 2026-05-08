# Governance — POC3 Adoption Guide

> Per CON-007 of [feature-agent-governance-toolkit-1.md](../plan/feature-agent-governance-toolkit-1.md).
> Land the AGT governance core into the POC3 worktree
> (`zava-control-plane-poc3-ai-agency`) without re-deriving the design
> from this plan. A separate developer should be able to land
> governance in POC3 from this doc alone.

## TL;DR

POC3 is a separate worktree that shares POC1's substrate skeleton. The
governance core landed in POC1 across 8 phases (1.4k+ lines, 115 new
tests, 10/10 OWASP ASI coverage). POC3 inherits all of it via two
mirrored chokepoints:

- `api/functions/graphs/_common.py::call_mcp` — every MCP call.
- `api/server/mcp_tools/_otel.py::traced_tool` — every server-side tool.

If POC3 keeps those two file paths intact, the whole governance package
drops in via `cp -r` of `api/server/services/governance/` and one
`pyproject.toml` edit. The rest of this doc is per-phase deltas.

## Design recap (5 minutes)

The kernel mediates four things:

| Surface | What | Where in POC1 |
|---|---|---|
| **MCP tool calls** | Every call routes through `kernel.evaluate_tool_call()` BEFORE the network hop. Decision carries `decision_id`, `policy_version`, `rule_id`, `enforcement_mode`. | `api/functions/graphs/_common.py`, `api/server/mcp_tools/_otel.py` |
| **Authority resolution** | First-match walk over `data/synthetic/authority/matrix.json` is in-process. HTTP fallback via `AUTHORITY_MCP_URL` for the Foundry-IQ swap-in. | `api/server/mcp_tools/delegated_authority.py`, `api/server/services/persona_responder.py` |
| **Audit ledger** | Per-workflow SHA-256 hash chain plus Ed25519 JWS receipts on entries that carry an `agent_id`. `verify_chain()` re-walks; `/api/governance/verify/{wf}` exposes it. | `api/server/services/audit_logger.py`, `api/server/routes/governance.py` |
| **Operator kill switch** | `POST /api/governance/kill {actor, tool, ttl_seconds, reason}` blocks fleet-wide for a TTL. Lazy-expired. Wildcards on actor + tool. | `api/server/services/governance/kill_switch.py`, `api/server/routes/governance.py` |

Two enforcement modes:
- `AGT_ENFORCE` unset / `"0"` → log-only (deny is recorded, never raised).
- `AGT_ENFORCE="1"` → enforce (deny raises `GovernanceDenied`).

## POC3 wiring points

POC3's `api/` tree is a sibling of POC1's. Mirror these files:

| POC1 path | POC3 action |
|---|---|
| `api/server/services/governance/` (all 6 files) | `cp -r` as-is. No POC3-specific edits needed. |
| `api/shared/agents.py` | Copy as-is, then expand `AGENTS` per the roster delta below. |
| `api/shared/types.py` (added 6 optional crypto fields to `ActionLedgerEntry`) | Apply the same diff. All fields default to `None`; fully back-compat. |
| `api/server/services/audit_logger.py` (chain + JWS hooks) | Copy as-is. |
| `api/functions/graphs/_common.py::call_mcp` (kernel guard before network hop) | Apply the same diff. |
| `api/server/mcp_tools/_otel.py::traced_tool` (kernel guard before tool body) | Apply the same diff. |
| `api/server/mcp_tools/delegated_authority.py` (in-process kernel; HTTP fallback) | Apply the same diff. |
| `api/server/services/persona_responder.py::_sandbox_authority_check` | Apply the same diff. |
| `api/server/routes/governance.py` (verify + kill endpoints) | Copy as-is. |
| `api/server/routes/authority.py` (docstring update; routing unchanged) | Apply diff. |
| `api/server/main.py` (register `governance_router`) | Add the import + the tuple entry. |
| `data/policies/tools.yaml` | Copy as-is, then add POC3-specific tool entries (HeyGen avatar, brand RAG, image_gen, etc.). |
| `data/policies/README.md` | Copy as-is. |
| `data/synthetic/authority/matrix.json` | Copy as-is OR keep POC3's existing matrix; the compiler handles either. |
| `data/governance/` (`README.md`, `agent-pubkeys/.gitkeep`) | Copy as-is. |
| `web/client/features/governance/` (EvidencePanel + KillSwitchPanel) | Copy as-is, slot into POC3's WorkflowDetail. |
| `tests/api/server/services/governance/` (60+ tests) | Copy as-is. |
| `tests/api/server/services/test_audit_chain.py` | Copy as-is. |
| `tests/api/shared/test_agents_registry.py` | Copy as-is. |
| `pyproject.toml` | Add `agent-governance-toolkit[full]>=3.4,<3.5` + `cryptography>=41`. |
| `.github/workflows/agt-governance.yml` | Copy as-is, adjust `paths:` filter to match POC3 layout. |
| `.github/hooks/pre-commit-agt` | Copy as-is. |
| `Makefile` | Add `agt-doctor` + `agt-verify` targets. |
| `docs/ARCHITECTURE.md` | Add the "fourth tier" callout + governance box (one paragraph + diagram update). |
| `docs/DEVELOPMENT.md` | Add the "Governance (AGT)" section. |
| `local.settings.example.json`, `local.settings.json.example` | Add `AGT_ENFORCE`, `AGT_DEFAULT_ACTOR`. |

## Agent roster delta

POC3 has different agents from POC1. Extend `AGENTS` in
`api/shared/agents.py` with these provisional entries (mirroring what
the audit identified for POC1 — see comment header in that file). Tool
names assume POC3 ships matching `tools.yaml` entries.

```python
# POC3 — creative campaign agents
"creative-director": AgentRegistryEntry(
    agent_id="creative-director",
    allowed_tools=("brand_rag", "policy.search", "policy.cite"),
    max_value_gbp=None,
    reversible_only=True,
    scope_function="creative",
    description="POC3 creative-direction agent. Reads brand corpus + policy.",
),
"brand-guardian": AgentRegistryEntry(
    agent_id="brand-guardian",
    allowed_tools=("brand_rag", "policy.cite", "compose_exception"),
    max_value_gbp=None,
    reversible_only=True,
    scope_function="creative",
    description="POC3 brand compliance check.",
),
"image-generator": AgentRegistryEntry(
    agent_id="image-generator",
    allowed_tools=("image_gen", "brand_rag"),
    max_value_gbp=None,
    reversible_only=False,  # image_gen is irreversible per tools.yaml
    scope_function="creative",
    description="POC3 brand image generator (Foundry gpt-image-2).",
),
"avatar-renderer": AgentRegistryEntry(
    agent_id="avatar-renderer",
    allowed_tools=("avatar.render",),
    max_value_gbp=None,
    reversible_only=False,
    scope_function="creative",
    description="POC3 HeyGen avatar render.",
),
```

The CI check `tests/api/shared/test_agents_registry.py` will fail until
every `agent_label` value in POC3 fixtures is registered. Run the
suite, look at the missing-set, add entries.

## Per-phase task checklist (mirrors this plan)

- [ ] **Phase 1 — Bootstrap** (TASK-001..007).
  - Add AGT to `pyproject.toml`. `uv sync`. Confirm `agt verify` and
    `agt doctor` both green.
  - Copy `api/server/services/governance/` (Phase 1 skeleton: `__init__`,
    `boot`, `kernel`).
  - Wire `init_governance()` into FastAPI lifespan + `function_app.py`.
  - Add `azurite-data/agt-keys/` to `.gitignore`.
  - Run `tests/api/server/services/governance/test_kernel_skeleton.py`.

- [ ] **Phase 2 — Tool manifest + log-only enforcement at chokepoints**
  (TASK-008..019).
  - Audit POC3's MCP tool surface. Author `data/policies/tools.yaml`
    (copy POC1's + add POC3-specific tools).
  - Copy `manifest.py`, `policy_compiler.py`. Wire into kernel
    `__init__`.
  - Apply the chokepoint diffs to `_common.py` and `_otel.py`.
  - Confirm 90/90 (or whatever POC3's baseline is).

- [ ] **Phase 3 — Authority MCP fold-in** (TASK-020..025).
  - Copy `governance/authority.py`. Wire into kernel.
  - Apply the `delegated_authority.py` + persona-responder diffs.
  - Drop `mocks/authority-mcp/` from default `boot-demo.sh` if POC3
    has one. Otherwise document the env-var swap.

- [ ] **Phase 4 — Hash-chained ledger** (TASK-026..033).
  - Apply the `ActionLedgerEntry` field additions.
  - Apply the `audit_logger.py` chain + verify_chain changes.
  - Copy `routes/governance.py` (verify endpoint).
  - Copy `EvidencePanel.tsx`. Slot into POC3's WorkflowDetail.
  - Copy `scripts/agt_backfill_chain.py`. Run if POC3 has historical
    blobs.

- [ ] **Phase 5 — Identity + JWS** (TASK-034..044).
  - Copy `agents.py`. Run the registry CI test; add POC3-specific
    entries until green.
  - Copy `governance/identity.py`. Wire into kernel.
  - Apply the `kernel.sign_action` / `verify_jws` additions.
  - Apply the `audit_logger.log()` signing diff.
  - Update EvidencePanel (TASK-042 — the signatures chip already
    exists in the POC1 file you copied).
  - Copy `data/governance/` documentation.

- [ ] **Phase 6 — Enforce mode + capability gates** (TASK-045..050).
  - Apply the `_registry_gate` to `kernel.evaluate_tool_call`.
  - Copy `tests/api/server/services/governance/test_enforce_mode.py`.
  - Add `AGT_ENFORCE` + `AGT_DEFAULT_ACTOR` to env example files.
  - **Leave AGT_ENFORCE=0 by default** until POC3's registry is
    settled. Iteration tail anticipated.
  - Update POC3's ARCHITECTURE.md with the "fourth tier" callout.

- [ ] **Phase 7 — Operator kill switch + UI** (TASK-051..057).
  - Copy `governance/kill_switch.py`. Wire into kernel.
  - Add the kill endpoints to `routes/governance.py` (or copy the
    extended file from POC1).
  - Copy `KillSwitchPanel.tsx`. Slot into WorkflowDetail.

- [ ] **Phase 8 — CI ring + microsite** (TASK-058..064).
  - Copy `.github/workflows/agt-governance.yml`. Adjust `paths:` for
    POC3 layout.
  - Copy `.github/hooks/pre-commit-agt`.
  - Add the OWASP badge to POC3's README.
  - If POC3 has a microsite, copy `OwaspCoverageCard.tsx`.

## Foundry-IQ swap-in note (POC3-specific MCPs)

POC3 ships `heygen-mcp` and a brand-RAG corpus that POC1 doesn't.
These are still ordinary MCPs from the kernel's perspective — they
appear in `data/policies/tools.yaml` like every other tool. The Foundry-IQ
swap-in (e.g. replacing the local Node mock for HeyGen with a real
Foundry-backed MCP) is the same pattern as
[Authority resolution backend (Phase 3)](DEVELOPMENT.md): set the
relevant `*_MCP_URL` env var and the substrate flips to HTTP.

The brand-RAG corpus is a read-only data source consulted by the
`brand_rag` tool. Treat it as a normal tool entry; if Foundry hosts it,
set `BRAND_RAG_MCP_URL`. No special governance handling required.

## Reviewer checklist

Before merging POC3 governance:

- [ ] `agt doctor` green.
- [ ] `agt verify --strict` shows 10/10 OWASP ASI coverage.
- [ ] `tests/api/server/services/governance/` all green.
- [ ] `tests/api/shared/test_agents_registry.py` green (= every
  `agent_label` in fixtures is registered).
- [ ] `agt lint-policy data/policies` clean.
- [ ] One workflow run end-to-end produces a `chain_intact: true`
  VerifyReport with `signatures_valid: true`.
- [ ] One operator kill via the API blocks the matching MCP call
  (test by running the autonomous loop and watching the deny narrative
  fire).
- [ ] Plan status badge updated.

Reviewer: if any of the above is red, hold the merge. Each item is
non-negotiable for the bid response's "OWASP Agentic Top 10 — 10/10
covered" claim to remain true after the POC3 merge.
