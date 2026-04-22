# WPP Control Plane — Demo Script

**Duration:** 3–5 minutes. Recorded via OBS or Loom at 1440p.

## Pre-flight
- `npm run dev`
- Wait until Fleet Dashboard shows ~30 workflows in-flight.
- Fleet Manager right rail should show "idle" transitioning to periodic wake-ups.

## Shot list

1. **Fleet Dashboard wide shot (5s)** — counters, filter bar, card grid, right rail visible. Pan to agency filter, select one agency, show filter works.
2. **Inject a duplicate burst** in a separate terminal:
   ```bash
   for i in 1 2 3; do curl -s -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"duplicate-invoice"}'; done
   ```
   Watch the right rail light up (wakeup → reasoning_start → tool_call → reasoning_done).
3. **Navigate to Exception Queue** — one bulk item (×3) should appear. Expand it. Show policy refs and recommendation.
4. **Click a workflow card** from the queue → Workflow Detail → Traces tab. Show OTEL span tree with tool durations.
5. **Back to queue** — select all 3 in the bulk group, click Bulk resolve, approve all.
6. **Policy screen** — click into `invoice-p2p.approval.auto_threshold`. Enter a new value (e.g. 10000), run dry-run, show impact, click "Propose as change".

## Hero screenshots (pause recording, capture PNGs)

1. Fleet Dashboard with ~40 workflows and 3 exceptions visible.
2. Exception Queue with expanded bulk-3 duplicate item.
3. Workflow Detail → Traces tab.
4. Bulk HITL modal with 3 checked.
5. Right rail mid-reasoning with `compose-exception` tool call.
6. What-If analysis with impact delta + "Propose as change" CTA.

## Post
- Trim, add a single title card "WPP Control Plane v1 — POC1 Finance P2P", export MP4 + 6 PNGs.
- Copy to `response/evidence/` for the written submission.
