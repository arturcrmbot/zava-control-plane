# POC2 Talent Lifecycle — Design Spec

> **Topic:** Build the Zava POC2 HR Talent Lifecycle "Frontier" demo end-to-end against the 22 capabilities in spec §4.1–4.22 — reusing the POC1 expense-compliance platform (~75% of code per [archive/poc1-inventory.md](../../archive/poc1-inventory.md)) and adding the genuinely new frontier capabilities (voice, avatar, A2A, jurisdiction switching, Threadlight, AG-UI).
> **Date:** 2026-04-28
> **Status:** Design — Track A.1 plan ready; Tracks A.2–A.10 + B–F to be planned in sequence
> **Source status doc:** [docs/poc2-status.md](../../poc2-status.md)
> **Architecture diagram (cloud target):** [docs/poc2-architecture.svg](../../poc2-architecture.svg)
> **Capability spec:** `spec.md` §4.1–4.22 (parent doc; not in this repo)
> **POC1 reuse inventory:** [docs/archive/poc1-inventory.md](../../archive/poc1-inventory.md)

---

## 1. Context

POC2 is the Zava "Frontier" demo: hire a Senior Data Engineer at a Zava USA agency over a 12-week sprint, end-to-end across 5 humans, 4 timezones, multiple surfaces, and two jurisdictions (USA + Germany / BetrVG). 15–20 concurrent hiring workflows on the Control Plane. Operator: HR Business Partner (London). 22 capability demos required from spec §4.1–4.22 — 7 of which are differentiating "Frontier" capabilities not in POC1: voice screening (GPT-Realtime via ACS), avatar onboarding (HeyGen), A2A boundary at the candidate edge, jurisdiction switching, crystallisation pipeline, episodic memory, AG-UI dynamic components, Threadlight SME-knowledge accelerator.

POC1 (expense compliance, 8-week sprint) ships first. POC2 starts from `v0.8-poc1-feature-complete` and reuses the entire platform layer: Durable Functions runtime, MAF Pregel graphs, Fleet Manager service, Apex Control Plane shell, validator-as-guardrail edge pattern, Azurite state, OTEL plumbing, audit ledger, economics service, simulator. Per the inventory ≈ 75% of POC1 source files are domain-agnostic platform code. POC2's work is the ~25% domain layer plus 7 net-new capabilities.

Same architectural thesis as POC1: **agents operate the systems; humans operate the Control Plane.** Same Three Tiers (Fleet Manager / Workflow Orchestration / Agentic Loops). Same skills-first agent design (`*.SKILL.md` declares behaviour; `@define_tool` declares interfaces; ephemeral SDK sessions per phase load both natively).

## 2. Goal

Ship a working talent-lifecycle POC2 demo that:

1. Covers **all 22 capabilities** from spec §4.1–4.22 with a real demo path (live where possible, recorded fallback for region failover).
2. Demonstrates a single hire walking through all 10 phases (Budget → Onboarding) end-to-end against mocks, with HITL gates landing on the correct human surface (Hiring Manager / Teams, HR BP / Control Plane, Finance BP / Adaptive Card, IT Ops / ServiceNow webhook, Candidate / web+voice).
3. Demonstrates jurisdiction switching: same hire scenario, USA vs Germany flag, Compliance phase adds BetrVG check without code change.
4. Demonstrates the seven Frontier capabilities live: voice screen, avatar onboarding, A2A boundary, AG-UI dynamic components, episodic recall, Threadlight SKILL.md generation, crystallisation pipeline.
5. Hits the 12-week sprint target with the 6-track build plan in [poc2-status.md §3](../../poc2-status.md).

Non-goals: production hardening; full Agent 365 integration (GA May 2026); real Workday-HR / Greenhouse / LinkedIn / ACS / HeyGen credentials (mocks); real APIM AI Gateway deployment (narrated in walkthrough); 5,000+ concurrent workflow scale (target architecture only).

## 3. Approach

**In-place addition on top of `v0.8-poc1-feature-complete`.** The POC1 expense-compliance code is preserved untouched. POC2 adds:

- A **second domain orchestrator** (`HiringOrchestrator`) alongside `ExpenseClaimOrchestrator`. Both register with the same Functions host. Simulator chooses which to spawn.
- A **second long-lived GHCP SDK session** (`ThreadlightService`) alongside `FleetManagerService` in FastAPI. Both run from app startup.
- **10 new phase graphs**, **10 new skills**, **7 new MCP mocks**, **MCP tool wrappers** for each mock, **synthetic CV/JD/policy corpus**.
- **3 new UI surfaces**: Hiring Manager (Teams-flavoured single-hire view), Threadlight chat, Candidate web portal. Existing Fleet Dashboard rebinds labels to handle hires; existing `/reviewer-queue` becomes the HR BP queue (POC1 SSC reviewer queue stays for expense scenarios).

Considered and rejected:

- **Replace POC1 with POC2 on `main`.** Would discard a deliverable. Both POCs need to demo; both stay shippable.
- **Two repos.** Doubles infra surface and breaks the "platform reuse" narrative that justifies the 12-week sprint.
- **Refactor POC1 code into a "platform" module before adding POC2.** Premature extraction. The reuse boundary is already implicit in the inventory; mark `domain == hiring | expense` in workflow records and let both run.

POC1 will be tagged `v0.8-poc1-feature-complete` before POC2 work begins.

## 4. Architecture

### 4.1 Orchestrator phase shape

The new `HiringOrchestrator` runs **10 phases** (vs POC1's 7). Same Durable Functions generator pattern, same `wait_for_external_event` HITL gating, same lifecycle event vocabulary (`workflow.started`, `suspended`, `resumed`, `workflow.completed`, `workflow.rejected`), same TrackedExecutor / validator-as-guardrail edge pattern. Long-running timers (days, not 72 hours).

| # | Phase | What happens | Key executors | HITL |
|---|---|---|---|---|
| 1 | **Budget & Approvals** | Pull position from Workday-HR, check budget envelope; gate above £10k | `position_lookup`, `agent_budget`, `validate_budget_schema` | Finance BP Adaptive Card if > £10k delegation |
| 2 | **Job Design** | Draft JD from role profile + market data | `agent_jd_drafter`, `validate_jd_schema` | HR BP review (optional) |
| 3 | **Sourcing** | Post to Greenhouse + LinkedIn; ingest applicants | `greenhouse_post`, `linkedin_search`, `agent_sourcing` | none (auto) |
| 4 | **Triage (Crystallisation)** | Multi-modal CV → structured profile (PDF + LinkedIn JSON + free text) | `cv_get`, `agent_cv_crystalliser`, `validate_profile_schema` | none (auto) |
| 5 | **Screening** | Score against rubric; auto-shortlist top N | `agent_auto_shortlister`, `validate_shortlist_schema` | none (auto with 10% spot-check) |
| 6 | **Voice Screen** | ACS dial; GPT-Realtime conversation; transcript scoring | `acs_dial`, `agent_voice_screener` (multimodal), `transcript_score` | candidate is the human; agent talks |
| 7 | **Interview** | Schedule via Graph; coordinate panel | `graph_calendar`, `graph_mail`, `agent_interview_coordinator` | Hiring Manager confirms panel |
| 8 | **Compliance** | Jurisdiction-route (USA/DE); run jurisdiction-specific checks | `jurisdiction_router`, `agent_compliance`, `validate_compliance_schema` | none (auto in USA path; BetrVG Works-Council notification in DE path) |
| 9 | **Offer** | Compose personalised offer; revocable send via Graph | `agent_offer_personaliser`, `graph_mail`, `validate_offer_schema` | HR BP final approval; candidate accept/decline |
| 10 | **Onboarding** | ServiceNow JML provision; HeyGen avatar welcome; Day 1 calendar | `servicenow_jml`, `heygen_render`, `graph_invite`, `agent_onboarding_buddy` | IT Ops ServiceNow webhook ack |

Cross-cutting (not per-phase):
- **Threadlight** — second long-lived GHCP SDK session in FastAPI. Conducts SME interview, emits `SKILL.md` to disk, registers next ephemeral session loads it.
- **Episodic recall** — `recall_similar_hires` MCP tool queries the state store for prior hires by `(role, jurisdiction)`. Available to any phase agent.
- **Drift detection + 10% spot-check** — Fleet Manager skill extension; reuses existing `query_traces`.

### 4.2 Three tiers (unchanged from POC1)

| Tier | Scope | Lifetime | Reasoning | New for POC2 |
|---|---|---|---|---|
| **Fleet Manager** | Always-on GHCP SDK session in FastAPI. Reads OTEL/event telemetry, composes exception queue, surfaces autonomy + cost reports + drift alerts. | Process-long | Yes — frontier model on triage-filtered events | One-paragraph skill extension: "hiring fleet domain, 15–20 concurrent hires" |
| **Threadlight** | Always-on GHCP SDK session in FastAPI, second instance. Conducts SME interview Q&A loop, emits SKILL.md to disk. | Process-long | Yes | Net-new long-lived session |
| **Workflow Orchestration** | Azure Durable Functions, one instance per hire. HITL waits across days/weeks at zero compute, timer escalation, parallel coordination, checkpoint/replay. | Days–weeks | No | New `HiringOrchestrator` class alongside `ExpenseClaimOrchestrator` |
| **Agentic Loops** | Ephemeral GHCP SDK sessions, one per phase. Same `client.create_session(skill_directories=[...], tools=[...])` pattern. Multi-modal where needed (PDF + JSON + voice). | Seconds–minutes | Yes — model varies by skill | 10 new skills + 10 new agent executors |

### 4.3 Multi-surface convergence (new for POC2)

POC1 has two surfaces: Fleet Dashboard (Finance Controller) and `/reviewer-queue` (SSC Reviewer). POC2 adds three more:

| Surface | User | Path | HITL signal |
|---|---|---|---|
| Fleet Dashboard | HR Business Partner (London) | `web/client/routes/FleetDashboard.tsx` (existing, rebind labels) | Bulk approval, exception queue resolution |
| `/reviewer-queue` | HR Business Partner (London) | existing — same route reskinned | Per-candidate accept/reject |
| `/hiring-manager` | Hiring Manager (LA) | new lightweight surface — single-hire view, panel scheduling RSVP, candidate scorecard | Panel approval, offer-letter sign-off |
| Adaptive Card | Finance BP (Mumbai) | sent via Graph mail mock; callback resolves Durable HITL | £10k+ budget approval |
| ServiceNow webhook | IT Ops (Chennai) | inbound `/api/webhooks/servicenow`; correlates to Durable instance | JML provisioning ack |

The Fleet Dashboard remains the **primary operator surface**. Other surfaces are HITL endpoints; their state surfaces back to the Fleet Dashboard via the existing event bus + SSE hub.

### 4.4 Multi-jurisdiction routing (new for POC2)

POC1 has one policy bundle. POC2 has two: `data/synthetic/policies/usa/` and `policies/de/` with divergent rules (visa thresholds, notice periods, works-council triggers). The `jurisdiction_router` deterministic executor reads `position.country` and routes the Compliance phase accordingly.

In the cloud target architecture, **APIM AI Gateway** does jurisdiction-aware model routing (data residency: EU traffic to EU model endpoints). For the local demo this is documented in the architecture walkthrough — not deployed.

### 4.5 A2A boundary (new for POC2)

The Candidate is **external** to Zava. Their interaction with the hiring agent crosses an organisational boundary. The architecture: an external Personal Agent (PA) talks to internal `hiring-agent@zava` over A2A protocol; APIM AI Gateway polices the boundary (auth, rate, content). For the local demo, the candidate PA is **simulated by the `acs-mcp`** transcript path — the A2A protocol is described and the boundary is shown in the Control Plane.

## 5. Components

Working from the [POC2 status doc capability matrix](../../poc2-status.md#1-capability-matrix--starting-state). Three buckets:

### 5.1 Reuse from POC1 untouched

Durable Functions runtime, `_common.py`, `_tracked_executor.py`, Fleet Manager service + queue + triage, event bus, SSE hub, state store, audit logger, economics service, durable client, `_wrapper.py`. All POC1 routes (`workflows.py`, `fleet.py`, `policy.py`, `audit.py`, `evals.py`, `orchestration.py`, `internal_durable_event.py`, `stream.py`, `accuracy.py`, `policy_md.py`). All POC1 services (`exception_factory`, `exception_narrative`, `synthetic_data`, `simulator_orchestrator`). All Apex UI shell components (`PhaseRibbon`, `EconomicsPanel`, `FleetAssignment`, `AuditTrail`, `OrchestrationView`, `OtelSpanTree`, `BulkHitlModal`, `SkillAmplificationPanel`, `WhatIfPanel`, `ExceptionItem`, `FleetManagerRail`).

POC1's existing MCP tools (`query_fleet`, `query_traces`, `compose_exception`, `propose_skill_amp`, `dry_run_policy`, `audit_query`) — all reusable as-is for hiring fleet.

### 5.2 Adapt from POC1 (rename + retarget; structure unchanged)

- `ExpenseClaimOrchestrator` (the **class**, not the file) becomes the template for `HiringOrchestrator` — generator pattern + `wait_for_external_event` + `task_any` timer race + lifecycle checkpoints. POC1 file stays put; POC2 adds a sibling.
- `WorkflowDetail.tsx`, `WorkflowCard.tsx`, `PhaseTimeline.tsx`, `Analytics.tsx`, `FleetDashboard.tsx` — labels rebind based on `workflow.domain` field (`hiring` | `expense`); no layout change.
- `simulator_orchestrator.py` — new `spawn_hiring_workflow(scenario, position_id?)` alongside `spawn_expense_workflow`.
- `synthetic_data.py` — new bridge to `data/synthetic/cvs/` and `policies/usa/de/`.
- `exception_factory.py` — new option set for hiring exceptions (`approve-budget`, `reject-budget`, `confirm-shortlist`, `reschedule-interview`, `revise-offer`, etc.).
- `fleet-manager.skill.md` — one paragraph for hiring domain (alongside the existing finance paragraph).

### 5.3 New for POC2

#### Per-phase skills (10)

`budget`, `jd-drafter`, `sourcing`, `cv-crystalliser`, `auto-shortlister`, `voice-screener`, `interview-coordinator`, `compliance`, `offer-personaliser`, `onboarding-buddy`. Each with `name`, `description`, `model`, `allowed-tools` frontmatter and a prompt body.

#### Cross-cutting skills

`threadlight-builder` — drives the SME-interview accelerator. `jurisdiction-router-skill` — paragraph in the Compliance skill that reads `position.country`.

#### Agent executors (10)

One per phase, mirroring POC1's `agent_rag_classifier` / `agent_receipt_validator` shape. Each loads its skill via `_wrapper.run_agent_session(prompt, tools=[...], skill_dir=Path)`.

#### Schema validators (10)

One per phase output. Same raise-then-adapt pattern as POC1's `validate_classification_schema`.

#### Phase graphs (10)

`budget.py`, `job_design.py`, `sourcing.py`, `triage.py`, `screening.py`, `voice.py`, `interview.py`, `compliance.py`, `offer.py`, `onboarding.py`. Each is a 3-executor `WorkflowBuilder`: `<agent> → <validator> → terminal` (some with deterministic pre-fetch like POC1's `lookup_claim → doc_intel → agent`).

#### MCP tools (~12 new)

| Tool | Domain | Notes |
|---|---|---|
| `position_lookup` | Workday-HR | Same shape as `claim_lookup` |
| `cv_get` | Greenhouse | Pre-fetches PDF to attach to multimodal session |
| `linkedin_search` | LinkedIn | Candidate sourcing |
| `greenhouse_post` | Greenhouse | Job posting |
| `graph_calendar` | MS Graph | Schedule interviews |
| `graph_mail` | MS Graph | Adaptive Cards + mail send |
| `servicenow_jml` | ServiceNow | JML ticket create |
| `acs_dial` | ACS | Voice screen kickoff (mock returns transcript) |
| `transcript_score` | local | Score voice transcript against rubric |
| `heygen_render` | HeyGen | Avatar render (mock returns mp4 path) |
| `recall_similar_hires` | local state | Episodic memory query |
| `jurisdiction_policy_search` | local corpus | Per-jurisdiction policy retrieval |

All follow POC1's dual-surface pattern: plain Python function with `@traced_tool("dotted.name")` + `Tool` instance via `@define_tool(name="underscored")`.

#### MCP mocks (7 Node services)

`greenhouse-mcp` (`:4201`), `linkedin-mcp` (`:4202`), `workday-hr-mcp` (`:4203`), `graph-mcp` (`:4204`), `servicenow-mcp` (`:4205`), `acs-mcp` (`:4206`), `heygen-mcp` (`:4207`). Each: Express + JSON fixtures + 4–6 endpoints. Same shape as POC1's `workday-mcp/concur-mcp/maconomy-mcp`.

POC1's three EMS mocks stay running for the expense scenarios; POC2 mocks add to the set.

#### Synthetic corpus

`data/synthetic/cvs/` (~200 PDFs across 10 roles), `data/synthetic/jds/` (10 JD templates), `data/synthetic/policies/usa/`, `data/synthetic/policies/de/` (BetrVG corpus), `data/synthetic/positions.json` (~30 positions across 10 roles, 2 jurisdictions), `data/synthetic/interview_transcripts/` (voice screen ground-truth).

#### Net-new services

- `threadlight_service.py` — second long-lived GHCP SDK session, mirrors `fleet_manager_service.py` shape.
- `adaptive_card.py` — Finance BP Adaptive Card composer + Graph send (hook-gated).

#### Net-new routes

- `/api/webhooks/servicenow` — inbound from IT Ops
- `/api/threadlight/*` — Threadlight chat surface
- `/api/a2a/*` — A2A boundary surface (simulated for demo)

#### Net-new UI

- `routes/HiringManager.tsx` — Teams-flavoured single-hire view
- `routes/Threadlight.tsx` — SME interview chat
- `routes/CandidatePortal.tsx` — candidate web portal
- `components/AgentDrivenComponent.tsx` — AG-UI dynamic component renderer

## 6. Demo path (12-minute compressed walkthrough)

The 12-week real-time hire compresses to 12 demo minutes via the simulator:

| Minute | What evaluator sees | Surfaces lit | Capabilities |
|---|---|---|---|
| 0:00–1:00 | HR BP opens Fleet Dashboard. 18 active hires. 3 stuck (exception queue). | Fleet Dashboard | §4.1, §4.4 |
| 1:00–2:00 | New requisition arrives for Senior Data Engineer (USA). Phase 1 Budget runs; £150k position triggers Finance BP Adaptive Card. Card resolves; Phase 2 fires. | Fleet Dashboard + Finance BP email mock | §4.3, §4.6 |
| 2:00–3:00 | Phases 2–5 run in fast-forward: JD draft, Greenhouse post, 50 CVs ingest, crystallisation, auto-shortlist top 5. Triage shows AG-UI scorecard. | Fleet Dashboard, AG-UI | §4.8, §4.21 |
| 3:00–4:00 | Voice screen: phone rings (simulated), transcript renders live, score 7.8/10, advance. | Candidate portal voice path | §4.5 |
| 4:00–5:00 | Interview phase: Graph calendar coordinates panel. Hiring Manager surface lights up (Teams). | Hiring Manager surface | §4.6 |
| 5:00–6:00 | Toggle USA→Germany flag. Same hire re-routes through Compliance with BetrVG check; Works-Council notification fires. | Compliance phase + Fleet Dashboard | §4.10, §4.22 |
| 6:00–7:00 | Offer letter composed with personalisation; HR BP approves; candidate accepts. | HR BP queue + candidate portal | §4.3, §4.13 |
| 7:00–8:00 | Onboarding: ServiceNow JML ticket creates (IT Ops webhook acks); HeyGen avatar welcome plays with new hire's name + manager. | IT Ops webhook + onboarding surface | §4.5, §4.6 |
| 8:00–9:00 | Episodic recall demo: "we've hired 3 Senior Data Engineers in DE last year — here's what we learnt". | Fleet Manager rail | §4.7 |
| 9:00–10:00 | Threadlight demo: HR BP runs SME interview with on-screen subject; new SKILL.md generates live; next hire uses it. | Threadlight surface | §4.14 |
| 10:00–11:00 | Region failure simulator: kill Functions host. 14 in-flight hires pause. Restart. Durable replays. No data loss. | Fleet Dashboard recovery | §4.22 |
| 11:00–12:00 | Cost-per-hire report. Drift detection. APIOps + Entra Agent ID architecture walkthrough. | Fleet Manager rail + narrative | §4.15, §4.17, §4.18, §4.20 |

Live where possible; recorded fallback for region failure if it flakes.

## 7. Capability map

22 demos from spec §4.1–4.22, each mapped to track + test evidence.

| § | Capability | Track | Status (after track lands) | Test evidence |
|---|---|---|---|---|
| 4.1 | Multi-agent orchestration | A | ✅ | E2E test: spawn hire → all 10 phases checkpoint |
| 4.2 | System integration & auth | A | ✅ | 7 mocks running; tools call them |
| 4.3 | HITL approval gates + bulk action | A + B | ✅ | Bulk approve 10 hires; Adaptive Card round-trip |
| 4.4 | Exception handling + self-healing | A | ✅ | Mock timeout + retry test |
| 4.5 | Voice + avatar | C | ✅ | Voice transcript test; avatar mp4 render |
| 4.6 | Multi-surface convergence | B | ✅ | Single hire fires all 5 surface HITLs |
| 4.7 | Episodic memory | E.5 | ✅ | `recall_similar_hires` test |
| 4.8 | Crystallisation | E.4 (in A) | ✅ | Multimodal CV ingest test |
| 4.9 | Synthetic CV gym | A | ✅ | 200-CV corpus + accuracy harness |
| 4.10 | Jurisdiction switching | D | ✅ | USA→DE toggle test; BetrVG fires |
| 4.11 | Tiered model usage | A | ✅ | Skill `model:` frontmatter; OTEL shows model name |
| 4.12 | Skill library + APIOps | F | 🟡 | Architecture walkthrough; APIOps narrated |
| 4.13 | Hooks for non-revocable sends | A | ✅ | Offer-letter hook + JML hook tests |
| 4.14 | Threadlight | E.1 | ✅ | E2E: SME chat → SKILL.md → next session loads |
| 4.15 | Entra Agent ID | F | 🟡 | Demo via preview API or narrated |
| 4.16 | Audit + jurisdiction-partitioned reports | F (POC1 reuse) | ✅ | `audit_query` test with partition |
| 4.17 | Cost-per-hire | F (POC1 reuse) | ✅ | `query_economics` test |
| 4.18 | Process evolution | F (POC1 reuse) | ✅ | `propose_skill_amp` test |
| 4.19 | A2A at candidate boundary | E.2 | 🟡 | Simulated; protocol narrated |
| 4.20 | Drift detection + 10% spot-check | F | ✅ | Fleet Manager skill paragraph + test |
| 4.21 | AG-UI dynamic components | E.3 | ✅ | Triage emits component spec; UI renders |
| 4.22 | Region failover + jurisdiction routing | D + F | ✅ | Region-fail simulator (POC1 reuse); APIM narrated |

**Counts:** 18 ✅, 4 🟡 (narrative), 0 ❌.

## 8. Risks

| Risk | Mitigation |
|---|---|
| GHCP SDK + ACS GPT-Realtime integration is undocumented | `acs-mcp` returns canned transcripts for the demo path; live realtime is stretch. |
| HeyGen API rate limits + render latency | Pre-render avatar clips; mock `heygen-mcp` returns mp4 paths. |
| A2A protocol still in spec evolution | Simulate via the `acs-mcp` transcript path; describe the protocol in the architecture walkthrough. |
| Foundry Hosted Agents max 5 replicas in preview | POC2 demo runs on the dev box, not Foundry — narrate cloud arch only. |
| BetrVG legal accuracy | Use synthetic policy text; disclaimer in demo: "illustrative not legal advice". |
| Multimodal CV ingestion (PDF + JSON + free-text) is finicky in current SDK | Validate with smoke test in Track A.4 (Triage); fall back to text-only if multimodal flakes. |
| 12-week sprint is tight for 22 capabilities | The capability matrix has 4 narrative-only items; sequencing puts reuse-track items in week 12 buffer. |

## 9. Plans

This spec is the **design contract** for POC2. Implementation lands as a sequence of plans, one per coherent work-unit. Each plan executes via the `superpowers:subagent-driven-development` workflow.

### 9.1 Track A — Domain Rebind (foundation)

Splits into **A.1 (walking skeleton)** and **A.2–A.10 (per-phase rollout)**.

| Plan | Scope | Plan doc |
|---|---|---|
| **A.1** | Walking skeleton — `HiringOrchestrator` + Phase 1 Budget end-to-end + `workday-hr-mcp` + simulator extension + UI label rebind. Establishes the template the remaining 9 phases follow. | [`docs/superpowers/plans/2026-04-28-poc2-track-a1-walking-skeleton.md`](../plans/2026-04-28-poc2-track-a1-walking-skeleton.md) |
| **A.2** | Phase 2 Job Design — JD drafter skill + agent + validator + graph + `linkedin-mcp` + `greenhouse-mcp` mocks (used by A.3 too) | TBD |
| **A.3** | Phase 3 Sourcing — `greenhouse_post` + `linkedin_search` tools + sourcing agent | TBD |
| **A.4** | Phase 4 Triage + Crystallisation — multimodal CV ingest. Covers §4.8. | TBD |
| **A.5** | Phase 5 Screening + auto-shortlister | TBD |
| **A.6** | Phase 6 Voice Screen — skeleton only (full ACS in Track C) | TBD |
| **A.7** | Phase 7 Interview — `graph-mcp` mock + interview coordinator | TBD |
| **A.8** | Phase 8 Compliance — skeleton only (jurisdiction in Track D) | TBD |
| **A.9** | Phase 9 Offer — offer personaliser + revocable send hook | TBD |
| **A.10** | Phase 10 Onboarding — ServiceNow + onboarding-buddy skeleton (avatar in Track C) | TBD |

End of Track A: a single hire walks all 10 phases against mocks. Tag `v0.9-poc2-track-a-complete`.

### 9.2 Tracks B–F

Sequenced to start once Track A is green.

| Track | Scope | Capabilities | Dependencies |
|---|---|---|---|
| **B** | Multi-surface convergence: Adaptive Card sender, ServiceNow webhook receiver, Hiring Manager Teams surface, Candidate web portal | §4.6, §4.3 (extends) | A complete |
| **C** | Voice + Avatar: ACS + GPT-Realtime, HeyGen | §4.5 | A.6 + A.10 |
| **D** | Compliance + Jurisdiction: per-jurisdiction policy bundles, BetrVG checker, jurisdiction-aware routing narrative | §4.10, §4.22 | A.8 |
| **E** | Frontier capabilities: Threadlight (E.1), A2A (E.2), AG-UI (E.3), Crystallisation (E.4 — already in A.4), Episodic (E.5) | §4.7, §4.14, §4.19, §4.21 | A complete |
| **F** | Reuse-from-POC1: cost-per-hire labels, drift detection, process evolution proposals, region failover, audit partitioning | §4.12, §4.15, §4.16, §4.17, §4.18, §4.20, §4.22 (rest) | A complete |

Each track gets its own plan. Plans referenced from this spec as they're authored.

## 10. Definition of done

POC2 is "feature-complete" when:

1. All 22 capabilities have a green test or a narrated demo path.
2. The 12-minute demo walkthrough runs end-to-end against local mocks.
3. Tag `v1.0-poc2-frontier` pushed.
4. `docs/poc2-DEMO.md` complete (mirror of POC1 DEMO doc).
5. Any narrative-only capabilities (§4.12, §4.15, §4.19) have one architecture-walkthrough page in `docs/`.
