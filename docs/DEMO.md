# Demo flow — Microsoft / WPP vendor presentation

Live, single-presenter walkthrough of the Microsoft Apex submission for
the WPP Agentic AI RFP. Three demo slots inside the 2-hour vendor day:
75 minutes of live evidence across the Control Plane and the two POCs,
backed by 30 minutes of probe Q&A on the running stack.

Everything below is **live** against the running substrate — no slides,
no recorded segments. The operator narrates over real workflows the
substrate is processing autonomously throughout.

---

## Slot 2 · Live Control Plane demo — 30 min

The operator-facing surface of the Apex framework. This is the day-one
experience for a WPP Finance Controller supervising a fleet of agentic
expense workflows.

| # | Beat | Time | Acceptance criterion |
|---|---|---|---|
| 1 | Open Fleet dashboard — ~30 in-flight workflows the substrate is processing autonomously | 2m | AC #1 fleet view · AC #2 exception-only surfacing |
| 2 | Drill into a flagged workflow — phases, agent reasoning, policy citations | 3m | AC #4 policy-driven classification |
| 3 | Bulk approve a clustered exception (one decision, many workflows) | 2m | AC #3 bulk action |
| 4 | Switch to Microsoft Foundry portal — the same workflow as a distributed trace with token telemetry, tool calls, agent identities | 5m | Telemetry escapes the substrate; same observability stack the engagement POC will use |
| 5 | Cost-per-task tile — derived from real model token telemetry × published Azure rates | 2m | AC #13 cost-per-task report |
| 6 | Open the workflow's immutable audit ledger — versioned, retention-policy-protected append blob | 2m | AC #12 immutable audit |
| 7 | Ask the Fleet Manager in natural language for a cost summary across the week | 2m | AC #13 reporting |
| 8 | SSC Reviewer queue — arbitration recommendation pre-composed with cited precedent | 3m | AC #8 reviewer interface |
| 9 | Justification round-trip — Red workflow → notification → justification → arbitration → resolution end-to-end | 4m | AC #7 autonomous learning loop |
| 10 | Behaviour-change proposal — Fleet Manager observes 50+ consistent reviewer decisions and proposes an autonomy promotion | 3m | AC #7 autonomous learning |
| 11 | Continuous evaluation page — both POCs' agents scored against ground truth and Microsoft Foundry evaluators | 2m | AC #4 evaluation pipeline |

Reserve evidence available on request: EMS extensibility (AC #10),
region failure recovery (AC #11), repeat-offender escalation (AC #6).

---

## Slot 3 · POC1 architecture walkthrough — 15 min

Architecture talk grounded in **live evidence per layer** — no abstract
diagrams without something running on screen to back the claim.

| Layer | Time | What we show |
|---|---|---|
| Context | 3m | Operator surface, EMS connections, Microsoft Foundry boundary. Live: the multi-EMS fleet view shows uniform claim cards regardless of source. |
| Container | 5m | Three tiers — long-lived Fleet Manager session, Durable Functions orchestrator, ephemeral per-phase agentic loops. Validators as the deterministic edge between agent reasoning and downstream state. Live: drill into a workflow's phases and see the deterministic / agent / validator executor mix. |
| Component — Fleet Manager | 5m | Single supervisor session, triage filter, debouncing queue, MCP toolkit. Live: ask the Fleet Manager a question and watch its tool calls and reasoning stream. |
| Operator probe | 2m | "Where would you like me to dig?" |

Reserve evidence available on request: continuous evaluation against
the corpus, real OCR via Azure Document Intelligence, progressive
enforcement on a repeat offender, multi-EMS uniformity side-by-side.

---

## Slot 4 · POC2 architecture walkthrough — 30 min

Same architectural shape, different domain — the POC2 hiring lifecycle
on the same substrate. Walks the candidate journey end-to-end and shows
the four genuinely new capabilities (voice, avatar, A2A, jurisdiction
switching) live.

| Beat | Time | What we show |
|---|---|---|
| Substrate reuse | 3m | The platform layer is identical between POC1 and POC2 — the orchestrator class and the per-phase graphs change; everything else is reused. |
| Candidate apply → live portal status | 3m | Public application form spawns the hiring orchestrator and emits a magic-link status URL within seconds. |
| Triage / CV crystallisation | 5m | Multimodal extraction from the candidate's CV PDF + LinkedIn profile, scored by per-field accuracy evaluators against ground truth. |
| Voice screen | 5m | Real Azure GPT-Realtime voice screen via WebRTC, with transcript scoring. |
| Jurisdiction switching | 3m | Flip the country flag USA → Germany; the workflow grows a Compliance step (BetrVG works-council notification) without any code change. |
| Multi-surface convergence | 5m | One hire walks across five different human surfaces — operator dashboard, Adaptive Card, ServiceNow, recruiter view, candidate portal — without losing identity or state. |
| Continuous hiring evaluations | 3m | Per-agent evaluator scores for CV extraction accuracy, jurisdiction routing correctness, shortlist decision quality — joined to ground truth from the synthetic CV corpus. |
| Onboarding avatar | 2m | Personalised welcome video rendered for the new hire. |
| Operator probe | 1m | "Where would you like me to dig?" |

Reserve evidence available on request: A2A boundary inbound from a
candidate's personal agent, dynamic AG-UI scorecards differing by role
family, region failover against in-flight hires.

---

## Slot 5 · Q&A — 30 min

Live stack remains running. The committee's standard probe questions
are answered against real evidence on screen.

Anticipated themes the operator is rehearsed on:

- Provenance of cost numbers and how they roll up
- Immutability of the audit ledger (live verification, not narrated)
- How a ninth domain is added — the substrate's central claim
- Where Microsoft Foundry surfaces (tracing, evaluation, observability)
  fit alongside the agent runtime
- The seam from the lab build to the engagement POC at signed contract
  — what changes, what stays
- Skills + MCP tool allow-lists vs prompt engineering
- Engagement-POC scope vs lab-build scope — what is real today, what is
  Microsoft committing to deliver during the engagement

Each anticipated question maps to a live artefact the operator can
pull up within seconds.
