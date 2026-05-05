# DEMO — Vendor day runbook (Fri 8-May → Wed 13-May 2026)

Operator runbook for the **2-hour WPP vendor presentation slot**. Six
slots; the three demo slots (2, 3, 4) are 75 minutes total and all live.
Single presenter. POC2 surfaces are fair game inside Slot 2 wherever
they reinforce the substrate story.

This file is **deliberately high-level** — the operator knows what to
say. Each slot lists the beats in order, the live URL, and the AC /
talking-point anchor. Detailed per-beat scripts (curl payloads, inject
recipes, fallbacks) live in `docs/DEMO.md.bak` if you need them; the
substrate's autonomous loop produces enough live traffic that you
mostly don't.

> **Other demos.** [poc2-DEMO.md](poc2-DEMO.md) (full POC2 hiring
> walk) and [poc2-quick-demo.md](poc2-quick-demo.md) (5–8-min apply →
> offer compressed) remain useful for rehearsing the POC2 mechanics.
> [blueprint.md](blueprint.md) is the editorial pitch the substrate
> carries.

---

## Pre-flight (15 min before guests)

| | |
|---|---|
| Boot stack | `make reset && make up` — wait for "All services up" + 30s simulator warm-up |
| Sanity check | `curl -s http://localhost:3001/api/foundry/health \| python3 -m json.tool` — every check should be green |
| Sign in | `az login` (audit blob URL must resolve), `gh auth status` |
| Tabs to open | `localhost:5173/` (Fleet) · `:5173/reviewer-queue` · `:5173/policy` · `:5173/evaluations` · `:5174/recruiter` (POC2) · `https://ai.azure.com/build/tracing` (Foundry portal) |
| Spare terminal | for `curl` injects, `git diff`, ad-hoc Q&A |
| Backup | recorded `docs/projectapexdemo.mp4` if anything flakes |

If `/api/foundry/health` returns anything red — STOP. Fix before guests
arrive. The Foundry Tracing tab beat is the single biggest credibility
moment; an empty Tracing tab undoes the demo.

---

## Slot 1 · Partnership vision (15 min)

Not in this runbook — separate deliverable.

---

## Slot 2 · Live Control Plane demo — 30 min

> **The differentiator slot.** This is where today's Foundry-credibility
> work has to land. Lean on these three moments: (a) tab to Foundry
> Tracing showing the workflow you just clicked, (b) cost number
> derived from real token telemetry × published Azure rates, (c) audit
> ledger as a live immutable blob URL.

| # | Beat | Time | URL | Anchor |
|---|---|---|---|---|
| 1 | Open Fleet — ~30 in-flight workflows ramping in autonomously | 2m | `/` | AC #1, #2 |
| 2 | Drill into one Amber → Phases / Reasoning / Amplification tabs | 3m | `/workflows/<id>` | AC #4 |
| 3 | Bulk approve a clause cluster (`§3.1 Meals` × ~12 claims) | 2m | `/exception-queue` | AC #3 |
| 4 | **Tab to Foundry Tracing** → same workflow, full span tree, gen_ai.usage tokens | 5m | `https://ai.azure.com/build/tracing` filtered on `customDimensions.workflow_id` | **Differentiator** |
| 5 | Back to UI → cost tile reads from real `gen_ai.usage.*` × published rates | 2m | `/workflows/<id>` Economics panel | AC #13 (literal) |
| 6 | **"Open immutable audit ledger →"** opens the live versioned append blob | 2m | `/workflows/<id>` audit panel | AC #12 (literal) |
| 7 | FM rail ask `> what's our cost-per-task this week?` | 2m | right rail | AC #13 |
| 8 | Reviewer queue → arbitration recommendation pre-selected | 3m | `/reviewer-queue` | AC #8 |
| 9 | Justification round-trip live (Red claim → simulator persona replies → reviewer accepts) | 4m | `/workflows/<id>` | AC #7 partial |
| 10 | Autonomy proposal — seed 50 reviewer decisions, FM tick → policy panel | 3m | `/policy` | AC #7 |
| 11 | Evaluations page — Hiring section shows live POC2 evaluator scores | 2m | `/evaluations` | New 2026-05-05 |

**Reserve (asked-on-demand only):** EMS extensibility 2-file diff (AC #10), region failure simulator (AC #11). Pull either if a committee member probes — both are 2 min.

---

## Slot 3 · POC1 architecture walkthrough — 15 min

Three layers, narrated, **with a live anchor per layer** so it doesn't
feel like a slide deck.

| Layer | Time | Talking thread | Live anchor |
|---|---|---|---|
| **Context** | 3m | WPP operator + WPP staff + Workday/Concur/Maconomy + Foundry — who talks to what | Fleet dashboard `/` shows multi-EMS fleet (one card from each EMS, no source label on the card — uniformity claim) |
| **Container** | 5m | Three tiers: Fleet Manager (FastAPI) / Durable Functions orchestrator / per-phase agentic loops + MCP mocks. Validators as the "bounded probabilism" edge. | Drill into a workflow → Phases tab shows the per-phase deterministic / agent / validator executor mix |
| **Component — Fleet Manager** | 5m | Long-lived GHCP session, triage filters bus events, `query_fleet`/`compose_exception`/`propose_skill_amplification` MCP tools, debounce + coalesce so token spend is sane | FM rail → `> summarise <claim>` shows real tool calls with timings |
| Q from operator | 2m | "Where would you like me to dig?" | reserve |

**Reserve evidence on tap:**
- AC #4 accuracy pipeline → `/evaluations` Finance section + Foundry portal Evaluations pane
- AC #5 receipt OCR → `/workflows/<id>` Receipt panel + Foundry trace showing `tool.server.ocr_extract`
- AC #6 progressive enforcement → repeat-offender ramp injection
- AC #9 multi-EMS uniformity → Concur/Workday/Maconomy claims side by side

---

## Slot 4 · POC2 architecture walkthrough — 30 min

Same architecture story + **POC2 layer overlay** (the 10-phase
HiringOrchestrator + 7 hiring MCP mocks + per-jurisdiction policy
bundles). Double the time = double the depth + walk the candidate
journey end-to-end.

| Beat | Time | Live anchor |
|---|---|---|
| Reuse story — same C4 shape, different orchestrator | 3m | Open `api/shared/domains.py` → eight domains in one registry, hiring sits next to expense |
| Candidate apply → portal status URL emits in seconds | 3m | `/apply` form on `:5174` |
| Triage / cv-crystalliser — multimodal CV + LinkedIn extraction | 5m | `/recruiter/<id>` shows extracted profile + AG-UI scorecard; Foundry Tracing tab shows `wpp.skill=cv_crystalliser` span with `gen_ai.usage.*` |
| Voice screen — real Azure GPT-Realtime via WebRTC | 5m | `/screen?token=…` → real call, no iframe; transcript scoring beat |
| Jurisdiction switch — flip USA → DE, watch BetrVG step appear | 3m | re-spawn with `country=DE` |
| Multi-surface convergence — five HITL surfaces in 12 min compressed | 5m | Adaptive Card → ServiceNow webhook → A2A inbound → recruiter UI → email |
| Hiring evaluator coverage (new 2026-05-05) | 3m | `/evaluations` Hiring section: cv_field_extraction_accuracy, jurisdiction_routing_correctness, shortlist_decision_match against `data/synthetic/hiring/labels.csv` ground truth. Optional: trigger `POST /api/accuracy/run/hiring` and let it complete in background. |
| Onboarding avatar render | 2m | `/portal?token=…` after offer accept |
| Q from operator | 1m | reserve |

**Reserve evidence on tap:**
- A2A boundary (§4.19) → `POST /api/a2a/inbound` from a stand-in candidate PA
- AG-UI dynamic components (§4.21) → Senior Data Engineer vs Creative Director scorecards differ
- Region failover (§4.22) → `simulate-region-failure` against in-flight hires
- Per-domain phase ribbon — every domain renders its own 3–10 phase shape from registry

---

## Slot 5 · Q&A — 30 min

Live stack stays up; pull up live evidence on demand. The reserve lists
in slots 2/3/4 cover most likely probes.

**Anticipated probes — quick lookup:**

| Probe | Live answer |
|---|---|
| "Where does the cost number come from?" | `economics.py` reads `gen_ai.usage.*` span attributes × `model_pricing.py` published Azure rates. Show the source URL + date in the module docstring. |
| "Is the audit really immutable?" | Click the audit ledger link → Azure portal shows version-level immutability policy on the container. `apexdemo62525/audit-ledger`. |
| "How many domains can the substrate hold?" | `api/shared/domains.py` registry — eight today, adding the ninth via [`compose-domain`](superpowers/skills/compose-domain/SKILL.md) is a YAML brief. Six of the eight were graduated by the meta-skill in a single weekend. |
| "Where do you swap GHCP for Foundry-hosted agents?" | The agent wrapper in `_wrapper.py` — same OTEL semantic conventions Microsoft Agent Framework / Semantic Kernel / OpenAI Agents SDK / GHCP all share. Foundry Tracing accepts spans from any of them. |
| "How is Foundry IQ swapped in for `policy_search`?" | The MCP contract is the seam. The Pydantic schema on `policy_search` doesn't change; the implementation moves from local sentence-transformers to Foundry IQ. Show [SCOPE-DELTA.md](SCOPE-DELTA.md) row. |
| "Where's the engagement-POC vs lab-build line?" | [SCOPE-DELTA.md](SCOPE-DELTA.md) — the substrate stays, the implementations swap. |
| "Show me one skill" | Open `api/server/skills/rag-classifier/SKILL.md` — frontmatter + allowed-tools + prompt. Model picks tools from the manifest, not from prompt-stuffing. |

---

## Slot 6 · Internal debrief — 15 min

Not in this runbook. Capture scores while fresh on the WPP scorecard.

---

## Failure surfaces

| Symptom | Cause | Fallback |
|---|---|---|
| Foundry Tracing tab empty | App Insights ingestion delay (~2-5 min) | Run a workflow as the first action of slot 2; tab over later. If still empty, screenshot at `docs/screenshots/foundry-tracing-poc1.png` |
| Audit blob URL 403s | `az login` expired or wrong tenant | `az login --tenant 16b3c013-d300-468d-ac64-7eda0820b6d3` |
| Functions host slow / metadata timeout | Cold-start latency on this machine | Use `scripts/run-func.bat`; reboot if necessary; fall back to recorded `docs/projectapexdemo.mp4` |
| Voice screen mic blocked | Browser permission | Pre-approve mic for `localhost:5174` before guests arrive |
| FM rail unresponsive | Triage debounce window | Inject one Red claim to wake the session, then retry |
| Region failure beat flakes | Functions host doesn't restart cleanly | Skip live, narrate the architecture; `docs/demo-failover.mp4` if recorded |

---

## Between takes

```bash
# Ctrl-C the make-up terminal
make reset    # wipe Azurite + sqlite eval store
make up       # fresh stack
```

The audit blob `audit-ledger` container persists across takes. To start
fresh:

```bash
az storage blob delete-batch --account-name apexdemo62525 \
  --source audit-ledger --auth-mode login
```

---

## Appendix — what landed when

- 2026-05-05 — Foundry credibility lift: live Tracing tab, real cost numbers, immutable audit blob, POC2 evaluator coverage. See [`plan/feature-foundry-credibility-friday-1.md`](../plan/feature-foundry-credibility-friday-1.md).
- 2026-05-04 — Eight-domain substrate parity. See [`plan/feature-fleet-domain-substrate-1.md`](../plan/feature-fleet-domain-substrate-1.md).
- 2026-05-03 — `compose-domain` v3 + 5 fleet-* domains graduated.
- 2026-04-30 — POC2 spine merged + candidate portal + voice/avatar real.
- 2026-04-27 — POC1 pivot to expense compliance.

Per-AC coverage and code anchors live in [`poc1-status.md`](poc1-status.md) §1 (POC1) and [`poc2-status.md`](poc2-status.md) §1 (POC2).
