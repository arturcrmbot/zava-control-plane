---
goal: Land two substrate primitives — a Delegated Authority MCP and a `compose-persona` meta-skill — so every approval gate in every domain resolves through one matrix instead of inline thresholds, and so new personae are composed from a brief instead of hand-authored. End state: the substrate visibly "breathes" (the persona library grows from ~16 to ~30 without per-role engineering, every approval surfaces an explainable authority resolution), and adding a domain in any new corporate function reduces to (a) a `compose-domain` brief, (b) a `compose-persona` brief per new role, (c) zero edits to skills/orchestrators that approve.
version: 1.1
date_created: 2026-05-05
last_updated: 2026-05-05
owner: Apex substrate
status: 'Completed'
tags: [feature, architecture, substrate, mcp, persona, authority]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

**Update 2026-05-05:** All seven phases shipped to `main` in commits
`48cf174c` (Phases 1–6: authority MCP + matrix + Python wrapper +
skill wiring + persona registry + threshold migration + compose-persona
meta-skill + 14 graduated personae), `dfda1d50` (Phase 7 backend +
Personae section on the blueprint microsite), and follow-on commits
for the Authority Matrix page (TASK-037) and the Authority resolution
card on Control Plane WorkflowDetail (TASK-035). The personas count
landed at **29** (15 original + 14 graduated), of which **15 read
thresholds from the delegated-authority matrix** instead of inlining
them.

Live validation: the 80-rule matrix MCP (`mocks/authority-mcp/` :4108)
resolved all 8 canonical domain test cases live; the FastAPI persona
responder loads the full 29 personae cleanly and closes gates
autonomously per `PERSONA_AUTO_CLOSE` (now wired in `.env` for the
default demo profile); the blueprint microsite renders the persona
library + authority matrix sections live from `/api/personas` and
`/api/authority/matrix`; the Control Plane workflow detail surfaces
the matched approver chip + governing rule_id on every workflow whose
type maps into the matrix.

65 new tests passing across the new modules (registry validation, route
proxies, persona parity, skill wiring assertions). Per-task checkboxes
below are kept as the source-of-truth implementation log.

Today every HITL gate in the substrate resolves through a hand-authored persona whose `decision_policy` carries threshold values inline (e.g. `abs(delta) > 10000` in `finance_bp`, `>25%` price-jump in `contract_finance_bp`, broad-scope role list in `it_access_it_admin`). That works for 8 domains × ~16 personae. It does not scale to the corporate-function map we're targeting (~50 domains, ~50 personae), and it can't survive the customer composing their own — every threshold change is a code edit a human has to land.

This plan lands the two primitives that collapse that cost:

1. **Delegated Authority MCP** — a single resolver keyed on `(action, value, category, business_unit, geography, requester_role)` returning the approver role, the resolved threshold, and the reasoning. Every persona/skill that today inlines a threshold delegates to it. New domains call it without thinking. Authority changes are a JSON edit on a deterministic mock now, a Foundry IQ swap later.
2. **`compose-persona` meta-skill** — sister to `compose-domain`, sandbox-only, design-time. Takes a persona brief (YAML or free-text dialogue) and emits a persona SKILL.md (frontmatter + executable `decision_policy`) + a registry entry + a graduate script. New personae cost minutes, not days.

To demonstrate the curve (the "breathing" claim), Phase 6 graduates ≥12 new personae across functions we don't yet have domains for (AP clerk, controller, FP&A analyst, sourcing lead, category manager, contracts counsel, DPO, account director, project manager, change manager, comp & ben analyst, mobility specialist). They sit in the registry as available cast — visible on the blueprint microsite — even before their domains land. Phase 7 (optional, last) surfaces the authority matrix and persona library to the operator UI.

No org-specific copy in any new artefact. Existing per-customer language (e.g. `finance-agent@zava` agent IDs) is left untouched; new code uses neutral nouns (`finance-agent`, `the operator`, `the requester`).

## 1. Requirements & Constraints

- **REQ-001**: All eight existing domains' HITL gates must resolve through the new authority MCP for at least the threshold/limit lookup, with no behavioural regression against the substrate-fix v2 contract.
- **REQ-002**: The authority MCP must answer two operations: `resolve_approver(action, value, category, requester_role, business_unit, geography) -> ApproverResolution` and `check_authority(role, action, value, category, business_unit, geography) -> AuthorityCheck`. Both are pure functions of the request + the authority matrix data; no side effects.
- **REQ-003**: The authority matrix data lives in `data/synthetic/authority/matrix.json` as an ordered list of rules with explicit precedence (first match wins), seeded with ≥80 rules covering every action exercised by the 8 existing domains.
- **REQ-004**: Every persona under `api/server/personae/` whose decision policy references a numeric threshold (currently 6 of 16) must call the authority MCP for that threshold instead of inlining it. Decision logic stays in the persona; only the threshold sourcing moves.
- **REQ-005**: Persona registry — `api/shared/personas.py` — exists, is the single source of truth for `(role, archetype, scope, default_authority_band, workflow_label, external_event_default)`, and is consumed by the persona responder, the FM skill text composer, the blueprint inventory, and the future operator-UI persona library.
- **REQ-006**: `compose-persona` meta-skill exists under `docs/superpowers/skills/compose-persona/` and is invocable end-to-end from a YAML brief. Its output lands strictly under `tools/scratch/compose-persona/<run-id>/`. Graduation is a separate, manual step.
- **REQ-007**: After Phase 6, ≥30 personae are registered (16 existing + ≥12 new + 2 from any incidental domain authoring), each with a SKILL.md, a registry entry, an archetype tag, and a `decision_policy` that round-trips through the responder's sandbox.
- **REQ-008**: The autonomous demo loop (`./scripts/profile-autonomous.sh` + `SIMULATOR_RAMP_ENABLED=1`) continues to produce the same mixed stream of completed/in-flight/auto-decided/escalated workflows after every phase. Each phase ships independently green.
- **SEC-001**: The authority MCP exposes a read-only surface; no operation mutates the matrix at runtime. Matrix changes are file-system edits, picked up at next process boot or via an explicit `/health` reload endpoint.
- **SEC-002**: `decision_policy` blocks generated by `compose-persona` reuse the existing `_DECISION_BUILTINS` whitelist sandbox in `api/server/services/persona_responder.py`. The meta-skill MUST NOT introduce new builtins; if a generated policy needs additional callables they go through the whitelist with explicit operator approval.
- **SEC-003**: No new code path bypasses `PERSONA_AUTO_CLOSE`. New personae default to closed (off the allow-list) and must be added by name to the env var to participate in autonomous closing.
- **SEC-004**: No org-specific identifiers, persona names, agency names, or proprietary process language in any new file. Reviewer must grep `grep -riE 'wpp|vml|ogilvy|wunderman|groupm|hogarth|kantar' tools/ data/synthetic/authority/ docs/superpowers/skills/compose-persona/ api/server/mcp_tools/delegated_authority.py api/shared/personas.py` and find zero hits.
- **CON-001**: Local-only. No real Azure resource provisioning. The authority MCP runs as a Node mock alongside the existing nine on a new port (4108). The matrix is JSON committed to git.
- **CON-002**: Backwards-compat: existing personae continue to run unchanged through Phase 1–3. Phase 4's wiring is opt-in per persona via a `uses_authority: true` frontmatter flag; the responder calls the MCP only when the flag is set. Last persona is migrated when all are visibly stable.
- **CON-003**: No frontend changes through Phase 6. Phase 7 (optional) is the only UI work in scope and is gated behind explicit operator sign-off after the backend phases ship.
- **CON-004**: No changes to the eight existing orchestrators (`api/functions/workflows/*.py`) or per-phase graphs (`api/functions/graphs/`). The authority MCP is consumed only by skills (agent context) and personae (HITL closure), both of which already mediate the orchestrator boundary.
- **GUD-001**: The authority MCP wrapper at `api/server/mcp_tools/delegated_authority.py` follows the same Pydantic-schema-+-mock-call pattern as `policy_search`, `employee_history`, and the other ten MCP tools. The MCP-contract-as-swap-in-seam claim from `docs/SCOPE-DELTA.md` applies: identical Pydantic shape, swap the backend later.
- **GUD-002**: The persona registry mirrors the domain registry shape (`api/shared/domains.py`) one-for-one. `Persona` is a frozen dataclass; `PERSONAS: dict[str, Persona]` keyed by `role`; same lookup helper conventions (`get(role)`, `by_archetype(archetype)`, `all_archetypes()`).
- **GUD-003**: The `compose-persona` meta-skill mirrors `compose-domain`'s five-step procedure (brief intake → emit SKILL.md + decision_code → emit registry entry → emit graduate.sh → operator review). It calls the existing `author-persona` sub-skill rather than re-implementing persona-file authoring.
- **PAT-001**: Authority resolution is a pure function. The MCP mock implements it as a deterministic ordered-rule walk over the matrix JSON; first matching rule returns `{approver_role, threshold, escalation_chain, rule_id, basis}`. No randomness, no LLM in the resolution path.
- **PAT-002**: Persona registry entries declare `archetype` (one of `approver`, `subject`, `reviewer`, `delegate`, `notifier`) so the operator UI's future persona library can group sensibly without per-role chrome.
- **PAT-003**: Generated personae carry a `generated_by: compose-persona/v1` provenance line in their SKILL.md frontmatter, so the registry validation test can assert that hand-authored vs. generated personae are distinguishable.

## 2. Implementation Steps

### Implementation Phase 1 — Authority matrix data model + mock MCP server

- GOAL-001: Stand up `mocks/authority-mcp/` (Node, port 4108) backed by `data/synthetic/authority/matrix.json`. The mock answers `resolve_approver` and `check_authority` operations against the matrix. No substrate consumer wired yet — phase ends with the mock returning correct rule-walks for hand-crafted test inputs covering all 8 existing domains.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `data/synthetic/authority/matrix.json` as an ordered array of rule objects with shape `{rule_id: str, action: str, category: str, value_band_gbp: {min, max}, business_unit: str \| "*", geography: str \| "*", requester_role: str \| "*", approver_role: str, escalation_chain: [str, ...], basis: str}`. Seed ≥80 rules covering every action used by the 8 existing domains: `expense_claim_approval`, `travel_preapproval`, `vendor_kyc_signoff`, `contract_renewal_signoff`, `it_access_grant`, `employee_onboarding_access`, `perf_calibration_signoff`, `hire_offer_approval`, `hire_budget_approval`. Include cross-cutting bands (≤£1k, ≤£10k, ≤£50k, ≤£250k, >£250k) and at least 3 business-unit / geography combinations to prove the matrix is multi-dimensional. | | |
| TASK-002 | Create `data/synthetic/authority/README.md` documenting the rule schema, the precedence rule (first match wins), the wildcard semantics (`"*"`), and an example resolution walk-through for each of the 8 existing domains. Do not mention any specific organisation or agency. | | |
| TASK-003 | Scaffold `mocks/authority-mcp/` mirroring the structure of `mocks/concur-mcp/`: `package.json` (express + zod), `server.js` (Express on `process.env.PORT \|\| 4108` with `/health`, `/resolve_approver`, `/check_authority`, `/reload` endpoints), `schemas.js` (zod request/response shapes). The `/reload` endpoint re-reads `matrix.json` from disk for live editing during demos. | | |
| TASK-004 | Implement the resolver in `mocks/authority-mcp/resolver.js` as a pure function `resolve(matrix, request) -> resolution`. Walks the matrix in order; returns the first rule where every non-wildcard field matches and `value` falls in `[value_band_gbp.min, value_band_gbp.max]`. Returns `{matched: false, reason: "no rule matched"}` if exhausted. Adds defensive bounds-checking: matrix entries with malformed bands skip with a warning to stderr. | | |
| TASK-005 | Add `mocks/authority-mcp/` to the root `package.json` `scripts` block: extend the existing `dev:mcp` and `dev:mcp:poc1` scripts (whichever is the canonical "all base mocks" target — confirm by reading the current file) to include `authority-mcp`. Do not add to `dev:mcp:poc2` (it's a base substrate concern, not a hiring-only one). | | |
| TASK-006 | Add `mocks/authority-mcp/test/resolver.test.js` (node:test or vitest, match the convention in `mocks/concur-mcp/`). Cover: (a) exact match wins, (b) wildcard fallback, (c) value-band edge cases (min, max inclusive), (d) no-match behaviour, (e) one canonical resolution per existing domain (8 cases). | | |

### Implementation Phase 2 — `delegated_authority` MCP tool wrapper

- GOAL-002: Add `api/server/mcp_tools/delegated_authority.py` exposing the same two operations as Pydantic-typed tools to agent skills and the persona responder. Tool wrapper follows the existing pattern from `policy_search`, `employee_history`, etc. Backend points at the Phase-1 mock by default; env override allows pointing elsewhere.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create `api/server/mcp_tools/delegated_authority.py` with two Pydantic models: `ApproverResolution { approver_role: str, threshold_gbp: float \| None, escalation_chain: list[str], rule_id: str, basis: str, matched: bool }` and `AuthorityCheck { allowed: bool, reason: str, governing_rule_id: str \| None }`. Two callables `resolve_approver(...)` and `check_authority(...)` that POST to `AUTHORITY_MCP_URL` (default `http://localhost:4108`). Mirror the httpx + retry + timeout pattern from `policy_search.py`. | | |
| TASK-008 | Register both tools in whatever MCP-tool registry surface the substrate uses for agent contexts (audit `api/server/skills/*/SKILL.md` for `allowed-tools:` syntax — likely the registration is implicit by tool name). Add `delegated_authority_resolve_approver` and `delegated_authority_check_authority` to the canonical tool list referenced by `compose-domain`'s YAML schema (`docs/superpowers/skills/compose-domain/SKILL.md`). | | |
| TASK-009 | Add `AUTHORITY_MCP_URL=http://localhost:4108` to `local.settings.json.example` and `.env.example`. Document the variable in `docs/DEVELOPMENT.md` under the MCP table. | | |
| TASK-010 | Add `tests/api/server/mcp_tools/test_delegated_authority.py` with: (a) unit test of the two callables against a stubbed mock (httpx `MockTransport`), (b) integration test (skipped unless `AUTHORITY_MCP_LIVE=1`) that hits the real Node mock and asserts the 8 canonical resolutions from TASK-006. | | |
| TASK-011 | Add a Makefile target `make mcp-authority` that runs the Node mock standalone for ad-hoc inspection: `cd mocks/authority-mcp && PORT=4108 node server.js`. Confirm `make up` brings the mock up via the existing concurrently chain (TASK-005 wired it into `dev:mcp`). | | |

### Implementation Phase 3 — Wire authority MCP into existing skills (additive only)

- GOAL-003: Add `delegated_authority_resolve_approver` to the `allowed-tools` of skills that today produce a HITL routing decision (where a persona will then re-approve), and have those skills call it as a sanity-check step. Phase is purely additive; no existing decision logic is removed yet. The skill output now carries a `resolved_approver: ApproverResolution` block alongside whatever it produced before. Personae continue to inline thresholds.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Audit existing skills for which ones produce a HITL routing/threshold decision: candidates by inspection are `escalation-advisor` (POC1), `budget-checker` (POC2), `fleet-travel-preapproval-policy-fit-checker`, `fleet-vendor-kyc-kyc-diligence-checker`, `fleet-it-access-request-access-risk-assessor`, `fleet-contract-renewal-renewal-terms-drafter`, `fleet-employee-onboarding-access-drafter`, `fleet-perf-review-calibration-drafter`. Confirm the list by reading each SKILL.md; produce the final list as a comment block at the top of `api/server/mcp_tools/delegated_authority.py`. | | |
| TASK-013 | For each skill in the audit list: extend its `allowed-tools:` frontmatter with `delegated_authority_resolve_approver`, and amend the prompt body's "process" section with a step `Call delegated_authority_resolve_approver(action=..., value=..., category=..., requester_role=..., business_unit=..., geography=...) and surface the result as resolved_approver in your output JSON.` Map each skill's domain to the right `action` constant (matching matrix.json). | | |
| TASK-014 | Add `tests/api/server/skills/test_authority_invocation.py` that runs each modified skill against a canned input and asserts `resolved_approver` is present in the structured output, with `matched=True` and `approver_role` matching the persona registered for that domain's HITL gate (read from the domain registry). | | |

### Implementation Phase 4 — Persona registry + threshold migration

- GOAL-004: Introduce `api/shared/personas.py` mirroring `api/shared/domains.py` shape. Refactor `persona_responder._load_personae` to populate `PERSONAS` from the registry (sourced from disk via SKILL.md frontmatter) and validate every persona referenced by the domain registry has a corresponding `Persona` entry. Migrate the 6 personae that today inline numeric thresholds to call `delegated_authority_check_authority` from their `decision_policy`. After this phase, no numeric threshold value lives in any persona file.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Create `api/shared/personas.py` with `Persona` dataclass and `PERSONAS: dict[str, Persona]` registry. `Persona` fields: `role: str`, `archetype: Literal["approver","subject","reviewer","delegate","notifier"]`, `scope_function: str`, `scope_business_unit: str = "*"`, `scope_geography: str = "*"`, `default_authority_band: str \| None`, `workflow_label: str`, `external_event_default: str \| None`, `uses_authority_mcp: bool = False`. Helpers: `get(role)`, `by_archetype(archetype)`, `by_function(function)`, `all_archetypes()`. Populate entries for all 16 existing personae by reading their SKILL.md frontmatter at module load (lazy-cached). | | |
| TASK-016 | Extend persona SKILL.md frontmatter schema to include `archetype`, `scope_function`, `scope_business_unit`, `scope_geography`, `uses_authority_mcp`. Backfill all 16 existing personae with reasonable defaults (e.g. `finance_bp` → archetype: approver, scope_function: finance). Hand-author this pass; do not generate. Document the schema additions in `api/server/personae/README.md` (create if absent). | | |
| TASK-017 | Refactor `api/server/services/persona_responder.py` `_load_personae` (or equivalent attach-time loader) to (a) parse the new frontmatter fields, (b) populate `PERSONAS` in `api/shared/personas.py`, (c) expose `_DECISION_BUILTINS` an extra callable `authority_check(action, value, category, requester_role, business_unit, geography) -> dict` that wraps `delegated_authority.check_authority` synchronously (the sandbox is sync; thread it via `asyncio.run_coroutine_threadsafe` against the responder's loop, OR resolve the call upstream and pass the result into `context["authority"]` — pick the cleaner option after reading the responder; document the choice in the module docstring). | | |
| TASK-018 | Migrate the 6 threshold-inlining personae (audit by `grep -nE '> *[0-9]{2,}|< *[0-9]{2,}|>= *[0-9]{2,}|<= *[0-9]{2,}' api/server/personae/*/SKILL.md` for the canonical list) to set `uses_authority_mcp: true` and rewrite their `decision_policy` to consult `context["authority"]` (or call `authority_check` from the sandbox per TASK-017). Each persona's behaviour must be unchanged: same approve/reject/escalate verdict on the same inputs. Add per-persona regression tests under `tests/api/server/personae/test_<role>_authority_parity.py`. | | |
| TASK-019 | Wire skills (Phase 3) and personae together: skills now emit `resolved_approver` into the suspended-event `context.authority` block; personae read `context.authority` rather than re-deriving. Confirm by inspecting one suspended event per migrated persona via `pytest -xvs tests/api/server/personae/`. | | |
| TASK-020 | Add `tests/api/shared/test_personas_registry.py` asserting: (a) every persona role declared in any `Domain.hitl_gates` has a `Persona` entry, (b) every `Persona` has a SKILL.md file under `api/server/personae/<role>/SKILL.md`, (c) `archetype` values are within the literal set, (d) `uses_authority_mcp=True` personae round-trip a sample `context.authority` block through the responder sandbox. | | |
| TASK-021 | Update `api/server/services/blueprint_inventory.py` and `api/server/services/fleet_manager_service.py` to read persona metadata from `api.shared.personas.PERSONAS` instead of re-parsing SKILL.md or hardcoded literals. The FM skill text composer (extended in `feature-fleet-domain-substrate-1.md` Phase 4) now also enumerates personae grouped by archetype + function. | | |

### Implementation Phase 5 — `compose-persona` meta-skill

- GOAL-005: Ship a sandbox-only design-time meta-skill that turns a persona brief (YAML or free-text dialogue) into a complete persona artefact set: SKILL.md (frontmatter + decision_policy + decision_code), persona registry entry, and `graduate.sh` script that mechanically wires the persona into `api/server/personae/` and `api/shared/personas.py`. Mirrors `compose-domain` end-to-end. Output is strictly under `tools/scratch/compose-persona/<run-id>/`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | Create `docs/superpowers/skills/compose-persona/SKILL.md` mirroring the shape of `docs/superpowers/skills/compose-domain/SKILL.md`. Five steps: (1) brief intake — YAML or free-text via existing `brainstorming` skill, (2) emit SKILL.md frontmatter + body via `author-persona` sub-skill, (3) emit registry entry as a Python snippet pasteable into `api/shared/personas.py`, (4) emit `graduate.sh` that copies SKILL.md into place + applies the registry diff via a marker comment, (5) operator review + manual graduate. Same `forbidden-runtime: true` flag and sandbox enforcement as `compose-domain`. | | |
| TASK-023 | Define the persona brief YAML schema in the SKILL.md, version v1: `persona.role` (snake_case), `persona.archetype`, `persona.scope_function`, `persona.scope_business_unit`, `persona.scope_geography`, `persona.workflow_label`, `persona.external_event` (optional), `persona.uses_authority_mcp` (bool), `persona.decision_policy_paragraph` (one paragraph human-readable rule), `persona.decision_inputs` (list of `context` keys the policy reads), `persona.decision_authority_action` (action constant from `data/synthetic/authority/matrix.json` if `uses_authority_mcp` is true). | | |
| TASK-024 | The `author-persona` sub-skill (already exists at `docs/superpowers/skills/author-persona/`) likely needs a v2 to emit the new frontmatter shape (Phase 4 fields + provenance). Audit it; if minor, extend in place; if substantial, version-bump per the existing `author-runtime-skill` pattern. Document the version bump in the sub-skill's SKILL.md changelog. | | |
| TASK-025 | Add a `tools/scratch/compose-persona/` directory README documenting the sandbox boundary and the graduate workflow, mirroring `tools/scratch/compose-domain/README.md` if present (create if absent). | | |
| TASK-026 | Dry-run the meta-skill end-to-end against a single brief (`controller` persona — see Phase 6) to validate: (a) sandbox output paths are correct, (b) generated SKILL.md compiles through the responder sandbox, (c) generated registry entry passes `tests/api/shared/test_personas_registry.py`. Capture the dry-run transcript under `tools/scratch/compose-persona/run-001/transcript.md`. | | |

### Implementation Phase 6 — Bulk persona graduation (the "breathing" beat)

- GOAL-006: Use `compose-persona` to author and graduate ≥12 new personae across functions for which we don't yet have domains. They sit in the registry as available cast — the operator UI's persona library (Phase 7) and the blueprint microsite render them as visibly-present roles. This phase proves the curve: the same primitive that took artisan effort once produces a dozen personae in hours.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-027 | Author 4 finance personae via `compose-persona`: `controller` (approver, finance), `fpa_analyst` (reviewer, finance), `ap_clerk` (subject, finance), `treasurer` (approver, finance, large value bands). Each ships with brief YAML under `tools/scratch/compose-persona/run-finance-batch/`, generated SKILL.md graduated to `api/server/personae/<role>/SKILL.md`, registry entry merged. None are added to `PERSONA_AUTO_CLOSE`. | | |
| TASK-028 | Author 3 procurement personae: `category_manager` (approver), `sourcing_lead` (reviewer), `cpo` (approver, top band). | | |
| TASK-029 | Author 3 legal personae: `contracts_counsel` (reviewer, archetype: reviewer), `dpo` (approver, scope_function: legal_privacy), `gc` (approver, top band). | | |
| TASK-030 | Author 2 commercial personae: `account_director` (approver, scope_function: commercial), `project_manager` (subject + delegate). | | |
| TASK-031 | Author 2 cross-cutting personae: `change_manager` (approver, scope_function: it), `comp_ben_analyst` (reviewer, scope_function: hr). | | |
| TASK-032 | After all 12 graduate, run `pytest tests/api/shared/test_personas_registry.py -v` and confirm 28+ personae pass the validation. Run the autonomous demo loop for 10 minutes and confirm zero regressions in the existing 8-domain mixed stream (new personae have no domain references yet, so they should be inert at runtime). | | |
| TASK-033 | Append a `## Persona library` section to `docs/blueprint.md` enumerating the 28+ personae grouped by archetype and function, with a sentence each describing the operational role. No org-specific copy. | | |

### Implementation Phase 7 — Optional operator UI surface

- GOAL-007: (Optional, gated behind explicit operator sign-off after Phase 6 lands.) Surface the authority matrix and persona library in the existing operator surfaces. Read-only, additive; no changes to existing pages' load/runtime behaviour.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-034 | Add a FastAPI route `GET /api/authority/resolve` that proxies to the authority MCP and returns `ApproverResolution` for query parameters `action`, `value`, `category`, `business_unit`, `geography`, `requester_role`. Same shape as the MCP tool. Add a corresponding test under `tests/api/server/test_authority_route.py`. | | |
| TASK-035 | Add a "Authority resolution" card to `WorkflowDetail.tsx` (Control Plane) that calls `/api/authority/resolve` with the workflow's HITL-gate context and displays `approver_role`, `threshold_gbp`, `rule_id`, `basis`. Renders only for workflows currently sitting at a HITL gate. | | |
| TASK-036 | Add a `GET /api/personas` route returning the registry as JSON. Add a `Personas` page to the blueprint microsite (`web/blueprint/src/`) rendering the cast grouped by archetype. Mirror the visual language of the existing domain mind-map. | | |
| TASK-037 | Add a `Authority matrix` page to the blueprint microsite rendering the full matrix as a sortable, filterable table (action / value-band / approver / scope). Read-only. | | |

## 3. Alternatives

- **ALT-001**: Inline threshold registry inside `api/shared/personas.py` instead of a separate MCP. Rejected: the MCP-as-seam claim from `docs/SCOPE-DELTA.md` is load-bearing; the engagement story is "swap the mock for Foundry IQ over the customer's authority matrix" — that requires a tool boundary, not a Python import.
- **ALT-002**: Generate personae from a YAML config file at runtime instead of a meta-skill. Rejected: the "agents compose new agents" claim from `docs/blueprint.md` is the whole pitch; meta-skills are how that's literally true. A config loader doesn't carry the same story.
- **ALT-003**: Make Phase 3 (skill wiring) destructive — remove existing routing logic, force authority MCP as the only source. Rejected for risk: phased migration with explicit `uses_authority_mcp` flag (Phase 4) lets us roll back per-persona if a regression surfaces.
- **ALT-004**: Add a `delegated_authority` skill (agentic) instead of a deterministic MCP. Rejected: authority resolution must be deterministic, auditable, and fast; an LLM in this path is a regression on every axis.

## 4. Dependencies

- **DEP-001**: Existing domain registry at `api/shared/domains.py` (shipped in `feature-fleet-domain-substrate-1.md` Phase 1). Required by Phase 4 (persona registry consumes domain HITL-gate persona references for validation) and Phase 5 (compose-persona's brief schema cross-references `Domain.workflow_type`).
- **DEP-002**: Persona responder sandbox (`_DECISION_BUILTINS`) in `api/server/services/persona_responder.py`. Required by Phase 4 (TASK-017) for threading the authority MCP into `decision_policy` execution.
- **DEP-003**: `compose-domain` v3 + `author-persona` sub-skill at `docs/superpowers/skills/`. Required by Phase 5 as the structural template and direct sub-skill invocation.
- **DEP-004**: Existing MCP-mock harness pattern in `mocks/concur-mcp/` and friends. Required by Phase 1 as the structural template for `mocks/authority-mcp/`.
- **DEP-005**: Per-domain phase ribbon + per-domain blueprint inventory composition (shipped in `feature-fleet-domain-substrate-1.md` Phases 4 + 6). Required by Phase 7 (TASK-035, TASK-036) for the UI cards to read registry-sourced metadata cleanly.

## 5. Files

- **FILE-001**: `data/synthetic/authority/matrix.json` — new, ≥80 rows, ordered. Phase 1.
- **FILE-002**: `data/synthetic/authority/README.md` — new, schema docs. Phase 1.
- **FILE-003**: `mocks/authority-mcp/{package.json,server.js,resolver.js,schemas.js,test/resolver.test.js}` — new mock. Phase 1.
- **FILE-004**: `api/server/mcp_tools/delegated_authority.py` — new MCP tool wrapper. Phase 2.
- **FILE-005**: `local.settings.json.example`, `.env.example` — `AUTHORITY_MCP_URL` env var. Phase 2.
- **FILE-006**: `api/server/skills/{escalation-advisor,budget-checker,fleet-travel-preapproval-policy-fit-checker,fleet-vendor-kyc-kyc-diligence-checker,fleet-it-access-request-access-risk-assessor,fleet-contract-renewal-renewal-terms-drafter,fleet-employee-onboarding-access-drafter,fleet-perf-review-calibration-drafter}/SKILL.md` — frontmatter + body amendment. Phase 3.
- **FILE-007**: `api/shared/personas.py` — new persona registry. Phase 4.
- **FILE-008**: `api/server/personae/<role>/SKILL.md` × 16 — frontmatter expansion (Phase 4 TASK-016) + 6 of them rewritten to call authority MCP (Phase 4 TASK-018).
- **FILE-009**: `api/server/personae/README.md` — schema docs. Phase 4.
- **FILE-010**: `api/server/services/persona_responder.py` — extended sandbox + registry population. Phase 4.
- **FILE-011**: `api/server/services/blueprint_inventory.py`, `api/server/services/fleet_manager_service.py` — read persona metadata from new registry. Phase 4 TASK-021.
- **FILE-012**: `docs/superpowers/skills/compose-persona/SKILL.md` — new meta-skill. Phase 5.
- **FILE-013**: `docs/superpowers/skills/author-persona/SKILL.md` — possibly v2 bump. Phase 5 TASK-024.
- **FILE-014**: `tools/scratch/compose-persona/{README.md,run-001/transcript.md}` — new sandbox. Phase 5.
- **FILE-015**: `api/server/personae/<role>/SKILL.md` × ≥12 — graduated personae. Phase 6.
- **FILE-016**: `docs/blueprint.md` — appended persona library section. Phase 6 TASK-033.
- **FILE-017**: `api/server/routes/authority.py`, `api/server/routes/personas.py` — new read-only routes. Phase 7.
- **FILE-018**: `web/client/components/apex/AuthorityCard.tsx`, `web/blueprint/src/{routes,components}/Personas{Page,List}.tsx`, `web/blueprint/src/{routes,components}/AuthorityMatrix{Page,Table}.tsx` — new UI. Phase 7.
- **FILE-019**: `tests/api/shared/test_personas_registry.py`, `tests/api/server/skills/test_authority_invocation.py`, `tests/api/server/personae/test_<role>_authority_parity.py`, `tests/api/server/mcp_tools/test_delegated_authority.py`, `tests/api/server/test_authority_route.py` — new test files across phases.

## 6. Testing

- **TEST-001**: Phase 1 — `pnpm --filter authority-mcp test` (or `node --test mocks/authority-mcp/test/resolver.test.js` matching the existing convention) passes the 8 canonical resolutions + edge cases.
- **TEST-002**: Phase 2 — `pytest tests/api/server/mcp_tools/test_delegated_authority.py` passes; `AUTHORITY_MCP_LIVE=1 pytest -m live` confirms wire-level integration against the running mock.
- **TEST-003**: Phase 3 — `pytest tests/api/server/skills/test_authority_invocation.py` confirms `resolved_approver` lands in every audited skill's structured output.
- **TEST-004**: Phase 4 — `pytest tests/api/shared/test_personas_registry.py` and `pytest tests/api/server/personae/` pass; the 6 migrated personae produce the same approve/reject/escalate verdicts on the existing per-persona regression fixtures.
- **TEST-005**: Phase 4 substrate parity — `./scripts/profile-autonomous.sh` runs for 10 minutes producing the same mixed stream of completed / in-flight / auto-decided / escalated workflows across all 8 domains as before the migration. Compare against a baseline JSONL captured pre-migration.
- **TEST-006**: Phase 5 — Dry-run transcript at `tools/scratch/compose-persona/run-001/transcript.md` shows clean end-to-end execution for the `controller` persona; the generated SKILL.md compiles in the responder sandbox without errors.
- **TEST-007**: Phase 6 — After all ≥12 graduations, `pytest tests/api/shared/test_personas_registry.py -v` reports 28+ personae passing all assertions; the autonomous loop again produces the baseline 8-domain mixed stream with zero new errors.
- **TEST-008**: Phase 7 — Existing Playwright e2e suites under `tests/e2e/` continue to pass; new smoke tests cover the Authority card render and the Personas page render.

## 7. Risks & Assumptions

- **RISK-001**: The persona responder sandbox is synchronous; calling an httpx-based MCP from inside `decision_policy` execution may require careful threading. Mitigation: Phase 4 TASK-017 explicitly considers the alternative of resolving authority upstream in the skill (Phase 3) and passing the result into `context["authority"]`, avoiding any sandbox/async complexity. Recommend that path unless there's a strong reason for sandbox-side calls.
- **RISK-002**: Authority matrix data is invented for the demo and may not reflect realistic enterprise authority schemes. Mitigation: matrix shape is correct (multi-dimensional, ordered, wildcard-aware); the data is swappable and explicitly documented as synthetic in `data/synthetic/authority/README.md`. Engagement-POC will replace with the customer's real matrix via Foundry IQ.
- **RISK-003**: ≥12 net-new personae with no domains may feel like padding to a critical reviewer. Mitigation: Phase 6 TASK-033's blueprint copy frames them explicitly as "available cast for the next dozen domains" — the breathing claim is exactly that, not pretending they're already in production.
- **RISK-004**: Generated personae from `compose-persona` could carry subtle decision-policy bugs that the sandbox catches at runtime but not at compile time. Mitigation: every graduated persona ships with a regression test (TASK-018 pattern) seeded by `compose-persona` itself; the dry-run in TASK-026 establishes the pattern.
- **ASSUMPTION-001**: The MCP-tool registration mechanism is implicit by tool name (no central registry to edit). To be confirmed at TASK-008 by reading one or two existing skills' `allowed-tools:` declarations.
- **ASSUMPTION-002**: `compose-domain` v3's YAML schema can absorb the two new authority tools as additional allowed-tool defaults without a v4 bump. To be confirmed at TASK-008.
- **ASSUMPTION-003**: All 8 existing domains' HITL gates can be expressed as `(action, value, category)` triples against a single shared matrix. The performance-review and onboarding gates are the highest-risk fits because they're not value-band shaped; the matrix schema's wildcard semantics on `value_band_gbp.min/max` cover this (set both to `null` for non-monetary actions). To be confirmed at TASK-001.

## 8. Related Specifications / Further Reading

- `api/shared/domains.py` — sister registry whose shape this plan mirrors.
- `plan/feature-fleet-domain-substrate-1.md` — the substrate-parity plan that landed the domain registry; this plan picks up where it stopped.
- `plan/feature-foundry-credibility-friday-1.md` — adjacent credibility lift; same shape of phased work.
- `docs/superpowers/skills/compose-domain/SKILL.md` — structural template for `compose-persona`.
- `docs/superpowers/skills/author-persona/SKILL.md` — direct sub-skill, possibly v2 bumped here.
- `docs/SCOPE-DELTA.md` — articulates the MCP-as-swap-in-seam contract this plan is built on.
- `docs/blueprint.md` — the pitch this plan extends; Phase 6 TASK-033 appends to it.
- `api/server/services/persona_responder.py` — sandbox + responder; touched in Phase 4.
- `api/server/mcp_tools/policy_search.py` and `api/server/mcp_tools/employee_history.py` — structural templates for the new MCP tool wrapper in Phase 2.
