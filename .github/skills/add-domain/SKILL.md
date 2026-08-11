---
name: add-domain
description: 'Add a new business domain (workflow_type) to the Zava control-plane substrate. Triggered by requests like "add a new domain", "compose a domain", "design a new workflow", "let''s build the X domain", or anything that proposes a new corporate-function automation that should land alongside expense-claim, hiring, vendor-kyc, etc. End-to-end recipe: brief → compose-domain sandbox → graduate.sh → validate active pack → VERTICAL-PROOF.md.'
---

# Add a domain

## What this is

A concise recipe for adding a new `workflow_type` to an **installed vertical
pack**. Every domain lives inside exactly one vertical; business assets are
owned by that pack and never shared across packs or global legacy roots.

## Key references

| Resource | Path |
|---|---|
| **Vertical build contract (primary authority)** | [docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md](../../../docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md) |
| **Meta-skill (primary authority)** | [docs/superpowers/skills/compose-domain/SKILL.md](../../../docs/superpowers/skills/compose-domain/SKILL.md) |
| Brief schema (v4) | [docs/superpowers/skills/compose-domain/brief.schema.yaml](../../../docs/superpowers/skills/compose-domain/brief.schema.yaml) |
| Checklist | [docs/superpowers/skills/compose-domain/CHECKLIST.md](../../../docs/superpowers/skills/compose-domain/CHECKLIST.md) |
| 19 worked-example briefs | [docs/superpowers/specs/archive/](../../../docs/superpowers/specs/archive/) |
| Authoring sub-skills | [author-durable-domain](../../../docs/superpowers/skills/author-durable-domain/SKILL.md), [author-runtime-skill](../../../docs/superpowers/skills/author-runtime-skill/SKILL.md), [author-persona](../../../docs/superpowers/skills/author-persona/SKILL.md), [author-mcp-tool](../../../docs/superpowers/skills/author-mcp-tool/SKILL.md) |
| Persona meta-skill | [docs/superpowers/skills/compose-persona/SKILL.md](../../../docs/superpowers/skills/compose-persona/SKILL.md) |
| Vertical proof requirements | [docs/VERTICAL-PROOF.md](../../../docs/VERTICAL-PROOF.md) |
| Architecture | [docs/ARCHITECTURE.md](../../../docs/ARCHITECTURE.md) §2, §4, §8, §11 |
| Constellation story spec | [docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md](../../../docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md) |

## Authority

Follow the code-first
[Vertical Build Contract](../../../docs/superpowers/contracts/VERTICAL-BUILD-CONTRACT.md).
This entry point adds one process to an installed pack; it does not define a
second ownership, readiness, or proof contract.

Generated business behavior must preserve the build-contract narrative
boundary: synthetic assets (actor world, personae, synthetic MCP adapters)
are functional demonstration scaffolding. Customer systems connect at those
edges — the synthetic adapter is replaced by a real one at the same tool
boundary without changing workflow, governance, or evidence contracts.
All proof, authority, pack rules, and deploy gates remain in force.

## Procedure

### 1 — Select the target vertical

Every run must declare a target vertical:

```bash
# Explicit (preferred):
vertical=telco   # or agency, or any installed pack

# Fallback: active ZAVA_VERTICAL env var
# Fallback: agency
```

### 2 — Run compose-domain (sandbox)

Invoke the [compose-domain](../../../docs/superpowers/skills/compose-domain/SKILL.md)
meta-skill with the vertical set:

```
compose-domain vertical=<name>
```

compose-domain generates a complete Durable-fidelity sandbox under
`tools/scratch/compose-domain/<run-id>/`, including an executable
`graduate.sh`. It does **not** touch any live tree.

### 3 — Graduate (pack-scoped)

Run the generated script from the repo root:

```bash
bash tools/scratch/compose-domain/<RUN_ID>/graduate.sh
```

The script performs six idempotent steps — all scoped to the selected
vertical pack (`verticals/<vertical>/`):

1. Validate the selected pack and sandbox layout.
2. Copy generated business assets (`skills/`, `personae/`, `mcp_tools/`,
   `entity_projections/`) into the pack.
3. Register the orchestrator and activities on the pack's `durable.py`.
4. Export graph builders into `api/functions/graphs/__init__.py`.
5. Register the spawner, domain declaration, and function membership on the
   pack's `spawners.py` / `domains.py` / `functions.py`.
6. Validate the active pack (`active_runtime().pack.domains` must include the
   new `workflow_type`) and print smoke commands.

### 4 — Validate active pack

After graduation, verify the pack:

```bash
ZAVA_VERTICAL=<vertical> python3 -c "
from api.shared.vertical_loader import active_runtime, validate_pack
rt = active_runtime()
validate_pack(rt.pack)
print('<wt> in pack:', '<wt>' in rt.pack.domains)
"
```

Expected: `<wt> in pack: True`.

### 4b — Prove live demo behavior

These are blocking checks, not optional polish:

1. Call the real governance `kernel().check_authority(...)` for every HITL
   persona using the action, category, and value emitted by the workflow.
2. Trigger each gate with `PERSONA_AUTO_CLOSE=*`; require
   `persona.decided`, `durable.resumed`, and terminal status within 15 seconds.
3. Inspect the suspended Workflow API record and require
   `payload.hitl_context` (`persona`, `external_event`, `phase`, context).
4. Keep the browser mounted across a backend restart; require cursor rewind on
   lower `latest_seq` and a visible event within one second of the next click.

### 4c — Pass the blocking execution-visibility gate

Actual execution evidence must be visible and self-consistent. Every active
non-stub workflow type needs an inspected instance; validate only phases,
reasoning, tool calls, decisions, lineage, outputs, and failures that actually
occurred. Use `run_agent_session` for agent work so canonical
`agent.completed` and tool-call evidence persist. Run
`tools/workflow_visibility_proof.py` with the live/replay commands in
`docs/superpowers/skills/compose-domain/CHECKLIST.md` §13.

### 5 — Satisfy docs/VERTICAL-PROOF.md

Before claiming the domain is shipped, collect the evidence required by
[docs/VERTICAL-PROOF.md](../../../docs/VERTICAL-PROOF.md):

- Full proof chain (actor world → sensor → Durable → typed command →
  world mutation → evaluation).
- Every HITL action has a matching authority matrix rule. With
  `PERSONA_AUTO_CLOSE=*`, a representative gate must emit
  `persona.decided`, resume Durable, and leave no workflow in
  `awaiting_hitl`.
- HITL recovery survives missed events and restarts: the workflow persists
  `hitl_context` (`persona`, `external_event`, `phase`, decision context) so
  the periodic sweep can reconstruct the resolving event.
- A browser kept open across a backend restart must detect a lower
  `latest_seq`, replay `/api/world/events?after=0`, and show the first visible
  scenario event within one second of the click.
- Identity consistency across all eight surfaces.
- Both replay probes (Functions disabled; actor world disabled).
- Zero browser errors; clean process teardown.
- Distinct evidence for hero and each shared-engine workflow.
- Recorded walks committed (`data/blueprint-recordings/<wt>-*.jsonl`).
- The blocking execution-visibility gate passes for every active non-stub workflow type.

## Hard rules

- **Sandbox-only generation.** compose-domain and every sub-skill write only
  under `tools/scratch/compose-domain/<run-id>/` and
  `docs/superpowers/specs/`. Never to live trees during Phase 3.
- **Pack ownership.** All business assets (skills, personae, MCP tools, entity
  projections, domain declaration, function membership, spawner) land in
  `verticals/<vertical>/`. Workflow implementation modules may remain under
  `api/functions/`; only the selected pack registers them.
- **No global business registry patches.** Never patch global compatibility
  adapters or cross-pack registries. `api/shared/domains.py`,
  `api/shared/functions.py`, and `api/shared/agents.py` are read-only
  adapters that delegate to the active pack — they are never modified by
  graduation.
- **No cross-pack leakage.** A domain graduated into the Telco pack must not
  appear when `ZAVA_VERTICAL=agency`. Verify with
  `tests/api/shared/test_vertical_pack_inventory.py`.
- **Completion requires VERTICAL-PROOF.md.** A vertical is not shippable
  until all criteria in `docs/VERTICAL-PROOF.md` §6 are satisfied.
- **No self-certifying HITL.** Matching persona names and external-event strings
  is insufficient. Run the real governance `authority_check` with the action,
  category, and value emitted by the workflow, then prove the live orchestration
  resumes.
