# Plan C — Public Cloud Deploy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the replay-mode container to the existing Azure Container App so visitors land on the operator UI at the existing FQDN and watch the recorded tape loop, with all three SPA bundles served by the same image.

**Architecture:** Multi-stage Docker image — Node stages build the three SPA bundles (`web/client/dist`, `web/blueprint/dist`, `web/portal/dist`); final stage runs FastAPI in `ZAVA_MODE=replay` on `127.0.0.1:3101` behind nginx on `:80`. nginx routes `/` → control plane bundle, `/blueprint/` → essay bundle, `/portal/` → candidate portal, `/api/*` + SSE → uvicorn. The 2-hour tape (from Plan B Phase 6) is baked into the image at `/app/tape/tape.tar.gz`. GitHub Action rebuilds + rolls the existing ACA revision on push to `main`.

**Tech Stack:** Docker multi-stage · nginx · uv · supervisord (or simple background process via shell) · Azure Container Registry · Azure Container Apps · GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-22-public-replay-landing-design.md` (sections: "Deploy", "What we deliberately leave out", "Open questions for the reviewer").

**Depends on:** Plan A merged (governance dashboard is part of the operator UI shipped here) AND Plan B merged (replay mode + recorded tape exists).

---

## Phase 1 — Container image

### Task 1.1: Multi-stage Dockerfile

**Files (create):**
- `deploy/replay/Dockerfile`
- `deploy/replay/nginx.conf`
- `deploy/replay/entrypoint.sh`
- `deploy/replay/.dockerignore`

- [ ] Dockerfile stages: `client-build` (Node 20, build all three SPAs); `api-build` (Python 3.11 + uv, sync dependencies, copy `api/` + `data/`); final (Python 3.11 slim + nginx + supervisord or a tiny entrypoint). Copy SPA bundles to `/var/www/{client,blueprint,portal}`. Copy `tapes/landing.tar.gz` to `/app/tape/tape.tar.gz`. Set env defaults: `ZAVA_MODE=replay`, `ZAVA_TAPE_PATH=/app/tape/tape.tar.gz`, `GOVERNANCE_HOT_RELOAD=0`.
- [ ] nginx config: root `/` → `/var/www/client`; `/blueprint/` → `/var/www/blueprint`; `/portal/` → `/var/www/portal`; `/api/` + `/internal/durable-event` → `proxy_pass http://127.0.0.1:3101` (with SSE-friendly `proxy_buffering off` + `proxy_read_timeout` extended).
- [ ] entrypoint: start uvicorn in background bound to `127.0.0.1:3101`, then `exec nginx -g 'daemon off;'` (so nginx is PID 1).
- [ ] `.dockerignore`: exclude `node_modules`, `.venv`, `dist`, `azurite-data`, `tests`, `.git` so the build context stays small.
- [ ] Commit: `feat(deploy): replay-mode multi-process container image`.

### Task 1.2: Local image smoke test

- [ ] `docker build -f deploy/replay/Dockerfile -t zava-replay:local .` — succeeds, image size < 1 GB.
- [ ] `docker run --rm -p 8080:80 zava-replay:local` boots; uvicorn log shows `ZAVA_MODE=replay` + tape loaded.
- [ ] `curl http://localhost:8080/ -o /dev/null -w "%{http_code}\n"` → 200.
- [ ] `curl http://localhost:8080/api/replay/meta` returns the tape's meta.
- [ ] `curl -N http://localhost:8080/api/blueprint/stream | head -5` shows events arriving.
- [ ] `curl -X POST http://localhost:8080/api/simulator/inject` → 403 with `error: "replay"`.
- [ ] Open `http://localhost:8080/` in a browser; control plane renders, dashboard shows workflows, drilling into a workflow opens the drawer with populated phases.
- [ ] Commit: `chore(deploy): local docker smoke test green`.

---

## Phase 2 — GitHub Action deploy workflow

### Task 2.1: Deploy workflow

**Files (create):** `.github/workflows/deploy-replay.yml`.

- [ ] Workflow triggers: push to `main` touching `api/**`, `web/**`, `deploy/replay/**`, `tapes/landing.tar.gz`, or `data/synthetic/authority/matrix.json`. Plus `workflow_dispatch`.
- [ ] Permissions: `id-token: write` for OIDC to Azure.
- [ ] Steps:
  1. Checkout.
  2. Azure login (federated identity).
  3. `az acr build` against the existing `blueprintacrzavademo` registry, image `replay:<TIMESTAMP>` + `replay:latest`, dockerfile `deploy/replay/Dockerfile`, context `.`.
  4. Resolve the new digest.
  5. `az containerapp update --name blueprint --resource-group zava-control-plane-demo --image <registry>/replay@<digest>` to roll the existing app (URL stays `blueprint.jollygrass-c41bb8b9.swedencentral.azurecontainerapps.io`).
- [ ] Concurrency group on the workflow so two pushes don't race a revision swap.
- [ ] Commit: `ci(deploy): deploy-replay workflow`.

### Task 2.2: First successful deploy

- [ ] Push to `main` (or trigger via workflow_dispatch). Watch the Action.
- [ ] On green: `curl -sf https://blueprint.jollygrass-c41bb8b9.swedencentral.azurecontainerapps.io/ -o /dev/null -w "%{http_code}\n"` → 200.
- [ ] If red: read logs, fix, re-trigger. Common gotchas: build context too large (revisit `.dockerignore`), ACA revision missing `targetPort: 80`, env vars not set.

---

## Phase 3 — Cloud verification

### Task 3.1: Cloud smoke commands

- [ ] `curl https://<fqdn>/api/replay/meta` returns expected `tape_id` + `recorded_at`.
- [ ] `curl -N https://<fqdn>/api/blueprint/stream` shows replayed events (run for 10 s, expect at least a couple of events).
- [ ] `curl -X POST https://<fqdn>/api/simulator/inject` → 403 with friendly message.
- [ ] `curl https://<fqdn>/api/governance/matrix | jq '.rules | length'` matches the matrix.json rule count.
- [ ] `curl https://<fqdn>/blueprint/` returns the essay bundle (Plan A's matrix dashboard NOT in this subpath — it lives under `/policy` on the root control plane).

### Task 3.2: Playwright cloud E2E

**Files (create):** `tests/e2e/cloud-replay.spec.ts` (gated on env `CLOUD_E2E=1` so it doesn't run in normal CI).

- [ ] Visit FQDN root, assert: replay badge visible, workflows visible within 10 s, drilling into a workflow shows the drawer with populated phases.
- [ ] Visit `/policy`, assert: matrix rows render with owner-persona chips, at least one row's `Last changed` is populated.
- [ ] Visit `/?view=constellation` route (control plane → blueprint cross-link), assert canvas renders.
- [ ] Attempt a POST via `page.request.post('/api/dream-pass/run')`, assert 403.
- [ ] Wait close to tape EOT (or skip if duration > 10 min); assert `Replay restarting…` banner appears.
- [ ] Commit: `test(deploy): cloud E2E smoke`.

### Task 3.3: Wire essay CTAs to the real URLs

**Files (modify):** environment defaults for `VITE_DEMO_URL` + `VITE_ESSAY_URL` in `web/blueprint/.env.production` and `web/client/.env.production` (create if missing).

- [ ] `VITE_DEMO_URL=https://blueprint.jollygrass-c41bb8b9.swedencentral.azurecontainerapps.io/`
- [ ] `VITE_ESSAY_URL=https://arturcrmbot.github.io/zava-control-plane/`
- [ ] Rebuild both bundles, deploy. Verify the two CTAs round-trip.
- [ ] Commit: `chore(deploy): wire bidirectional CTA URLs to production`.

---

## Phase 4 — Documentation + safety marker

### Task 4.1: README update

**Files (modify):** `README.md`, `.poc-safety`.

- [ ] In README, add a "Live demo" section above the existing safety section linking to the FQDN with a screenshot.
- [ ] Add an explicit bullet to `.poc-safety` (or its README counterpart): *"Exception: the read-only replay mode (`ZAVA_MODE=replay`) is safe for public ingress — it serves a recorded tape, gates every write at 403, and runs no LLM. Removing the `POC_UNSAFE_FOR_PUBLIC_DEPLOY=1` marker is NOT required for the replay deploy and MUST NOT be done until the live-mode hardening items are complete."*
- [ ] Commit: `docs(deploy): README live-demo section + .poc-safety clarification`.

### Task 4.2: Operator runbook

**Files (create):** `docs/operator/replay-deploy.md`.

- [ ] How to record a new tape (link to Plan B Phase 6).
- [ ] How to swap the deployed tape (push new `tapes/landing.tar.gz` to `main` → workflow auto-rolls).
- [ ] How to roll back (revert the commit; workflow auto-rolls).
- [ ] How to check the running container status (`az containerapp show ...`, recent log query).
- [ ] Commit: `docs(deploy): operator runbook for replay container`.

---

## Done criteria

- The FQDN serves a fully clickable read-only control plane backed by the 2-hour tape.
- All three SPA bundles are reachable (`/`, `/blueprint/`, `/portal/`).
- Every write returns 403 with the friendly message; the visitor sees a toast.
- The constellation route on the blueprint origin works (i.e. visitors who follow `/blueprint/?view=constellation` get the 3D scene rendered against the replay-mode API).
- The deploy workflow runs cleanly on every push touching the relevant paths.
- Cloud E2E spec is green when run with `CLOUD_E2E=1`.
- Cost stays ≤ $20/day (no LLM calls in replay mode; container is a single small ACA replica).

## Estimate

| Phase | Days |
|---|---|
| 1 — image | 0.5 |
| 2 — deploy workflow + first deploy | 0.5 |
| 3 — verification + cloud E2E + CTAs | 0.5 |
| 4 — docs + runbook | 0.25 |
| **Total** | **~1.75** |
