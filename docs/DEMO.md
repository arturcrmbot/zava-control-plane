# DEMO — POC1 Expense Compliance (30-minute walkthrough)

Operational run-book for the POC1 demo. Beats are timed in ~2-minute
slots; full run is ~30 minutes including transitions. The canonical AC
status table (live / partial / to-build) lives in
[poc1-status.md](poc1-status.md); this doc tells the operator how to
drive each beat.

---

## Pre-flight (5 min before guests)

```bash
make reset          # wipe Azurite state between takes
make up             # boot azurite + mocks (4101/4102/4103) + functions + fastapi + vite
# wait for "All services should be up" banner + 30s simulator warm-up
```

URLs the operator needs in tabs:

- `http://localhost:5173/` — Fleet Dashboard
- `http://localhost:5173/reviewer-queue` — SSC reviewer queue (AC #8)
- `http://localhost:5173/policy` — policy editor
- Terminal pane visible for `curl` injects + `git diff`

Verify the four mocks responded once during boot — Workday `4101`,
Concur `4102`, Maconomy `4103`. If Maconomy didn't bind (it boots last),
restart the stack; the AC #10 beat needs it live.

---

## Walkthrough

### Beat 1 — Open dashboard (2 min · AC #1, #2)

Open `/`. Operator narrates:
- Counters show ~30 in-flight workflows ramping in (`SIMULATOR_TARGET_WORKFLOWS=30`).
- Each card shows verdict (Green / Amber / Red) badge and ledger continuity.
- Right-rail Fleet Manager is idle until an exception fires.

Drop into the simulator inject from terminal to spawn one explicit Green
claim so a fresh card appears live:

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{"scenario":"baseline-green"}'
```

### Beat 2 — Drill into an Amber (2 min · AC #4)

Click an Amber card → Workflow Detail. Show:
- **Phases** tab — per-phase elapsed + executor list.
- **Reasoning** side-by-side with the policy clause cited by the
  classifier. The reasoning paragraph names a §-level rule.
- **Amplification** tab — what the FM proposed (precedents + policy refs).

### Beat 3 — Edit policy + re-run accuracy (2 min · AC #4)

Open `/policy`. Edit a single rule (e.g. tighten the UK solo meal cap from
£40 → £35). Save. Note the dry-run result tile updating.

Trigger the accuracy harness against a smoke sample:

```bash
curl -X POST http://localhost:3001/api/accuracy/run \
  -H "Content-Type: application/json" -d '{"sample_size":20}'
```

Show the verdict shift: claims now cluster Amber instead of Green at the
£35–40 band. Property: classification is policy-driven, not hardcoded.

> Full 300-claim ≥95% gate runs separately. See [poc1-accuracy-runbook.md](poc1-accuracy-runbook.md).

### Beat 4 — Bulk approve (2 min · AC #3)

Open Exception Queue. Filter by clause `§3.1 Meals`. Show ~12 Amber
claims clustered. Bulk-select → "Approve all with reason: client-meeting
context". Single decision propagates; ledger entries land within seconds.

### Beat 5 — Receipt mismatch flavours (3 min · AC #5)

In a fresh terminal, fire all six flavours sequentially:

```bash
for s in correct wrong-amount wrong-date wrong-vendor missing-line-item missing-receipt; do
  curl -X POST http://localhost:3001/api/simulator/inject \
    -H "Content-Type: application/json" \
    -d "{\"scenario\":\"receipt-mismatch-${s/_/-}\"}"
  sleep 2
done
```

Watch six new cards arrive; click into each; show validator output. The
Phase 3 receipt validator flags each flavour with a distinct reason and
the ledger captures the OCR comparison.

### Beat 6 — Repeat-offender ramp (2 min · AC #6)

```bash
curl -X POST http://localhost:3001/api/simulator/repeat-offender \
  -H "Content-Type: application/json" \
  -d '{"employee_id":"EMP-0001","count":3}'
```

Three claims spawn for the same employee. Show the escalation tier
ramp on the cards: **warning → escalation → major-violation**. Open the
third claim's audit drawer; tier override decision is logged.

### Beat 7 — Concur claim, no EMS marker (2 min · AC #9)

Inject a Concur claim:

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{"scenario":"concur-baseline"}'
```

Card has no EMS badge — operator's pitch: "the operator doesn't see
which EMS this came from on the card; they see a uniform claim
surface." Open the audit drawer; `ems_source: "concur"` appears in the
ledger. Property: the EMS is invisible at the operator UI but provable in audit.

### Beat 8 — Reviewer queue + arbitration (3 min · AC #8)

Open `/reviewer-queue`. Show the queue sorted by severity then age.
Click into one Amber → arbitration recommendation pre-selected with:
- the **recommendation** (one of: accept-justification, escalate, reject, request-more-info)
- **rationale** (1-2 sentences)
- **cited precedent** id and **policy clause**

Operator clicks Accept; SSE shows `workflow.completed` immediately.

### Beat 9 — Justification round-trip (3 min · AC #7 partial)

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{"scenario":"breach-with-justification"}'
```

A Red claim spawns; notification dispatches; simulator auto-replies
with a justification within 5s. Watch the Workflow Detail panel:
notification → justification.received → arbitration → reviewer accepts
→ `workflow.completed`. Full HITL round-trip, ~30s wall-clock.

### Beat 10 — Behaviour-change autonomy proposal (3 min · AC #7)

Fast-forward simulator: 50 reviewer decisions on the same clause.

```bash
curl -X POST http://localhost:3001/api/simulator/seed-decisions \
  -H "Content-Type: application/json" \
  -d '{"clause":"§3.1","decision":"accept-justification","count":55}'
```

Trigger Fleet Manager tick:

```bash
curl -X POST http://localhost:3001/api/simulator/fleet-tick
```

Watch right-rail SkillAmplificationPanel: FM proposes routing matching
claims to auto-approve (cluster count ≥ 50, accept-justification
dominant). Operator clicks Approve → autonomy promotion logged.

### Beat 11 — Audit + cost reports from FM rail (2 min · AC #12, #13)

In the FM rail, type two natural-language asks:

```
> summarise CLM-0042
```

FM invokes `claim_summary` + `audit_query`; returns a 50–100 word
narrative paragraph anchored to a `(timestamp, actor_id, action)`
triple from the ledger.

```
> what's our cost-per-task this week?
```

FM invokes `query_economics` (168h window) and produces a
`compose_exception` tile with total / avg / by-verdict breakdown. If
red avg > 3× green avg, the tile flags the ratio.

### Beat 12 — EMS extensibility narration (2 min · AC #10)

Open a terminal next to the browser tab and walk
[demo-ems-extensibility.md](demo-ems-extensibility.md) — show the
two-file diff for adding Maconomy:

```bash
git diff main~3 main -- mocks/maconomy-mcp/server.ts api/server/mcp_tools/claim_lookup.py
git diff main~3 main -- api/server/skills/ api/functions/graphs/  # EMPTY
```

Then inject a Maconomy claim through the live mock:

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{"scenario":"maconomy-baseline"}'
```

Same dashboard, same audit drawer pattern; `ems_source: "maconomy"`.

### Beat 13 — Region failure + recovery (2 min · AC #11)

Mark the audit window:

```bash
curl -X POST http://localhost:3001/api/simulator/region-failure \
  -H "Content-Type: application/json" -d '{"stop_seconds":15}'
```

Now stop the Functions host (Ctrl-C the `func start` pane or
`docker compose stop functions`). FastAPI keeps running; UI shows
workflow cards freezing at their current phase; counter for "in-flight"
flat.

After 15s, restart:

```bash
make functions  # or `func start --port 7071`
```

Durable replays from Azurite checkpoint. Workflows resume from where
they paused; ledger continuity proven (no duplicate phase entries; no
gaps). If live demo flakes, fall back to recorded `docs/demo-failover.mp4`.

---

## Acceptance criteria coverage map

| AC | Beat | Status |
|----|------|--------|
| #1 In-flight fleet visible | 1 | ✅ |
| #2 Verdict badges on cards | 1 | ✅ |
| #3 Bulk approve from queue | 4 | ✅ |
| #4 Policy-driven classification | 2, 3 | ✅ pipeline; full ≥95% gate post-tag |
| #5 Receipt mismatch — 6 flavours | 5 | ✅ |
| #6 Repeat-offender escalation | 6 | ✅ |
| #7 Autonomous learning loop | 9, 10 | ✅ |
| #8 SSC reviewer interface | 8 | ✅ |
| #9 Multi-EMS uniformity | 7, 12 | ✅ |
| #10 EMS extensibility | 12 | ✅ |
| #11 Region failure recovery | 13 | ✅ |
| #12 Immutable audit + reporting | 11 | ✅ |
| #13 Cost-per-task | 11 | ✅ |

---

## Between takes

```bash
# Ctrl-C the make-up terminal
make reset    # wipe Azurite
make up       # fresh stack, fresh in-memory state
```
