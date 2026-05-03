# Substrate fix — proper event vocabulary, persona coverage, autonomous run

**Date:** 2026-05-03
**Driver:** Need an honest local stack that runs every domain end-to-end
autonomously, so the recorder can capture full-fidelity walks per domain
and the deployed page replays the real thing. Currently the demo path
relies on hand-coded synthetic templates because three platform issues
prevent recording from working. Worth fixing properly before scaling
to 10–20 generated domains.

**Sister artefacts:**
- [2026-05-03-compose-domain-meta-skill-design.md](2026-05-03-compose-domain-meta-skill-design.md) — meta-skill v1/v2 (will lift to v3 after this work)
- [2026-05-03-blueprint-microsite-design.md](2026-05-03-blueprint-microsite-design.md) — page that consumes the events
- `docs/blueprint-microsite-contributor-guide.md` — recorder + replay path

---

## 1. The three problems we're fixing

### 1.1 Two parallel event vocabularies
The Functions-host `_tracked_executor` emits **executor-level** webhook
events (`executor.invoked` with stage start/complete) per skill /
validator / deterministic step. The FastAPI-side
`internal_durable_event` translates them into **phase-level** FleetEvents
on the bus (`workflow.phase.started`, `workflow.phase.completed`,
`workflow.exception.detected`, etc.).

The observatory (`_OBSERVATORY_TYPES`), the synthetic templates, and the
recorder filter all expect the **rich `durable.*` set**:
`durable.step.started`, `durable.step.completed`,
`durable.executor.invoked`, `durable.validator.blocked`,
`durable.suspended`, `durable.resumed`, `durable.workflow.completed`.

The result: real workflows produce ~6 events to the bus; the page renders
only header-level activity; the recorder captures the same coarse subset.

### 1.2 Hand-built domains don't stamp `workflow_type`
Travel does (we added it). Expense and hiring do not. Recordings come
out filenamed `unknown-...` and have `workflow_type: None` on every
event, so on replay `_domain_from_workflow_type` resolves to None and
the page can't pick a ring.

### 1.3 HITL gates have no responders for hand-built domains
Travel has `line_manager`. Expense (justification + arbitration) and
hiring (budget + offer + voice + interview) do not. Without responders,
captured walks stop at the first HITL.

---

## 2. The contract we're settling on

### 2.1 Bus event vocabulary (canonical)

The bus speaks `durable.*` for everything orchestrator-runtime-related,
plus `workflow.*` for the cross-cutting workflow-level signals. Both
producers (`internal_durable_event` translating Functions webhooks) and
consumers (observatory, recorder, mind-map, persona responder) read this
set.

**Forwarded set (= `_OBSERVATORY_TYPES` = `RECORDED_TYPES`):**

| Event | When | Carries |
|---|---|---|
| `durable.workflow.started` | orchestrator emits `workflow.started` checkpoint | `workflow_id`, `workflow_type`, `instance_id` |
| `durable.step.started` | each phase entry | `+ phase`, `+ step` |
| `durable.step.completed` | each phase exit | `+ phase`, `+ duration_ms` |
| `durable.executor.invoked` | each `_tracked_executor` start AND complete | `+ name`, `+ type`, `+ stage`, `+ tool?`, `+ duration_ms?` |
| `durable.validator.blocked` | validator returns `ok: false` | `+ name`, `+ reason` |
| `agent.completed` | GHCP session ends | `+ skill`, `+ skill_label`, `+ tool_calls` |
| `durable.suspended` | orchestrator parks at HITL | `+ reason`, `+ wait_kind`, `+ phase`, `+ persona`, `+ external_event`, `+ context` |
| `workflow.hitl.requested` | suspended → translated for responders | mirrors `durable.suspended` payload |
| `workflow.exception.detected` | validator-blocked turns into a card | `+ category`, `+ severity` |
| `durable.resumed` | external event resolves the gate | `+ phase` |
| `durable.workflow.completed` | orchestrator finishes | terminal |
| `workflow.resolved` | composition signal mirroring completion | terminal |

The previous `workflow.phase.started` / `workflow.phase.completed` events
get **renamed** to `durable.step.started` / `durable.step.completed`.
Existing Fleet Manager subscribers, accuracy harness, etc., are checked
for the rename and updated.

### 2.2 Mandatory event stamping

Every FleetEvent emitted on the bus from `internal_durable_event` carries:

- `workflow_id` (always)
- `workflow_type` (always — via the `_workflow_types` cache populated on first sight)
- `domain` (NOT — resolved at the consumer, not the producer; consumers are `_normalise_event` for SSE and the recorder)

Every orchestrator emits a `workflow.started` checkpoint with `workflow_type` in payload. Required (orchestrator-side regression test enforces).

Every orchestrator HITL stamps in `suspended` payload:
- `reason`, `wait_kind`, `phase` (existing)
- `persona`, `external_event`, `context` (NEW for hand-built domains; already true for Travel)

### 2.3 Persona responder set

| Persona | SKILL.md | Closes | Decision policy |
|---|---|---|---|
| `line_manager` | exists | travel: `manager_approval_decision` | in-policy + low/mid → approve |
| `claim_submitter` | NEW | expense: `justification` | always submits a synthetic justification (auto-deterministic; mirrors `simulate_justification`) |
| `ssc_reviewer` | NEW | expense: `reviewer_decision` | accept-justification when `category in {meals, travel}` and `amount < £500`; otherwise reject. Mirrors the existing reviewer-decision corpus's modal pattern. |
| `finance_bp` | NEW | hiring: `budget_approval` | approve when `requires_finance_bp == false` OR `delta_vs_midpoint_gbp ≤ £10k`; reject otherwise |
| `hr_bp` | NEW | hiring: `offer_approval` | approve when `offer.confidence > 0.7` AND no flagged_clauses; reject otherwise |
| `recruiter` | NEW | hiring: `invite_decision` + `interview_decision` | always invite; always advance after interview (deterministic green path) |
| `candidate` | NEW | hiring: `voice_complete` + `slot_picked` | synthesise voice score 0.75, pick first available slot |

Each responder is added to `PERSONA_HANDLERS` registry in
`api/server/services/persona_responder.py`. SKILL.md per role under
`api/server/personae/<role>/SKILL.md`. Hand-built orchestrators get
edits to stamp `persona`/`external_event`/`context` on each suspended
payload.

### 2.4 Steady-state ramp

`api/server/services/simulator_orchestrator.py` already has `ramp_loop`
for expense. Generalised to:

```python
async def ramp_loop():
    """Domain-aware steady-state ramp.
    
    Env vars:
      SIMULATOR_RAMP_ENABLED              0/1; default 1 in this branch
      SIMULATOR_RAMP_AVG_INTERVAL_SECONDS per-domain default ~60
      SIMULATOR_RAMP_DOMAINS              csv of domain names to spawn;
                                          default = every live domain in
                                          the manifest
    """
```

Per-domain spawn delegates to the existing `spawn_*_workflow` helpers.
Jitter ±30%. Independent goroutines per domain so failures in one don't
stall others.

### 2.5 What `compose-domain` v3 picks up

After this commit lands, the meta-skill SKILLs are updated to encode
the contract:

- The orchestrator template includes `workflow_type` stamping on every
  checkpoint.
- The orchestrator template includes `persona`/`external_event`/`context`
  on every HITL payload.
- The persona SKILL.md template is paired with a stub
  `PERSONA_HANDLERS[role] = ...` snippet the GRADUATION.md tells the
  engineer to add.
- The vocabulary table above is documented as the "what events the page
  expects" reference.

Compose-domain v3 is a follow-up commit, scoped after the substrate
fix lands.

---

## 3. Order of work

1. **Vocabulary alignment** (`internal_durable_event` rename + bus emit
   shape). Verify hand-built workflows still complete; existing tests
   pass.
2. **`workflow_type` stamping** in expense + hiring orchestrators.
   Mirrors the Travel pattern.
3. **Persona SKILLs + responder handlers** (6 new SKILL.md files, 6 new
   `PERSONA_HANDLERS` entries). Mirror `line_manager` exactly.
4. **HITL payload extension** in expense + hiring orchestrators. Adds
   `persona`/`external_event`/`context` to every `suspended` checkpoint.
5. **Ramp loop generalisation** (per-domain spawn cadence).
6. **Recorder verification.** Run all 4 domains under steady-state for
   5 min; record; replay; confirm orbit detail. Commit recordings.
7. **`compose-domain` v3** (separate commit) — encode the contract.

Total: ~7 atomic commits on main. Each one shippable on its own.

---

## 4. Done criteria

- `make up` (or equivalent) runs all 4 domains autonomously without
  manual intervention. Run it for 5 min, get ≥3 completed workflows
  per domain.
- Recorder captures full-fidelity walks per domain (≥7 events for
  expense, ≥10 for hiring, ≥5 for travel, ≥3 for onboarding).
- After replay, the page renders the same orbit detail as live.
- All existing tests pass.
- `compose-domain` v3 spec drafted (separate commit) but not yet built.

---

## 5. What this is explicitly NOT doing

- Composing new domains. That's the next phase, after the substrate is
  stable.
- Deploying. Recordings get committed; deploy is a separate step.
- Real GHCP-session personae. Deterministic only in v1; agentic personae
  are a v2 lift.
- Replacing the synthetic `_STREAM_TEMPLATES` immediately. They stay as
  fallback until the recordings prove out; then we can decide to drop
  them or keep as a "no recordings" safety net.
- Time-of-day arrival profiles, region failures, repeat-offender ramps,
  etc. Steady-state per-domain spawn only.
