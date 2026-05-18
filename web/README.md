# `web/` — three React apps, one repo

This directory hosts three sibling React 19 + Vite + TypeScript apps that share
the FastAPI backend on `http://localhost:3101` (proxied at `/api`). They are
intentionally separate Vite projects so each can be built, deployed, and
projected independently. **Pick the right one before editing — they look
similar but serve very different audiences.**

| App                  | Port  | Audience                                | Status                |
| -------------------- | ----- | --------------------------------------- | --------------------- |
| `web/client/`        | 5273  | Internal operator / agent administrator | Live (legacy host)    |
| `web/portal/`        | 5274  | External candidates + recruiters        | Live                  |
| `web/blueprint/`     | 5275  | Public-facing essay + cosmic lens       | Live (most active)    |
| `web/shared/`        | —     | Cross-app TypeScript types/utilities    | Library, not an app   |

A quick-reference rule of thumb: **operator dashboards → `client`, hiring flow
→ `portal`, narrative + 3D constellation → `blueprint`.**

---

## `web/blueprint/` — cosmic-lens essay + constellation

- **Purpose.** The public-facing "cosmic lens" experience: an editorial
  long-read (`Opening`, `Analogy`, `Argument`, `Composition`, `Personae`,
  `Authority`, `MetaSkill`, `Observatory`, `Closing`) plus standalone
  full-screen views addressable via `?view=constellation|entities|functions|org-clone`.
  Built on `@react-three/fiber` + `three.js` + `d3-force`. This is where the
  rocket-as-workflow visualisation, KnowledgePulse strip, and CityView
  inspectors live.
- **Status.** Live. Most active development surface in the repo (~70 commits
  in the last 90 days).
- **Entry point.** `web/blueprint/src/main.tsx` → `web/blueprint/src/App.tsx`.
- **Dev command.** `npm run dev:blueprint` (or `cd web/blueprint && npm run dev`)
  — serves on **port 5275**. `npm run demo:blueprint` runs the production
  preview on the same port. Build with `npm --prefix web/blueprint run build`.
- **When to edit.** You're touching the constellation, the essay sections, any
  Three.js / R3F scene, the humanization layer for orchestration labels, or
  anything reachable from `?view=…`. Note the `dedupe: ["three", ...]` in
  `vite.config.ts` — do not remove it (PR #6 fix).

## `web/portal/` — candidate + recruiter portal

- **Purpose.** The hiring/recruiting flow used by Project Apex POC2: external
  candidate journey (`/apply`, `/portal`, `/screen`, `/book`) and the internal
  recruiter view (`/recruiter`, `/recruiter/c/:id`). Uses `react-router-dom`,
  Tailwind v4, MSW, and Vitest. Talks to the FastAPI backend for
  cv-crystalliser, screening, booking, and recruiter decisions.
- **Status.** Live. Real, user-facing surface for the hiring POC.
- **Entry point.** `web/portal/src/main.tsx` → `web/portal/src/App.tsx`
  (wrapped in `BrowserRouter`).
- **Dev command.** `npm run dev:portal` (or `cd web/portal && npm run dev`) —
  serves on **port 5274**. `npm run demo:portal` runs the production preview.
  Tests: `npm --prefix web/portal run test` (Vitest + Testing Library + MSW).
- **When to edit.** You're changing anything a candidate or recruiter sees:
  apply form, screening transcript, booking, recruiter timeline, Phase 7
  panels, post-screen redirect logic, or hiring-flow API contracts.

## `web/client/` — operator control plane (legacy host)

- **Purpose.** The internal operator / "Agent Administrator" UI: a single
  **Feed of Work** at `/` (cards for workflows, exceptions, and HITL items)
  with a right-side **drawer** for per-workflow detail (Decision / Activity /
  Audit sections), plus policy & autonomy, analytics, evaluations, economics,
  and the hiring-manager view. The governance toolkit (`KillSwitchPanel`,
  `EvidencePanel`, `OtelSpanTree`, signed audit chains) is surfaced through
  the drawer and dedicated routes. Legacy paths (`/fleet`, `/exceptions`,
  `/reviewer-queue`) redirect into the feed with the appropriate filter.
- **Status.** Live, but **hosted from the repo root, not from `web/client/`
  itself.** Unlike the other two apps, this one has **no `package.json` and no
  `vite.config.ts` of its own.** It is served by:
  - the root `index.html`, which loads `/web/client/main.tsx`;
  - the root `vite.config.ts`, which exposes `@client → web/client`;
  - the root `tsconfig.json` and `tailwind.config.ts`, which scope `@client/*`
    and `./src/client/**/*.{ts,tsx}` (legacy alias) into the build;
  - the root `vitest.config.ts`, for unit tests.
- **Entry point.** `web/client/main.tsx` → `web/client/App.tsx`, mounted by
  the **repo-root** `index.html`.
- **Dev command.** `npm run dev:client` (root-level `vite`) — serves on
  **port 5273**. `npm run demo:ui` runs the production preview on 5273.
  Build via the root `npm run build`. Tests via root `npm test`.
- **When to edit.** You're changing the operator Feed of Work, the
  workflow drawer (Decision / Activity / Audit), the policy / analytics /
  economics / evaluations routes, the governance toolkit (kill switch,
  evidence panel, audit chain), or anything under
  `web/client/components/apex/`. The constellation link in
  the sidebar deliberately opens `web/blueprint/` in a new tab — do not try
  to inline it here (it gets squashed by the dashboard's grid layout; see
  commit `98acc04b`).

---

## Decision: keep `web/client/` (do **not** archive or delete)

`web/client/` is unusual because it has no `package.json` of its own, which
made it look like a stale leftover at first glance. It is in fact the **active
host application for the operator control plane**, wired directly into the
repo-root Vite project. Concrete evidence of live use:

1. **Repo-root `index.html`** (`<script type="module" src="/web/client/main.tsx">`)
   — the root Vite dev server boots this app.
2. **Root `package.json`** scripts `dev:client` (`vite`) and `demo:ui`
   (`vite preview --host 0.0.0.0 --port 5273`) both serve it.
3. **`vite.config.ts`, `tsconfig.json`, `vitest.config.ts`, `tailwind.config.ts`**
   all declare `@client → web/client` aliases / content globs.
4. **Recent git activity:** ~55 commits to `web/client/` in the last 90 days,
   including the Phase 5–7 governance toolkit (Ed25519 identities, JWS-signed
   audit entries, operator kill switch, EvidencePanel) and POC3 Phase 5
   frontend wiring. This is not a dead surface.
5. **Cross-app references:** the constellation link in
   `web/client/App.tsx` deep-links to `web/blueprint/`'s `?view=constellation`,
   confirming `client` is the operator-facing shell that *embeds* the other
   surfaces, not the other way around.

Archiving or deleting `web/client/` would break the root `vite`/`vitest` build
and the `dev:client` / `demo:ui` scripts. **Decision: keep, document as the
operator control plane, and treat the missing `package.json` as a deliberate
"hosted by the repo root" arrangement rather than a bug.** A future
clean-up could migrate it into its own `package.json` for symmetry with
`portal/` and `blueprint/`, but that is out of scope for this todo.
