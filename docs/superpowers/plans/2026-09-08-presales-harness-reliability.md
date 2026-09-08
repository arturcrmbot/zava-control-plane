# Presales Harness Reliability Implementation Plan

> **For agentic workers:** Use `executing-plans` to implement this plan inline,
> task by task. Use the existing test runners; add regression cases before fixes.

**Goal:** Make the existing presales harness start reliably, enforce its shared
execution boundaries, and report operator actions and outcomes truthfully.

**Architecture:** Keep the current single-process control plane, Durable
orchestrators, runtime providers, and vertical packs. Repair existing boundaries
instead of adding a broker, database, framework, or parallel implementation.
Keep the current public status vocabulary; express failure reasons in existing
metadata and events.

**Tech stack:** Python/FastAPI/Durable Functions, React/TypeScript, pytest, Vitest.

## Scope and guardrails

This is one focused reliability pass, not implementation of every audit finding.
Compared with a quick packaging-only patch, it also covers the execution and
operator defects that can contradict a live demonstration. A persistent recovery
redesign would be a separate project and is deliberately excluded.

- No new vertical features, industry optimisers, or conversion of reference
  scenarios into additional Durable workflows.
- No new infrastructure or dependencies; no general `AppState` rewrite.
- No learning experiments, memory-store migration, or production authentication
  programme in this pass.
- No claim of restart recovery or exactly-once execution. A failed critical
  delivery must become an explicit error, not pretend success.
- Work in the current checkout. Do not commit, push, deploy, or make paid model
  calls unless separately requested.

## 1. Package the runtime that the loader expects

**Files:** `deploy/Dockerfile`, `.dockerignore`, `api/shared/vertical_loader.py`,
`tests/api/shared/test_vertical_loader.py`,
new `tests/tools/test_runtime_image_contract.py`.

- [x] Add regressions for required vertical assets in the image and preservation
  of mixed-case data-directory paths.
- [x] Include `verticals/` in the Python image stage; trim filesystem settings
  without lowercasing them. Leave enum-like configuration normalisation intact.
- [x] Exercise all seven pack registrations using existing offline validation.
  Inspect `.dockerignore` for required assets and credential exclusions.
- [x] Run the focused tests. If Docker is available, build and exercise the
  packaged import/runtime-manifest boundary with simulation and live models off.
  Do not claim image startup was exercised if only source-level checks ran.

**Container follow-through (2026-09-08):** The existing Colima profile runs
without a reset. A real Linux/AMD64 image was built and its packaged replay
served the runtime API and operator UI. Broken download-CDN TLS paths were
worked around with build-local HTTPS mirrors, frozen Python hashes, and
`npm ci` integrity checks; no TLS verification or dependency pins were removed.
Actual startup exposed Kuzu's 8 TiB address-space reservation under emulation;
an optional configured DB-size bound fixes that OOM without changing the
native default. The remaining whole-container/live and portal proof is tracked
below, not implied by the packaged import result.

## 2. Stop false success at shared execution boundaries

**Files:** `api/functions/webhook.py`,
`api/functions/workflows/activities.py`,
`api/functions/graphs/_tracked_executor.py`,
`api/server/services/workflow_event_ingestor.py`,
`api/server/services/persona_responder.py`,
`api/functions/workflows/hiring.py`.

**Tests:** `tests/api/server/services/test_workflow_event_ingestor.py`,
`tests/api/server/services/test_persona_responder_edge_cases.py`,
`tests/api/unit/test_hiring_segment_b.py`,
new `tests/api/unit/test_webhook_delivery.py`,
new `tests/api/unit/test_tracked_executor_validation.py`.

- [x] Add failing cases for a non-2xx/transport-failed checkpoint callback,
  a blocked validator reaching the next executor, rejected budget approval,
  timeout-as-success, and a missing Durable instance being marked completed.
- [x] Give checkpoint delivery an explicit required-delivery path that checks
  HTTP status and propagates failure. Preserve best-effort tracing; do not add
  automatic retries around business side effects.
- [x] Stop a graph on an explicit validator failure and preserve its diagnostic
  event. Honour the existing rejection vocabulary at the hiring budget gate;
  this is an adapter repair, not new hiring logic.
- [x] Preserve terminal reasons and route timeout/orphan failures through
  existing failure handling. Keep successful and legitimate rejected outcomes
  distinguishable without adding a new application-wide status enum.
- [x] Run focused positive and negative cases, including the existing expense
  and hiring orchestration coverage for the changed boundary.

## 3. Make runtime and supervisor contracts consistent

**Files:** `api/functions/graphs/executors/agents/runtime.py`,
`api/functions/graphs/executors/agents/runtime_ghcp.py`,
`api/functions/graphs/executors/agents/runtime_aoai.py`,
`api/functions/graphs/executors/agents/_wrapper.py`,
`api/server/services/fleet_manager_queue.py`.

**Tests:** `tests/api/functions/agents/test_runtime_protocol.py`,
`tests/api/functions/graphs/executors/agents/test_runtime_aoai.py`,
`tests/api/unit/test_fleet_manager_queue.py`.

- [x] Add cases for unregistered required tools, required tools never succeeding,
  valid tool evidence, and new queue entries arriving during an active batch.
- [x] Enforce the same required-tool success contract for both real providers;
  reuse one small pure validation helper if needed. Do not redesign tool schemas,
  prompts, or every agent adapter.
- [x] Drain work arriving during a supervisor batch without requiring a later
  unrelated event. Keep one processor active and retain current wake deduplication.
- [x] Run the provider and queue tests with mocked SDK/network boundaries.

## 4. Make feed Undo cancel the actual pending action

**Files:** `web/client/hooks/useResolutionStore.tsx`,
`web/client/components/feed/cards/ExceptionCard.tsx`,
`web/client/components/feed/cards/ResolvedCard.tsx`,
and directly affected callers of the resolution-store API.

**Tests:** existing `useResolutionStore`, `ExceptionCard`, and `ResolvedCard`
tests under `web/client/hooks/__tests__/` and
`web/client/components/feed/__tests__/cards/`.

- [x] Add a regression that clicks the resolved card's Undo before the delayed
  POST, plus cases for toast Undo, HTTP failure, acknowledgement, and reload.
- [x] Give the pending action one cancellation owner shared by card and toast.
  Do not offer browser-only Undo after sending/committing a server action.
- [x] Do not persist executable callbacks or revive an expired/pending Undo
  capability from local storage. Preserve ordinary resolution history.
- [x] Run the affected component/hook tests and the existing frontend build.

## 5. Leave a small repeatable harness check

**Files:** `Makefile`, `docs/DEVELOPMENT.md`, `docs/runtime-providers.md`,
`tests/conftest.py` (opt-in offline fixture),
`tests/api/shared/test_vertical_pack_contracts.py` where an existing check needs
extension. Reuse the regression tests above, not a new proof framework.

- [x] Add one `make test-harness` target selecting these backend and feed
  contracts, plus existing pack inventory/validation checks.
- [x] Keep live-state and replay fixture cohorts in separate pytest processes;
  their current import-time application state must not contaminate each other.
- [x] Document the command, its offline scope, and the explicit limits:
  no production failover, live-model quality, or industry-completeness claim.
- [x] Run the target, inspect the final diff, and confirm no vertical business
  features or unrelated refactors have entered the change set.

**Core pass:** The selected shared defects have regression coverage and minimal fixes;
the existing packs remain usable through the same interfaces. Broader recovery,
agent-input rewiring, telemetry-provenance cleanup, and domain outcome modelling
remain explicit follow-up work, not hidden claims of this pass.

## 6. Prove the actual container and prepare publication

Added after the user explicitly requested Docker/browser evidence, updated
documentation, and push/deploy preparation. Public release intent remains Agency
read-only replay; deterministic Telco execution is a shared-harness probe, not
a substitute Agency seller story.

- [x] Resume Colima, build the Linux/AMD64 image, exercise its API and browser,
  and resolve observed dependency transport and Kuzu startup failures.
- [x] Repair the observed `/portal/recruiter` source routing and mounted links;
  add server and frontend regressions.
- [x] Prove Functions-host startup and child-process supervision. The real
  deterministic Telco instance `d98f8795453a4578b604bb214a1896ce` completed,
  rerouted 184 sessions, and recovered SITE-03. The image was a boot-only
  overlay, not a final current-source release image.
- [x] Build the full immutable image from pushed source `3fe95702` and exercise
  all three browser surfaces, including portal navigation/reload. The unchanged
  retry passed `uv export`; the subsequent export-space failure was resolved by
  removing only the completed boot-overlay image and its four exact cache
  records. No dependency or source changes were needed.
- [x] Repeat real Durable execution in that full-source image:
  `c18a0a2c33964d7190597547bedc183b` rerouted all 184 affected sessions and
  recovered SITE-03. Killing its Functions host stopped the container in two
  seconds and finalized a source-attributed technical recording.
- [x] Bind new recordings/public manifests to the full source commit, selected
  vertical, and pack fingerprint. Reject dirty or historical release inputs.
- [x] Archive the old Fashion proof and historical tapes without deleting them;
  replace the authoritative root manifest with explicit pending release status.
- [x] Correct current run/publish documentation, including the historical public
  tape, actual FastAPI SPA hosting, and mode-specific release boundaries.
- [ ] Publish only after fresh Agency live/replay evidence and the operator's
  seller review pass. Never manufacture human approval to bypass this gate.
- [ ] Investigate and resolve the long-running replay memory failure before
  publication. The older historical-replay container was killed at its 4 GiB
  memory limit after 7,862 seconds; the kernel reports a container-limit OOM,
  not VM-wide pressure. Short current-image checks are not a passed soak test.

Checkpoint the reviewed source separately from the remaining image/release
gate. After commit, new evidence must name that exact source SHA; the earlier
dirty-development and boot-overlay images must not be relabelled as its proof.
