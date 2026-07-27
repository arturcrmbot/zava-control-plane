---
goal: Bring the existing Fashion vertical to Telco demo parity
version: 1.0
date_created: 2026-07-27
last_updated: 2026-07-27
owner: Zava
status: 'In progress'
tags: [feature, fashion, telco, parity, demo]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

Fashion already exists and already has eight executable workflows, a live actor
world, the standard operator UI, Knowledge, Constellation and permanent proof
tooling. This plan does not introduce new UX.

The task is to close the implementation and evidence gaps between Fashion and
the Telco golden standard while using the same customer journey:

`World → workflow drawer → execution timeline → Memory → Knowledge → AG-UI → Constellation`

## 1. Requirements & Constraints

- **REQ-001**: Keep the existing shared operator UI and navigation used by Telco.
- **REQ-002**: Run all eight existing Fashion workflows; add no new workflow types.
- **REQ-003**: Every workflow must expose its exact ID and terminal outcome on every Telco proof surface.
- **REQ-004**: Fashion Memory must contain an exact workflow-ID match for every completed workflow.
- **REQ-005**: Fashion replay must render all eight workflows, not merely a disabled-world page.
- **REQ-006**: The Playwright proof must exercise every workflow drawer and AG-UI run panel.
- **REQ-007**: Produce a polished video using the same World/drawer/Knowledge/Constellation flow used for Telco.
- **CON-001**: Demo deadline is 16:00 on 2026-07-27.
- **CON-002**: Do not create new screens, dashboards, KPI ribbons, story rails or UX concepts.
- **CON-003**: Do not expand Fashion toward Telco's 37-process catalogue today.
- **CON-004**: Do not redesign deployment, branching, worktrees or unrelated infrastructure.
- **CON-005**: Prioritize code fixes and browser behavior. Run focused tests only.
- **PAT-001**: Use `tools/telco_zava_e2e_proof.*` and Fashion's stronger historical proof at commit `02ea8302` as implementation references.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Restore Telco-equivalent cross-surface proof for Fashion.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Compare current `tools/fashion_zava_e2e_proof.mjs` with `tools/telco_zava_e2e_proof.mjs` and `git show 02ea8302:tools/fashion_zava_e2e_proof.mjs`. Restore the Fashion checks that were lost: all eight drawers, all eight exact Memory matches, all eight Knowledge nodes, all eight AG-UI run panels and Constellation workflow presence. | | |
| TASK-002 | Keep Fashion-specific assertions—inventory threshold, real stock mutation, authority and eight workflow types—but use the same proof-surface structure and browser error gate as Telco. | | |
| TASK-003 | Write `proof/summary.json`, `memory.json`, `entity-graph.json`, screenshots and recordings using observed data only. Do not hardcode PASS values. | | |

### Implementation Phase 2

- GOAL-002: Fix real runtime gaps exposed by parity proof.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Confirm the memory fix on `main` writes scalar Chroma metadata and exact structured workflow IDs. Run all eight Fashion workflows and verify `/api/memory/v2/memories?domain=<workflow-type>` contains the matching workflow. | ✅ | 2026-07-27 |
| TASK-005 | Fix resolved feed identity using the existing feed cards only: retain `workflowId` and `domain` after an exception closes so the standard Telco/Fashion drawer link never becomes `—`. | | |
| TASK-006 | Run all eight existing Fashion workflows through the existing Durable/world path. Fix only concrete failures in observation, authority, typed command, state mutation or terminal evaluation. | | |

### Implementation Phase 3

- GOAL-003: Make Fashion replay equivalent to the Telco demo path.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Restore Fashion's existing pack-recording replay behavior from commit `02ea8302`: start the Blueprint demo stream, observe all eight Fashion workflow types and render Constellation with Functions and the actor world disabled. | | |
| TASK-008 | If a real substrate tape already exists or can be produced quickly, use `ZAVA_RECORD_TO`/`ZAVA_MODE=replay`. Do not block today's demo on new replay infrastructure; the minimum parity gate is all eight recorded Fashion workflows rendering through the existing Telco-style UI. | | |
| TASK-009 | Verify replay has zero failed/dead-letter workflows, zero browser errors and the same workflow identities as live evidence. | | |

### Implementation Phase 4

- GOAL-004: Validate the existing Fashion UX end to end.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Start the Fashion stack with the existing proof runner or deterministic demo profile. Open `/world`; confirm the current Fashion Retail world, state-derived trigger, automatic workflow cards and stock outcome render. | | |
| TASK-011 | Open each of the eight existing workflow drawers. Confirm exact ID, completed status, declared phases, approval, reasoning/deterministic evidence, command and terminal lifecycle. | | |
| TASK-012 | Open the existing Memory, Knowledge, AG-UI and Constellation views. Fix missing data or broken links; do not invent replacement UI. | | |

### Implementation Phase 5

- GOAL-005: Record the customer-ready walkthrough.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Record the existing UX with Playwright: Fashion World, inventory trigger/outcome, workflow drawer/timeline, Memory, Knowledge and Constellation. | | |
| TASK-014 | Produce a 45–90 second H.264 MP4. Use overlays only for chapter titles and evidence callouts; do not add product UI. | | |
| TASK-015 | Run the focused Fashion backend tests, focused changed UI tests, `npm run build`, and the Fashion proof command. Commit and push the completed fixes. | | |

## 3. Alternatives

- **ALT-001**: Add an executive story dashboard. Rejected because Telco did not require one and Fashion must use the same shared UX.
- **ALT-002**: Add more Fashion workflows. Rejected because the existing eight are sufficient for today's demo.
- **ALT-003**: Redesign replay infrastructure. Rejected unless the existing Telco/Fashion recording path cannot render all eight workflows.

## 4. Dependencies

- **DEP-001**: Remote `main` commit `9439d957` or later.
- **DEP-002**: Existing Telco proof scripts and Fashion pack recordings.
- **DEP-003**: Existing Playwright, Functions, Azurite and Vite toolchain.

## 5. Files

- **FILE-001**: `tools/fashion_zava_e2e_proof.mjs`
- **FILE-002**: `tools/fashion_zava_e2e_proof.sh`
- **FILE-003**: `tools/fashion_proof_manifest.py`
- **FILE-004**: `web/client/hooks/useResolutionStore.tsx`
- **FILE-005**: `web/client/hooks/useFeedItems.ts`
- **FILE-006**: Existing adjacent tests for changed behavior
- **FILE-007**: Fashion runtime files only when the proof exposes a concrete defect

## 6. Testing

- **TEST-001**: Focused Fashion backend suite.
- **TEST-002**: Focused feed identity tests.
- **TEST-003**: `npm run build`.
- **TEST-004**: `make prove VERTICAL=fashion`.
- **TEST-005**: One Playwright walkthrough across the existing Telco-equivalent surfaces.

## 7. Risks & Assumptions

- **RISK-001**: Current Fashion replay proof is weaker than Telco and may hide missing data.
- **RISK-002**: Cloud environments may not run Functions or browser recording; finish source fixes remotely and run the final proof locally if required.
- **ASSUMPTION-001**: No new UX is required.
- **ASSUMPTION-002**: The eight existing Fashion workflows are the complete demo scope.

## 8. Related Specifications / Further Reading

- `docs/VERTICAL-PROOF.md`
- `tools/telco_zava_e2e_proof.mjs`
- `tools/telco_zava_e2e_proof.sh`
- `docs/superpowers/specs/2026-07-20-fashion-retail-vertical-design.md`
