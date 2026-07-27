---
goal: Ship a working executive Fashion Trading Shock demo before 16:00
version: 1.0
date_created: 2026-07-27
last_updated: 2026-07-27
owner: Zava
status: 'In progress'
tags: [feature, fashion, demo, playwright]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

This is the implementation-first plan for today's Fashion demo. It starts from
remote `main` commit `2e39f5c2`, where the causal Trading Shock model, eight
workflow cascade, workflow memory repair and core backend tests already exist.

The remaining work is to make that implementation visible, easy to run and
safe to present. Do not spend the demo window redesigning infrastructure,
creating worktrees, expanding the process catalogue or perfecting every proof
gate.

## 1. Requirements & Constraints

- **REQ-001**: The `/world` route must explain the Fashion story without verbal setup.
- **REQ-002**: One visible trading shock must connect all eight existing Fashion workflows.
- **REQ-003**: The UI must show story status, commercial KPI movement and each workflow stage.
- **REQ-004**: Every created stage must retain its exact workflow ID and open the workflow drawer.
- **REQ-005**: Resolved approval cards must retain workflow IDs instead of rendering `—`.
- **REQ-006**: The deterministic live demo must complete all eight workflows without model quota.
- **REQ-007**: The demo must expose the world, workflow timeline, Knowledge and Constellation.
- **REQ-008**: Produce one polished MP4 walkthrough before handoff.
- **CON-001**: Demo deadline is 16:00 on 2026-07-27.
- **CON-002**: Work directly in the current remote checkout. Do not create extra worktrees.
- **CON-003**: Do not add new Fashion workflows or refactor unrelated substrate code.
- **CON-004**: Use retailer-neutral synthetic data. Do not add ASOS branding or proprietary claims.
- **CON-005**: Prioritize implementation and browser behavior over broad test-suite work.
- **GUD-001**: Run only the targeted tests covering changed code until the demo works.
- **GUD-002**: Preserve the existing pack-owned architecture and shared generic renderers.
- **GUD-003**: If true replay is not complete by the final hour, use deterministic live mode and finish the demo/video.

## 2. Implementation Steps

### Implementation Phase 0

- GOAL-001: Confirm and preserve the current working backend checkpoint.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Start from commit `2e39f5c2`. Confirm `tests/api/fashion`, `test_world_bridge_actor.py`, `test_world_workflow_adapter.py` and `test_travel_operational_memory.py` remain green. Do not redesign the Trading Shock backend unless the live browser exposes a real defect. | ✅ | 2026-07-27 |
| TASK-002 | Keep the existing story stages, dependency graph, KPI projection, memory scalarization and story ID propagation. | ✅ | 2026-07-27 |

### Implementation Phase 1

- GOAL-002: Make the connected Fashion story visible to executives.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Create `web/client/components/world/TradingShockPanel.tsx`. Render an executive briefing, six KPI before/after cards and an eight-stage causal journey from `state.story`. | | |
| TASK-004 | Add `WorldStory`, `WorldStoryStage` and `WorldStoryKpi` types to `web/client/hooks/useWorldSimulation.ts`. Mount `TradingShockPanel` above the spatial map in `web/client/components/world/SpatialWorld.tsx`. | | |
| TASK-005 | Each stage must show its business label, owning function/state, autonomy label, dependency, exact workflow ID and link to `/workflows/<id>` when bound. Failed stories must show an explicit interrupted state rather than a green outcome. | | |
| TASK-006 | Add focused component coverage in `web/client/components/world/__tests__/TradingShockPanel.test.tsx`; run only this test and the existing SpatialWorld test while implementing. | | |

### Implementation Phase 2

- GOAL-003: Fix customer-visible approval and workflow identity defects.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Extend the persisted resolution record in `web/client/hooks/useResolutionStore.tsx` with `workflowId` and `domain`. Pass both values from HITL, exception and external-wait card actions. | | |
| TASK-008 | Update `web/client/hooks/useFeedItems.ts` so orphan resolved cards use the stored `workflowId` and `domain`. Verify resolved cards remain clickable after the server removes the live exception. | | |
| TASK-009 | Run the focused `useFeedItems` and `ResolvedCard` tests. Do not run the full frontend suite until the live demo is usable. | | |

### Implementation Phase 3

- GOAL-004: Add a one-command deterministic demo runner.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Create `tools/fashion_demo_now.sh` by reusing `tools/lib/actor_world_proof_stack.sh`. Start isolated Azurite, Functions, FastAPI, Control Plane and Blueprint with `ZAVA_VERTICAL=fashion`, seed `42`, world speed `6`, `ZAVA_FASHION_AGENT_MODE=deterministic` and no external LLM dependency. | | |
| TASK-011 | Add an approval loop that resolves each Fashion HITL exception through the real `/api/exceptions/<id>/resolve` route as `fashion-demo-operator@zava.local`. Stop when all eight workflow types are completed or any workflow fails. | | |
| TASK-012 | Keep the stack running after the story completes. Print the World, Control Plane, Knowledge and Constellation URLs plus the eight workflow IDs. Stop cleanly on Ctrl-C using exact PIDs. | | |
| TASK-013 | Use readiness polling and workflow state, not long fixed sleeps. The runner must fail with the exact workflow/error when a stage fails. | | |

### Implementation Phase 4

- GOAL-005: Exercise and polish the real customer journey in Playwright.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Start `tools/fashion_demo_now.sh`; open `/world` in Playwright at `1600x1000`; confirm the briefing, KPI ribbon, eight-stage rail and live retail map render. | | |
| TASK-015 | Open every workflow from the journey rail and confirm the exact ID, completed status, declared phases, approval and terminal lifecycle are visible. Fix code defects immediately; do not replace failures with waits or mocks. | | |
| TASK-016 | Open `/memory`, `/knowledge` and Constellation. Confirm Fashion identity, workflow nodes and completed decisions are visible. Memory is already repaired in the backend; if it remains empty, inspect the actual API log and fix the write path. | | |
| TASK-017 | Remove customer-visible errors: em-dash workflow IDs, empty success cards, misleading labels, broken links, console errors and layout overflow. Ignore non-blocking development-only warnings. | | |

### Implementation Phase 5

- GOAL-006: Record and hand off the executive demo.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Create `tools/fashion_trading_shock_video.mjs` using Playwright screencast chapters: executive briefing, trading shock, connected journey, human approval, measured outcome, Knowledge and Constellation. | | |
| TASK-019 | Record a 45–120 second WebM from the working deterministic demo and convert it to H.264 MP4 with `ffmpeg`. Save it under `proof/fashion-trading-shock/executive-video.mp4`. | | |
| TASK-020 | Visually inspect a contact sheet and final frame. Re-record if any chapter is blank, clipped, loading or misleading. | | |
| TASK-021 | Run `npm run build`, the targeted Fashion backend tests and the targeted changed UI tests. Commit and push the working demo branch. | | |

### Implementation Phase 6

- GOAL-007: Improve replay only after the live demo and video work.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | If at least 60 minutes remain, wire `ZAVA_RECORD_TO` into the working runner, gracefully finalize `fashion-trading-shock.tar.gz`, boot it with `ZAVA_MODE=replay`, and verify the same story and workflow IDs. | | |
| TASK-023 | If replay work threatens the demo deadline, stop. Keep deterministic live mode as the customer path and document replay as follow-up. Do not break the working live demo. | | |

## 3. Alternatives

- **ALT-001**: Expand toward Telco's 37-process catalogue. Rejected for today because breadth does not improve the immediate executive story.
- **ALT-002**: Finish every formal live/replay visibility proof before UI work. Rejected for today because the demo currently lacks the customer-facing story.
- **ALT-003**: Produce only a scripted video. Rejected because the user also needs a working interactive fallback.

## 4. Dependencies

- **DEP-001**: Remote `main` contains commit `2e39f5c2`.
- **DEP-002**: Existing `uv`, Node, Playwright, Azure Functions Core Tools and Azurite dependencies.
- **DEP-003**: `ffmpeg` for MP4 conversion; WebM remains acceptable if unavailable.
- **DEP-004**: No GitHub Copilot or Azure OpenAI quota is required for deterministic demo mode.

## 5. Files

- **FILE-001**: `web/client/components/world/TradingShockPanel.tsx`
- **FILE-002**: `web/client/components/world/SpatialWorld.tsx`
- **FILE-003**: `web/client/hooks/useWorldSimulation.ts`
- **FILE-004**: `web/client/hooks/useResolutionStore.tsx`
- **FILE-005**: `web/client/hooks/useFeedItems.ts`
- **FILE-006**: `tools/fashion_demo_now.sh`
- **FILE-007**: `tools/fashion_trading_shock_video.mjs`
- **FILE-008**: Focused tests adjacent to the files above
- **FILE-009**: Backend files only when live browser evidence exposes an actual defect

## 6. Testing

- **TEST-001**: `uv run --frozen --no-sync pytest tests/api/fashion -q`
- **TEST-002**: `uv run --frozen --no-sync pytest tests/api/server/services/test_world_workflow_adapter.py tests/api/server/services/test_world_bridge_actor.py -q`
- **TEST-003**: `npx vitest run web/client/components/world/__tests__/TradingShockPanel.test.tsx web/client/components/world/__tests__/SpatialWorld.test.tsx`
- **TEST-004**: `npx vitest run web/client/hooks/__tests__/useFeedItems.test.tsx web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx`
- **TEST-005**: `npm run build`
- **TEST-006**: One Playwright live walkthrough of World, all eight workflows, Knowledge and Constellation

## 7. Risks & Assumptions

- **RISK-001**: Remote cloud hosts may not run Azure Functions, Azurite or browser recording. Mitigation: complete source changes and focused tests remotely; run `tools/fashion_demo_now.sh` and record locally if required.
- **RISK-002**: True replay tape finalization may consume the remaining demo window. Mitigation: treat replay as Phase 6 after the live demo and MP4 pass.
- **RISK-003**: Supporting workflow cascades may expose a real state/version conflict. Mitigation: inspect the failed workflow and fix the command/state contract; do not bypass it.
- **ASSUMPTION-001**: The current eight-workflow backend checkpoint is the correct foundation.
- **ASSUMPTION-002**: A deterministic live demo plus polished video is acceptable for today's meeting if true replay is not finished.

## 8. Related Specifications / Further Reading

- `docs/superpowers/specs/2026-07-27-fashion-trading-shock-demo-design.md`
- `docs/superpowers/plans/2026-07-27-fashion-trading-shock-demo.md`
- `docs/VERTICAL-PROOF.md`
