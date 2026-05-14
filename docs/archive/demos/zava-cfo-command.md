# Zava — live "CFO command" demo (90 seconds)

A scripted closer for the end of the 30-minute demo. The operator
issues one voice command; the system fans out across the visualisation,
the API, and the audit ledger; total elapsed wall-clock is ≤90 seconds.

> **Why this exists:** decision-makers want to see a single human
> sentence trigger an end-to-end traversal of the control plane —
> persona graph, KPI panel, timeline replay, decision replay, audit
> ledger — and finish in under two minutes. This script delivers that.

## The single sentence

> *"Show me everything that touched Soylent's Q3 budget."*

## Pre-flight (do this BEFORE the audience walks in)

- `make demo-warm` is up; constellation visible at
  `http://localhost:5173/?view=constellation`.
- Audit ledger tab pre-opened in a second browser tab.
- Terminal tab pre-opened with the curl fallbacks pre-typed but
  unsent (Ctrl-R history primed).
- Microphone tested. Voice pipeline endpoint health-checked:

  ```bash
  curl -s http://localhost:8000/api/voice/health | jq .ok
  # => true
  ```

- The Soylent Q3 period id is known. Capture it once into a shell var:

  ```bash
  export PERIOD_ID=$(curl -s http://localhost:8000/api/entities/search \
    -G --data-urlencode 'q=Soylent Q3 budget' \
    --data-urlencode 'type=period' | jq -r '.results[0].id')
  echo "$PERIOD_ID"   # sanity: should be PER-soylent-q3-2025 or similar
  ```

## The 90-second wall-clock script

| t (s) | Operator action | What the audience sees | Curl-equivalent fallback |
|---|---|---|---|
| 0 | Click the **voice** button at the bottom of the constellation | Mic icon turns red; audio meter ticks | n/a (voice-only) |
| 0–4 | Say *"Show me everything that touched Soylent's Q3 budget."* | Live transcription overlays the lens | `curl -X POST $API/voice/transcribe -F "audio=@cmd.wav"` |
| 4 | (system) Voice pipeline routes the question | Toast: *"Routing to entity-resolver…"* | `curl -X POST $API/intents/resolve -d '{"text":"..."}'` |
| 5–8 | (system) Cosmic lens highlights `ORG-client-soylent-group` and the 4 subsidiaries that worked it | 5 nodes light up on the holding-network panel | `curl $API/entities/ORG-client-soylent-group/neighbours?depth=1` |
| 8–14 | (system) AgencyKPIs panel zooms to **Gross profit per brand** filtered to Soylent's brands | KPI panel re-renders with 3 brand bars | `curl $API/kpis/gross-profit-per-brand?client=soylent` |
| 14–22 | (system) Timeline endpoint returns ~200 events for the period | Lens replays the events via the J4 time-scrub | `curl $API/entities/$PERIOD_ID/timeline | jq '.events | length'` |
| 22–60 | (system) J4 time-scrub auto-plays the 200 events at 8× speed | Rocket trails sweep across all 4 subsidiaries; intercompany edges pulse | (scrub manually) drag J4 slider from `t0` to `t_now` |
| 60–75 | (system) Decision-replay endpoint runs the top-3 decisions | Toast for each: *"Would still decide same: ✅"* | `curl $API/decisions/replay/$DECISION_ID` (×3) |
| 75–90 | Operator clicks the **Audit** tab | Immutable ledger panel scrolls to the 200 entries with hashes | `curl $API/audit/period/$PERIOD_ID | jq '.[:5]'` |

The operator says nothing between t=4 and t=75. The system narrates
itself via toasts.

## Closing line (operator, at t=90)

> *"One sentence. Five subsidiaries traversed. Two hundred events
> replayed. Three decisions defended. One audit trail. The whole
> Soylent Q3 story, in ninety seconds, with the receipts."*

## Manual fallback — if the voice pipeline fails

Read the line aloud anyway so the audience hears the phrasing, then
run the six curl commands in sequence. Each one corresponds to one row
of the wall-clock table above. They are pre-typed in the terminal tab.

```bash
# 1. Resolve the intent
curl -s -X POST http://localhost:8000/api/intents/resolve \
  -H 'content-type: application/json' \
  -d '{"text":"Show me everything that touched Soylent Q3 budget"}' | jq .

# 2. Pull the entity neighbourhood (lights up the lens)
curl -s "http://localhost:8000/api/entities/ORG-client-soylent-group/neighbours?depth=1" | jq .

# 3. Pull the filtered KPI (zooms the AgencyKPIs panel)
curl -s "http://localhost:8000/api/kpis/gross-profit-per-brand?client=soylent" | jq .

# 4. Pull the timeline (drives the J4 scrub)
curl -s "http://localhost:8000/api/entities/$PERIOD_ID/timeline" | jq '.events | length'

# 5. Replay the top-3 decisions
for D in $(curl -s "http://localhost:8000/api/entities/$PERIOD_ID/decisions/top?n=3" \
             | jq -r '.[].id'); do
  curl -s "http://localhost:8000/api/decisions/replay/$D" \
    | jq '{id, would_decide_same, rationale}'
done

# 6. Show the audit slice
curl -s "http://localhost:8000/api/audit/period/$PERIOD_ID" | jq '.[:5]'
```

If any of the six fail, finish on whichever step succeeded last and
say *"the rest of this lives in the audit ledger; happy to walk it
offline."* Do not freeze, do not apologise on stage.

## What this segment proves (the "so what")

- **Voice → action → audit** is one continuous pipeline, not three
  disconnected demos.
- **Cross-subsidiary traversal** is the default behaviour, not a
  special case — the lens and the KPI panel both pivot on the same
  entity id.
- **Replay is real:** the I7 endpoint is not a screenshot; it is hit
  live, and the ✅ comes back from the orchestrator.
- **Defensibility is the close.** A CFO leaves the room remembering
  *"one sentence, full receipts."*

## Timing budget — total 90 seconds

| Segment | Budget |
|---|---|
| Voice capture + transcription | 4s |
| Routing + entity highlight | 4s |
| KPI zoom | 6s |
| Timeline fetch | 8s |
| Auto-replay scrub | 38s |
| Decision replay (×3) | 15s |
| Audit ledger reveal | 15s |
| **Total** | **90s** |

If the room runs hot, drop the auto-replay scrub from 8× to 16× and
recover 19 seconds. Never drop the audit-ledger reveal — that is the
close.
