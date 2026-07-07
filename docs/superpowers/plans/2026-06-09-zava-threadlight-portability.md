# Zava ↔ Threadlight Portability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** Supersedes [`2026-05-27-foundry-substrate-unification.md`](2026-05-27-foundry-substrate-unification.md). That plan's Phase B (governance middleware factory) and Phase D (MCP-on-ACA protocol conformance) are folded in as this plan's Phase 4. Old plan's Phases A (deps), C (model bump), E (observability), F (tenant preflight) are deferred to a separate "substrate parity backlog" — useful work, not on the portability critical path.

> **Plan revision history:**
> - 2026-06-09 v1: initial draft
> - 2026-06-09 v2: rubber-duck pass. Major restructure: added Phase 0 spike, split Phase 1 into 1A/1B/1C/1D, redesigned tools-manifest split as layered (providers/shared/domains) rather than per-domain, renamed `import` package (Python keyword), moved gate derivation server-side, added HITL loss table, added version-compat + collision semantics, fixed `web/client` paths.

## Goal

A use case designed in Threadlight (`aiappsgbb/threadlight-skills`) can be **installed as a Zava domain** by running a single command. The reverse direction (export a Zava domain as a deployable Foundry hosted agent) follows once the import direction is stable.

The headline customer story this unlocks:

> A customer ran a threadlight pilot on their tenant six months ago. They like it; they buy Zava as their agentic-org substrate. They expect to keep their use case running — now alongside Zava's other domains, governed by the AGT kernel, learning via dream-pass, visible in the Fleet Manager — without redesigning anything.

## Non-goals

- ❌ Teams Adaptive Cards in Zava. Imported HITL gates render in Zava's existing Drawer surface. (Confirmed 2026-06-09: keeps Phase 2 small. Can revisit if a customer specifically asks.)
- ❌ Foundry Memory Store adapter. Zava keeps `DomainMemory` + dream-pass.
- ❌ MAF runtime peer. Zava keeps raw GHCP `CopilotSession`.
- ❌ Tying Kratos to Zava in any direction. Kratos stays a separate product. (Confirmed 2026-06-09.)
- ❌ Auto-generating threadlight SPECs from chat / customer brief inside Zava. `threadlight-design` already does that — not duplicating it.
- ❌ "Round-trip" parity between import and export. Provenance metadata gives **traceability**, not **reversibility**. Imported domains may diverge from their source SPEC after operator edits.

## Architecture in one diagram

```
                ┌──────────────────────────────┐
                │  threadlight-design          │
                │  brief.txt → specs/SPEC.md   │
                │           + manifest.json    │
                │           + spec.json ★      │  ★ Phase 4.1: upstream PR
                └──────────────┬───────────────┘
                               │
                               ▼ Phase 5 (the skill)
                ┌──────────────────────────────┐
                │  threadlight-to-zava skill   │  Phase 5. Lives in
                │  (thin wrapper)              │  aiappsgbb/threadlight-skills
                └──────────────┬───────────────┘
                               │
                               ▼ Phase 4 (the translator, inside Zava)
                ┌──────────────────────────────┐
                │  api/server/importers/       │  Phase 4.
                │  threadlight/                │  Tested standalone.
                │  spec.json → bundle/         │
                └──────────────┬───────────────┘
                               │
                               ▼ Phase 2 (the bundle CLI)
                ┌──────────────────────────────┐
                │  uv run zava import-domain   │  Phase 2.
                │  <bundle-path>               │
                └──────────────┬───────────────┘
                               │
                               ▼ Phase 1 (the receiver — what makes this safe)
                ┌──────────────────────────────────────────────────────────┐
                │  ZAVA SUBSTRATE                                          │
                │  ─────────────                                           │
                │  1A graduate.sh / domain-registration idempotency        │
                │  1B tools manifest loader supports providers/shared/     │
                │     domains layering                                     │
                │  1C authority/gate derivation moved server-side          │
                │  1D bundle provenance + idempotent re-import             │
                └──────────────┬───────────────────────────────────────────┘
                               │
                               ▼ Phase 3 — Phase 0 spike
                ┌──────────────────────────────────────────────────────────┐
                │  Manual TL→Zava translation of ONE real SPEC             │
                │  See what survives, what bleeds, where the bundle needs  │
                │  shape changes. THIS RUNS FIRST.                         │
                └──────────────────────────────────────────────────────────┘
                               │
                               ▼ Phase 4 — paste-compat (so a TL-built agent can call Zava)
                ┌──────────────────────────────────────────────────────────┐
                │  Substrate paste-compat (subset of old foundry plan)      │
                │  Governance factory + at least the mocks the import      │
                │  fixture actually depends on (not all 18)                │
                └──────────────────────────────────────────────────────────┘
```

## Acceptance bar (the whole plan)

The plan is done when **all three** of these work:

1. **Import smoke** (Phase 1–4): `uv run zava import-domain tests/fixtures/threadlight/<example>/bundle/` produces a working Zava domain. After server restart the domain appears in `/api/blueprint/composition`, accepts injections via `POST /api/simulator/<example>`, surfaces in Fleet Manager filters, and renders HITL gates in the Drawer with authority resolution working.

2. **Foundry paste-compat smoke** (Phase 4): the `foundry-agt/references/maf-middleware-snippet.py:build_governed_agent(...)` snippet pasted into a new file under `api/server/agents/` runs without our wrapper rejecting the call shape. The `foundry-mcp-aca` § "Bicep: ACA for MCP Server" snippet drops into `infra/modules/aca-mcp.bicep` with only resource-name edits. **Note:** "all mocks speak MCP" is NOT in the acceptance bar — only the mocks the import fixture exercises.

3. **End-to-end portability** (Phase 5): `threadlight-design` produces a SPEC for a new vertical. `threadlight-to-zava` consumes it and emits a Domain Bundle. `zava import-domain` materialises it. Within one working session: brief → SPEC → Zava domain → running workflow with HITL gate.

## Decision log

- 2026-06-09: Drawer-only for imported HITL gates. No Teams integration.
- 2026-06-09: Rewrite the foundry-substrate-unification plan to fold portability adapters in. Old plan superseded.
- 2026-06-09: Don't entangle Kratos — keep it as a separate product.
- 2026-06-09: Build the Zava receiver before the threadlight skill — BUT prove the shape with a manual translation spike first (Phase 0).
- 2026-06-09: Tools manifest split is layered (providers/shared/domains), not per-domain.
- 2026-06-09: Gate derivation moves server-side (`POST /api/authority/resolve-for-workflow`), not data-driven in React.

---

## Phase 0 — Manual TL→Zava translation spike

**Duration:** 2–3 days, NOT a phase to land in code.
**Goal.** Pick one real Threadlight SPEC and manually translate it to a draft Zava Domain Bundle. Find out where the mapping leaks before hardening the receiver around assumptions.

**Why first.** "Build the receiver before the sender" is right for production sequencing, wrong for discovery. If the receiver's shape is dictated by what TL actually produces, we need to see one real TL output first. Skipping this risks a Phase 1–2 that ships, then collapses in Phase 4 when reality bites.

**Tasks:**
- [ ] 0.1 Pick a TL SPEC. Options: (a) one of the threadlight-design `references/domain-primers/fsi-kyc-aml.md` worked output, (b) generate one via `threadlight-design` against a synthetic brief, (c) ask GBB for a real engagement's SPEC.md if any are non-confidential.
- [ ] 0.2 Hand-translate it into the proposed Domain Bundle shape (Phase 2.1 schema as currently drafted).
- [ ] 0.3 Write a "translation notes" file recording: every TL SPEC section, where it landed (or didn't) in the bundle, every field that needed invention, every field that was lost. Save as `docs/superpowers/specs/2026-06-XX-threadlight-spike-notes.md`.
- [ ] 0.4 Identify mandatory schema changes to either the Zava brief.yaml OR the proposed Domain Bundle format. Update Phase 1.B and Phase 2.1 task definitions BEFORE starting them.
- [ ] 0.5 Identify SPEC sections that demand an upstream change (e.g. need a structured `spec.json` rather than parsing markdown). Open an upstream issue against `aiappsgbb/threadlight-skills`.

**Exit criteria:**
- One TL SPEC manually translated to a valid (per current schema) Domain Bundle, OR a documented list of required schema changes that prevent translation.
- Decision: do we depend on an upstream `spec.json` (Phase 4.1) or do we ship a markdown parser as primary?

---

## Phase 1 — Stabilise the Zava receiver (split into 1A/1B/1C/1D)

**Overall goal.** Make Zava's domain composition surface stable enough to receive an external bundle without hand-stitching. Each sub-phase is a separate PR.

**Why split.** v1 of this plan bundled all of 1A–1D into one ~2-week phase. The duck (correctly) flagged this as 4–6 weeks of work. Splitting lets each PR land independently, reduces conflict risk, and gives faster feedback.

### Phase 1A — graduate.sh + domain-registration idempotency

**Duration estimate.** 1.5 weeks.

**Why first inside Phase 1.** Today, adding a domain runs through `compose-domain` + `graduate.sh` which touches 12 files in the live tree — 4 reliably patched, 8 hand-stitched (see [add-domain skill](/.github/skills/add-domain/SKILL.md) §"Known regressions"). Two regressions (KR-1: spawn helper missing `upsert_workflow`; KR-2: HITL `external_event` must byte-match persona frontmatter) silently break new domains. An importer that calls this surface inherits all those failure modes. Until graduate.sh is reliable, nothing downstream is safe.

#### Task 1A.1: Fix KR-1 — spawn helper missing `upsert_workflow`

**Files:**
- Modify: `docs/superpowers/skills/compose-domain/sub-skills/author-domain-skeleton/` — generator template for the spawn helper now includes `app_state.store.upsert_workflow(w)` and imports `build_fleet_<wt_snake>_workflow` from `synthetic_data`
- Modify: `api/server/services/synthetic_data.py` — add a generic `build_workflow_for_domain(workflow_type, workflow_id, record=None)` helper that derives the first phase name + display name from `DOMAINS[workflow_type]`, removing the per-domain `build_fleet_<x>_workflow` proliferation
- Modify: `graduate.sh` — patch step 5 to emit the fixed shape, OR strip step 5 entirely and let `author-domain-skeleton` codegen carry the helper
- Add: `tests/scripts/test_graduate_smoke.py` — graduate a throwaway brief, assert the resulting workflow upserts on injection

**Tasks:**
- [ ] 1A.1.1 Add `build_workflow_for_domain(...)` to `synthetic_data.py` driven by `DOMAINS` registry
- [ ] 1A.1.2 Update generator template in `author-domain-skeleton`
- [ ] 1A.1.3 Decide: fix `graduate.sh` step 5 OR remove it (write conclusion in PR description)
- [ ] 1A.1.4 Add smoke test
- [ ] 1A.1.5 Re-graduate one existing domain (say `purchase-card`) and diff against current — should be byte-identical or strictly improved

#### Task 1A.2: Fix the hand-stitched rows 5–9 (blueprint_inventory, constants, functions, ambient agents, domains.py)

**Files:**
- Modify: `graduate.sh` step 7 — remove dependence on the dead `"Procurement"` marker; patch `_PHASE_ALIASES` in `blueprint_inventory.py` by appending a new dict entry
- Modify: `graduate.sh` steps 8, 9, 10 — make each idempotent and re-runnable; don't `set -e` across the whole script; handle per-step failures with explicit error messages
- Modify: `api/shared/domains.py` — accept registration via `Domain.register(workflow_type=…)` decorator OR provide a `scripts/register_domain.py <bundle>` helper that programmatically appends to the file with sentinel markers
- Add: `tests/scripts/test_graduate_full_stitch.py` — graduate a brand-new throwaway brief end-to-end; assert all 12 files are patched

**Tasks:**
- [ ] 1A.2.1 Audit `graduate.sh` for every `set -e` and every grep-for-marker; replace with idempotent shell or move to a Python `scripts/graduate.py`
- [ ] 1A.2.2 Add sentinel markers (`# === BEGIN compose-domain <name> ===` / `# === END compose-domain <name> ===`) to every file the script patches; use them for re-import / removal later
- [ ] 1A.2.3 Build the end-to-end smoke test
- [ ] 1A.2.4 Document the 12-row stitch (now reduced) in `docs/ARCHITECTURE.md` §"How a new domain lands" — replaces the regressions block in the skill file

#### Task 1A.3: Fix KR-2 — HITL `external_event` byte-match enforcement

**Files:**
- Modify: `docs/superpowers/skills/compose-domain/sub-skills/author-domain-skeleton/SKILL.md` — for any HITL phase that names `persona: <role>`, read `api/server/personae/<role>/SKILL.md` frontmatter and stamp the exact `external_event:` into the generated brief
- Modify: graduate.sh — validate the brief at graduate-time and reject if `external_event` mismatches the persona's frontmatter
- Add: `tests/api/scripts/test_graduate_validates_external_event.py`

**Tasks:**
- [ ] 1A.3.1 Build a `validate_brief()` function that loads persona frontmatter for every HITL phase and asserts match
- [ ] 1A.3.2 Wire into graduate.sh as a pre-flight check (fail fast with a clear error)
- [ ] 1A.3.3 Test with a deliberately-mismatched brief

#### Task 1A.4: Removal semantics

**Why.** A bundle that imports cleanly should also remove cleanly. Sentinel markers from 1A.2.2 enable this. Spec the removal flow now even if the CLI flag lands in Phase 2.

**Tasks:**
- [ ] 1A.4.1 Define removal: which artefacts are physically deleted, which leave a "graveyard" entry, which require restart
- [ ] 1A.4.2 Manual smoke: graduate a domain, then remove it, then re-graduate. Assert no residue.

**Phase 1A exit gate:**
- [ ] Graduate a fictitious domain via the script only (no hand-edits); restart; domain appears everywhere
- [ ] Remove via the `--remove` flag (or manual sentinel-marker delete); clean removal
- [ ] PR merged

### Phase 1B — Tools manifest loader supports layered `tools.d/` (providers/shared/domains)

**Duration estimate.** 1 week.

**Why this layering and not per-domain.** The current `tools.yaml` has 58 tools (26 finance + 21 shared + 8 hiring + 3 creative) organized by `scope_function`, NOT by domain. Many tools (e.g. `authority.resolve_approver`, `lesson.*`) are used by multiple domains. Forcing a "one domain owns this tool" split would either duplicate definitions (causing duplicate-id errors) or arbitrarily assign ownership (losing cross-domain reuse). The duck called this out as "wrong first split" and was correct.

**Target shape:**

```
data/policies/tools.d/
  _shared.yaml                  # authority.*, lesson.*, kernel.*, governance.*
  providers/
    concur.yaml                 # concur.* (called by expense-claim, travel-preapproval, ...)
    workday.yaml                # workday.* (called by hiring, employee-onboarding, perf-review, ...)
    d365.yaml                   # d365.* (finance plane)
    contract_repository.yaml
    sap.yaml
    dynamics.yaml
    ...
  domains/
    purchase-card.yaml          # ONLY truly domain-local tools (rare)
    vendor-kyc.yaml             # (rare)
    ...
```

**Bundle declarations carry tool dependencies, not tool definitions.** An imported bundle says `depends_on_tools: [concur.search_claims, authority.resolve_approver, ...]` and the importer validates those tools exist in the manifest. New tools introduced by the bundle land in `domains/<wt>.yaml` (rare) or, if they're shared, an explicit operator decision moves them to `providers/` or `_shared.yaml`.

#### Task 1B.1: Loader supports `tools.d/` with merge semantics

**Files:**
- Modify: `api/server/services/governance/manifest.py` — load all `tools.d/**/*.yaml`, dedupe by `id`, error on conflict
- Keep: `data/policies/tools.yaml` UNCHANGED in this task. Loader reads both and merges. This is intentional — migration happens in 1B.2.
- Add: `tests/api/services/governance/test_manifest_layered.py` — covers single-file (back-compat), multi-file (new), conflict detection

**Tasks:**
- [ ] 1B.1.1 Implement glob loader + merge
- [ ] 1B.1.2 Add tests
- [ ] 1B.1.3 Verify existing 38 domains still load via the unchanged tools.yaml

#### Task 1B.2: Migrate existing tools.yaml to layered files

**Files:**
- Create: 1× `_shared.yaml` + N× `providers/<provider>.yaml` (count derived from existing prefixes)
- Modify: `data/policies/tools.yaml` → keep as a thin shim that the loader still reads but contains zero tool entries (just a banner directing operators to `tools.d/`)
- Run: `REGEN_GOLDEN=1` to refresh AGT policy snapshots

**Tasks:**
- [ ] 1B.2.1 Categorise each of the 58 tools: shared / provider / domain-local. Document categorisation in the PR.
- [ ] 1B.2.2 Write `scripts/migrate_tools_yaml.py` that does the split mechanically
- [ ] 1B.2.3 Run migration; commit as a single atomic change
- [ ] 1B.2.4 Regen AGT snapshots
- [ ] 1B.2.5 Verify all 38 existing domains still pass their AGT bundle smoke

#### Task 1B.3: Bundle tool-dependency contract

**Files:**
- Modify: Domain Bundle schema (defined in Phase 2.1) to require `depends_on_tools: [tool_id, ...]`
- Modify: `manifest.py` to expose a `validate_dependencies(declared_tool_ids: list[str])` check

**Tasks:**
- [ ] 1B.3.1 Define the dependency-resolution algorithm
- [ ] 1B.3.2 Test missing-tool and version-mismatch scenarios

**Phase 1B exit gate:**
- [ ] Loader supports both legacy single-file AND layered files
- [ ] All 58 tools migrated; tools.yaml is empty (or near-empty)
- [ ] AGT snapshots regenerated; CI green
- [ ] PR merged

### Phase 1C — Authority/gate derivation moved server-side

**Duration estimate.** 1.5 weeks.

**Why server-side, not data-drive in React.** `web/client/components/apex/AuthorityCard.tsx:deriveMatrixRequest()` is ~150 lines of per-workflow-type derivation: payload JSONPath traversal, category inference from scenario strings, value derivation. The v1 draft of this plan said "data-drive in React via a hook" — that would either require a JSONPath evaluator in React (heavy, fragile) or a sea of per-workflow data files that mirror the existing switch case (no improvement). The duck (correctly) recommended moving the derivation server-side. Frontend becomes a thin renderer of the resolved authority result.

#### Task 1C.1: Build `POST /api/authority/resolve-for-workflow` endpoint

**Files:**
- Create: `api/server/routes/authority.py` — new endpoint that takes `{workflow_id: str}` and returns `{action: str, category: str, value: float | null, matrix_rule_id: str, approver_chain: [...]}`
- Create: `api/server/services/authority/derivation.py` — port the existing TS `deriveMatrixRequest()` to Python, working off the in-memory workflow store
- Add: `tests/api/server/routes/test_authority_resolve.py` — covers all 14+ existing workflow types currently in the TS switch case
- Modify: `web/client/components/apex/AuthorityCard.tsx` — replace `deriveMatrixRequest(w)` call with `useAuthorityResolution(w.id)` hook that fetches the endpoint

**Tasks:**
- [ ] 1C.1.1 Port the 14+ workflow-type-specific derivation blocks from TS to Python; one test per workflow type proving equivalence
- [ ] 1C.1.2 Add the endpoint with TTL caching (authority resolution doesn't change mid-workflow)
- [ ] 1C.1.3 Replace React-side derivation with a hook
- [ ] 1C.1.4 Manual smoke: every existing domain's AuthorityCard renders identically before/after
- [ ] 1C.1.5 Stretch: write a Playwright suite covering AuthorityCard per workflow type if one doesn't exist

#### Task 1C.2: Add gate-definition slot in the brief

**Why.** Once derivation is server-side, the per-domain logic CAN be data-driven without React-side complexity. Add a `gates:` block to the brief schema where each gate declares its derivation rules.

**Files:**
- Modify: `docs/superpowers/skills/compose-domain/brief.schema.yaml` — add a `gates:` block per HITL phase
- Modify: `api/server/services/authority/derivation.py` — when a workflow's domain has gate definitions in the brief, use those; else fall back to the hardcoded logic. New domains use the new path.
- Add: `tests/api/services/authority/test_brief_driven_derivation.py`

**Tasks:**
- [ ] 1C.2.1 Define gate-definition schema (action template, category-derivation rule with JSONPath, value-derivation rule)
- [ ] 1C.2.2 Implement the brief-driven path in `derivation.py`
- [ ] 1C.2.3 Migrate ONE existing domain (say `purchase-card`) to use brief-driven gates as a smoke test. Don't migrate all 14 — that's a separate backlog item.

**Phase 1C exit gate:**
- [ ] All existing domains' AuthorityCard renders identically (no UI change)
- [ ] Derivation runs server-side
- [ ] New domains CAN declare gates in the brief; one existing domain migrated as proof
- [ ] PR merged

### Phase 1D — Bundle provenance + idempotent re-import

**Duration estimate.** 0.5 weeks.

**Why last in Phase 1.** Needs the receiver work (1A) and the layered manifest (1B) to be stable before provenance can attach to a real bundle landing.

#### Task 1D.1: Provenance lives in `bundle.yaml`, not a separate SOURCE.md

**Why.** Duck flagged the duplication. A `bundle.yaml` top-level `source:` block is single-source-of-truth.

**Files:**
- Create: `data/workflow-types/<wt>/PROVENANCE.yaml` — copy of the imported bundle's `source:` block, written by `zava import-domain`
- Modify: `api/shared/domains.py` `Domain` dataclass → carry an optional `source: DomainSource | None` field
- Add: `api/server/routes/admin/domains.py` `GET /api/admin/domains/<wt>/provenance` → reads PROVENANCE.yaml
- Add: `tests/api/server/routes/test_domain_provenance.py`

**Tasks:**
- [ ] 1D.1.1 Define provenance schema (origin SPEC path, spec_hash, importer version, bundle_format_version, last_imported_at, importer_run_id)
- [ ] 1D.1.2 Existing 38 hand-authored domains get a stub `PROVENANCE.yaml` that says `origin: hand_authored`
- [ ] 1D.1.3 Add admin route + test

#### Task 1D.2: Idempotent re-import semantics

**Why.** Operator runs `zava import-domain` on a bundle whose `workflow_type` already exists. Behaviour must be predictable.

**Tasks:**
- [ ] 1D.2.1 Define behaviour matrix: existing-and-newer / existing-and-older / existing-and-same-hash / `--force`. Document in `docs/zava-domain-bundle.md`.
- [ ] 1D.2.2 Implement in the CLI (Phase 2.2 — flag the dependency)

**Phase 1D exit gate:**
- [ ] Every domain has a PROVENANCE.yaml
- [ ] Admin endpoint returns the right one per `wt`
- [ ] Re-import semantics documented; CLI implementation deferred to Phase 2

---

## Phase 2 — Zava Domain Bundle format + `zava import-domain` CLI

**Goal.** Define the canonical on-disk format an importer drops in, and the CLI that materialises it into the live tree.

**Why now.** Phase 1 made the receiver safe. Phase 2 gives it a documented input contract.

### Task 2.1: Define the Zava Domain Bundle format

**Files:**
- Create: `docs/superpowers/specs/zava-domain-bundle.schema.yaml` — canonical schema
- Create: `docs/zava-domain-bundle.md` — operator-facing format reference

**Minimum viable bundle:**

```
<bundle>/
  bundle.yaml      # REQUIRED: format-version, source, depends_on, depends_on_tools
  brief.yaml       # REQUIRED: full compose-domain v4 brief (re-uses existing schema)
```

**Optional slices:**

```
<bundle>/
  tools.yaml       # New tool definitions ONLY. Drops into tools.d/domains/<wt>.yaml
  policies/        # AGT policy snippet overrides (rare)
  fixtures/        # Seed JSON for synthetic_data.py
  personae/        # New personae (SKILL.md + stub response handler)
```

**`bundle.yaml` shape:**

```yaml
format_version: 1                       # Phase 2.1; bumps on breaking schema change
zava_min_version: "2026.6.0"            # rejects on older Zava
threadlight_spec_version: "0.4.0"       # if origin is TL; informational
source:
  origin: threadlight | hand_authored | kratos | other
  spec_path: specs/SPEC.md              # relative to engagement repo
  spec_hash: sha256:abc123...
  importer_version: "0.1.0"
  imported_at: "2026-06-09T10:30:00Z"
  importer_run_id: uuid
depends_on:
  - other_workflow_type                 # rare; for cross-domain orchestration
depends_on_tools:
  - authority.resolve_approver
  - concur.search_claims
  - lesson.list
```

**Tasks:**
- [ ] 2.1.1 Draft the schema. Re-use `brief.schema.yaml` shape for the `brief.yaml` slot. Update based on Phase 0 spike findings.
- [ ] 2.1.2 Write the operator doc with two worked examples (one minimal: bundle.yaml + brief.yaml only; one full-featured: all optional slices)
- [ ] 2.1.3 Bundle the existing `purchase-card` domain into this format as the reference example. Lives at `tests/fixtures/bundles/purchase-card/`.

**Verify:** Schema validates the reference example.

### Task 2.2: Collision and upgrade semantics

**Why.** Bundles can collide with existing state on: `workflow_type`, tool IDs, persona roles, external events, matrix actions, workflow ID prefixes. Define behaviour before writing the CLI.

**Tasks:**
- [ ] 2.2.1 Behaviour matrix for each collision class. Document in `docs/zava-domain-bundle.md` §Collisions.
- [ ] 2.2.2 Defaults: workflow_type collision → reject without `--force`; tool ID collision → reject always (operator must rename in bundle); persona collision → reject without `--force` (overwriting personae is dangerous); external_event collision → warn, allow (events are namespaced by workflow_type at runtime); workflow ID prefix collision → reject without `--force`.

### Task 2.3: `uv run zava import-domain <bundle-path>` CLI

**Files:**
- Create: `scripts/zava_cli/__init__.py`
- Create: `scripts/zava_cli/import_domain.py`
- Modify: `pyproject.toml` — `[project.scripts]` entry: `zava = "scripts.zava_cli:main"`
- Add: `tests/scripts/zava_cli/test_import_domain.py`

**CLI behaviour:**
- Validate bundle against schema (uses Phase 2.1 schema)
- Check `zava_min_version` against current Zava version
- Validate `depends_on_tools` against the merged manifest (uses Phase 1B.3 dependency contract)
- Apply collision policy (Phase 2.2)
- Copy slices into the live tree (uses Phase 1A's sentinel markers for clean removal later)
- Write `PROVENANCE.yaml` (Phase 1D.1)
- Invoke the (now-fixed) `graduate.sh` programmatically
- Hot-reload AGT (or print "restart required" if the deltas need it)
- Exit 0 on success; non-zero with a structured error report on failure

**Tasks:**
- [ ] 2.3.1 Implement the CLI
- [ ] 2.3.2 Add `--dry-run` flag (prints what would happen, touches nothing)
- [ ] 2.3.3 Add `--force` and `--remove <wt>` flags
- [ ] 2.3.4 Test against the `purchase-card` bundle from Task 2.1.3 → produces a byte-identical-or-better materialisation vs the hand-authored version
- [ ] 2.3.5 Test failure modes: malformed bundle, missing dependency, name collision without `--force`, `zava_min_version` mismatch

**Verify:** End-to-end: drop the `purchase-card` bundle into a scratch workspace, `zava import-domain` it, restart server, hit `/api/simulator/purchase-card`, workflow runs to completion.

### Phase 2 exit gate

- [ ] Bundle schema documented + validated
- [ ] Collision semantics defined and enforced
- [ ] CLI green across happy + failure paths
- [ ] One real domain (`purchase-card`) round-trips bundle ⇄ materialised

---

## Phase 3 — Foundry paste-compat (subset of old foundry plan)

**Goal.** A threadlight-built agent calling Zava's tools works without hand-wiring. This is the "you can use Zava's tools from outside Zava" half of the integration.

**Scope discipline.** Only the parts of the old foundry plan that are on the portability critical path. The old plan's Phases A (deps), C (model bump), E (observability), F (tenant preflight) move to a separate "substrate parity backlog" tracker (see [old plan](2026-05-27-foundry-substrate-unification.md) for the detail).

### Task 3.1: `create_governance_middleware()` factory + `build_governed_agent()`

**Why.** Threadlight code uses these factory shapes. Without them, a threadlight-built agent that wants Zava's governance has to know Zava's internal kernel API. With them, `build_governed_agent(client, instructions, tools, policy_dir=...)` from threadlight pastes into Zava unchanged.

**Files (lifted from old plan Phase B):**
- Create: `api/server/services/governance/middleware.py` → `create_governance_middleware(policy_dir, ...)` factory mirroring upstream AGT surface for GHCP
- Create: `api/server/services/governance/build_governed_agent.py` → `build_governed_agent(client, instructions, tools, policy_dir)` paste-compatible with `foundry-agt` snippet
- Modify: `api/server/services/governance/permission_handler.py` → delegate to new `middleware.py` factory rather than calling kernel directly. Keep the GHCP-SDK `PermissionRequest` signature.
- Add: `tests/api/services/governance/test_middleware.py` — factory contract tests
- Add: `tests/api/services/governance/test_paste_compat.py` — literally paste the `foundry-agt/references/maf-middleware-snippet.py` snippet into a test fixture; assert it imports and runs

**Tasks:**
- [ ] 3.1.1 Read [`agent_os.policies`](https://github.com/aiappsgbb/agent-governance-toolkit) v3.6.0 source for the canonical factory signature (re-verify before starting — re-plan trigger if shape moved)
- [ ] 3.1.2 Write `middleware.py` factory that wraps existing kernel
- [ ] 3.1.3 Write `build_governed_agent.py`
- [ ] 3.1.4 Refactor `permission_handler.py` to use new factory; verify no behaviour change
- [ ] 3.1.5 Add paste-compat test
- [ ] 3.1.6 Document the public surface in `docs/ARCHITECTURE.md` §"Governance factory surface"

### Task 3.2: MCP-on-ACA, scoped to the import-fixture's actual dependencies

**Why this scoping.** Migrating all 18+ mocks to MCP streamable-http is real work and not on the critical path for the portability story. What IS on the critical path: the mocks that the Phase 4–5 end-to-end import fixture exercises must speak MCP, because that's what makes the acceptance bar honest.

**MCP migration matrix (filled in after Phase 0 spike):**

| Mock provider | Legacy HTTP | MCP `/mcp` | Used by import smoke? | Required before Phase 5? |
|---|---|---|---|---|
| concur-mcp | ✅ | ⏳ Task 3.2.2 | (depends on Phase 0 fixture) | tbd |
| workday-mcp | ✅ | ❌ | tbd | tbd |
| d365-mcp | ✅ | ❌ | tbd | tbd |
| ... | | | | |

**Files:**
- Create: `mocks/_mcp_protocol/server.py` — shared FastMCP wrapper exposing `initialize`, `notifications/initialized`, `tools/list`, `prompts/list`, `resources/list`, `logging/setLevel` on `/mcp` + `/health`
- Create: `mocks/concur-mcp/mcp_server.py` — reference implementation (concur mock as FastMCP)
- Create: `mocks/concur-mcp/Dockerfile` — Linux/amd64, port 8080, uv-installed
- Keep: existing `mocks/concur-mcp/server.js` under `MCP_TRANSPORT=local` for legacy local-mode
- Add: `tests/mocks/test_mcp_protocol_compliance.py` — all 6 JSON-RPC methods return 200 on the reference mock
- Modify: `infra/modules/aca-mcp.bicep` (create if needed) — paste-compat with `foundry-mcp-aca` § "Bicep: ACA for MCP Server"

**Tasks:**
- [ ] 3.2.1 Build the shared `_mcp_protocol/server.py` (uses `fastmcp>=2.0.0,<3.0.0`)
- [ ] 3.2.2 Ship `concur-mcp` as the reference; both new MCP shape AND existing Node server work side-by-side
- [ ] 3.2.3 Wire compliance test in CI
- [ ] 3.2.4 After Phase 0 fixture is chosen, fill in the migration matrix and migrate only the mocks the fixture needs
- [ ] 3.2.5 Document the migration playbook in `docs/runtime-providers.md` so the remaining mocks can be migrated later, by anyone

**Important:** the acceptance bar for Phase 3 does NOT include "all 18 mocks migrated". It includes "every mock the Phase 5 fixture depends on speaks MCP". The remaining mocks stay legacy until a real customer hits them.

### Phase 3 exit gate

- [ ] Factory paste-compat green (acceptance bar #2 of the old plan)
- [ ] At least one mock speaks MCP streamable-http on `/mcp` + `/health` (the reference)
- [ ] Every mock the Phase 5 fixture exercises speaks MCP
- [ ] Acceptance bar items #1 (governance) and #4 (Bicep) of the old plan satisfied

---

## Phase 4 — TL → Zava translator library (inside Zava)

**Goal.** A pure-Python module inside Zava that reads threadlight outputs and emits a Zava Domain Bundle. Testable standalone. The Phase 5 skill is a thin wrapper around this.

**Package path:** `api/server/importers/threadlight/` (not `import/` — Python keyword).

### Task 4.1: Negotiate machine-readable SPEC.json upstream

**Why.** Parsing markdown sections of SPEC.md is fragile. Any drift in numbering, table shape, or prose wording breaks import. The duck (correctly) recommended pushing upstream for a `specs/spec.json` emitted by `threadlight-design` alongside `SPEC.md`.

**Tasks:**
- [ ] 4.1.1 Open an issue against `aiappsgbb/threadlight-skills`: "Emit `specs/spec.json` alongside SPEC.md for downstream consumers." Spec the JSON shape (mirror SPEC.md sections: business_rules, data_models, tool_contracts, hitl_gates, triggers, workspace_declaration, eval_scenarios).
- [ ] 4.1.2 If upstream agrees: contribute the spec.json emitter to `threadlight-design`. Then Phase 4.2 consumes JSON.
- [ ] 4.1.3 If upstream declines or is slow: build a markdown parser as primary AND lobby for spec.json as a v2 enhancement. Mark this as a re-plan trigger in §Re-plan triggers.

### Task 4.2: SPEC → brief.yaml mapping (driven by Phase 0 findings)

**Mapping table** (refined after Phase 0 spike):

| TL SPEC section | Zava brief section | Notes / loss |
|---|---|---|
| § 1 process overview | `domain.description` | Free text |
| § 2 business rules (BR-XXX) | mostly `decisions[].attributes_from_context` + AGT policy snippets; some bleed into prose | LOSSY — see §Risk: BR translation |
| § 3 personae | `phases[].persona` + scaffold new `api/server/personae/<role>/` | OK; closes loop with Phase 1A.3 validation |
| § 4 data models | `entities[]` + fixtures | OK; system-of-record annotations preserved |
| § 5 system integrations | `phases[].external_systems` + `bundle.yaml depends_on_tools` | OK |
| § 6 tool contracts | New tool defs to `tools.yaml` slice; existing tools to `depends_on_tools` | Must derive `reversible`, `value_field`, `scope_function` — heuristic, may need operator confirmation |
| § 7 agent invocation contract | `phases[].kind = agent` + `agent_skill_name` | OK |
| § 8 HITL action gates | `phases[].kind = hitl` + `gates:` block in brief | LOSSY — see §HITL loss table |
| § 9 eval scenarios | Punt to fixtures-only in v1. Phase 6 maps to dream-pass scenarios. | DEFERRED |
| § 10 / 10b triggers | `function.ambient` block | OK for ACA-job style; Functions-style needs adapter |
| § 11c tech-stack selectors | `bundle.yaml runtime_hints` (informational only) | LOSSY — Zava substrate fixed, hints are advisory |

**Files:**
- Create: `api/server/importers/__init__.py`
- Create: `api/server/importers/threadlight/__init__.py`
- Create: `api/server/importers/threadlight/spec_parser.py` — if Task 4.1 went the markdown route, parses `specs/SPEC.md` into a typed IR
- Create: `api/server/importers/threadlight/json_parser.py` — if Task 4.1 went the JSON route, parses `specs/spec.json` into the same IR
- Create: `api/server/importers/threadlight/manifest_parser.py` — parses `specs/manifest.json`
- Create: `api/server/importers/threadlight/translator.py` — IR → Zava Domain Bundle
- Add: `tests/api/server/importers/threadlight/test_spec_parser.py`
- Add: `tests/api/server/importers/threadlight/test_translator.py`
- Add: `tests/api/server/importers/threadlight/fixtures/` — at least 3 real-shape TL `specs/` examples

**Tasks:**
- [ ] 4.2.1 Build the typed IR (one Pydantic model per SPEC section)
- [ ] 4.2.2 Build the JSON parser (if 4.1 went that way) OR markdown parser
- [ ] 4.2.3 Build the translator — one section's mapping at a time, each with a test
- [ ] 4.2.4 Translator outputs warnings (not errors) for fields it can't translate — surfaces to the operator as a `import-warnings.md` in the bundle
- [ ] 4.2.5 Persona scaffolding: when a SPEC names a persona that doesn't exist in Zava, emit a stub `personae/<role>/SKILL.md` with the right `external_event:` frontmatter (closes the loop with Phase 1A.3 validation)
- [ ] 4.2.6 HITL gate translation: per the HITL loss table, mark unsupported gate types as warnings

### Task 4.3: End-to-end integration test (TL spec → running Zava domain)

**Files:**
- Add: `tests/integration/test_threadlight_import_e2e.py`
  - Fixture: a complete TL `specs/` directory for a small use case (Phase 0 spike output)
  - Steps: translator → bundle → `zava import-domain` → server restart (via fixture) → injection → workflow runs to completion → HITL gate fires → Drawer renders authority resolution

**Tasks:**
- [ ] 4.3.1 Wire the test
- [ ] 4.3.2 Document the worked example end-to-end in `docs/threadlight-import.md`

### Phase 4 exit gate

- [ ] SPEC.json upstream decision made (4.1)
- [ ] Translator handles 3+ real TL specs without manual intervention
- [ ] E2E integration test green
- [ ] `import-warnings.md` honestly reports lost fields

---

## Phase 5 — `threadlight-to-zava` skill

**Goal.** Public skill in `aiappsgbb/threadlight-skills` that calls into the Phase 4 translator. Closes the loop for TL users.

### Task 5.1: Skill scaffold + upstream PR

**Files (upstream, in `aiappsgbb/threadlight-skills`):**
- `skills/threadlight-to-zava/SKILL.md` — the skill contract (when to invoke, inputs, outputs, gotchas)
- `skills/threadlight-to-zava/references/zava-domain-bundle.md` — copy of Zava's bundle schema doc
- `skills/threadlight-to-zava/references/hitl-loss-table.md` — what behaviour is lost vs Teams cards

**Behaviour:**
- Reads `specs/spec.json` (preferred) or `specs/SPEC.md` (fallback) + `specs/manifest.json`
- Calls into the Zava translator: subprocess into a checked-out Zava `uv run python -m api.server.importers.threadlight`
- Writes the bundle to `./out/zava-domain-bundle/` by default
- Prints next-step instructions: "Drop this bundle into a Zava deployment via `uv run zava import-domain ./out/zava-domain-bundle/`"

**Tasks:**
- [ ] 5.1.1 Author the SKILL.md (follow the existing 8-skill style)
- [ ] 5.1.2 Document subprocess invocation (Zava-checkout-required pattern)
- [ ] 5.1.3 PR to upstream
- [ ] 5.1.4 Add an end-to-end demo recording (asciinema or equivalent)

### Task 5.2: Discoverability + docs

- [ ] 5.2.1 Update `aiappsgbb/threadlight-skills/README.md` table — add the 9th skill
- [ ] 5.2.2 Update `aiappsgbb/threadlight-skills/THREADLIGHT.md` chain diagram
- [ ] 5.2.3 Update Zava `docs/README.md` and `README.md` — "Importing a threadlight use case" section
- [ ] 5.2.4 Update Zava `docs/ARCHITECTURE.md` — new §15 on the import surface

### Phase 5 exit gate

- [ ] Skill PR merged upstream
- [ ] End-to-end demo: `threadlight-design` → `threadlight-to-zava` → `zava import-domain` runs in a single working session with no hand-edits
- [ ] Public docs updated

---

## Phase 6 — Export (Zava → TL/Foundry hosted agent). DEFERRED.

**Why deferred.** The export direction surfaces an unresolved product question with three honest answers and no obvious winner:

1. **Crippled export** — ship the agent, drop substrate features (no dream-pass, no fleet bus, no replay). Cheapest, lowest fidelity.
2. **Hosted Zava-as-a-service backing** — exported agent calls back to a Zava SaaS for governance + memory. Max fidelity, biggest infra commitment.
3. **Embedded Zava-Lite library** — ship a thin substrate library inside the container. Middle ground.

Each is a different product. Don't scope until import is shipping and we have customer signal on which they want.

**Placeholder tasks:**
- [ ] 6.0.1 Decide: cripple / SaaS / embedded
- [ ] 6.0.2 Draft a separate plan once decided

---

## HITL loss table (what changes when an imported gate goes through Drawer-only)

| Threadlight feature | Zava v1 import behaviour |
|---|---|
| Teams Adaptive Card surface | Not imported. Renders in Drawer instead. |
| `approve` / `reject` / `signoff` gate kinds | Supported — map to existing Drawer gates |
| `edit-and-approve` | Partial — Drawer doesn't currently surface form-editing of payload. Imported gates of this kind get a warning. Operator can approve as-is or reject. |
| `escalate` | Supported via existing matrix escalation chains |
| `request-info` | Not supported in v1 — gate fires but no UI prompt for additional info. Marked as a warning. |
| `audit-view` | Not supported in v1 — read-only audit views go through existing Audit tile, not as a gate |
| SLA watcher + timeout escalation | Partial — Drawer has no per-gate SLA enforcement today. SLA fields in SPEC are recorded in PROVENANCE.yaml but not enforced. |
| Card-side action handler (Python code) | Imported, but only the input/output contract is preserved. Behaviour runs inside the Zava orchestrator pipeline. |
| Audit trail of who clicked what when | Supported — Drawer events flow through Zava's existing audit log |

**Documented in:** `docs/threadlight-import.md` §HITL behaviour.

---

## Cross-cutting concerns and risks

### Risk: tools.yaml refactor (Phase 1B) is a big surface change

**Mitigation.** Two-step migration. Step 1B.1 makes the loader support both layouts side-by-side. Step 1B.2 does the actual file split. If 1B.2 surfaces unexpected coupling, fall back: keep the monolithic tools.yaml, have the importer rewrite it in place. Either way the loader change in 1B.1 is forward-compatible.

### Risk: BR translation (SPEC § 2 business rules) is fundamentally lossy

**Mitigation.** Numbered business rules in TL SPECs are prose ("BR-007: Approvals over $10k require CFO signoff"). They translate to a mix of AGT policy rules, deterministic-phase logic, and operator-facing documentation. The translator emits warnings, not errors, for rules it can't crisply map. `import-warnings.md` becomes the operator's TODO list. v1 = the loop closes for the easy cases. v2 = chase the hard cases as real customers hit them.

### Risk: TL workspace UI (SPEC § 8b) doesn't import

**Mitigation.** Out of scope for v1 (documented in HITL loss table). TL's workspace UI is per-use-case; Zava's portal is global. They don't map. Operator sees the imported domain in Zava's existing Fleet Manager + Drawer; the TL workspace UI is left behind.

### Risk: Phase 0 spike reveals the bundle shape needs to change

**Mitigation.** This is BY DESIGN. Phase 0 exists precisely to let the bundle shape evolve before being baked into the receiver. Phase 1.B and 2.1 task definitions explicitly re-open after Phase 0 completes.

### Risk: AGT v3.6.0 factory shape moves before Phase 3.1 starts

**Mitigation.** Pinned in old plan to `agent-governance-toolkit==3.6.0`. Re-verify in Task 3.1.1; re-plan trigger if it has moved.

### Risk: Plan length itself

**Mitigation.** The original foundry plan was 71KB / 82 tasks / 0 shipped. This one is intentionally shorter (~40KB) and gated phase-by-phase with re-plan checkpoints AFTER 1A, 1B, 1C, 2, 3, 4. Each sub-phase ships as its own PR. If Phase 0 reveals a wrong premise, replan before sinking effort into Phase 1.

### Things explicitly NOT in this plan (track separately)

- Foundry observability three-layer wiring (old Phase E)
- Model defaults bump to gpt-5.4 (old Phase C)
- pyproject.toml dep stack realignment (old Phase A)
- Azure tenant isolation preflight (old Phase F)
- `respx` rewrite of `_HTTP_STUB_SKIP`-decorated delegated-authority tests
- `tests/api/services/dream_pass/test_orchestrator_events.py` stale-kwargs fix
- Dropping BC keys `flagged_lesson_ids` / `lessons_flagged: 0` after one release
- Node.js 20 → 24 deprecation in CI (deadline 2026-06-16)
- Archiving stale plan docs that have effectively shipped (memory-simplification, dreaming-sessions, replay)
- Migrating the other ~14 mocks to MCP streamable-http (Phase 3 ships only the ones the import fixture needs)

---

## Estimated timeline (calendar, working solo)

| Phase | Estimate | Risk |
|---|---|---|
| Phase 0 — manual translation spike | 2–3 days | Low (it's discovery, not implementation) |
| Phase 1A — graduate.sh idempotency | 1.5 weeks | Medium |
| Phase 1B — tools.d layered manifest | 1 week | Medium |
| Phase 1C — server-side authority derivation | 1.5 weeks | Medium-high (touches frontend + 14+ workflow types) |
| Phase 1D — provenance + re-import | 0.5 weeks | Low |
| Phase 2 — bundle format + CLI | 1 week | Low if Phase 1 went well |
| Phase 3 — substrate paste-compat (scoped) | 1 week | Medium (factory shape needs care) |
| Phase 4 — translator | 2 weeks | Medium (SPEC parsing is the unknown; spec.json upstream PR is a wildcard) |
| Phase 5 — skill + upstream PR | 0.5 weeks | Low (upstream review time outside our control) |
| **Total to "TL → Zava works end-to-end"** | **~10 weeks solo** | |
| Phase 6 — export | TBD | Defer |

Note: v1 of this plan estimated 7 weeks total. Duck pass added ~3 weeks of realism, almost all of it in Phase 1.

## Re-plan triggers

Stop and rewrite this plan if any of:

- Phase 0 reveals the bundle shape is fundamentally wrong (more than minor field additions)
- Phase 1A's graduate.sh hardening reveals the `compose-domain` skill itself needs a rewrite (rather than just bug fixes)
- Phase 1B reveals cross-domain coupling in tools.yaml that resists the providers/shared/domains split
- Phase 3.1 reveals AGT v3.6.0 factory shape has moved
- Phase 4.1 — upstream declines to add spec.json, AND markdown parsing turns out to be more than 1 week of work
- A customer comes in with a Teams-cards requirement that breaks the Drawer-only assumption
- Threadlight upstream changes the SPEC schema in a way that invalidates Phase 4 parsers
