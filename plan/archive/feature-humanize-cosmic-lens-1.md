---
goal: Make every interactive surface of the Cosmic Lens readable to a non-technical user
version: 1.0
date_created: 2026-05-11
last_updated: 2026-05-11
owner: Cosmic Lens HUD
status: 'Shipped'
tags: [feature, ux, humanization]
---

# Introduction

![Status: Shipped](https://img.shields.io/badge/status-Shipped-green)

> **Update 2026-05-11 — Shipped.** Track F (`f1`–`f8`) of
> `refactor-repo-coherence-remediation-1.md` landed in commits
> `fd707b53`, `55e312a9`, `18b1e84c`, `cf7ad9ea`, `472f7e9e`,
> `f500e568`, `f16464df`, and the f8 ship commit. Every cosmic-lens
> surface now reads as plain English via `web/shared/humanize.ts`.

The Cosmic Lens (constellation view, served from `web/blueprint/`) currently leaks runtime jargon into every interactive surface — `awaiting HITL decision (ap_clerk)`, `executor.deterministic_invoice_lookup`, `entity.upserted`, `vendor-kyc · UBO Resolver · 852s old`, raw Kuzu relationship names like `OWNS`. A non-technical reader cannot click anything and immediately understand what happened, when, who did it, or why.

We have already shipped a single-source-of-truth humanizer at [`web/shared/humanize.ts`](../../web/shared/humanize.ts) and converted the workflow drawer + fleet rail to use it. This plan extends the same dictionary to every remaining surface so that the entire constellation reads as plain English by default. **No data-structure changes** — humanization is a pure presentation layer.

## 1. Requirements & Constraints

- **REQ-001**: Every text-rendering surface in the constellation view must read as plain English. No raw event types (`durable.executor.invoked`), no snake_case actor ids (`ap_clerk`), no internal verbs (`HITL`, `BLOCKED`, `awaiting_*`).
- **REQ-002**: All wording goes through `web/shared/humanize.ts` — single source of truth. New strings are added by extending its dictionaries, never by inlining one-off labels in components.
- **REQ-003**: Workflow ids (`HIRE-0001`), entity ids (`INV-0871`), and phase names (`UBO Resolver`) stay verbatim — those are the demo's currency.
- **REQ-004**: Humanization is deterministic and synchronous (no LLM in the rendering path).
- **REQ-005**: A persona role appearing on a city label, in a decision row, in a tooltip, and in the rail must read **identically** in all four places.
- **CON-001**: No backend schema changes. The runtime keeps emitting `executor.*`, `entity.upserted`, etc. — humanization is read-only on the client.
- **CON-002**: Build is `web/blueprint/` → `vite build` → bundle served by FastAPI on `:3001` from `web/blueprint/dist/`. Source edits do not show until the bundle is rebuilt. Use `./node_modules/.bin/vite build` directly (the project's `npm run build` chains `tsc -b` which fails on pre-existing vitest type errors).
- **CON-003**: The shared module is consumed via a relative import (`../../../../../shared/humanize`) from blueprint app — vite alias is unreliable for blueprint at build time, but resolves fine for `web/client` via the existing `@shared/*` alias.
- **GUD-001**: Wording target = "what happened in business terms", not "what code ran". Example: `executor.agent_kyc_diligence_checker` → "Ran KYC diligence checks", not "Agent KYC diligence checker invoked".
- **GUD-002**: When data is genuinely a duration of zero (synthetic workflows compress into <1s), show milliseconds, not "+0s".
- **PAT-001**: All new dictionaries (personas, entity verbs, relationship verbs, status pills) live as exported maps in `web/shared/humanize.ts` next to `EXECUTOR_OVERRIDES` so they are discoverable in one file.

## 2. Implementation Steps

### Implementation Phase 1 — Persona dictionary (highest-impact, blocks everything downstream)

- GOAL-001: Convert every persona-role identifier (`ap_clerk`, `dpo`, `creative_director`, `it_access_line_manager`, `vendor_kyc_finance_bp`, etc.) into a single canonical human label rendered identically wherever a persona is displayed (city label, badge, decision row, hover tooltip, fleet rail).

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In [`web/shared/humanize.ts`](../../web/shared/humanize.ts) add `PERSONA_LABELS: Record<string, string>` mapping every role id from [`api/server/config/personae.py`](../../api/server/config/personae.py) (or whichever file owns the catalogue — verify before editing) to a display string. Required entries at minimum: `ap_clerk → "AP Clerk"`, `controller → "Controller"`, `cfo → "CFO"`, `treasurer → "Treasurer"`, `dpo → "Data Protection Officer"`, `gc → "General Counsel"`, `cpo → "Chief People Officer"`, `hr_bp → "HR Business Partner"`, `finance_bp → "Finance Business Partner"`, `vendor_kyc_finance_bp → "Finance BP (Vendor KYC)"`, `recruiter → "Recruiter"`, `hiring_manager → "Hiring Manager"`, `creative_director → "Creative Director"`, `account_director → "Account Director"`, `category_manager → "Category Manager"`, `sourcing_lead → "Sourcing Lead"`, `it_access_line_manager → "Line Manager (IT Access)"`, `it_access_it_admin → "IT Admin (IT Access)"`, `onboarding_it_admin → "IT Admin (Onboarding)"`, `perf_review_hr_bp → "HR BP (Perf Review)"`, `perf_review_line_manager → "Line Manager (Perf Review)"`, `contract_finance_bp → "Finance BP (Contracts)"`, `contract_line_manager → "Line Manager (Contracts)"`, `contracts_counsel → "Contracts Counsel"`, `change_manager → "Change Manager"`, `claim_submitter → "Claim Submitter"`, `comp_ben_analyst → "Comp & Ben Analyst"`, `fpa_analyst → "FP&A Analyst"`, `ssc_reviewer → "SSC Reviewer"`, `project_manager → "Project Manager"`, `line_manager → "Line Manager"`, `ap_clerk → "AP Clerk"`, `candidate → "Candidate"`, `finance_controller → "Finance Controller"`. | | |
| TASK-002 | Update existing `prettyActor()` in [`web/shared/humanize.ts`](../../web/shared/humanize.ts) to consult `PERSONA_LABELS` first, fall back to `titleCase()` for unknown roles. | | |
| TASK-003 | In [`web/blueprint/src/components/cosmicLens/Cities.tsx`](../../web/blueprint/src/components/cosmicLens/Cities.tsx) — the `formatCityLabel()` helper at the bottom of the file — when `city.kind === "persona"` route the label through `prettyActor(city.label)` from `@shared/humanize` (use relative import — see CON-003). Persona city tooltips, badges, and the always-on label all use the same source. | | |
| TASK-004 | Audit [`api/server/routes/cities.py`](../../api/server/routes/cities.py) (or the city builder) — confirm the persona city `label` field carries the role id, not a pre-formatted name. If it carries the role id (current behaviour), TASK-003 is sufficient. If it pre-formats, leave the API alone and let TASK-003 strip the format and re-apply. | | |
| TASK-005 | Verify by inventory: open the running app, hover every persona city, confirm "AP Clerk" not "ap_clerk", "Data Protection Officer" not "dpo", etc. | | |

### Implementation Phase 2 — Activity rail + parked rocket labels (highest-traffic surface)

- GOAL-002: Replace [`web/blueprint/src/components/cosmicLens/lib/labels.ts`](../../web/blueprint/src/components/cosmicLens/lib/labels.ts) so its `labelForCapability` and `labelForEntity` functions emit plain English, by routing through `humanizeLabel()` and `prettyActor()` from `@shared/humanize`. Both the activity rail (`HUD/ActivityRail.tsx`) and parked rocket on-canvas labels read from these functions.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Rewrite `labelForCapability` in [`labels.ts`](../../web/blueprint/src/components/cosmicLens/lib/labels.ts): `persona.thinking` → `${prettyActor(persona)} is reviewing` (drop "HITL"); `persona.decided` → `${prettyActor(persona)} decided`; `tool.invoked` → `Running ${humanizeLabel(name).text}`; `tool.completed` → `${humanizeLabel(name).text} — done`; `ambient.decided` → `${prettyActor(agent_name)} reasoned`; `decision.recorded` → `Decision recorded`; `workflow.sub_spawned` → `Spawned a sub-workflow`. Default branch: NEVER return `ev.type` raw — return `humanizeLabel(ev.type).text` or `"Activity"` if empty. | | |
| TASK-007 | Rewrite `labelForEntity` to drop terminal verbs: `entity.read` → `Looked up ${kindToVerb(kind)}${id}`; `entity.upserted` with `verb=create` → `Created ${kindToVerb(kind)}${id}`; with `verb=update` → `Updated ${kindToVerb(kind)}${id}`; `entity.linked` → `Connected ${kindToVerb(kind)}${id}`; `entity.write.failed` → `Couldn't save ${kindToVerb(kind)}${id}`; `entity.write.killed` → `Save blocked: ${kindToVerb(kind)}${id}`. Default: `humanizeLabel(ev.type).text`. | | |
| TASK-008 | Update activity-rail filter chip labels in [`HUD/ActivityRail.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx): `decisions / thinking / done / exceptions / started / spawned / tools / entities` → `Decisions / People reviewing / Completed / Problems / Started / New cases / System tools / Records`. Filter `key`s stay the same (they map to event categorise() — internal). | | |
| TASK-009 | Update activity-rail empty state copy and section header in same file: "No activity yet. Try the ⚡ BURST button." → "No activity yet. Press the BURST button to spawn a few cases."; "Live activity" header stays. | | |
| TASK-010 | Verify by inventory: open the running app, watch the rail for 30s, confirm no rows containing raw event names like `executor.*`, `entity.*`, `tool.*`, `workflow.*`, `persona.*`, or snake_case actor ids. | | |

### Implementation Phase 3 — Top vital-signs bar wording

- GOAL-003: Tighten the top-bar stat labels and status pill so a non-technical reader can read the bar from left to right without external context.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | In [`HUD/VitalSignsBar.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx) update `Stat label` props: `in-flight → "Active cases"`, `pending decisions → "Awaiting people"`, `steps / min → "Steps per minute"`, `at gate → "Stuck at a person"`, `events / min → "Events per minute"`. | | |
| TASK-012 | In `StatusPill` map raw status to plain English: `watching → "Live"`, `connecting → "Connecting…"`, `offline → "Disconnected"`. Colour mapping unchanged. | | |
| TASK-013 | Button labels: `seed kpis → "Load demo KPIs"`, `⚡ BURST 8 → "Spawn 8 cases"`. Keep the lightning glyph as a small prefix. Tooltip stays for power users. | | |
| TASK-014 | Mode toggle stays as `Capabilities` / `Entities` — already English. Add `title` attributes: Capabilities = "Show me what's being done", Entities = "Show me which records are being touched". | | |

### Implementation Phase 4 — Function (planet) drawer

- GOAL-004: When a user clicks a planet (function), the resulting drawer must list workflows in plain English with no `vendor-kyc · UBO Resolver · 852s old`-style metadata strings.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Add `WORKFLOW_TYPE_LABELS: Record<string, string>` to [`web/shared/humanize.ts`](../../web/shared/humanize.ts) — at minimum: `vendor-kyc → "Vendor KYC"`, `ap-invoice → "Invoice processing"`, `perf-review → "Performance review"`, `hiring → "Hiring"`, `treasury-fx → "Treasury FX"`, `creative-campaign → "Creative campaign"`, `employee-onboarding → "Employee onboarding"`, `it-access-request → "IT access request"`, `contract-renewal → "Contract renewal"`, `purchase-order → "Purchase order"`, `contract-review → "Contract review"`, `privacy-dpia → "Privacy DPIA"`. Export `humanWorkflowType(slug: string): string` that consults the map then falls back to `titleCase(slug.replace(/-/g, "_"))`. | | |
| TASK-016 | Add `formatAge(seconds: number): string` to [`web/shared/humanize.ts`](../../web/shared/humanize.ts) — returns `"started 14 minutes ago"`, `"started 2 hours ago"`, `"started just now"`, `"started 3 days ago"`. Use the existing `formatOffset` rules for sub-minute handling. | | |
| TASK-017 | In [`HUD/WorkflowDrawer.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx) `FunctionView`, change the workflow-row metadata line from `${wf.workflow_type ?? "—"} · ${wf.phase ?? "—"} · ${Math.round(wf.age_s ?? 0)}s old` to `${humanWorkflowType(wf.workflow_type)} · ${wf.phase ?? "—"} · ${formatAge(wf.age_s)}`. | | |
| TASK-018 | Change the empty-state string in `FunctionView` from "No in-flight workflows for this function right now." to "No active cases for this function right now.". Header subtitle "function" stays — it's already English. | | |

### Implementation Phase 5 — City drawer (Entities mode)

- GOAL-005: When a user clicks a city in Entities mode, the resulting detail panel reads as plain English with no raw graph relationship names or event types.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | Add `RELATIONSHIP_LABELS: Record<string, string>` to [`web/shared/humanize.ts`](../../web/shared/humanize.ts). Source from [`api/server/services/entity_graph.py`](../../api/server/services/entity_graph.py) — enumerate every rel name (`OWNS`, `DECIDED_ON`, `RESPONSIBLE_FOR`, `BELONGS_TO`, `WORKS_FOR`, `MANAGES`, `APPROVED`, `REJECTED`, `RESOLVED`, `LINKED_TO`, etc.). Map to short verb phrases: `OWNS → "owns"`, `DECIDED_ON → "decided"`, `RESPONSIBLE_FOR → "responsible for"`, `BELONGS_TO → "belongs to"`, `LINKED_TO → "linked to"`. Export `humanRelationship(rel: string, count: number, partnerKind: string): string` that returns a sentence: e.g. `OWNS, 12, Vendor → "Owns 12 vendors"`. | | |
| TASK-020 | In [`HUD/WorkflowDrawer.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx) `CityView`: section header "Top relationships" → "Connected to". Each relationship row renders `humanRelationship(rl.rel, rl.count, rl.partner_kind)` instead of `${rl.rel} ${rl.partner_kind} · ${rl.count}`. Plural the partner kind via a tiny `pluralize(kind, n)` helper in `humanize.ts` (handles common kinds: Person→People, Vendor→Vendors, Invoice→Invoices, Contract→Contracts, etc.). | | |
| TASK-021 | Same file, `CityView` "Live activity" section: each row renders `labelForEntity(f)` from the rewritten labels.ts (Phase 2) plus `f.workflow_id` if present. Currently shows `f.type.replace("entity.", "")` — replace with the humanizer call. | | |
| TASK-022 | Header subtitle template `${meta.count} entities · ${meta.rate.toFixed(1)}/min` → `${meta.count} records · ${meta.rate.toFixed(1)} changes/min`. | | |
| TASK-023 | Empty-state strings: "No entities of this kind yet." → "No records of this type yet."; "No relationships incident to this kind." → "Not connected to anything yet."; "No recent events for this kind." → "No recent activity for this type.". | | |

### Implementation Phase 6 — Entity drawer

- GOAL-006: When a user clicks a specific entity (record), the drawer reads as plain English. Currently shows raw kind labels, snake_case attribute keys, and ISO timestamps.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-024 | Read [`HUD/WorkflowDrawer.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx) `EntityView` (the function continues from line ~508 — verify line numbers before editing). Catalogue every text it renders. | | |
| TASK-025 | Replace the header subtitle (currently the entity kind verbatim, e.g. `Person`) with `kindToVerb(kind)` from [`labels.ts`](../../web/blueprint/src/components/cosmicLens/lib/labels.ts) so `Person` reads as "person details", `Vendor` as "vendor record", etc. Keep entity id verbatim as the header title. | | |
| TASK-026 | Linked-entities section: show "Connected to" not "Linked to". Each row formats relationship via `humanRelationship` from Phase 5 with count=1 and the partner kind name humanized. | | |
| TASK-027 | Source workflows section: instead of raw workflow ids, prefix with `humanWorkflowType()` from the workflow id slug — e.g. `HIRE-0001` → "Hiring · HIRE-0001". | | |
| TASK-028 | Any ISO timestamp (`first_seen_at`, `last_seen_at`, `decided_at`) renders via `formatRelative()` (already in [`entityRender.ts`](../../web/blueprint/src/components/cosmicLens/lib/entityRender.ts)) — confirm it does and that it produces "5 minutes ago" style output, not "2026-05-11T08:01:28". | | |

### Implementation Phase 7 — Knowledge pulse strip + Hot functions

- GOAL-007: Polish the two smallest surfaces last so the whole UI lands consistently.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-029 | In [`HUD/KnowledgePulse.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx) update stat titles: `Total entities → "Total records"`. `Decisions/min` and `Links/min` stay (already plain). Sub copy `+5 in last 60s` stays. | | |
| TASK-030 | Cross-domain panel header `Cross-domain leaders → "Records used by multiple teams"`. Each row currently shows `${e.workflow_types_count} domains · ${e.workflow_count} wfs` — change to `${e.workflow_types_count} teams · used by ${e.workflow_count} cases`. | | |
| TASK-031 | In [`HUD/HotFunctions.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/HotFunctions.tsx) header `Hot functions · in-flight → "Busiest teams · active cases"`. The function `label` already comes from the API as a display name; no mapping needed. | | |

### Implementation Phase 8 — Verification + bundle ship

- GOAL-008: Confirm every fixed surface in a single audit pass, rebuild the bundle, and confirm the FastAPI server is serving the new hash.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-032 | Type-check both apps with the project's local `tsc`: `cd web/blueprint && ./node_modules/.bin/tsc --noEmit -p .` (ignore the four pre-existing vitest-related test errors). | | |
| TASK-033 | Build bundle: `cd web/blueprint && ./node_modules/.bin/vite build`. Capture new bundle hash. | | |
| TASK-034 | Confirm `curl -s http://localhost:3001/ \| grep -oE 'index-[A-Za-z0-9_-]+\\.js'` returns the new hash. If it returns the old one, the FastAPI server is serving a cached `dist/` — rebuild already overwrote it; reload browser with cache disabled. | | |
| TASK-035 | Manual audit pass: open `/?view=constellation`, click each interactive surface in this order — top bar stats, status pill, ⚡ BURST button, mode toggle, every visible planet, every visible city (capabilities mode), every persona city, every workflow drawer, switch to Entities mode, click each city, click an entity, hover several moons. For each surface confirm: no raw event types, no snake_case ids, no `HITL`/`BLOCKED`/`awaiting_*`, persona names match across all surfaces. Record any surface that still leaks jargon and add a follow-up task. | | |
| TASK-036 | Commit all changes in one commit: `git add web/shared/humanize.ts web/blueprint/src/components/cosmicLens/...` then `git commit -m "feat(humanize): make every cosmic-lens surface read as plain English"`. Do not push. | | |

## 3. Alternatives

- **ALT-001**: Drive labels from a server-side dictionary (e.g. extend the `/api/functions` payload with display strings for personas, workflow types, relationships). Rejected: forces a backend change for every UI copy tweak; the data is small enough to ship in the bundle; we already have `web/shared/humanize.ts` as the convention.
- **ALT-002**: Inject an LLM to "describe what just happened" per event. Rejected: non-deterministic, slow, expensive, untestable, and the same event would read differently each time — the opposite of what a layperson needs.
- **ALT-003**: Rename the underlying event types in the runtime (`durable.executor.invoked` → `agent_ran`). Rejected: breaks a stable event contract used by tests, the entity reflector, OTEL spans, and downstream consumers; pure presentation fix is safer.

## 4. Dependencies

- **DEP-001**: Existing [`web/shared/humanize.ts`](../../web/shared/humanize.ts) module + its current consumers (workflow drawer, fleet rail) — must stay green.
- **DEP-002**: [`api/server/config/personae.py`](../../api/server/config/personae.py) (or wherever the persona catalogue lives) as the source of truth for the role id list. Verify file exists before TASK-001; if catalogue is split across files, list all of them.
- **DEP-003**: [`api/server/services/entity_graph.py`](../../api/server/services/entity_graph.py) for the canonical relationship name list (TASK-019).

## 5. Files

- **FILE-001**: [`web/shared/humanize.ts`](../../web/shared/humanize.ts) — extended with `PERSONA_LABELS`, `WORKFLOW_TYPE_LABELS`, `RELATIONSHIP_LABELS`, `humanWorkflowType()`, `humanRelationship()`, `pluralize()`, `formatAge()`. Existing `EXECUTOR_OVERRIDES`, `humanizeLabel`, `prettyActor`, `formatOffset`, `verdictVerb` stay.
- **FILE-002**: [`web/blueprint/src/components/cosmicLens/lib/labels.ts`](../../web/blueprint/src/components/cosmicLens/lib/labels.ts) — `labelForCapability` and `labelForEntity` rewritten to route through `humanize.ts`.
- **FILE-003**: [`web/blueprint/src/components/cosmicLens/Cities.tsx`](../../web/blueprint/src/components/cosmicLens/Cities.tsx) — persona city labels via `prettyActor`.
- **FILE-004**: [`web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx) — stat labels, status pill, button labels, mode-toggle tooltips.
- **FILE-005**: [`web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx) — filter chip labels, empty state.
- **FILE-006**: [`web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx) — `FunctionView`, `CityView`, `EntityView` rewordings.
- **FILE-007**: [`web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/KnowledgePulse.tsx) — stat titles, cross-domain panel.
- **FILE-008**: [`web/blueprint/src/components/cosmicLens/HUD/HotFunctions.tsx`](../../web/blueprint/src/components/cosmicLens/HUD/HotFunctions.tsx) — header.
- **FILE-009**: [`docs/visualisation-contributor-guide.md`](../../docs/visualisation-contributor-guide.md) — update the "To add wording for a new agent or executor" section to also list `PERSONA_LABELS`, `WORKFLOW_TYPE_LABELS`, `RELATIONSHIP_LABELS` as the same-source-of-truth maps.

## 6. Testing

- **TEST-001**: Run the existing humanizer unit tests (if any) under `web/blueprint/src/components/cosmicLens/lib/__tests__/`. Add cases per new dictionary: `PERSONA_LABELS["ap_clerk"] === "AP Clerk"`, `humanWorkflowType("vendor-kyc") === "Vendor KYC"`, `humanRelationship("OWNS", 12, "Vendor") === "Owns 12 vendors"`, `formatAge(900) === "started 15 minutes ago"`.
- **TEST-002**: Manual audit pass per TASK-035. Capture before/after screenshots of: top bar, activity rail row, parked rocket label, workflow drawer row, function drawer row, city drawer relationships, entity drawer linked rows, knowledge pulse cross-domain panel.
- **TEST-003**: Grep verification: after build, `grep -oE 'awaiting_[a-z_]+|executor\.[a-z_.]+|entity\.[a-z_.]+' web/blueprint/dist/assets/index-*.js | sort -u` should return only strings used as keys in the dictionaries (i.e. inside `EXECUTOR_OVERRIDES`-style maps), never as user-visible content. If a raw type leaks into a render path, this catches it.

## 7. Risks & Assumptions

- **RISK-001**: Persona catalogue has more than ~32 roles when including domain-prefixed variants (`it_access_*`, `perf_review_*`, etc.). Mitigation: enumerate from the catalogue file rather than guessing; provide a `titleCase()` fallback so unknown ids still render acceptably.
- **RISK-002**: `RELATIONSHIP_LABELS` (Phase 5) has no single source file — relationships are scattered across the entity-graph upsert call sites. Mitigation: extract from a `git grep -E "rel.*=.*['\"][A-Z_]+['\"]"` over `api/server/`, then audit before merging.
- **RISK-003**: Workflow drawer `EntityView` (Phase 6 TASK-024) reads attributes via `keyAttrFor()` which already does some humanization; double-humanizing could produce ugly strings. Mitigation: read the helper before editing, skip surfaces that are already clean.
- **RISK-004**: `formatAge()` returning English ("started 14 minutes ago") inside table-row metadata makes the row significantly wider than the current `852s old`. Mitigation: cap row width / allow truncation; verify visually in TASK-035.
- **ASSUMPTION-001**: The user is happy with British spelling (e.g. "Summarised", "Refined") — the existing `humanize.ts` already uses British spelling. New strings follow the same convention.
- **ASSUMPTION-002**: The `web/shared/humanize.ts` file's relative-import path from blueprint is stable. If the directory layout changes, the import in `humanizeTimeline.ts` (and any new consumers) needs updating.
- **ASSUMPTION-003**: The bundle-rebuild + browser-reload cycle will pick up changes immediately. If a deploy pipeline caches `dist/` separately, that cache must also be invalidated — out of scope for this plan.

## 8. Related Specifications / Further Reading

- [`docs/visualisation-contributor-guide.md`](../../docs/visualisation-contributor-guide.md) — existing humanizer contributor doc (extended in TASK FILE-009).
- [`web/blueprint/src/components/cosmicLens/STATE.md`](../../web/blueprint/src/components/cosmicLens/STATE.md) — current verified state of the cosmic lens scene.
- [`web/shared/humanize.ts`](../../web/shared/humanize.ts) — existing dictionary + helpers.
- [`api/server/routes/workflows.py`](../../api/server/routes/workflows.py) — timeline endpoint (already humanized server-side for ordering; no further change needed here).
