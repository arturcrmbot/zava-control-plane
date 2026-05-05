---
goal: Bring the six weekend-generated `fleet-*` domains up to first-class Fleet-Manager substrate parity with POC1 (expense) and POC2 (hiring), so all eight domains run unattended, register in shared state, surface in operator + FM views, and produce demo-grade narrative variety.
version: 1.0
date_created: 2026-05-04
last_updated: 2026-05-05
owner: WPP Control Plane POC1 — substrate
status: 'Completed'
tags: [feature, architecture, refactor, substrate, fleet-manager]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

**Update 2026-05-05:** All six implementation phases shipped to `main`
in commits `eef6d7fb` (Phases 1–3: registry, generalised
`Workflow.payload`, generalised resolve route), `cbe01787` (Phases 4–6:
Fleet Manager domain awareness, per-domain seed corpora, persona
`escalate` verdict), and `0d13bbf8` (per-domain phase ribbon, hiring
HITL contract, no-clobber on rejection). Verified by
`tests/api/shared/test_domains_registry.py`,
`tests/api/server/test_workflow_payload.py`,
`tests/api/server/test_resolve_route_per_domain.py`,
`tests/api/server/test_fleet_manager_domain_awareness.py`,
`tests/api/server/test_seed_corpora.py`,
`tests/api/server/test_persona_escalate.py`. Per-domain task
checkboxes below are kept as the source-of-truth implementation log.

POC1 (expense) and POC2 (hiring) are first-class citizens of the Fleet Manager substrate: they upsert `Workflow` records into the in-process `StateStore`, light up `query_fleet`, resolve HITL gates from the operator UI, and carry domain-aware language inside the FM skill. The six `fleet-*` domains generated over the weekend (`travel-preapproval`, `vendor-kyc`, `employee-onboarding`, `it-access-request`, `contract-renewal`, `perf-review`) execute end-to-end on the same Durable + MAF spine, light up the blueprint observatory, and (with `PERSONA_AUTO_CLOSE`) close their own HITL gates — but they are invisible to `query_fleet`, the operator UI cannot resolve their gates by hand, the FM skill has no language for them, their inputs cycle through tiny hardcoded arrays so the demo rail is monotonic, and every persona returns binary `approve`/`reject` so the FM has no escalated exception traffic from the new domains.

This plan delivers parity in five independently shippable phases. Each phase ends in a strictly better state than the one before. The endpoint is a substrate where adding a ninth domain via `compose-domain` is a config change, not an integration project.

## 1. Requirements & Constraints

- **REQ-001**: All eight domains must appear in `query_fleet` results consumed by the Fleet Manager session.
- **REQ-002**: All eight domains must be resolvable from the operator UI's exception queue without per-domain `if/elif` branches in the resolve route.
- **REQ-003**: Autonomous demo loop (`./scripts/profile-autonomous.sh` + `SIMULATOR_RAMP_ENABLED=1`) must produce a mixed stream of completed, in-flight, auto-decided, and FM-escalated workflows across all eight domains within 10 minutes of boot, with no human input.
- **REQ-004**: HITL closure for the six weekend domains must continue to use the existing persona contract (executable `decision_policy` block in persona `SKILL.md` frontmatter) — no parallel mechanism.
- **REQ-005**: The Fleet Manager skill (`api/server/skills/fleet-manager/SKILL.md`) must enumerate every registered domain at runtime, not via hardcoded paragraphs.
- **REQ-006**: Per-domain wake hints (analogue of `claim.routed.red`) must be opt-in via the registry, not a global edit to `WAKE_TYPES`.
- **REQ-007**: Each weekend domain must have a committed seed corpus that drives spawner inputs, sized to ≥40 records per domain, with a documented `scenario` mix (clean / amber / escalated).
- **SEC-001**: No new code path may bypass the `PERSONA_AUTO_CLOSE` allow-list. Personae whose role is not in the env var must still leave their gates open.
- **SEC-002**: Persona `decision_policy` blocks remain sandboxed via the existing `_DECISION_BUILTINS` whitelist in `api/server/services/persona_responder.py`. The new `escalate` verdict must reuse that sandbox; no `eval`/`exec` outside it.
- **CON-001**: No UI work in scope. The operator may consume new state via the existing exception queue and workflow detail pages; new copy is acceptable, new pages are not.
- **CON-002**: No changes to the orchestrator generator files in `api/functions/workflows/fleet_*.py` or to per-phase graphs in `api/functions/graphs/`. The contract those files emit (workflow_type, persona, external_event, context on suspended payloads) is the input to this plan.
- **CON-003**: No changes to the deterministic-synthesis MCP stubs in `api/server/mcp_tools/`. They are designed to be input-driven; this plan changes the inputs, not the synthesis.
- **CON-004**: `Workflow.type` literal in `api/shared/types.py` already includes the six fleet workflow_type values (`travel-preapproval`, `vendor-kyc`, `employee-onboarding`, `it-access-request`, `contract-renewal`, `perf-review`); the registry must preserve compatibility with this literal until the literal is widened in Phase 2.
- **CON-005**: Back-compat: existing POC1/POC2 reads of `Workflow.claim` / `Workflow.invoice` / `Workflow.metadata` must continue to work for at least one release after Phase 2; deprecation warnings only.
- **GUD-001**: Single source of truth for every domain fact lives in `api/shared/domains.py`. `blueprint_inventory.DOMAINS`, `simulator_orchestrator._spawners`, `workflows.py._FLEET_PREFIX_TO_TYPE` all read from it.
- **GUD-002**: Phase ordering matters: Phase 1 (registry) and Phase 2 (Workflow.payload) ship together as one PR because they are co-dependent. Phases 3, 4, 5, 6 are independently shippable on top.
- **PAT-001**: Per-domain seed corpora live under `data/synthetic/<workflow_type>/` with one JSON file per logical record collection (e.g. `vendors.json`, `joiners.json`). File shape mirrors `data/synthetic/employees.json` — a top-level array of records with `id`, semantic fields, and an optional `scenario` tag.
- **PAT-002**: Persona `decision_policy` blocks may now return one of three verdicts: `approve` | `reject` | `escalate`. The responder honours `escalate` by leaving the Durable gate open and emitting an enriched `workflow.hitl.requested` event tagged `escalated_from: <persona_role>` so the FM picks it up via triage.

## 2. Implementation Steps

### Implementation Phase 1 — Domain registry

- GOAL-001: Introduce `api/shared/domains.py` as the single source of truth for every per-domain integration fact (workflow_type, prefix, orchestrator name, phases, persona/external_event per HITL phase, operator surface, optional wake hints). Every existing per-domain table in the codebase folds into it without behaviour change.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `api/shared/domains.py` with `Phase`, `WakeHint`, `Domain` dataclasses and a `DOMAINS: dict[str, Domain]` registry keyed by `workflow_type`. Populate entries for all 8 domains: `expense-claim`, `hiring`, `travel-preapproval`, `vendor-kyc`, `employee-onboarding`, `it-access-request`, `contract-renewal`, `perf-review`. Each `Phase` declares `name`, `kind` (`deterministic`/`agent`/`hitl`), and for HITL phases `persona` + `external_event`. | | |
| TASK-002 | Add a `registry.resolve_external_event(workflow_type, phase_name) -> str \| None` helper to `api/shared/domains.py` for use by the resolve route in Phase 3. | | |
| TASK-003 | Add a `registry.all_wake_hints() -> set[str]` helper returning the union of `WakeHint.event` strings from every registered domain, for use by `triage.py` in Phase 4. | | |
| TASK-004 | Refactor `api/server/services/blueprint_inventory.py`'s top-level `DOMAINS: list[dict]` to be derived from `api.shared.domains.DOMAINS` at import time. The visual mind-map's `phase_aliases` mapping stays in `blueprint_inventory.py` (it is a UI concern), but `name`, `status`, `workflow_type`, `skills` are sourced from the registry. | | |
| TASK-005 | Refactor `api/server/routes/workflows.py` `_FLEET_PREFIX_TO_TYPE` constant to be derived from `api.shared.domains.DOMAINS` at module load. Delete the literal dict; build it from `{d.workflow_id_prefix: d.workflow_type for d in DOMAINS.values()}`. | | |
| TASK-006 | Add a unit test `tests/api/shared/test_domains_registry.py` asserting: (a) every `Domain` has a unique `workflow_type` and `workflow_id_prefix`, (b) every HITL phase declares both `persona` and `external_event`, (c) every `persona` referenced exists as a SKILL.md under `api/server/personae/`, (d) every `orchestrator_name` exists as a decorated function in `function_app.py` (parsed via AST or via importing `function_app`). | | |

### Implementation Phase 2 — Generalise `Workflow.payload`

- GOAL-002: Replace the per-domain field sprawl on `Workflow` (`claim`, `invoice`, `metadata`) with a single opaque `payload: dict`. Maintain back-compat properties so POC1/POC2 reads keep working. All six `spawn_fleet_*` functions begin upserting `Workflow` records into `app_state.store`. `query_fleet` now sees all eight domains automatically.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | In `api/shared/types.py`: widen `Workflow.type` to `str` (registry-validated) by deleting the `Literal[...]` whitelist; add `payload: dict = Field(default_factory=dict)`; mark `vendor`, `invoice`, `claim`, `metadata` fields as deprecated by adding a comment block citing the registry as the new source of truth. Keep the fields physically present so existing serialisations keep working. | | |
| TASK-008 | Add a runtime validator in `Workflow.__init__` (or a Pydantic `model_validator`) that asserts `workflow_type in api.shared.domains.DOMAINS` for every newly constructed `Workflow`. The validator emits a `DeprecationWarning` rather than raising for one release so existing test fixtures keep working. | | |
| TASK-009 | Add `build_fleet_<domain>_workflow(wid, **kwargs) -> Workflow` factory functions to `api/server/services/synthetic_data.py` for each of the six fleet domains. Each factory builds a `Workflow` with the correct `workflow_type`, sets `payload` to the domain-specific input dict, derives `created_at`/`sla_due_at`/`agency`/`jurisdiction` from sensible defaults. | | |
| TASK-010 | Update each `spawn_fleet_*_workflow` function in `api/server/services/simulator_orchestrator.py` (six functions, lines L501-L800) to: (a) call the new builder from TASK-009, (b) call `app_state.store.upsert_workflow(w)` immediately after constructing the workflow, (c) pass `w.payload` as the orchestration input under the existing keys the orchestrator expects (e.g. `trip` for travel, `vendor` for KYC). | | |
| TASK-011 | Delete `_synthesize_workflow` and `_FLEET_PREFIX_TO_TYPE` from `api/server/routes/workflows.py`. The detail endpoint now relies on the store always containing the workflow record. | | |
| TASK-012 | Update `api/server/services/economics.py` and any other consumer that reads `w.claim` / `w.invoice` to gracefully handle the new `payload`-shaped workflows by checking `w.workflow_type` first, then falling back to `payload`. List of consumers to audit: `api/server/services/economics.py`, `api/server/services/exception_narrative.py`, `api/server/routes/workflows.py`, `api/server/mcp_tools/query_economics.py`. | | |
| TASK-013 | Add unit tests `tests/api/server/test_workflow_payload.py` covering: (a) a `Workflow` with `workflow_type="vendor-kyc"` and `payload={...}` round-trips through `model_dump(by_alias=True)` and back, (b) `app_state.store.list_workflows()` returns the workflow, (c) `query_fleet` MCP tool's response includes the workflow in `total` and `by_phase` counts. | | |

### Implementation Phase 3 — Generalise the resolve route

- GOAL-003: Replace the hardcoded phase-name switch in `api/server/routes/exceptions.py` with a registry lookup. Operator-UI resolves now work for all eight domains, including correctly raising the per-domain external event back to the Durable orchestrator.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | In `api/server/routes/internal_durable_event.py`: extend the existing `_workflow_types` cache with a parallel `_pending_gates: dict[str, dict[str, str]]` that on every `suspended` event records `{(workflow_id): {"phase": <phase>, "external_event": <event>}}`. Cleared on `resumed`/`workflow.completed`. | | |
| TASK-015 | In `api/server/routes/exceptions.py` `_resolve_one`: replace the `if phase == "Approval"` switch (lines L60-L72) with `event_name = _pending_gates.get(w.id, {}).get("external_event")`. Falls back to the registry's `resolve_external_event(w.workflow_type, w.current_phase)` if the cache is cold (e.g. after FastAPI restart). Returns 422 with a structured error if neither yields an event name. | | |
| TASK-016 | Move `_pending_gates` from a module-level dict in `internal_durable_event.py` into a small singleton `api/server/services/pending_gates.py` so both routes import it cleanly without circular imports. | | |
| TASK-017 | Add an integration test `tests/api/server/test_resolve_route_per_domain.py` that, for each of the 8 domains, simulates a `suspended` event with the canonical `external_event` field, then POSTs `/api/exceptions/{id}/resolve`, then asserts the test double for `raise_orchestration_event` was called with the correct event name. | | |

### Implementation Phase 4 — Fleet Manager domain awareness

- GOAL-004: The Fleet Manager SDK session is taught the substrate's full domain catalogue at boot, and per-domain wake hints fire from validators or activities so the FM has anticipatory signal for the new domains rather than only seeing them at HITL/exception boundaries.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | In `api/server/services/fleet_manager_service.py` `start()`: after loading the static skill text from `skills/fleet-manager/SKILL.md`, append a templated "Domains under supervision" section composed at runtime from `api.shared.domains.DOMAINS` — for each domain emit `<workflow_type> · <display_name> · operator surface: <operator_surface> · HITL events: [<external_event>, ...]`. | | |
| TASK-019 | Edit `api/server/skills/fleet-manager/SKILL.md` to remove the hardcoded "POC1 surface = expense claims … POC2 surface = hiring" paragraph and replace with a placeholder section header: `## Domains under supervision\n\n(Templated at runtime from the domain registry.)`. The templated text from TASK-018 is appended after this block. | | |
| TASK-020 | Add `WAKE_TYPES` augmentation in `api/server/services/triage.py` `should_wake`: change `wakes_fleet_manager(e)` to `e.type in WAKE_TYPES or e.type in registry.all_wake_hints()`. No change to the underlying `WAKE_TYPES` literal in `api/shared/events.py`. | | |
| TASK-021 | Update `api/shared/events.py` `FleetEventType` literal to be widened with a permissive escape hatch: keep current literal entries for typing of legacy code paths, and add a sentinel comment `# Per-domain wake events are added via registry.WakeHint and accepted via FleetEvent.model_config extra='allow'`. (No code change needed; `FleetEvent` already has `extra='allow'`.) | | |
| TASK-022 | For each of the six fleet domains, add (in the registry) a `wake_hints=[...]` list with at least one domain-specific event name (e.g. `vendor-kyc`: `vendor.kyc.high_risk`, `it-access-request`: `access.scope.privileged`, `travel-preapproval`: `travel.policy.exception`, `perf-review`: `perf.calibration.outlier`, `contract-renewal`: `contract.renewal.price_jump`, `employee-onboarding`: `onboarding.access.broad_scope`). These are declared but not yet emitted in this phase — they prove the FM's wake set widens. | | |
| TASK-023 | Add a regression test `tests/api/server/test_fleet_manager_domain_awareness.py` asserting: (a) the FM's appended skill text contains every registered domain's `workflow_type`, (b) `triage.should_wake(FleetEvent(type="vendor.kyc.high_risk", workflow_id="VKY-001"))` returns True. | | |

### Implementation Phase 5 — Seed corpora and scenario-aware spawners

- GOAL-005: Replace the small hardcoded input arrays in each `spawn_fleet_*_workflow` with a per-domain seed JSON corpus carrying `scenario` tags. The autonomous ramp loop rotates through scenarios per domain, producing a deterministic, varied stream of workflows.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-024 | Create `data/synthetic/travel-preapproval/trips.json` with ≥40 records, each carrying `id`, `employee_id`, `origin`, `destination`, `depart_date`, `return_date`, `business_reason`, `scenario` ∈ `{"in-policy", "policy-exception", "high-cost-band"}`. Ratio target: 60% in-policy, 25% policy-exception, 15% high-cost-band. | | |
| TASK-025 | Create `data/synthetic/vendor-kyc/vendors.json` with ≥40 records: `id`, `vendor_name`, `country_of_incorporation`, `proposing_agency`, `scenario` ∈ `{"clean", "sanctions-hit-entity", "sanctions-hit-ubo", "adverse-media"}`. Ratio target: 60% clean, 15% each of the three flagged scenarios. | | |
| TASK-026 | Create `data/synthetic/employee-onboarding/joiners.json` with ≥40 records: `id`, `employee_id`, `department`, `buddy_id`, `start_date`, `scenario` ∈ `{"standard", "elevated-access-request", "external-contractor"}`. | | |
| TASK-027 | Create `data/synthetic/it-access-request/requests.json` with ≥40 records: `id`, `employee_id`, `department`, `requested_role_templates` (list), `business_justification`, `scenario` ∈ `{"routine-rotation", "privileged-broad", "post-incident-narrow"}`. | | |
| TASK-028 | Create `data/synthetic/contract-renewal/contracts.json` with ≥40 records: `id`, `contract_id`, `vendor_name`, `current_annual_value`, `proposed_annual_value`, `scenario` ∈ `{"flat-renewal", "price-jump", "scope-expansion", "below-market"}`. | | |
| TASK-029 | Create `data/synthetic/perf-review/reviewees.json` with ≥40 records: `id`, `employee_id`, `cycle`, `prior_rating`, `scenario` ∈ `{"on-track", "calibration-outlier-high", "calibration-outlier-low", "promotion-candidate"}`. | | |
| TASK-030 | Add a `_load_corpus(workflow_type) -> list[dict]` helper to `api/server/services/simulator_orchestrator.py` that lazily reads and caches the per-domain JSON. Mirrors the lazy `_build_corpus_indices()` pattern used today for POC1 expense claims (lines L57-L76). | | |
| TASK-031 | Add a `_pick_record(workflow_type, scenario=None) -> dict` helper that returns either a round-robin record (no scenario specified) or a deterministic pick from the records matching `scenario`. Mirrors `_pick_claim_for_flavour` at L91-L99. | | |
| TASK-032 | Refactor each `spawn_fleet_*_workflow` function to call `_pick_record(workflow_type, scenario=scenario)` instead of synthesising input from hardcoded arrays. Pass `scenario` through to the workflow `payload` so downstream activities and personae can branch on it. | | |
| TASK-033 | Extend `_per_domain_ramp` in `api/server/services/simulator_orchestrator.py` to accept an optional `scenario_rotation: list[str]` argument. When set, every nth spawn picks the next scenario in the rotation; default behaviour (None) is unchanged. Drive the rotation from each domain's registered seed-corpus scenarios. | | |
| TASK-034 | Add a regression test `tests/api/server/test_seed_corpora.py` asserting each per-domain JSON has ≥40 records, every record has the required fields, every `scenario` value matches the documented allow-list. | | |

### Implementation Phase 6 — `escalate` verdict for personae

- GOAL-006: Extend the persona contract with a third decision verdict `escalate` so a persona can leave a gate open and produce an enriched HITL event for the Fleet Manager. Update 2-3 personae's `decision_policy` blocks to demonstrate the verdict on edge cases. The autonomous loop now produces real FM exception traffic from the new domains.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | In `api/server/services/persona_responder.py`: widen the `_compile_decision_policy` `decide` callable's verdict allow-list from `{"approve", "reject"}` to `{"approve", "reject", "escalate"}`. Update the invalid-decision error string accordingly. | | |
| TASK-036 | In `_handle_hitl`: when the persona returns `decision == "escalate"`, do not call `raise_orchestration_event`. Instead, emit a new `FleetEvent(type="workflow.hitl.escalated", workflow_id=..., persona=persona_role, reason=..., context=context, instance_id=instance_id, external_event=external_event_override)`. The Durable gate stays open. | | |
| TASK-037 | In `api/shared/events.py`: add `"workflow.hitl.escalated"` to the `FleetEventType` literal and to the `WAKE_TYPES` frozenset. Update the FM skill text in TASK-018's templated section to mention escalated events as a high-priority signal. | | |
| TASK-038 | Update `api/server/personae/vendor_kyc_finance_bp/SKILL.md` `decision_policy` to escalate (not approve) when `kyc.country in {"RU", "BY", "IR", "KP", "SY"}` even if no sanctions hit, with reason "high-risk jurisdiction; require human signoff". | | |
| TASK-039 | Update `api/server/personae/it_access_it_admin/SKILL.md` `decision_policy` to escalate when `len(context.access_drafter.requested_role_templates) >= 4` with reason "broad scope request; require human signoff". | | |
| TASK-040 | Update `api/server/personae/contract_finance_bp/SKILL.md` `decision_policy` to escalate when `payload.proposed_annual_value > payload.current_annual_value * 1.25` with reason "price jump >25%; require human signoff". | | |
| TASK-041 | Add a regression test `tests/api/server/test_persona_escalate.py` asserting: (a) a persona returning `escalate` does NOT call `raise_orchestration_event`, (b) the bus receives a `workflow.hitl.escalated` event, (c) the `FleetManagerService` triage path enqueues the escalated event for batch processing. | | |
| TASK-042 | Document the new verdict in [docs/superpowers/skills/compose-domain/SKILL.md](docs/superpowers/skills/compose-domain/SKILL.md): every future persona's `decision_code` block may return one of three verdicts; the responder honours all three. | | |

## 3. Alternatives

- **ALT-001**: Hand-edit each integration point (`exceptions.py`, `query_fleet.py`, FM skill, `_FLEET_PREFIX_TO_TYPE`) with per-domain `if/elif` branches. Rejected: works for 8 domains, breaks at 16, embeds the demo's POC1/POC2 history into the substrate's permanent shape.
- **ALT-002**: Build per-domain `Workflow` subclasses (`ExpenseWorkflow(Workflow)`, `VendorKycWorkflow(Workflow)` …) instead of `payload: dict`. Rejected: forces every UI consumer to know all 8 subclasses; duplicates the registry's job; breaks Pydantic deserialisation from the camelCase API responses.
- **ALT-003**: Generate seed corpora at runtime via `Faker` rather than committing JSON files. Rejected: kills demo determinism — same boot, same workflows, same FM exceptions, same recordings is the whole reason POC1 has 300 committed `CLM-*.json` files.
- **ALT-004**: Add a fourth verdict `defer` to the persona contract for "decide later". Rejected: indistinguishable from leaving the gate open (the Durable timer fires regardless); `escalate` already covers the human-needed case with richer signal for the FM.
- **ALT-005**: Move the registry into a YAML file under `docs/superpowers/specs/` and load it dynamically. Rejected: defers compile-time validation; the `Domain` dataclass form gives Pylance autocomplete + IDE refactor coverage; spec YAMLs already exist as the inputs to `compose-domain` v3 and remain the design-time source of truth.

## 4. Dependencies

- **DEP-001**: All six weekend orchestrators in `api/functions/workflows/fleet_*.py` are present and emit the substrate-fix v2 contract (workflow_type, persona, external_event, wait_kind, context on every suspended payload). Verified live as of 2026-05-04.
- **DEP-002**: All persona SKILL.md files exist under `api/server/personae/<role>/SKILL.md` with valid YAML frontmatter and compilable `decision_policy` blocks. Verified.
- **DEP-003**: `function_app.py` registers all eight orchestrators and their activities as Azure Durable Functions triggers. Verified.
- **DEP-004**: `api/server/services/blueprint_inventory.py` carries skill names for all six fleet domains. Verified.
- **DEP-005**: `api/server/services/persona_responder.py` PERSONA_AUTO_CLOSE allow-list mechanism is in place and documented in `scripts/profile-autonomous.sh`. Verified.
- **DEP-006**: No new third-party Python or Node packages required. The plan uses only `pydantic`, `dataclasses`, `pathlib`, `json` — all already in `pyproject.toml`.

## 5. Files

- **FILE-001**: `api/shared/domains.py` — NEW. Domain registry dataclasses + the `DOMAINS` dict. ≈250 lines.
- **FILE-002**: `api/shared/types.py` — MODIFY. Widen `Workflow.type`, add `payload: dict`, deprecation comments on `claim`/`invoice`/`metadata`.
- **FILE-003**: `api/server/services/synthetic_data.py` — MODIFY. Add six `build_fleet_<domain>_workflow` factories.
- **FILE-004**: `api/server/services/simulator_orchestrator.py` — MODIFY. Six spawners updated to upsert + use seed corpora; new `_load_corpus` and `_pick_record` helpers; `_per_domain_ramp` accepts scenario rotation.
- **FILE-005**: `api/server/routes/workflows.py` — MODIFY. Delete `_synthesize_workflow` and `_FLEET_PREFIX_TO_TYPE`.
- **FILE-006**: `api/server/routes/exceptions.py` — MODIFY. Replace phase-name switch with registry-driven external-event lookup.
- **FILE-007**: `api/server/routes/internal_durable_event.py` — MODIFY. Cache `external_event` per workflow on `suspended`; clear on `resumed`/`workflow.completed`.
- **FILE-008**: `api/server/services/pending_gates.py` — NEW. Tiny singleton holding the per-workflow pending gate cache. ≈30 lines.
- **FILE-009**: `api/server/services/blueprint_inventory.py` — MODIFY. Source name/status/workflow_type/skills from registry; keep phase_aliases local.
- **FILE-010**: `api/server/services/fleet_manager_service.py` — MODIFY. Append templated domain catalogue to skill text at session creation.
- **FILE-011**: `api/server/skills/fleet-manager/SKILL.md` — MODIFY. Remove hardcoded POC1/POC2 paragraph; add placeholder section header.
- **FILE-012**: `api/server/services/triage.py` — MODIFY. Widen wake check to include `registry.all_wake_hints()`.
- **FILE-013**: `api/shared/events.py` — MODIFY. Add `"workflow.hitl.escalated"` to `FleetEventType` and `WAKE_TYPES`.
- **FILE-014**: `api/server/services/persona_responder.py` — MODIFY. Allow `escalate` verdict; emit enriched event when returned.
- **FILE-015**: `api/server/personae/vendor_kyc_finance_bp/SKILL.md` — MODIFY. Add escalate branch on high-risk jurisdiction.
- **FILE-016**: `api/server/personae/it_access_it_admin/SKILL.md` — MODIFY. Add escalate branch on broad-scope requests.
- **FILE-017**: `api/server/personae/contract_finance_bp/SKILL.md` — MODIFY. Add escalate branch on price jump >25%.
- **FILE-018**: `data/synthetic/travel-preapproval/trips.json` — NEW. ≥40 records with scenario tags.
- **FILE-019**: `data/synthetic/vendor-kyc/vendors.json` — NEW. ≥40 records with scenario tags.
- **FILE-020**: `data/synthetic/employee-onboarding/joiners.json` — NEW. ≥40 records.
- **FILE-021**: `data/synthetic/it-access-request/requests.json` — NEW. ≥40 records.
- **FILE-022**: `data/synthetic/contract-renewal/contracts.json` — NEW. ≥40 records.
- **FILE-023**: `data/synthetic/perf-review/reviewees.json` — NEW. ≥40 records.
- **FILE-024**: `tests/api/shared/test_domains_registry.py` — NEW.
- **FILE-025**: `tests/api/server/test_workflow_payload.py` — NEW.
- **FILE-026**: `tests/api/server/test_resolve_route_per_domain.py` — NEW.
- **FILE-027**: `tests/api/server/test_fleet_manager_domain_awareness.py` — NEW.
- **FILE-028**: `tests/api/server/test_seed_corpora.py` — NEW.
- **FILE-029**: `tests/api/server/test_persona_escalate.py` — NEW.
- **FILE-030**: `docs/superpowers/skills/compose-domain/SKILL.md` — MODIFY. Document the three-verdict persona contract.

## 6. Testing

- **TEST-001**: Registry validity (TASK-006). Static asserts: unique workflow_types, unique prefixes, every persona in registry has a SKILL.md, every orchestrator_name resolves.
- **TEST-002**: `Workflow.payload` round-trip (TASK-013). Construct → upsert → list → query_fleet → assert visible.
- **TEST-003**: Per-domain resolve (TASK-017). For each of 8 domains, simulate suspended → POST resolve → assert `raise_orchestration_event` called with correct event name.
- **TEST-004**: FM domain awareness (TASK-023). Skill text contains all 8 workflow_types; `should_wake` returns True for declared wake hints.
- **TEST-005**: Seed corpora structural (TASK-034). Each JSON has ≥40 records; required fields present; scenarios within allow-list.
- **TEST-006**: Persona escalate (TASK-041). `escalate` verdict does not raise external event; `workflow.hitl.escalated` lands on bus; FM triage enqueues it.
- **TEST-007**: End-to-end autonomous run (manual, gates ship). Boot with `./scripts/profile-autonomous.sh` + `SIMULATOR_RAMP_ENABLED=1` + `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS=30` for 10 minutes. Assert: ≥30 workflows visible across ≥8 distinct workflow_types in `/api/workflows`; ≥3 escalated exceptions visible in `/api/exceptions`; FM session log shows `query_fleet` returning all 8 workflow_types in its `by_phase` aggregate.

## 7. Risks & Assumptions

- **RISK-001**: `Workflow.type` widening from `Literal[...]` to `str` may break a downstream consumer that pattern-matches on the exact literal. Mitigation: TASK-008 emits a `DeprecationWarning` rather than raising for one release; CI grep for `Literal["expense-claim"` and similar patterns to find hidden consumers.
- **RISK-002**: Back-compat shim on `Workflow.claim` / `Workflow.invoice` / `Workflow.metadata` may mask test failures where those fields are spuriously read on a fleet workflow. Mitigation: TEST-002 explicitly asserts on a fleet workflow that the back-compat fields return `None` cleanly.
- **RISK-003**: `_pending_gates` cache survives across FastAPI restarts only if Durable replays the suspend (it does — that's the whole point of Durable). But if a workflow is resolved from the UI within seconds of a restart and the cache is cold, the registry fallback in TASK-015 must be exercised. Mitigation: TEST-003 boots a fresh process to exercise the cold path.
- **RISK-004**: Seed corpora may produce LLM agent runs that fail validators on records the agent finds confusing (e.g. unusual `business_justification` strings). Mitigation: each seed JSON's `scenario` mix biases toward the deterministic synth's known-good shapes; the 60/15/15/15 ratios in Phase 5 keep the failure rate low.
- **RISK-005**: Adding `escalate` to the persona verdict allow-list may cause an existing persona to escalate on a code path nobody noticed. Mitigation: only TASK-038/039/040 introduce escalate-returning code; existing personae keep their two-verdict behaviour.
- **RISK-006**: Six weekend orchestrators emit `workflow.started` with `payload.workflow_type` set, but the original `workflow.started` handler in `internal_durable_event.py` constructs its `FleetEvent` without setting `workflow_type` because `_workflow_types` is populated *after* the legacy `workflow.started` emit fires. Net effect: the very first event for each workflow lacks `workflow_type` on the bus. Mitigation: in TASK-014, populate `_workflow_types` from `body.payload.get("workflow_type")` BEFORE the `_emit("workflow.started", wid)` call (small reorder of existing code in `receive_durable_event`).
- **ASSUMPTION-001**: Phases 1+2 ship together as one PR; subsequent phases ship independently.
- **ASSUMPTION-002**: The eight `workflow_type` values stabilise at this iteration; renaming any one is a separate migration.
- **ASSUMPTION-003**: Autonomous-profile reproducibility is more valuable than scenario surprise — every demo run produces the same workflow stream when seeded the same way (deterministic round-robin + deterministic synth).
- **ASSUMPTION-004**: The Fleet Manager's GHCP SDK session can re-read its appended skill text within one debounce cycle of the new domain registry being loaded, so a runtime registry change does not require a process restart. Validated via the existing `start()` flow.
- **ASSUMPTION-005**: Operator UI is acceptable to continue showing "Awaiting operator review" generically for the new domains; per-domain copy is out of scope per CON-001.

## 8. Related Specifications / Further Reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — three-tier substrate (Fleet Manager / Durable / per-phase Pregel graphs).
- [docs/superpowers/skills/compose-domain/SKILL.md](docs/superpowers/skills/compose-domain/SKILL.md) — the meta-skill that generates new domains; v3 is the contract this plan honours.
- [docs/SCOPE-DELTA.md](docs/SCOPE-DELTA.md) — what is laboratory vs engagement-POC; this plan stays strictly within the laboratory build.
- [api/server/services/persona_responder.py](api/server/services/persona_responder.py) — the persona contract and PERSONA_AUTO_CLOSE allow-list this plan extends.
- [scripts/profile-autonomous.sh](scripts/profile-autonomous.sh) — the autonomous demo profile this plan makes meaningful for all 8 domains.
- [api/functions/workflows/fleet_travel_preapproval.py](api/functions/workflows/fleet_travel_preapproval.py) — canonical example of the substrate-fix v2 contract every weekend orchestrator emits.
