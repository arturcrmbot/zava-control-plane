# compose-domain v3 — encode the substrate-fix contract

**Date:** 2026-05-03
**Sister artefacts:**
- [2026-05-03-substrate-fix-design.md](2026-05-03-substrate-fix-design.md) — what the substrate now requires
- [2026-05-03-compose-domain-meta-skill-design.md](2026-05-03-compose-domain-meta-skill-design.md) — v1/v2 baseline

---

## 1. Why v3

Substrate-fix v2 (commits c07f37d5..e2326f8a) shipped 5 platform changes
that change what a generated domain MUST emit and provide:

1. Bus event vocabulary canonical = `durable.*` set. Orchestrators must
   stamp `workflow_type` on every checkpoint payload so the
   `_workflow_types` cache in `internal_durable_event` propagates the
   domain to every downstream FleetEvent.
2. Every HITL `suspended` payload must stamp `persona`,
   `external_event`, `context` so the persona responder can close the
   gate without a human.
3. Personae are now SKILL.md + `decision_policy` Python in YAML
   frontmatter, loaded by `persona_responder` at attach time. Each new
   HITL phase needs a paired persona SKILL.md.
4. `PERSONA_AUTO_CLOSE` allow-list is the demo/operations switch — no
   change at compose time but the SKILL needs to make this honest in
   the generated GRADUATION.md.
5. Domain-aware steady-state ramp loop now lives in
   `simulator_orchestrator.ramp_loop`; new domains need the spawn
   helper added to its `spawners` dict so the ramp picks them up.

`compose-domain` v1/v2 generates none of this contract. A v2 sandbox
graduated today would produce broken recordings (no `workflow_type` on
events), HITL gates that no responder can close (no
`persona`/`external_event`), and would not appear in the autonomous
ramp.

v3 encodes all of it. After v3 lands, every generated domain inherits
the contract by construction.

## 2. What changes in v3

### 2.1 Brief schema (additive, backward-compatible)

Two new optional fields per phase. v2 briefs still parse; v3 enriches
the agent/HITL phases.

```yaml
phases:
  - name: <snake>
    kind: agent
    agent_skill_name: <kebab>
    external_systems: [<id>, ...]
    # NEW v3: scope the agent's allowed-tools instead of getting all
    # tools from external_systems. Defaults to the union of all
    # tools from the phase's external_systems if omitted.
    allowed_tools: [<mcp_tool>_<operation>, ...]

  - name: <snake>
    kind: hitl
    persona: <role>
    # NEW v3: name the external event the orchestrator waits on.
    # Defaults to `<phase.name>_decision` (the existing convention).
    external_event: <snake>
    # NEW v3: which prior-phase outputs should be put on the
    # suspended payload's `context`? Defaults to the previous
    # phase's name.
    context_keys: [<phase.name>, ...]
```

The `personae` block gains an optional `external_event` default per
persona (so a persona handling multiple gates can vary the event name
per gate). Same convention default.

### 2.2 Author-durable-domain emits the substrate contract

Every generated orchestrator now:

- Reads `workflow_type` from the input payload at the top:
  `workflow_type = input_dict.get("type", "<domain.name from brief>")`
- Stamps `workflow_type` on EVERY `checkpoint_activity_trigger`
  payload (`workflow.started`, every `suspended`, every `resumed`,
  `workflow.completed`).
- For HITL phases, stamps `persona`, `external_event`, `context`
  (sourced from the brief's `context_keys` or default).

`templates/orchestrator.py.tmpl` updated. The HITL block becomes:

```python
yield context.call_activity("checkpoint_activity_trigger", {
    "workflow_id": workflow_id, "instance_id": context.instance_id,
    "kind": "suspended",
    "payload": {
        "reason": "awaiting_<phase>",
        "phase": "<phase>",
        "wait_kind": "<from brief>",
        "workflow_type": workflow_type,
        "persona": "<persona role>",
        "external_event": "<event name>",
        "context": {
            "<key>": enriched.get("<key>"),
            ...
        },
    },
})
```

### 2.3 Persona authoring lifted into compose-domain

v1 had `author-runtime-skill` write personae the same way it wrote
phase-agent skills. That's wrong now — personae are a different shape
(YAML frontmatter with executable Python in `decision_policy`).

`author-runtime-skill` keeps responsibility for **phase-agent** SKILL.md
only.

A new sub-skill `author-persona` writes personae:

- One SKILL.md per persona role at
  `<output_root>/api/server/personae/<role>/SKILL.md`.
- Frontmatter exactly matches the live shape (name, description,
  allowed-tools, workflow_label, external_event, decision_policy).
- The `decision_policy` block is the executable Python the responder
  compiles. Mirrors the live `line_manager`, `claim_submitter`, etc.
- The body is human-readable prose tracking the same rule.

The brief's `personae[].decision_policy` paragraph (currently free
prose) is taken as the prose for the SKILL.md body. The executable
Python is **derived from the prose by the operator at compose time**
— i.e. compose-domain step 1 (brief intake) elicits both the prose
and the equivalent Python. v3 adds a brief field
`personae[].decision_code: |` (Python source).

### 2.4 GRADUATION script (replaces the manual checklist)

v1 produced a `GRADUATION.md` with hand-edit instructions. v3 produces
a `graduate.sh` script that mechanically applies the diffs:

- copies the sandbox files into the real trees;
- prepends imports + appends decorators to `function_app.py`;
- adds `build_*` exports to `api/functions/graphs/__init__.py`;
- adds a `spawn_<domain>_workflow` helper to
  `api/server/services/simulator_orchestrator.py`;
- adds the spawner to the `ramp_loop`'s `spawners` dict (NEW);
- adds the `inject` route to `api/server/routes/simulator.py`;
- adds the DOMAIN entry (with `workflow_type`, `phase_aliases`) to
  `api/server/services/blueprint_inventory.py`;
- lifts `<PHASE>_TIMEOUT` constants into `api/shared/constants.py`;
- prints the smoke command + expected event sequence at the end.

The GRADUATION.md still exists as a human-readable reference describing
what graduate.sh does, but the engineer no longer hand-edits.

### 2.5 Recorder verification (NEW step in compose-domain)

After graduation, compose-domain step 6 prompts the operator to record
real walks for the new domain so the deployed page replays them. The
prompt is concrete: `./scripts/profile-autonomous.sh & ; sleep 60 ;
curl POST /api/blueprint/_recorder/start ; ... etc`. The compose-domain
SKILL ends with the recording instructions, not with "graduation done".

This closes the loop the substrate-fix work made possible: a generated
domain becomes visible in the deployed page within minutes of
graduation, with no synthetic templates needed.

## 3. What v3 does NOT change

- The 4 sub-skills (compose-domain, author-runtime-skill,
  author-mcp-tool, author-durable-domain) remain. author-persona is
  added as a 5th.
- Sandbox layout. Same `tools/scratch/compose-domain/<run-id>/`.
- The CHECKLIST. Items get refreshed for the new contract; structure
  unchanged.
- Determinism criterion. Two runs against the same brief still must
  diff to nothing meaningful.

## 4. Determinism test

After v3 lands, regenerate `fleet-travel-preapproval` against its
existing brief. Compare the resulting orchestrator to the
already-graduated one (the v2 work that closes the substrate-fix's
HITL contract for travel by hand). If the v3-generated version
matches the live file modulo whitespace, v3 has correctly encoded
the contract.

## 5. Order of work

1. Update brief schema documentation in compose-domain SKILL step 1.
2. Update `templates/orchestrator.py.tmpl` with workflow_type stamping
   + HITL persona contract.
3. Update author-durable-domain SKILL step 3 to emit the new HITL block
   shape.
4. Add `author-persona` SKILL + persona SKILL.md template.
5. Update compose-domain step 4 sub-skill table (route persona writes
   to author-persona, not author-runtime-skill).
6. Replace GRADUATION.md template with `graduate.sh.tmpl` +
   GRADUATION.md.tmpl reference.
7. Add step 6 recorder-verification prose to compose-domain SKILL.
8. Refresh CHECKLIST items.
9. Determinism test: regenerate fleet-travel-preapproval, diff against
   live.
10. Commit + push.

## 6. Done criteria

- Generating a new domain via compose-domain v3 produces a sandbox
  whose graduate.sh runs without error against a clean checkout.
- The graduated domain appears in the autonomous ramp loop, with HITL
  gates that close themselves under PERSONA_AUTO_CLOSE.
- Recorder captures full-fidelity walks for the new domain on the first
  run.
- Re-running compose-domain against the fleet-travel-preapproval brief
  produces an orchestrator that matches the live file (proves the
  contract is encoded, not improvised).

## 7. Out of scope

- Real GHCP-session personae. v3 keeps the Python `decision_policy` in
  SKILL.md frontmatter that the responder compiles.
- A persona-from-prose code generator (translates the
  `decision_policy` prose paragraph into the equivalent Python). For
  v3 the operator writes both, separately.
- Recorder bug fixes (workflow.resolved double-write, missing
  skill/tool labels on durable.executor.invoked) — tracked separately.
- The 5 new domains. compose-domain v3 is the tool; the next batch is
  what we use it for.
