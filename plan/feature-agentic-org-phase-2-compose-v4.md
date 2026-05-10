---
goal: Restructure `compose-domain` from v3 (parallel sub-skill dispatch over one prompt) into v4 — a sequential enrichment pipeline that grows a shared YAML brief through five new authoring sub-skills (skeleton → entity-projection → decision-mapping → function-membership → ambient-trigger) before invoking the existing v3 generators, so every newly graduated synthetic-journey domain ships with a per-domain entity projection, per-decision Cypher, declared function ownership, and an optional ambient hook — all by construction. Includes backfill of the eleven `fleet-*` domains + `creative-campaign` brief files so they regenerate the same artefacts without orchestrator changes.
version: 1.0
date_created: 2026-05-08
last_updated: 2026-05-08
owner: Zava Control Plane — substrate
status: 'Shipped'
tags: [feature, design-time, agentic-org, compose-domain, skill]
---

# Introduction

![Status: Not Started](https://img.shields.io/badge/status-Not%20Started-lightgrey)

Phase 2 of the four-phase Agentic Org Blueprint rollout (see
[docs/agentic-org-blueprint.md §9](../docs/agentic-org-blueprint.md)). The
spec section that drives this plan is §4 *"How a domain plugs in —
`compose-domain` v4"*: today's v3 meta-skill fans out four parallel
authoring sub-skills against one prompt and stops at the orchestrator +
graphs + personae + MCP stubs surface. It does not know about the entity
graph that Phase 1 builds, nor the `FUNCTIONS` registry that Phase 3
introduces, nor decision precedent that Phase 4 wires into personae.

v4 reshapes the meta-skill into a **sequential enrichment pipeline**: a
shared YAML brief (`brief.yaml v0..v5`) flows through five new authoring
sub-skills — `author-domain-skeleton` → `author-entity-projection` →
`author-decision-mapping` → `author-function-membership` →
`author-ambient-trigger` (optional) — each enriching one section,
validating it, and handing off. The existing v3 generators
(`author-runtime-skill`, `author-persona`, `author-mcp-tool`,
`author-durable-domain`) run last, unchanged, and are joined by two new
codegens that emit `api/server/services/entity_projections/<domain>.py`
and `api/server/services/precedent_queries/<domain>_<phase>.cypher`.
Failure is fail-fast: a validation miss at any pass stops the pipeline
with a structured report — no recovery guess.

Backfill is the second half of the work: the eleven `fleet-*` domains
plus `creative-campaign` (twelve briefs total under
`docs/superpowers/specs/<domain>-brief.yaml`) get the new
`entities:` / `decisions:` / `function:` / `ambient:` blocks added in
place, then compose-domain v4 runs in *re-projection-only* mode against
each. Orchestrators stay byte-equal; only the new artefacts land. POC1
(`expense-claim`) and POC2 (`hiring`) are excluded per locked decision
#8. After Phase 2, adding a thirteenth synthetic-journey domain produces
an entity-aware, function-aware, decision-recording domain end-to-end
with no manual fixups.

## 1. Requirements & Constraints

- **REQ-001**: Restructure `docs/superpowers/skills/compose-domain/SKILL.md` into a five-step *sequential* enrichment pipeline followed by the existing v3 generators: `author-domain-skeleton` → `author-entity-projection` → `author-decision-mapping` → `author-function-membership` → `author-ambient-trigger` (optional) → existing generators (`author-runtime-skill`, `author-persona`, `author-mcp-tool`, `author-durable-domain`). Each enrichment sub-skill reads the working brief, writes exactly one new top-level section, runs structural validation, and hands the enriched brief to the next.
- **REQ-002**: The `entities:` block on the brief must compile to one Python file per domain at `api/server/services/entity_projections/<workflow_type_with_underscores>.py` (e.g. `ap_invoice.py`, `purchase_card.py` — hyphens replaced with underscores so the module is importable) exposing `def project(workflow) -> list[EntityWrite | RelWrite | DecisionWrite]` (bare name `project`, not `project_<workflow_type>` — Phase 1 PAT-005 locks the structural invariant of "exactly twelve `def project(workflow:` definitions"). The `EntityWrite` / `RelWrite` / `DecisionWrite` types are the ones Phase 1 publishes from `api/server/services/entity_graph.py`.
- **REQ-003**: The `decisions:` block must compile to one Cypher file per HITL phase at `api/server/services/precedent_queries/<workflow_type>_<phase_name>.cypher`. The Cypher must MERGE a `Decision` node keyed on `(workflow_id, phase, persona_role)` and CREATE a `DECIDED_ON` edge to each entity the phase decided on, matching the ULID dedupe contract from blueprint §10 decision #4.
- **REQ-004**: The `function:` field must validate against the `FUNCTIONS` registry from Phase 3 (`api/shared/functions.py`); `graduate.sh` patches `FUNCTIONS["<fn>"].owns_domains` idempotently. If Phase 3 is not yet merged, the validator runs against a `FUNCTIONS_PLACEHOLDER` constant inside `docs/superpowers/skills/compose-domain/sub-skills/author-function-membership/validator.py` so Phase 2 ships standalone.
- **REQ-005**: The optional `ambient:` block compiles to an `AmbientAgent(...)` entry appended to `api/server/services/ambient_agents/<function>.py`. Trigger shape is the discriminated union from blueprint §2 / decision #5: `BusTrigger`, `CypherTrigger`, or `CadenceTrigger`. If Phase 3's `AmbientAgent` primitive is not yet merged, the file is written but the registration call is gated behind `if hasattr(api.server.services.ambient_agents, "AmbientAgent"):`.
- **REQ-006**: Sandbox layout is unchanged from v3: every wholesale build lands under `tools/scratch/compose-domain/<RUN_ID>/` with the mirrored real-tree layout. `RUN_ID = <YYYYMMDD-HHMMSS>-<domain.name>`. Re-running the meta-skill against an already-graduated domain in `--re-projection-only` mode writes only the projection + decision + function + ambient artefacts and skips the orchestrator/graphs/personae/MCP layers.
- **REQ-007**: Backfill all twelve synthetic-journey briefs (`fleet-ap-invoice`, `fleet-contract-renewal`, `fleet-contract-review`, `fleet-employee-onboarding`, `fleet-it-access-request`, `fleet-perf-review`, `fleet-privacy-dpia`, `fleet-purchase-order`, `fleet-travel-preapproval`, `fleet-treasury-fx`, `fleet-vendor-kyc`, `creative-campaign`) so re-running compose-domain v4 in re-projection-only mode regenerates every projection + decision + function + ambient artefact without touching the orchestrators in `api/functions/workflows/`.
- **REQ-008**: Smoke test — author a thirteenth brief `fleet-purchase-card` end-to-end through v4 (no shortcuts, no manual fixups) and verify the resulting sandbox graduates cleanly, the projection function appears as `def project(workflow)` in `api/server/services/entity_projections/purchase_card.py` (underscored module name), the four Cypher files appear in `api/server/services/precedent_queries/`, and `FUNCTIONS["finance"].owns_domains` lists `purchase-card`.
- **SEC-001**: Enrichment sub-skills run in the design-time sandbox only; no production code path imports them. The runtime guards from v3 stay (`forbidden-runtime: true` frontmatter; sandbox-only writes outside `docs/superpowers/specs/`). Brief files are checked into git per-fork (Zava is canonical here per locked decision #6).
- **SEC-002**: Persona `decision_code` and projection codegen continue to use the `_DECISION_BUILTINS` whitelist from `api/server/services/persona_responder.py`. Generated projection functions may import only from `api.server.services.entity_graph` and `api.shared.types`; the codegen's import allow-list is enforced by the `author-entity-projection` validator.
- **CON-001**: Do **not** modify any orchestrator under `api/functions/workflows/fleet_*.py` or `api/functions/workflows/creative_campaign.py` during backfill. The contract those files emit (workflow_type stamping + persona/external_event/context on suspended payloads) is the input to Phase 2 and stays byte-equal pre/post.
- **CON-002**: Do **not** author `entities:`, `decisions:`, `function:`, or `ambient:` blocks for `expense-claim` or `hiring`. They are deprioritised per blueprint §11 and locked decision #8; their `function` field is set to the placeholder `"legacy"` by Phase 3, not by this plan.
- **CON-003**: Preserve every existing v3 generator output (orchestrator, MAF graphs, personae, MCP stubs, validators) byte-for-byte where the input brief's `domain` / `phases` / `personae` / `external_systems` blocks are unchanged. Determinism check from `compose-domain/CHECKLIST.md §6.1` must continue to pass.
- **CON-004**: Do not couple compose-domain v4 to a specific `FUNCTIONS` catalogue shape — that is Phase 3's job. The `author-function-membership` sub-skill validates against either the live registry (when Phase 3 has merged) or the `FUNCTIONS_PLACEHOLDER` constant; switching between the two is a one-line edit to the validator's import block.
- **GUD-001**: Each enrichment sub-skill is ≤ ~100 lines (SKILL.md + validator.py combined excluding canonical-example references); each writes exactly one new section to the brief; each runs structural validation before handoff. Brief storage is one growing YAML document at `docs/superpowers/specs/<domain>-brief.yaml` — versions v0..v5 are conceptual passes, not separate files.
- **GUD-002**: Sandbox path for wholesale builds: `tools/scratch/compose-domain/<RUN_ID>/`. Sandbox path for re-projection-only runs: `tools/scratch/compose-domain/<RUN_ID>-reproj/` with a `--re-projection-only` flag set in `REPORT.md`. `graduate.sh` is idempotent and mechanical; re-projection-only graduate.sh patches only the four new file kinds.
- **GUD-003**: Validation cascade: `author-domain-skeleton` validates phase + persona shape (already covered by v3 brief schema); `author-entity-projection` validates entity refs against the Phase 1 Kuzu schema in `api/server/services/entity_graph.py:_SCHEMA`; `author-decision-mapping` validates that every named phase exists in the brief skeleton and is `kind: hitl`; `author-function-membership` validates against `FUNCTIONS` (or `FUNCTIONS_PLACEHOLDER`); `author-ambient-trigger` validates the discriminated trigger shape and that the named function exists.
- **PAT-001**: An enrichment sub-skill = one `SKILL.md` plus one tiny Python validator co-located at `docs/superpowers/skills/compose-domain/sub-skills/<sub-skill-name>/SKILL.md` and `.../validator.py`. The meta-skill orchestrates the sequence, stops at the first validation failure, and prints the failure structured (skill name, brief path, validator error, suggested fix).
- **PAT-002**: The brief schema lives at `docs/superpowers/skills/compose-domain/brief.schema.yaml` (NEW) and is the canonical reference both sub-skills and the v4 SKILL.md cite. Schema validation runs against `pyyaml` + `jsonschema` (already in `pyproject.toml`).
- **PAT-003**: The two new codegens (`projection_codegen.py` and `cypher_codegen.py`) live under `docs/superpowers/skills/compose-domain/sub-skills/author-entity-projection/codegen.py` and `.../author-decision-mapping/codegen.py` respectively. Each is a pure function `(brief: dict) -> str` returning the file body; the meta-skill writes the file. Pure-function shape mirrors the existing template-rendering style in `docs/superpowers/skills/compose-domain/templates/`.

## 2. Implementation Steps

### Implementation Phase 1 — Brief schema v4 + sandbox layout

- GOAL-001: Codify the v4 brief schema at `docs/superpowers/skills/compose-domain/brief.schema.yaml` covering all five new top-level sections (`entities`, `decisions`, `function`, `ambient`) on top of the v3 schema (`domain`, `phases`, `personae`, `external_systems`). Define the `--re-projection-only` sandbox path convention. Land the meta-skill scaffolding so subsequent phases plug in.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `docs/superpowers/skills/compose-domain/brief.schema.yaml` as a JSON-Schema YAML document covering the v3 sections (`domain`, `phases`, `personae`, `external_systems`) plus the four v4 sections: `entities` (list of `{kind, ref_field, attributes}` where `kind ∈ {Person, Organisation, Asset, Money, Decision, Place, Period}`), `decisions` (list of `{phase, decided_on_entities, attributes_from_context}`), `function` (single `string`, must match a key in `FUNCTIONS`), `ambient` (optional `{name, trigger: {kind: bus|cypher|cadence, …}, reasoning_skill?, spawnable_workflow_types}`). | | |
| TASK-002 | Add `tests/docs/superpowers/test_brief_schema.py` (NEW) asserting: (a) the v3 reference brief `docs/superpowers/specs/fleet-vendor-kyc-brief.yaml` validates against the schema with the v4 sections absent (back-compat), (b) a synthetic full v4 brief validates clean, (c) every malformed example in the test fixture fails with a JSON-Schema error pointing at the bad path. | | |
| TASK-003 | Restructure `docs/superpowers/skills/compose-domain/SKILL.md` "five steps" section into the v4 pipeline. Rename "five steps" → "the v4 pipeline" and renumber: Step 1 = Brief intake (unchanged); Step 2 = Sequential enrichment (NEW — invokes the five sub-skills below in order); Step 3 = Inventory and isomorphism (unchanged); Step 4 = Generate into sandbox (existing v3 generators, called after enrichment); Step 5 = Self-check; Step 6 = Determinism; Step 7 = Recorder verification. Insert the v4 Mermaid pipeline diagram from blueprint §4 lines 493-512. | | |
| TASK-004 | Add a `--re-projection-only` flag handling section to the v4 SKILL.md: when set, Step 1 is skipped (brief must already exist), Step 2 runs only `author-entity-projection`, `author-decision-mapping`, `author-function-membership`, `author-ambient-trigger`, Step 4 invokes only the new codegens (no orchestrator/graphs/personae/MCP), and the sandbox path becomes `tools/scratch/compose-domain/<RUN_ID>-reproj/`. | | |
| TASK-005 | Add `compose-domain/CHECKLIST.md` v4 sections: §8 Entity projection (`<run-id>/api/server/services/entity_projections/<workflow_type_with_underscores>.py` exists; importable; bare `def project(workflow)` callable). §9 Decision mapping (one `.cypher` per HITL phase; MERGE keyed on `(workflow_id, phase, persona_role)`). §10 Function membership (graduate.sh patches `owns_domains`). §11 Ambient (optional; if `ambient:` block present, file appended idempotently). | | |
| TASK-006 | Document the sub-skill orchestration contract in `docs/superpowers/skills/compose-domain/SKILL.md` Step 2: the meta-skill loads the brief, calls each sub-skill with structured inputs `{brief_path, brief_dict, write_section_name}`, blocks on the sub-skill's validator, and aborts on first failure with a structured report (skill name, validator error, brief path). | | |

### Implementation Phase 2 — `author-domain-skeleton` sub-skill

- GOAL-002: Extract the v3 brief-intake/structuring behaviour (Step 1 today) into a discrete sub-skill that owns just the `domain` / `phases` / `personae` / `external_systems` sections of the brief. This isolates the "shape the workflow" decision from the four enrichment passes that follow.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-domain-skeleton/SKILL.md`: tightly scoped prompt that takes either a free-text idea or an existing skeleton and emits the four v3 brief sections (`domain`, `phases`, `personae`, `external_systems`). Hands off to `superpowers:brainstorming` for the conversational portion (matching today's Step 1 behaviour). | | |
| TASK-008 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-domain-skeleton/validator.py`: a Python function `validate_skeleton(brief: dict) -> None` raising `SchemaError` with structured detail. Validates: `domain.name` starts with `fleet-`, every persona referenced by a HITL phase exists in `personae`, every persona has both `decision_policy` (prose) and `decision_code` (Python) (the v3 contract from `compose-domain/CHECKLIST.md §2.5`), at least one phase is `kind: agent`, at least one phase is `kind: hitl`. | | |
| TASK-009 | Add `tests/docs/superpowers/skills/compose_domain/sub_skills/test_author_domain_skeleton.py` (NEW) with a brief→skeleton round-trip: feed the validator a stripped-down synthetic skeleton input, assert it validates clean; mutate one field at a time (drop persona, missing decision_code, no HITL phase) and assert each failure mode raises `SchemaError` with the expected `path` field. | | |

### Implementation Phase 3 — `author-entity-projection` sub-skill + projection codegen

- GOAL-003: Add the `entities:` block to the brief schema and emit a per-domain projection function at `api/server/services/entity_projections/<workflow_type_with_underscores>.py` that the Phase 1 `EntityReflector` can call. Validates entity kinds and ref fields against the Phase 1 Kuzu schema.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-entity-projection/SKILL.md`: prompt that reads `brief.domain`, `brief.phases`, and the workflow's `payload` shape, then emits the `entities:` block. Each entity entry declares `kind` (one of the seven Phase 1 node tables), `ref_field` (the path inside `workflow.payload` that holds the entity id), `attributes` (a dict mapping Kuzu column → payload path), and `relations` (a list of `{kind, target_ref}` declarations matching Phase 1 REL TABLE definitions). | | |
| TASK-011 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-entity-projection/validator.py`: validates entity kinds against the Phase 1 schema declared in `api/server/services/entity_graph.py:_SCHEMA` (or `_SCHEMA_PLACEHOLDER` if Phase 1 not merged); validates that each `ref_field` is a payload path that exists in the orchestrator's emitted payload (parsed by AST-walking the orchestrator file under `api/functions/workflows/<workflow_type_with_underscores>.py`); validates relation `kind` against the Phase 1 REL TABLE list. | | |
| TASK-012 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-entity-projection/codegen.py`: pure function `render_projection(brief: dict) -> tuple[str, str]` returning `(module_filename, body)` where `module_filename = brief["workflow_type"].replace("-", "_") + ".py"` (Python identifiers cannot contain hyphens — the directory layout used by the Phase 1 `PROJECTIONS` registry depends on this) and `body` is the source for `api/server/services/entity_projections/<workflow_type_with_underscores>.py`. The body exposes a module-level `WORKFLOW_TYPE = "<workflow_type>"` constant and a bare `def project(workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:` that reads from `workflow.payload` and `workflow.workflow_type` (Phase 1 PAT-005 locks the function name as `project`, not `project_<wt>`, so the registry can `from <module> import project, WORKFLOW_TYPE` uniformly). Imports `EntityWrite`, `RelWrite`, `DecisionWrite` from `api.server.services.entity_graph` (Phase 1). Decision writes are emitted by the codegen in TASK-014, not here — this codegen produces only `EntityWrite` + `RelWrite`. | | |
| TASK-013 | Add `tests/api/server/services/entity_projections/test_codegen.py` (NEW) with TDD coverage: (a) feed the codegen a synthetic brief with two entities + one relation, assert the rendered file imports the right types, defines bare `project` returning the right shape, and that `render_projection(brief)[0]` is the underscored filename (e.g. `purchase_card.py`); (b) feed it a brief with an unknown entity kind, assert validator raises `SchemaError(path="entities[0].kind", reason="unknown entity kind 'Foo'")`; (c) feed it a brief whose `ref_field` does not appear in the orchestrator AST, assert the validator raises with the unresolved path. | | |

### Implementation Phase 4 — `author-decision-mapping` sub-skill + Cypher codegen

- GOAL-004: Add the `decisions:` block to the brief schema and emit one Cypher file per HITL phase at `api/server/services/precedent_queries/<workflow_type>_<phase_name>.cypher` that creates a `Decision` node and its `DECIDED_ON` edges. The ULID + dedupe contract from blueprint §10 decision #4 lives in the Cypher template.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-decision-mapping/SKILL.md`: prompt that reads `brief.phases` (filtered to `kind: hitl`) and `brief.entities`, then emits the `decisions:` block. Each decision entry declares `phase` (must match a HITL phase in the skeleton), `decided_on_entities` (list of entity refs from the `entities:` block), and `attributes_from_context` (map of `Decision.attributes` JSON keys → context paths from the orchestrator's `suspended` payload `context` field). | | |
| TASK-015 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-decision-mapping/validator.py`: validates that every `phase` named in `decisions:` exists in `brief.phases` with `kind: hitl`; validates that every `decided_on_entities` ref resolves to an entry in the `entities:` block; validates that no two decisions name the same phase (one decision per HITL phase, matching the ULID dedupe key `(workflow_id, phase, persona_role)`). | | |
| TASK-016 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-decision-mapping/codegen.py`: pure function `render_cypher(brief: dict, decision: dict) -> str` returning a Cypher file body that MERGEs a `Decision` node keyed on `(workflow_id, phase, persona_role)` (the dedupe triple from Phase 1) with ULID-derived `id`, then CREATEs `DECIDED_ON` edges to each entity in `decided_on_entities`, then sets `attributes` to a JSON blob built from `attributes_from_context`. The meta-skill iterates decisions and calls the codegen once per decision, writing each to `api/server/services/precedent_queries/<workflow_type>_<phase>.cypher`. | | |
| TASK-017 | Add `tests/api/server/services/precedent_queries/test_cypher_codegen.py` (NEW): (a) round-trip a two-decision brief through the codegen, assert each output file MERGEs on the dedupe triple and CREATEs the right number of DECIDED_ON edges; (b) assert a brief naming a non-HITL phase fails validation with `SchemaError(path="decisions[0].phase", reason="phase 'X' is not kind: hitl")`; (c) assert two decisions on the same phase fail validation. | | |

### Implementation Phase 5 — `author-function-membership` sub-skill + FUNCTIONS patcher

- GOAL-005: Add the `function:` field to the brief schema, validate it against the Phase 3 `FUNCTIONS` registry (or `FUNCTIONS_PLACEHOLDER` for standalone Phase 2 ship), and teach `graduate.sh` to patch `FUNCTIONS["<fn>"].owns_domains` idempotently with the new domain's `workflow_type`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-function-membership/SKILL.md`: prompt that reads `brief.domain.description` + `brief.phases` and proposes a single `function:` value from the Phase 3 `FUNCTIONS` keys (`finance`, `hr`, `revenue`, `ops`, `legal`, `marketing`, `tech`, `data`, `customer-success` — exact strings, no synonyms; `legacy` reserved for POC1/POC2). Hands off to operator confirmation if more than one function is plausible. | | |
| TASK-019 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-function-membership/validator.py`: imports `FUNCTIONS` from `api.shared.functions` if importable, otherwise falls back to `FUNCTIONS_PLACEHOLDER = {"finance", "hr", "revenue", "ops", "legal", "marketing", "tech", "data", "customer-success", "legacy"}` declared in the same file (these ten function-name keys mirror Phase 3 TASK-001 verbatim — drift here would trip Phase 3's boot validator). Validates `brief.function` is a member; validates the domain's `workflow_type` is not already claimed by a different function in the live registry (orphan/dup check). | | |
| TASK-020 | Extend `docs/superpowers/skills/compose-domain/templates/graduate.sh.tmpl` with a new patch step: append `<workflow_type>` to `FUNCTIONS["<fn>"].owns_domains` in `api/shared/functions.py`. The patch uses a sentinel comment `# compose-domain:owns_domains:<fn>` so re-running graduate.sh on an already-claimed domain is a no-op. **Guarded skip:** if `api/shared/functions.py` does not yet exist (Phase 3 not merged), graduate.sh logs `"warn: api/shared/functions.py absent — skipping FUNCTIONS patch (Phase 3 will own this)"` and exits 0 for that step only; remaining graduate.sh steps still run. Document the step + the guarded-skip behaviour under `compose-domain/CHECKLIST.md §10`. | | |
| TASK-021 | Add `tests/docs/superpowers/skills/compose_domain/sub_skills/test_author_function_membership.py` (NEW): (a) brief with `function: finance` validates clean against `FUNCTIONS_PLACEHOLDER`; (b) brief with `function: not-a-function` raises `SchemaError(path="function", reason="unknown function 'not-a-function'")`; (c) when run with a mock `FUNCTIONS` registry that already lists the domain under a *different* function, validator raises with the dup-claim error. | | |

### Implementation Phase 6 — `author-ambient-trigger` sub-skill (optional)

- GOAL-006: Add the optional `ambient:` block to the brief schema, validate the discriminated trigger shape (bus | cypher | cadence) from blueprint §10 decision #5, and emit/append an `AmbientAgent(...)` registration into `api/server/services/ambient_agents/<function>.py`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-ambient-trigger/SKILL.md`: prompt that asks "does this domain need an ambient hook" and, if yes, emits the `ambient:` block: `name`, `trigger` (one of `BusTrigger{event_type, filter}`, `CypherTrigger{pattern, sweep_seconds}`, `CadenceTrigger{cron}`), `reasoning_skill` (optional GHCP SDK skill name; null = deterministic), `spawnable_workflow_types` (list of registered workflow_types). If the operator answers "no", the sub-skill writes no block and returns. | | |
| TASK-023 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-ambient-trigger/validator.py`: validates the trigger discriminated union (exactly one of the three shapes); validates `spawnable_workflow_types` are present in the live `DOMAINS` registry (`api.shared.domains.DOMAINS`) or are the brief's own `workflow_type`; validates that `brief.function` exists (so the codegen knows which file to write). | | |
| TASK-024 | Create `docs/superpowers/skills/compose-domain/sub-skills/author-ambient-trigger/codegen.py`: pure function `render_ambient(brief: dict) -> tuple[str, str]` returning `(file_path, append_block)`. `file_path` is `api/server/services/ambient_agents/<brief.function>.py`; `append_block` is the Python source for one `AmbientAgent(...)` constructor wrapped in a sentinel `# compose-domain:ambient:<workflow_type>` block so graduate.sh can append idempotently. The codegen guards the constructor with `if hasattr(_module, "AmbientAgent"):` so the file is import-clean before Phase 3 lands the primitive. | | |
| TASK-025 | Add `tests/api/server/services/ambient_agents/test_ambient_codegen.py` (NEW): (a) brief with a `BusTrigger` ambient validates and renders; (b) brief naming a `spawnable_workflow_types` value not in `DOMAINS` fails validation; (c) brief with two trigger kinds set raises `SchemaError(path="ambient.trigger", reason="exactly one of bus/cypher/cadence required")`; (d) re-rendering against a file already containing the sentinel block produces the same file (idempotent append). | | |

### Implementation Phase 7 — Backfill the twelve synthetic-journey briefs

- GOAL-007: For each existing synthetic-journey domain, edit its brief at `docs/superpowers/specs/<domain>-brief.yaml` to add the four new v4 sections, then run compose-domain v4 with `--re-projection-only` and verify orchestrators stay byte-equal pre/post while the projection / decision / function / ambient artefacts land. POC1 (`expense-claim`) and POC2 (`hiring`) are explicitly excluded.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-026 | Backfill `docs/superpowers/specs/fleet-ap-invoice-brief.yaml`. Entities: `Money{kind=invoice, ref_field=payload.invoice_id}`, `Organisation{kind=vendor, ref_field=payload.vendor_id}`. Decision phase: `ap_signoff`. Function: `finance`. No ambient. Run `compose-domain --re-projection-only` against the brief; assert `git diff api/functions/workflows/fleet_ap_invoice.py` is empty; assert `api/server/services/entity_projections/ap_invoice.py` (underscored) and `api/server/services/precedent_queries/ap-invoice_ap_signoff.cypher` exist. | | |
| TASK-027 | Backfill `docs/superpowers/specs/fleet-contract-renewal-brief.yaml`. Entities: `Asset{kind=contract, ref_field=payload.contract_id}`, `Organisation{kind=vendor, ref_field=payload.vendor_name}`, `Money{kind=budget-line, ref_field=payload.proposed_annual_value}`. Decision phases: `finance_signoff`, `contract_owner_signoff`. Function: `finance`. Ambient: `CypherTrigger` for `>25%` price jumps spawning `variance-investigation` (from blueprint §2 example). Re-projection-only run; orchestrator byte-equal; four artefacts (1 projection + 2 cypher + 1 ambient append) land. | | |
| TASK-028 | Backfill `docs/superpowers/specs/fleet-contract-review-brief.yaml`. Entities: `Asset{kind=contract, ref_field=payload.contract_id}`. Decision phase: `legal_signoff`. Function: `legal`. No ambient. Re-projection-only run; orchestrator byte-equal. | | |
| TASK-029 | Backfill `docs/superpowers/specs/fleet-employee-onboarding-brief.yaml`. Entities: `Person{kind=joiner, ref_field=payload.employee_id}`, `Asset{kind=laptop, ref_field=payload.laptop_id}`. Decision phase: `manager_signoff`. Function: `hr`. No ambient (Phase 3 will add `HireToProductiveTrigger` separately as a meta-workflow brief). Re-projection-only run; orchestrator byte-equal. | | |
| TASK-030 | Backfill `docs/superpowers/specs/fleet-it-access-request-brief.yaml`. Entities: `Person{kind=requester, ref_field=payload.employee_id}`, `Asset{kind=access_scope, ref_field=payload.requested_role_templates}`. Decision phase: `it_admin_signoff`. Function: `tech` (matches Phase 3 TASK-001 canonical name — *not* `technology`). No ambient. Re-projection-only run; orchestrator byte-equal. Module lands at `api/server/services/entity_projections/it_access_request.py`. | | |
| TASK-031 | Backfill `docs/superpowers/specs/fleet-perf-review-brief.yaml`. Entities: `Person{kind=reviewee, ref_field=payload.employee_id}`. Decision phase: `calibration_signoff`. Function: `hr`. No ambient. Re-projection-only run; orchestrator byte-equal. | | |
| TASK-032 | Backfill `docs/superpowers/specs/fleet-privacy-dpia-brief.yaml`. Entities: `Asset{kind=data_process, ref_field=payload.process_id}`. Decision phase: `dpo_signoff`. Function: `legal`. No ambient. Re-projection-only run; orchestrator byte-equal. | | |
| TASK-033 | Backfill `docs/superpowers/specs/fleet-purchase-order-brief.yaml`. Entities: `Money{kind=po, ref_field=payload.po_id}`, `Organisation{kind=vendor, ref_field=payload.vendor_id}`. Decision phase: `buyer_signoff`. Function: `finance`. No ambient. Re-projection-only run; orchestrator byte-equal. | | |
| TASK-034 | Backfill `docs/superpowers/specs/fleet-travel-preapproval-brief.yaml`. Entities: `Person{kind=traveller, ref_field=payload.employee_id}`, `Money{kind=trip_cost, ref_field=payload.estimated_cost}`. Decision phase: `manager_signoff`. Function: `hr`. No ambient. Re-projection-only run; orchestrator byte-equal. | | |
| TASK-035 | Backfill `docs/superpowers/specs/fleet-treasury-fx-brief.yaml`. Entities: `Money{kind=fx, ref_field=payload.treasury_op.id}`. Decision phase: `approver_signoff` (event name `treasury_signoff_decision` per the orchestrator at `api/functions/workflows/fleet_treasury_fx.py`). Function: `finance`. Ambient: `CypherTrigger` matching `(m:Money {kind:'fx'}) WHERE m.attributes.exposure > threshold` spawning `treasury-fx` workflows hourly (FxExposureWatcher from blueprint §5). Re-projection-only run; orchestrator byte-equal. | | |
| TASK-036 | Backfill `docs/superpowers/specs/fleet-vendor-kyc-brief.yaml`. Entities: `Organisation{kind=vendor, ref_field=payload.vendor.id, attributes={country: payload.vendor.country_of_incorporation, risk_band: payload.kyc.risk_band}}`. Decision phase: `finance_signoff`. Function: `finance`. Ambient: `CypherTrigger` matching `(o:Organisation {kind:'vendor'}) WHERE o.risk_band = 'high'` spawning `vendor-kyc` re-screen (VendorRiskWatcher from blueprint §5). Re-projection-only run; orchestrator byte-equal. | | |
| TASK-037 | Backfill `docs/superpowers/specs/creative-campaign-brief.yaml`. Entities: `Asset{kind=campaign, ref_field=payload.campaign_id}`, `Money{kind=budget, ref_field=payload.budget}`. Decision phase: `creative_director_signoff`. Function: `marketing`. No ambient. Re-projection-only run; orchestrator byte-equal. | | |
| TASK-038 | Add `tests/api/server/services/test_backfilled_projections.py` (NEW) iterating over all twelve workflow_types from TASK-026 through TASK-037. For each: assert `api/server/services/entity_projections/<workflow_type_with_underscores>.py` (e.g. `ap_invoice.py`, `creative_campaign.py`) imports clean; assert the module exposes a bare `project` callable (matches Phase 1 PAT-005); assert at least one `.cypher` file exists under `api/server/services/precedent_queries/` matching `<workflow_type>_*.cypher`; assert the workflow_type appears in exactly one `FUNCTIONS["<fn>"].owns_domains` (or `FUNCTIONS_PLACEHOLDER` equivalent if Phase 3 not merged). | | |

### Implementation Phase 8 — Smoke test + skill docs update

- GOAL-008: Prove substrate-by-construction by running compose-domain v4 end-to-end on a fresh thirteenth synthetic-journey domain `fleet-purchase-card`, then update the operator-facing docs (`docs/superpowers/skills/compose-domain/SKILL.md` and `.github/skills/add-domain/SKILL.md`) so future operators discover the v4 pipeline.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-039 | Author `docs/superpowers/specs/fleet-purchase-card-brief.yaml` from a free-text idea ("employee corporate card spend reconciliation; merchant + amount intake → policy match agent → manager signoff HITL"). Run compose-domain v4 wholesale (no `--re-projection-only`) into a fresh sandbox under `tools/scratch/compose-domain/<RUN_ID>-fleet-purchase-card/`. Assert sandbox has every artefact from `compose-domain/CHECKLIST.md §1` plus the four new v4 artefact kinds from §8/§9/§10/§11. | | |
| TASK-040 | Run `bash tools/scratch/compose-domain/<RUN_ID>-fleet-purchase-card/graduate.sh` from repo root. Assert: orchestrator at `api/functions/workflows/fleet_purchase_card.py` exists; `api/server/services/entity_projections/purchase_card.py` (underscored) exists, is importable, and exposes a bare `project` callable; one `.cypher` file at `api/server/services/precedent_queries/purchase-card_manager_signoff.cypher` exists; `FUNCTIONS["finance"].owns_domains` contains `"purchase-card"`; running graduate.sh a second time is a no-op (re-runs the test). | | |
| TASK-041 | Update `docs/superpowers/skills/compose-domain/SKILL.md` "Inputs" + "What this is" sections to reflect the v4 pipeline. Update `.github/skills/add-domain/SKILL.md` Phase 3 (Run compose-domain) to mention the four new sections in the brief and the `--re-projection-only` flag. Embed the v4 Mermaid pipeline diagram from blueprint §4 lines 493-512 in both. | | |
| TASK-042 | Add a one-paragraph note to `docs/superpowers/skills/compose-domain/CHECKLIST.md` Graduation section that re-projection-only graduation patches only the four new file kinds (no `function_app.py`, no `simulator_orchestrator.py`, no `blueprint_inventory.py` edits) and is therefore safe to re-run on every backfill iteration. | | |

## 3. Done means

> Every new `compose-domain` run produces an entity-aware,
> function-aware, decision-recording domain by construction; we can never
> again add a synthetic-journey domain that doesn't populate the graph
> or claim a function owner.
>
> — `docs/agentic-org-blueprint.md` §9 Phase 2

Smoke-test commands:

```bash
# 1. Fresh-domain end-to-end (TASK-039 + TASK-040).
#    Authors brief, runs v4 pipeline, graduates, asserts artefacts.
bash tools/scratch/compose-domain/<RUN_ID>-fleet-purchase-card/graduate.sh

# 2. Backfill regression — re-projection-only on every existing domain.
#    Orchestrators must stay byte-equal pre/post.
for d in fleet-ap-invoice fleet-contract-renewal fleet-contract-review \
         fleet-employee-onboarding fleet-it-access-request fleet-perf-review \
         fleet-privacy-dpia fleet-purchase-order fleet-travel-preapproval \
         fleet-treasury-fx fleet-vendor-kyc creative-campaign; do
  python -m docs.superpowers.skills.compose_domain \
    --brief docs/superpowers/specs/${d}-brief.yaml \
    --re-projection-only
done
git diff --quiet api/functions/workflows/  # must exit 0

# 3. Backfilled-projection regression test (TASK-038).
pytest tests/api/server/services/test_backfilled_projections.py -v

# 4. Sub-skill validator unit tests (TASK-009, -013, -017, -021, -025).
pytest tests/docs/superpowers/skills/compose_domain/ \
       tests/api/server/services/entity_projections/ \
       tests/api/server/services/precedent_queries/ \
       tests/api/server/services/ambient_agents/ -v
```
