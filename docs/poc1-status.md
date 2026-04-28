# POC1 Expense Compliance — Status & Plan

Handover doc for the technical team. Three sections: where we are against the brief, the architecture (with local-vs-cloud split), and what's left to build.

---

## 1. Acceptance criteria — status

[Brief §7](poc1-brief.md#sec-7), 13 criteria.

| # | Criterion | Status | Code anchor |
|---|---|---|---|
| 1 | Single Finance Controller view across 30+ workflows | ✅ | [expense_claim.py](../api/functions/workflows/expense_claim.py); [simulator_orchestrator.py](../api/server/services/simulator_orchestrator.py) |
| 2 | Exception-only surfacing | ✅ | [WorkflowCard.tsx](../web/client/components/WorkflowCard.tsx) |
| 3 | Bulk approval 10+ | ✅ | [BulkHitlModal.tsx](../web/client/components/BulkHitlModal.tsx) |
| 4 | ≥95% R/A/G accuracy | 🟡 | Pipeline live; first 300-claim run 64.3%; smoke 5/6 after one prompt iteration; full re-run is post-tag work per [accuracy run-book](poc1-accuracy-runbook.md). [rag-classifier/SKILL.md](../api/server/skills/rag-classifier/SKILL.md), [accuracy_harness_workflow.py](../api/functions/workflows/accuracy_harness_workflow.py) |
| 5 | Receipt cross-validation | ✅ | Live smoke 3/3. [receipt-validator/SKILL.md](../api/server/skills/receipt-validator/SKILL.md), [receipt.py](../api/functions/graphs/receipt.py) |
| 6 | Progressive enforcement | ✅ | [escalation-advisor/SKILL.md](../api/server/skills/escalation-advisor/SKILL.md), [employee_history.py](../api/server/mcp_tools/employee_history.py) |
| 7 | Autonomous learning | ✅ | Phase 5 HITL justification round-trip + FM `fleet.tick` behaviour-change loop. [fleet-manager/SKILL.md](../api/server/skills/fleet-manager/SKILL.md), [query_reviewer_decisions.py](../api/server/mcp_tools/query_reviewer_decisions.py) |
| 8 | SSC Reviewer interface | ✅ | [arbitration/SKILL.md](../api/server/skills/arbitration/SKILL.md), [arbitrate.py](../api/functions/graphs/arbitrate.py), [ReviewerQueue.tsx](../web/client/routes/ReviewerQueue.tsx) |
| 9 | Multi-EMS Control Plane | ✅ | [concur-mcp/](../mocks/concur-mcp/), [maconomy-mcp/](../mocks/maconomy-mcp/), [claim_lookup.py](../api/server/mcp_tools/claim_lookup.py) |
| 10 | EMS extensibility narration | ✅ | Maconomy rebound to expense surface + 2-file diff property. [demo-ems-extensibility.md](demo-ems-extensibility.md) |
| 11 | Region failure recovery | ✅ | [simulator_orchestrator.py::simulate_region_failure](../api/server/services/simulator_orchestrator.py); `/api/simulator/region-failure` route. |
| 12 | Immutable audit + reporting | ✅ | [audit-summariser/SKILL.md](../api/server/skills/audit-summariser/SKILL.md), [audit.py](../api/functions/graphs/audit.py), [audit_query.py](../api/server/mcp_tools/audit_query.py) |
| 13 | Cost-per-task report | ✅ | [query_economics.py](../api/server/mcp_tools/query_economics.py) + FM `report.cost_per_task` skill section |

**12 demoable, 1 partial.** AC #4 (corpus-wide ≥95%) is one ~25-minute model run away; the pipeline is shipped (smoke 5/6 after iteration). Run via [poc1-accuracy-runbook.md](poc1-accuracy-runbook.md) post-tag.

---

## 2. Architecture

Everything below `Dev box` runs on a single laptop. Anything in `Cloud` is reached over HTTPS. There is no Azure deployment for the POC demo — Durable state is in Azurite, FastAPI/Functions/Vite are local processes. Only the model API (GitHub Copilot) and OTEL export (Azure Monitor) are cloud-side.

```mermaid
flowchart TB
    BROWSER["Browser · evaluator workstation"]

    subgraph DEVBOX["Dev box (laptop · localhost)"]
        VITE["Vite dev server :5173<br/>React Control Plane UI"]
        FASTAPI["FastAPI :8000 · uvicorn<br/>routes / EventBus / SSEHub / StateStore<br/>FleetManagerService (long-lived GHCP session)"]
        FUNC["Azure Functions host :7071 · func start<br/>ExpenseClaimOrchestrator (Durable)<br/>activities: intake/classify/receipt/route/notify/(arbitrate)/(audit)"]
        AZURITE[("Azurite :10000-10002<br/>Durable state · checkpoints · timers<br/>blob/queue/table emulator")]
        WORKDAY["Node mock :4101<br/>workday-mcp · 150 claims"]
        CONCUR["Node mock :4102<br/>concur-mcp · 150 claims · OAuth"]
        MACONOMY["Node mock :4103<br/>maconomy-mcp · narration only"]
        SYNTH[("data/synthetic/<br/>policy.md · 300 claims · 300 PNGs<br/>30 employees · 53 precedents")]

        VITE -- "fetch · /api" --> FASTAPI
        VITE -- "SSE · /api/stream/fleet" --> FASTAPI
        FASTAPI -- "schedule_new_orchestration HTTP" --> FUNC
        FUNC -- "Durable state · checkpoint/replay" --> AZURITE
        FUNC -- "/internal/durable-event webhook" --> FASTAPI
        FUNC -- "claim_lookup HTTP" --> WORKDAY
        FUNC -- "claim_lookup HTTP" --> CONCUR
        FASTAPI -.- SYNTH
        WORKDAY -.- SYNTH
        CONCUR -.- SYNTH
    end

    subgraph CLOUD["Cloud (HTTPS)"]
        GHCP["GitHub Copilot endpoint<br/>gpt-4.1 chat + multimodal<br/>tools registered via @define_tool"]
        APPINSIGHTS["Azure Monitor / App Insights<br/>OTEL spans · Foundry Tracing tab<br/>(only when APPLICATIONINSIGHTS_CONNECTION_STRING is set)"]
        APIM["APIM AI Gateway<br/>(out of scope for POC demo)"]
    end

    BROWSER -- "http :5173 · ws SSE" --> VITE
    FASTAPI -- "long-lived session · gh auth token" --> GHCP
    FUNC -- "ephemeral session per phase · gh auth token" --> GHCP
    FASTAPI -- "OTEL exporter (optional)" --> APPINSIGHTS
    FUNC -- "OTEL exporter (optional)" --> APPINSIGHTS

    classDef cloud fill:#e0f2fe,stroke:#0284c7
    classDef local fill:#fef3c7,stroke:#d97706
    classDef stub stroke-dasharray:5 5,fill:#f1f5f9
    class CLOUD cloud
    class DEVBOX local
    class APIM stub
```

### Inside the Functions host — per-claim flow

Each `ExpenseClaimOrchestrator` instance walks the seven phases. All seven are wired to MAF Pregel graphs as of `v0.8`.

```mermaid
flowchart LR
    START(["claim arrives"])
    P1["Phase 1 · Intake<br/>lookup_claim → doc_intel → field_extractor → required_fields"]
    P2["Phase 2 · Classify<br/>agent_rag_classifier → schema validator<br/>tools: policy_search, claim_get_structured"]
    P3["Phase 3 · Validate Receipt<br/>agent_receipt_validator → schema validator<br/>tool: claim_get_structured · attachment: PNG"]
    P4["Phase 4 · Route<br/>agent_escalation → apply_verdict_routing<br/>tool: employee_history"]
    G{"Verdict?"}
    GREEN(["auto-approve"])
    AMBER(["reviewer queue"])
    P5["Phase 5 · Notify (Red)<br/>agent_notification<br/>tools: claim_summary, policy_cite"]
    HITL{"wait_for_external_event<br/>justification · 72h timer"}
    P6["Phase 6 · Arbitrate<br/>agent_arbitration → schema validator<br/>tools: precedents_search, policy_search"]
    HITL2{"wait_for_external_event<br/>reviewer_decision · 72h timer"}
    P7["Phase 7 · Audit<br/>agent_audit_summariser → terminal<br/>tools: claim_summary, audit_query"]
    DONE(["workflow.completed"])
    TIMEOUT(["timeout"])
    REJECTED(["rejected"])

    START --> P1 --> P2 --> P3 --> P4 --> G
    G -->|green| GREEN --> P7
    G -->|amber| AMBER --> P7
    G -->|red| P5 --> HITL
    HITL -->|justification| P6 --> HITL2
    HITL -->|72h timer| TIMEOUT
    HITL2 -->|accept| P7
    HITL2 -->|reject| REJECTED
    HITL2 -->|72h timer| TIMEOUT
    P7 --> DONE
```

**Three tiers (unchanged from the spec).** Fleet Manager: always-on session in FastAPI, reads telemetry, owns the exception queue. Workflow Orchestration: Durable Functions, one instance per claim, HITL waits at zero compute. Agentic Loops: ephemeral SDK sessions per phase, `client.create_session(skill_directories=[…], tools=[…])` registers skills + native tools, the model invokes them per `allowed-tools` frontmatter — no Python prompt-stuffing.

---

## 3. What's left

### AC #4 — Corpus-wide accuracy gate

The pipeline is live; one ~25-minute model run captures the number into `docs/poc1-accuracy-baseline.json`. Per the [run-book](poc1-accuracy-runbook.md), iterate prompt + retrieval if < 95% (we're already at smoke 5/6 after one tweak). Run post-tag, not pre-demo.

### Demo dry run

Walk through [DEMO.md](DEMO.md) end-to-end with someone playing WPP evaluator. Capture bugs; record `docs/demo-failover.mp4` as the AC #11 backup.

---

## 4. Repo pointers

| Topic | File |
|---|---|
| Brief verbatim | [poc1-brief.md](poc1-brief.md) |
| Pivot design spec | [superpowers/specs/2026-04-27-...-design.md](superpowers/specs/2026-04-27-poc1-expense-compliance-pivot-design.md) |
| Accuracy run-book | [poc1-accuracy-runbook.md](poc1-accuracy-runbook.md) |
| First baseline (64.3%) | [poc1-accuracy-baseline.json](poc1-accuracy-baseline.json) |
| GHCP SDK skill conventions (global) | `~/.claude/skills/ghcp-sdk-python/SKILL.md` |
| Local dev | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Demo script | [DEMO.md](DEMO.md) |

**Current tag:** `v0.8-poc1-platform-complete`. AC #4 corpus-wide accuracy run is the only remaining work.
