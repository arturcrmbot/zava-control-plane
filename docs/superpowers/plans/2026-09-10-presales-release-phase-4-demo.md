# Evidence-led Constellation Implementation Plan

> **For agentic workers:** Use `executing-plans` after implementation approval. Follow the [master plan](2026-09-10-presales-release-readiness.md). Do not substitute a new static story for the current static story.

**Goal:** Make Constellation understandable and make every guided statement traceable to a real live or recorded Aurora run.

**Architecture:** Keep the existing scene, workflow APIs, AG-UI client, recorder and player. Introduce one shared source-mode contract and a typed journey reference. The guide follows actual workflow detail/lineage; recorded chapters are local presentation over immutable evidence, not shared server playback mutations.

**Tech Stack:** React/TypeScript, FastAPI, existing replay schemas, Vitest and Playwright.

**Status:** Superseded by [master plan v2](2026-09-10-presales-release-readiness.md). Reference only; use existing evidence APIs before adopting the proposed new contracts or tape format.

---

## Task 4.1: Give every surface the same source-mode truth

**Files**

- Modify: `web/blueprint/src/lib/useReplayMode.ts`
- Modify: `web/blueprint/src/pages/ConstellationPage.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/CosmicLens.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/TimeScrub.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/DecisionTicker.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/ActivityRail.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/VitalSignsBar.tsx`
- Modify: existing tests for those components
- Create: `web/blueprint/src/lib/__tests__/useReplayMode.test.ts`

- [ ] Add tests for delayed metadata, live metadata, replay metadata, HTTP failure and malformed metadata. No test may equate unavailable metadata with live execution.
- [ ] Replace the boolean-only source model with:

```ts
export type SourceMode =
  | { mode: "loading" }
  | { mode: "live" }
  | {
      mode: "replay";
      tapeId: string;
      recordedAt: string;
      durationSeconds: number;
      sourceCommit: string | null;
    }
  | { mode: "unavailable"; message: string };
```

- [ ] Keep one metadata owner on `ConstellationPage` and pass the result to the scene/HUD. Update all `useReplayMode` consumers in the same change; no component retains its own optimistic "live" default.
- [ ] Hide mutating controls until mode is confirmed live. Loading/unavailable states cannot initiate a scenario.
- [ ] For public replay, remove the wall-clock `LIVE now` time scrub. Display recording position/date from metadata; retain local previous/next journey controls separately. Do not enable replay seeking against the shared server session.
- [ ] Preserve the live-history tool, but distinguish source mode from viewing history. A historical live-source snapshot must not change the label of the underlying source.
- [ ] Run the affected hook/HUD tests in one Vitest invocation, including existing `StoryGuide`, `TimeScrub` and `DecisionTicker` tests.

**Acceptance:** a replay page contains no claim that it is live; a failed metadata request produces an explicit unavailable state.

## Task 4.2: Capture a real journey with the tape

**Files**

- Modify: `api/server/services/replay/tape_format.py`
- Modify: `api/server/services/replay/recorder.py`
- Modify: `api/server/services/replay/snapshot.py`
- Modify: `api/server/services/replay/tape_loader.py`
- Modify: `api/server/routes/replay.py`
- Modify: `api/server/routes/workflows.py`
- Modify: `tools/public_replay_manifest.py`
- Modify: existing replay/tape/manifest tests
- Create: `tests/api/server/services/replay/test_journey_capture.py`

- [ ] Introduce tape format version `2`, while retaining read support for historical version `1`. Version 1 has no guaranteed guided journey; it must not receive invented references.
- [ ] Add a typed journey reference with `journey_id="aurora-budget-response"`, actual root/child workflow IDs, first/last persistent event IDs and recording-relative start/end offsets. All referenced IDs must exist in captured evidence.
- [ ] Capture complete workflow-detail records for the root and children using the existing `/api/workflows/{id}` shape and workflow-visibility projection. Store them in `snapshot_t0/workflow_details.json` using the existing `{"workflows": [...]}` envelope.
- [ ] Populate the journey reference only after a real run is terminal and its required phase/decision evidence exists. Partial/failed runs remain inspectable, but cannot be labelled the approved golden journey.
- [ ] Serve captured detail through the existing workflow route. In replay, serve captured parent/child lineage rather than manufacturing an unknown root from an absent graph.
- [ ] Extend replay metadata and the release verifier to expose/verify the journey and details hashes, application SHA, vertical and fingerprint. Reject mismatched source, missing roots/children, invalid offsets and duplicate IDs.
- [ ] Add version-1 compatibility, version-2 round-trip and malformed-journey cases to the existing replay test cohort. No live reflector, policy evaluator or writer starts while reading either tape version.

**Acceptance:** every recorded chapter and every displayed outcome resolves to immutable captured evidence. A legacy tape can still play historical activity, but cannot masquerade as a current guided release.

## Task 4.3: Follow evidence instead of playing canned captions

**Files**

- Modify: `web/blueprint/src/components/cosmicLens/HUD/guidedJourney.ts`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/StoryGuide.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/Narrator.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/DemoHUD.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HUD/WorkflowDrawer.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/CameraFocus.tsx`
- Modify: `web/blueprint/src/components/cosmicLens/HoveredWorkflowPath.tsx`
- Reuse: `web/blueprint/src/components/workflowRun/AGUIClient.ts`
- Modify: related existing tests
- Create: `tests/e2e/aurora-journey.spec.ts`

- [ ] Delete `REPLAY_ARC`, `WF-replay-001`, fixed percentages, fixed cascade counts and timer-generated business outcomes. Replace the existing test that requires replay to make no data request.
- [ ] Live: use the Phase 2 accepted root, subscribe to its actual AG-UI stream and retrieve real detail/child lineage. Retry requests with the same intent ID; disable repeated starts while acceptance is pending.
- [ ] Replay: select the captured journey and read its stored details. Previous/next controls change only the viewer's local selected evidence row. Do not change the global recording position or send a business POST.
- [ ] Map declared phase IDs to plain-language chapter names. Numbers, actors, outcomes and timestamps come from evidence. Missing phases display "not reached"; missing required evidence disables that chapter with a reason.
- [ ] Use existing scene focus/selection components to identify the actual root and active children. Keep whole-organisation context visible but quiet unrelated cast/feed panels during the guided view; restore the user's view when the guide closes.
- [ ] Make the persistent first view answer: which organisation, what source mode, what business situation and what to click. Retain a direct evidence/drawer link in each chapter.
- [ ] Render approval provenance explicitly: real operator versus synthetic persona, role, governing rule and outcome. Never label a synthetic decision "a person approved".
- [ ] Add an accessible flat journey/timeline fallback when WebGL is unavailable, plus keyboard focus, reduced-motion behaviour and non-colour status labels.

**Behaviour case**

```ts
import { expect, test } from "@playwright/test";

test("replay narrates captured facts rather than constants", async ({
  page, request,
}) => {
  const metaResponse = await request.get("/api/replay/meta");
  expect(metaResponse.ok()).toBeTruthy();
  const meta: {
    journeys: Array<{ journey_id: string; workflow_id: string }>;
  } = await metaResponse.json();
  const journey = meta.journeys.find(
    (item) => item.journey_id === "aurora-budget-response",
  );
  if (!journey) throw new Error("Fixture has no captured Aurora journey");

  await page.goto("/blueprint/?view=constellation");
  await page.getByRole("button", { name: /follow one decision/i }).click();
  await expect(page.getByTestId("journey-root-id")).toHaveText(
    journey.workflow_id,
  );
  await expect(page.getByTestId("journey-source-mode")).toHaveText("Recorded");
  await expect(page.getByTestId("journey-evidence-link")).toHaveAttribute(
    "href", `/api/workflows/${journey.workflow_id}`,
  );
});
```

The E2E fixture supplies an actual exported root with deliberately non-default invoice counts and outcomes. Assert those exact fixture values, request history and linked child IDs. A literal string assertion alone is insufficient.

## Task 4.4: Protect the published entry path

**Files**

- Modify: `tests/e2e/public-story.spec.ts`
- Modify: `tests/tools/test_public_story_deployment.py`
- Modify: `tests/tools/test_workflow_visibility_proof.py`

- [ ] Extend public-story coverage beyond the presence of a button: follow the journey, inspect a child and decision, and compare visible provenance with `/api/replay/meta`.
- [ ] Exercise 390px mobile width, a typical 1280x720 presentation and a 1440px desktop. Assert no hidden primary action, unusable evidence drawer or horizontal page overflow.
- [ ] Exercise metadata failure, missing journey, legacy tape and stream reconnection. Do not fall back to success-shaped sample data.
- [ ] Confirm UI interaction produces no write request in public replay.

## Phase gate and rollback

- [ ] Actual live/replay records drive the same business chapter sequence.
- [ ] Missing data remains visibly missing.
- [ ] Public recording date, source mode and journey identity agree across surfaces.
- [ ] Guided view remains understandable without the author decoding colours.

Rollback retains ordinary recorded activity with the guide explicitly unavailable. It never restores canned captions as execution evidence.
