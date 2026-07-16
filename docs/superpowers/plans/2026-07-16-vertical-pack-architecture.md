# Interchangeable Vertical Packs Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans`. Keep one active
> task, one focused test command, and one commit per boundary.

**Goal:** Agency remains the default experience; Telco loads explicitly; no
business asset from the inactive vertical appears in Functions, Blueprint,
worlds, projections, memory, recordings, governance, or UI.

**Architecture:** `VerticalRuntime` resolves one manifest at process start.
Existing registries remain the canonical declaration files but expose an
active-only view. Pack manifests own selection, assets, worlds, projections,
recordings, UI metadata, and Durable module loading.

**Baseline:** `origin/main` at `76e0e989`.

---

## Completed

| Task | Commit | Result |
|---|---|---|
| Contracts and loader | `61d2b02b` | Static Agency/Telco selection, validation, namespaced data |
| Transitional business views | `2ba1eef9` | Added active-only compatibility views before ownership inversion |
| Durable isolation | `6d62d545` | Functions imports only the selected vertical module |
| Runtime bootstrap | `cf7d1b43` | AppState, ramp, lifecycle, and storage use active runtime |
| Runtime assets | `af577247` | Worlds, responders, projections, memory isolated |
| Blueprint assets | `db3b0cda` | Domains, skills, MCPs, aliases, personae pack-scoped |
| Recordings | `7d14db5f` | Curated and captured replay pack-scoped |
| Runtime registry consolidation | `7c80ce36` | Removed transitional runtime copies; declarations still awaited pack ownership |
| Business registry ownership | `3e84298b` | Moved domains, functions, agents, authority, and personae into packs |
| Agency lifecycle isolation | `3cd2d256` | Moved Agency ambient startup and teardown behind its lifecycle |

Validated boundaries:

- shared/registry suite: 118 passed
- actor-world suite: 116 passed
- Agency runtime/world suite: 142 passed
- Telco bridge/projection suite: 13 passed
- Functions/validator suite: 73 passed
- namespaced storage suite: 40 passed
- Agency and Telco governance focused suites: passed

---

## Completion record

### Task A: Finish runtime-driven UI

**Status:** Complete in `ee215533`, `67de5141`, `a0bfe035`, and `956cc553`.

**Files:**

- `web/shared/runtime.ts`
- `web/client/hooks/useRuntimeManifest.ts`
- `web/client/components/feed/LeftRail.tsx`
- `web/client/routes/World.tsx`
- `web/client/routes/SupportWorld.tsx`
- `web/client/routes/TelcoWorldRoute.tsx`
- `web/blueprint/src/lib/types.ts`
- focused Vitest files

**Acceptance:**

- navigation comes from `/api/runtime` capabilities
- Agency with no world hides World and keeps Compose
- Telco shows World and hides Agency-only Compose
- World renderer comes from manifest lens, not snapshot inference
- Blueprint displays active vertical identity

**Verification:**

```bash
npx vitest run \
  web/client/hooks/__tests__/useRuntimeManifest.test.tsx \
  web/client/components/feed/__tests__/LeftRail.vertical.test.tsx \
  web/client/components/feed/__tests__/LeftRail.test.tsx \
  web/client/routes/__tests__/World.test.tsx \
  web/client/routes/__tests__/TelcoWorld.test.tsx
npm run build:blueprint
```

Commit: `feat(ui): render active vertical manifest`

### Task B: Remove remaining global fallbacks

**Status:** Complete in `3e84298b` and `3cd2d256`; final regression cleanup
lands with Task C.

**Scope:**

- make compose output target `verticals/<name>/`
- namespace compose tapes under `runtime.data_dir`
- remove obsolete profile/scanning compatibility code
- update active documentation paths

Do not add plugin discovery, host fingerprint negotiation, or new abstractions.
Both processes already select from the same required environment; prove that
in isolated launch scripts instead.

**Verification:**

```bash
PORTAL_DATA_DIR="$(mktemp -d)" .venv/bin/pytest \
  tests/api/shared \
  tests/docs/superpowers/skills/compose_domain \
  tests/api/server/services/test_blueprint_pack_isolation.py \
  tests/api/server/services/test_recording_pack_isolation.py -q
git diff --check
```

Commit: `refactor(verticals): remove global fallbacks`

### Task C: Prove and hand off

**Status:** Complete.

- focused Python: 199 passed / 1 skipped and 227 passed
- changed frontend: 51 passed
- Control Plane and Blueprint Vite builds: passed
- Agency support browser proof: passed with zero console/page errors
- Telco live proof: passed across network, care, happy order, HITL order,
  Memory, Knowledge, AG-UI, graph, Control Plane, and Constellation
- Telco replay-only proof: passed for all three Telco workflow types with
  Functions unreachable, actor world disabled, and zero browser errors
- all isolated proof ports released

1. Run focused Python and Vitest suites.
2. Build Control Plane and Blueprint.
3. Run isolated Agency proof.
4. Run existing isolated Telco live/replay proof.
5. Assert zero browser/page/application-network errors.
6. Stop exact process handles and verify all proof ports clear.
7. Review diff against the design and open a PR; never push directly to
   `main`.

Final static checks:

```bash
.venv/bin/ruff check api/shared/vertical*.py api/server/routes/runtime.py verticals
git diff --check
git status --short
```
