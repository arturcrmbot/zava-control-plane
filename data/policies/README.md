# `data/policies/` — AGT policy inputs

Per [`plan/feature-agent-governance-toolkit-1.md`](../../plan/feature-agent-governance-toolkit-1.md)
TASK-010, this directory holds the **inputs** that the kernel's policy
compiler ([`api/server/services/governance/policy_compiler.py`](../../api/server/services/governance/policy_compiler.py))
consumes at boot to produce the `agent_os.policies.PolicyDocument`
bundle that mediates every MCP tool call.

The bundle itself is **not** committed (CON-005). It is regenerated
deterministically every boot from these inputs plus the agent registry
([`api/shared/agents.py`](../../api/shared/agents.py), Phase 5+).

## Files

| File              | Owner        | What                                                              |
|-------------------|--------------|-------------------------------------------------------------------|
| `tools.yaml`      | substrate    | Manifest of every MCP tool the substrate calls.                  |
| `agents.policy.yaml` | substrate (Phase 6) | Hand-authored AGT YAML rules for capability + reversibility gates. |
| _(matrix.json)_   | authority    | Lives at [`data/synthetic/authority/matrix.json`](../synthetic/authority/matrix.json) — read by the compiler, not duplicated here. |

## `tools.yaml` schema

Validated by `api.server.services.governance.manifest.ToolManifestEntry`
(Pydantic). Fields:

| Field                | Type            | Meaning                                                              |
|----------------------|-----------------|----------------------------------------------------------------------|
| `id`                 | `str` (unique)  | Canonical tool name as it appears in `@traced_tool(...)` / MCP path. |
| `reversible`         | `bool`          | `false` for any side-effecting call (write/submit/send/cancel/delete/create/post/book). |
| `requires_capability`| `str \| null`   | Capability name the calling agent must declare in its registry entry (Phase 5+). |
| `requires_authority` | `bool`          | `true` if the call needs a matrix authority resolution before execution. |
| `value_field`        | `str \| null`   | Dotted JSON path inside `args` at which the GBP value sits.          |
| `scope_function`     | `str`           | Operating function: `finance` / `hiring` / `creative` / `shared`.    |
| `description`        | `str`           | One-line human description; surfaces in policy YAML + Control Plane chips. |

## Reversibility convention (SEC-004 of the plan)

Reversibility is declared in **one place** — this file — and nowhere
else. Persona SKILL.md / agent SKILL.md may reference it but may not
carry duplicate flags.

| Suffix pattern                                                         | `reversible` |
|-------------------------------------------------------------------------|--------------|
| `*.write_*`, `*.submit_*`, `*.send_*`, `*.cancel_*`, `*.delete_*`, `*.create_*`, `*.post*`, `*.book_*` | `false` |
| `*.list_*`, `*.get_*`, `*.search_*`, `*.lookup_*`, `*.query_*`, `*.find_*`, `*.check_*`, `*.resolve_*` | `true`  |

CI (Phase 8) greps the manifest for any `reversible: true` whose name
matches the destructive pattern and fails the build.

## Engagement-POC swap procedure

When a real Foundry-IQ MCP replaces one of the local mocks:

1. Add / amend the corresponding `tools.yaml` entry to match the real
   tool's name and value-field shape.
2. Re-run the test suite — the policy bundle hash will change; that
   is the intended evidence that policy is in sync with the new tool
   surface.
3. If the real tool ships new operations, add them as separate
   manifest entries. Do not bundle multiple operations under one id.

## Phase status

- **Phase 2 (this PR):** `tools.yaml` populated; manifest + compiler
  online; kernel runs in `log_only` mode at the two chokepoints.
- **Phase 6:** `agents.policy.yaml` lands; `AGT_ENFORCE=1` flips the
  default-deny behaviour on missing manifest entries.
