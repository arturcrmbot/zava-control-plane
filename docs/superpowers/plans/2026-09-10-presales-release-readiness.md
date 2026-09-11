# Presales Release Readiness Implementation Plan

> **Execution owner: Copilot.** This is the active plan. The six earlier phase documents are reference material, not an executable backlog. Work in small, reviewed changes; do not implement an abstraction merely because an older draft proposed it.

**Goal:** Finish a convincing, technically honest Zava presales package that runs reliably in its documented demo environment.

**Architecture:** Keep the existing stack, verticals and deployment approach. Repair demonstrated defects, make Agency/Aurora execute for real, and connect the presentation to that evidence. Add infrastructure or shared abstractions only when a reproduced failure makes them necessary.

**Tech Stack:** Python, FastAPI, Azure Durable Functions, existing Azure/GitHub agent runtimes, Azure Storage, Azure Container Apps, Bicep/azd, React/TypeScript, pytest, Vitest, Playwright and the existing media toolchain.

**Status:** Local implementation complete; external release gates pending. **Version:** 2.0, narrowed after user feedback. **Date:** 2026-09-10.

**Source baseline:** `31554c66825e903725f36c3513a479448ca48965`.

**Approved direction:** Agency/Aurora remains the organisation-wide flagship. No new verticals. The user is not responsible for engineering, testing, writing, recording or coordinating this work.

---

## 1. What changed

Version 1 expanded a presales-readiness task into a platform-engineering programme.
It prematurely prescribed a generic persistence backend, writer leases, broad
restart guarantees and extensive new contracts. Those are not prerequisites for
a compelling, honest demonstrator.

Keep the observed defects and required outcomes. Challenge proposed machinery
before implementing it. Real Aurora execution and safe deployment remain in scope.

## 2. How Copilot executes

1. Select one concrete defect or user-visible outcome; inspect its real callers.
2. Reproduce the failure with the smallest existing test or browser/runtime case.
3. Make the smallest complete fix, reusing existing helpers and platform features.
4. Review requirement coverage and correctness; use an independent reviewer for substantial changes, not a new agent for every tiny edit.
5. Exercise the actual behaviour, update directly affected docs and mark the task complete.

One writer per shared checkout. Delegate only bounded work that benefits from
separate context. Copilot owns integration, investigation, code, tests, prose and
media preparation. The user is not given technical homework.

If a design assumption fails, revise that task before expanding implementation.
Do not launch another whole-repository audit or blindly execute an old checklist.

## 3. Work A: Make the demonstrated behaviour true

| Task | Exact starting points | Required result |
|---|---|---|
| A1 - Fix deployed configuration | `infra/modules/aca-app.bicep`, `infra/main.bicep`, `infra/main.parameters.json`, `deploy/entrypoint.sh`; existing loader/entrypoint/deployment tests | Default Agency memory settings validate. Configured paths are actually used. API and Functions do not reopen the same embedded database. |
| A2 - Fix Azure provider gap | `api/server/services/fleet_manager_service.py`, existing `LLMRuntime.run_session()` and `runtime_aoai.py`; FM/AOAI tests | Required Azure supervisor runs without hidden `gh auth`; actual deployment selection and tool evidence are correct. Preserve GitHub behaviour. Do not add another generic session framework. |
| A3 - Make Aurora real | `api/server/routes/demo_triggers.py`, `api/server/services/policy_application.py`, `verticals/agency/`, existing `fleet_ap_invoice.py` and governance/approval routes | Real registered Durable parent and AP children, actual operator gate, correct approve/reject/timeout behaviour, idempotent scenario actions and real evidence. No synchronous simulated decision cascade presented as execution. |
| A4 - Fix guided evidence and labels | `guidedJourney.ts`, `useReplayMode.ts`, `TimeScrub.tsx`, `StoryGuide.tsx`, `Narrator.tsx` under `web/blueprint/src/`; existing workflow-detail/replay APIs | Remove fixed `REPLAY_ARC` claims. Follow a captured/live root and its actual decisions. No `LIVE` label on recorded activity or failed metadata. Missing evidence stays visibly missing. |

- [x] A1 code changes complete: pack-derived memory, selected-vertical wiring, configured data root and isolated Functions child. Azure provisioning/recovery claims remain Work C.
- [x] A2 complete: Azure/fake supervisor paths use the existing runtime; GitHub behaviour and explicit model selection remain supported.
- [x] A3 complete locally: actual model recommendation, operator wait, governed policy and two real AP child executions completed; a separate real recommendation was rejected without policy or children.
- [x] A4 complete: real workflow selection/evidence, correct source states, no random template workflows in the normal stream, replay progression and readable rejection outcomes.

Start with A1. A3 is the main engineering investment and follows a focused design
of the real flow, not wholesale implementation of the old persistence proposal.
Use the Agency pack's existing registration/graduation contracts. Reuse the AP
engine rather than creating another. Call selected invoices "queued" unless
actual event ordering proves they were already in flight.

For A4, first use existing recorded workflow detail and metadata. Introduce a new
tape version or journey API only if those surfaces demonstrably cannot supply
the required evidence.

## 4. Work B: Make the first encounter compelling

- [x] Keep the existing article as a deep explanation; add a short business-first opening and put the Aurora example before architecture detail.
- [x] Make Constellation orient a new viewer, follow one decision and expose readable evidence without the presenter decoding colours.
- [x] Produce a 1:42, 1920x1080 captioned development walkthrough from actual recorded execution, with explicit source/limitations metadata. It is not a clean-source public release.
- [x] Produce one concise seller guide: talk track, exact demo path, common objections, what is real and what remains reference-only.
- [x] Align primary README/article/film/builder links. The buyer path now leads to the reference installation guide; the companion skill catalogue is an optional builder link.

Primary files: `web/blueprint/src/sections/`, existing HUD components, `README.md`,
`docs/presales/` and `docs/media/`. Keep the canonical
[story contract](../specs/2026-08-10-zava-constellation-story-design.md).
Changes to `aiappsgbb/zava-constellation` belong in its own approved workspace.

Draft prose alongside engineering. Capture final film only after the real flow
and visible evidence are stable. Label automatically exercised operator paths as
such; do not invent a human participant or human approval.

## 5. Work C: Make the reference straightforward to deploy

- [x] Implement the single-replica Bicep configuration and document mandatory resources, identities, model deployments, permissions and cost assumptions.
- [x] Configure private-live authentication and closed-by-default ingress separately from public replay. No Azure resources have been changed.
- [x] Separate readiness from liveness and require the actual Functions worker to respond.
- [x] Exercise the selected workflow, operator paths and recording in an isolated native local environment.
- [ ] Exercise the final image and authentication in an explicitly approved Azure target.
- [ ] Publish a fresh source-bound replay and update the documented recording date/duration from actual metadata. Preserve the previous approved replay for rollback.
- [ ] Finish the existing normal-speed stability gate beyond the previous 131-minute failure window and complete the required human publication review.

Primary files: `infra/`, `deploy/`, existing deployment/proof scripts,
`api/server/services/read_route_auth.py`, `api/server/main.py`,
`docs/DEVELOPMENT.md` and `docs/zava-hosting-brief.md`.
Create a focused reference-install guide only where the existing docs do not
provide one clear path.

### Recovery boundary

Durable history does not automatically persist the control plane. Reproduce the
selected reference's restart behaviour and state its actual limits. If a failure
blocks the supported demo or can duplicate an action, fix that case using the
smallest viable storage/reconciliation change. Do not hide it behind success or
relax a safety check.

Do not promise recovery for every workflow or implement a general persistence
platform merely to make that promise. A mounted Azure Files share is not proof
that native databases or pending approvals are recoverable.

## 6. Explicitly deferred

Generic `WorkflowRepository`/Blob-backend rewrite; distributed writer leases;
universal cross-workflow failover; new tape formats without a demonstrated need;
new agent/provider frameworks; active-active scaling; customer integrations;
additional verticals; production certification; and a mandatory fleet of agents.

Authentication, authority checks, error handling, accessibility, truthful
evidence and defects directly affecting the supported reference are **not**
deferred.

## 7. Completion and permissions

Complete means the chosen demo runs honestly, the article/film sell that same
capability, and the documented Azure reference can actually be installed and
operated within its stated limits. It does not mean "all technology is 100%
correct".

Local evidence and deliverables: [captioned walkthrough](../../media/aurora-recorded-walkthrough.mp4),
[source/limitations](../../media/aurora-recorded-walkthrough.provenance.json),
[seller guide](../../presales/seller-guide.md) and
[reference installation](../../zava-hosting-brief.md).
Three authorised model-backed runs were used: strict-schema rejection, a complete
approved workflow, and an operator-rejected workflow. The operator interface was
exercised by automation; this is not human seller sign-off.

**Checkpoint, 2026-09-11:** Runtime, Aurora, deployment configuration, evidence UI
and the seller package have separate local commits following user approval.
Nothing has been pushed or deployed to Azure. Committing the source does not
relabel the earlier dirty-source film as clean-source release evidence.

Implementation is distinct from this plan revision. Commits, pushes, paid calls,
tenant/access changes and public publication retain their applicable approval
requirements. Copilot asks only for necessary permission or a genuine unresolved
business decision, not routine engineering choices. Human release approval
cannot be manufactured.

Preserve the previous approved public replay until its replacement is ready.
Never roll back by weakening authentication, discarding user data or restoring
fabricated success.

## 8. Reference material, not additional work orders

The six version-1 phase files retain findings and possible implementation detail.
Their broad designs and dependencies are superseded by this plan; consult a
relevant section only when needed for a current task.

- [Canonical Zava/Constellation story](../specs/2026-08-10-zava-constellation-story-design.md)
- [Vertical Build Contract](../contracts/VERTICAL-BUILD-CONTRACT.md)
- [Vertical Proof](../../VERTICAL-PROOF.md)
- [Previous reliability work and remaining release gates](2026-09-08-presales-harness-reliability.md)
- [Architecture](../../ARCHITECTURE.md)
- [Current development/deployment guide](../../DEVELOPMENT.md)
- [Durable retry semantics](https://learn.microsoft.com/azure/durable-task/common/durable-task-error-handling#automatic-retry-on-failure)
