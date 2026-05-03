---
name: author-mcp-tool
description: |
  Sub-skill of `compose-domain`. Writes ONE in-process Python MCP tool stub
  to a sandbox path, shape-isomorphic to existing tools under
  `api/server/mcp_tools/`. The stub is callable from a runtime SKILL via
  `allowed-tools` and emits OTEL spans + FleetEvents the same way real
  tools do. Returns deterministic synthetic data — no real backend.
audience: design-time-only
forbidden-runtime: true
---

# author-mcp-tool

You write **one** Python file per invocation: an in-process MCP tool stub.
The stub mirrors the shape of `api/server/mcp_tools/claim_lookup.py` and
`api/server/mcp_tools/policy_search.py` exactly. It is callable from a
runtime SKILL via the GHCP SDK's `tools=[…]` channel and produces OTEL
spans the same way real tools do — so the Observatory animates correctly
without anyone having to plug in a real backend.

## Inputs you require from the caller

1. **`output_path`** — absolute path inside the sandbox, e.g.
   `tools/scratch/compose-domain/<run-id>/api/server/mcp_tools/<tool>.py`.
2. **`tool_brief`** — the relevant `external_systems[]` entry from the
   YAML brief:
   ```yaml
   id: <snake_case>
   mcp_tool: <snake_case Python module name>
   operations: [<snake_case function name>, ...]
   ```
3. **`canonical_example_path`** — one absolute path. v1 canonical is
   `api/server/mcp_tools/claim_lookup.py` (HTTP-backed pattern with the
   in-memory escape hatch). The three v1 graduated stubs
   (`workday_hr_employee.py`, `concur_travel_policy.py`,
   `concur_travel_search.py`) are working examples of the in-memory
   shape this skill produces.

If any input is missing, **stop and ask**.

## Note on standalone smoke testing

Importing any module under `api/server/mcp_tools/` triggers
`api/server/mcp_tools/__init__.py`, which transitively imports
`api/server/state.py` → `BlobStore`, which connects to Azurite at
`localhost:10000` on construction. Standalone import-smoke of a generated
tool therefore requires Azurite running:

```bash
azurite --silent --location azurite-data \
  --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0 &
```

Without Azurite, `python -c 'import api.server.mcp_tools.<tool>'` hangs
in retry loops until SIGINT. This is a property of the existing harness,
not of the generated stub.

## Procedure

### Step 1 — Read both canonical examples

Read `canonical_example_path` end-to-end. Note:
- the module docstring style (purpose + how it's exposed + a one-line
  caveat about what's a stub vs production-grade).
- the `from copilot.tools import ToolResult, define_tool` import.
- the `from ._otel import traced_tool` import.
- the Pydantic params class convention (`_FooParams(BaseModel)`).
- the `@define_tool(name=..., description=...)` registration pattern.
- the `@traced_tool("<dotted.name>")` wrapper on the underlying function.

You will mirror this shape. The three v1 graduated stubs
(`workday_hr_employee.py`, `concur_travel_policy.py`,
`concur_travel_search.py`) are good targets to compare against once
you've drafted yours — they are deterministic, self-contained, and
passed CHECKLIST §4.6–4.7.

### Step 2 — Decide: HTTP-backed or in-memory?

For v1 we always pick **in-memory deterministic stub**. Reasons:
- The point of the generated domain is to animate in the Observatory and
  exercise the orchestrator harness — not to integrate with a real
  upstream system.
- HTTP-backed adds a Node mock server, port assignment, env var, and a
  health check. All real engineering, all out of v1 scope.

If the operator/caller insists on HTTP-backed, **stop**. Tell them an HTTP-
backed tool is a separate workflow that lives outside this skill: it
requires authoring a Node mock server under `mocks/<name>-mcp/`, picking a
port, adding it to `docker-compose.yml`, etc. They should write that by
hand, then point a future revision of the in-memory tool at it.

### Step 3 — Build the body

Use the template at `docs/superpowers/skills/compose-domain/templates/mcp_tool.py.tmpl`
as the skeleton.

The shape:

```python
"""<tool>.<operation> MCP tool — <one-line purpose>.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the body of <impl_function> with a real HTTP call
when wiring to a production system.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


@traced_tool("<tool>.<operation>")
def <operation>(<typed-args>) -> dict:
    """<One-line purpose. Mention this is a stub.>"""
    span = trace.get_current_span()
    span.set_attribute("wpp.<tool>.<arg>", str(<arg>))
    return _synth(<arg>)


def _synth(<arg>) -> dict:
    """Deterministic synthesis. Same input → same output across runs."""
    seed = int(hashlib.sha256(str(<arg>).encode()).hexdigest()[:8], 16)
    # …deterministic dict construction keyed on `seed`…
    return {…}


class _<Operation>Params(BaseModel):
    <arg>: <type> = Field(description="<one line>")


@define_tool(
    name="<tool>_<operation>",
    description=(
        "<One sentence describing what this tool does and when an agent would call it. "
        "Stub: returns deterministic synthetic data.>"
    ),
)
def <tool>_<operation>_tool(params: _<Operation>Params) -> ToolResult:
    try:
        result = <operation>(params.<arg>)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
```

> **SDK contract.** `ToolResult.__init__` takes
> `text_result_for_llm: str` and `result_type: "success" | "failure"`.
> It does NOT accept `success=` / `content=` (an older draft API).
> Always JSON-serialise the dict result into `text_result_for_llm`; the
> SDK feeds that string back to the model as the tool output. Returning
> the wrong shape silently breaks every tool call — the model sees a
> `TypeError` string and falls back to invented prose.

One Python module = one `mcp_tool` from the brief = one or more
`operations`. If the brief lists multiple `operations` for the same
`mcp_tool`, generate one `<operation>` function and one
`<operation>_tool` registration per operation, all in the same module.

### Step 4 — Determinism

Every operation must be **pure**: same input → byte-identical output. Use
`hashlib.sha256(str(input).encode())` to seed any synthetic structure
(employee names, calendar busy windows, leave balances). No `time.time()`,
no `random.random()`, no environment reads.

This matters because the meta-skill's quality bar is "two runs against
the same brief diff to nothing". Non-deterministic tool stubs would break
that even if the SKILL.md generator is perfectly stable.

### Step 5 — Synthetic-data realism

Make the synthesis good enough that the agent skill's `allowed-tools`
calls return something the agent can plausibly reason over.

For example, for a `workday_hr_leave_balance.get_leave_balance(employee_id)`
operation:

```python
{
  "employee_id": "EMP-0042",
  "year": 2026,
  "annual_entitlement_days": 25,
  "taken_days": 12,
  "booked_days": 5,
  "remaining_days": 8,
  "carry_over_from_prior_year": 0,
}
```

— numbers consistent (taken + booked + remaining = entitlement + carry_over),
keyed off the seed so the same `employee_id` always returns the same record.

Do not include real-looking PII. Synthesised employee names should follow
the existing repo convention (`EMP-NNNN`, fixture employees only).

### Step 6 — Write the file

Write the assembled Python module to `output_path`. Create parent
directories if needed.

### Step 7 — Self-check

Before returning, verify:

- Module imports resolve textually against the canonical examples
  (`copilot.tools`, `opentelemetry.trace`, `pydantic`, `._otel`).
- Every `operation` from the brief has both an `<operation>` function and
  an `<operation>_tool` registration.
- Every `<operation>` function is `@traced_tool(…)`-wrapped.
- The synth function is pure (no `time`, `random`, `os.environ`,
  network).
- No `TODO` placeholder remains.
- The output JSON shape is internally consistent (cross-field
  invariants hold).

If any check fails, **fix in place**. If a check fails because the brief
asks for something you can't deterministically synthesise, stop and tell
the caller.

## Anti-patterns

- Reading from `data/synthetic/` to "make it more realistic". The real
  synthetic corpus is for the existing two domains. New domains
  synthesise from a seed.
- Importing `httpx` and pointing at a non-existent localhost port. The
  whole point of the in-memory stub is no port management.
- Inventing OTEL attribute names. Mirror what `claim_lookup.py` does
  (`wpp.<tool>.<arg>`).
- Returning lists where the canonical examples return dicts. Stay
  isomorphic.
- Adding multiple `mcp_tool` files in one invocation. One file per call.
  The caller decides how many calls.
