# Fashion Trading Shock Executive Demo Design

**Date:** 2026-07-27  
**Status:** Approved for implementation by delegated decision  
**Target:** Executive-grade Fashion Retail demo with Telco-level narrative impact

## 1. Decision

Build one connected, deterministic **Fashion Trading Shock** story across the
existing eight Fashion workflows. Do not expand the process catalogue in this
release. The default customer experience is a real recorded replay with a live
deterministic fallback.

The demo must feel native to Fashion rather than copying Telco. Its centre of
gravity is the commercial impact of a sudden trading event: demand, stock,
promotion, supply, fulfilment, marketplace, markdown and returns decisions all
change because of one visible cause.

The result is suitable for retail executives and transformation leaders. It
opens with business risk and KPI movement, then allows drill-down into workflow,
human authority, reasoning, command, world and Knowledge evidence.

## 2. Executive story

A warm-weather event and viral social campaign accelerate demand for a hero
style in the UK. Oxford Street approaches a stockout while Paris retains
eligible owned stock. At the same time:

- a promotion window is approaching
- one supplier milestone is delayed
- one marketplace seller reports unreliable stock
- fulfilment exceptions begin to appear
- source-region stock creates markdown exposure
- the increased sales volume produces a returns-disposition queue

The world emits one `retail.trading-shock.detected` event with a stable
`story_id`, causal event ID and deterministic seed. That story connects eight
distinct workflow instances:

1. `demand-spike-response`
2. `inventory-rebalancing`
3. `promotion-readiness`
4. `supplier-delay-recovery`
5. `marketplace-seller-exception`
6. `fulfilment-exception-resolution`
7. `markdown-governance`
8. `returns-disposition`

Each workflow retains its own workflow ID, owner, approval, command and terminal
outcome. The shared `story_id` groups them without collapsing their identity.

## 3. Architecture

### 3.1 Pack-owned story definition

Add `verticals/fashion/trading_shock.py` as the only Fashion-specific story
coordinator. It owns:

- the deterministic scenario stages and dependencies
- shared story identity and causal metadata
- executive KPI baseline and target measurements
- the mapping from stage to existing workflow type
- completion criteria for the overall story

No Fashion-specific branching belongs in shared world or UI infrastructure.
Shared code may gain optional, industry-neutral story fields and rendering.

### 3.2 Causal execution

The hero remains state-derived. No primary UI process-run button starts it.

1. Ordinary world activity establishes a browser-visible baseline.
2. The world creates the weather and campaign state changes.
3. A Fashion sensor emits `retail.trading-shock.detected`.
4. Demand and inventory sensors derive their existing workflow events.
5. Completion or mutation events unlock dependent story stages.
6. Independent supplier and marketplace branches run in parallel.
7. Fulfilment, markdown and returns stages consume the changed world state.
8. The story closes only when all eight workflows are terminal and the KPI
   evaluation is written.

Follow-on stages use the same internal process-start boundary as existing
world responders. They are not browser clicks and are not success-shaped mock
events.

### 3.3 Story state

Expose an optional, generic story projection through the world state:

```json
{
  "story": {
    "id": "fashion-trading-shock-42",
    "type": "trading-shock",
    "title": "The viral summer drop",
    "status": "running",
    "cause_event_id": "evt-...",
    "started_at_sim_time": 42,
    "stages": [
      {
        "workflow_type": "inventory-rebalancing",
        "workflow_id": "rebalance-evt-...",
        "status": "completed",
        "dependency_ids": ["demand-spike-response"],
        "autonomy": "human-approved"
      }
    ],
    "kpis": {
      "availability_pct": {"before": 61, "after": 94},
      "projected_lost_sales_gbp": {"before": 48000, "after": 9000},
      "full_price_sell_through_pct": {"before": 68, "after": 76},
      "fulfilment_success_pct": {"before": 91, "after": 97},
      "markdown_exposure_gbp": {"before": 62000, "after": 41000},
      "recovery_value_gbp": {"before": 0, "after": 14500}
    }
  }
}
```

Numbers derive from deterministic world evaluation. They are synthetic demo
assumptions, not claims about a named retailer.

## 4. Executive demo experience

### 4.1 Executive briefing

The Fashion world route opens with a compact story panel when story metadata is
available:

- what changed
- why action is required now
- revenue and availability at risk
- current story stage
- autonomy versus human-decision count

### 4.2 KPI ribbon

Show before and after values for:

- product availability
- projected lost sales
- full-price sell-through
- fulfilment success
- markdown exposure
- returns recovery value

Values animate only when the underlying projection changes. Replay and live
mode render the same values.

### 4.3 Causal journey rail

Render all eight workflows as one causal journey. Each stage shows:

- business label and owning function
- waiting, active, awaiting-person, completed or failed state
- the exact workflow ID when created
- its causal dependency
- autonomous, policy-safe or human-approved execution

Selecting a stage opens the existing workflow drawer. The drawer and execution
timeline remain the source of detailed phase, reasoning, tool, approval and
ledger evidence.

### 4.4 Visual acts

The demo has four acts:

1. **Trading shock:** the world changes and the commercial risk becomes visible.
2. **Bounded autonomy:** Zava proposes and executes safe actions while routing
   consequential choices to named Fashion personas.
3. **Connected response:** the causal journey advances across merchandising,
   supply chain, marketplace and returns.
4. **Measured outcome:** the KPI ribbon, Knowledge graph and Constellation show
   the resolved commercial result.

The UI remains retailer-neutral and synthetic. It may be recognisably relevant
to an ASOS-style operating model but uses no ASOS marks, records or proprietary
process claims.

## 5. Replay and live fallback

### 5.1 True replay tape

The customer-facing default uses the substrate recorder, not the Blueprint-only
JSONL stream:

- record through `ZAVA_RECORD_TO`
- snapshot workflows, phases, decisions, memory, entities and story state
- capture bus events and mutations through story completion
- finalise a `fashion-trading-shock.tar.gz`
- replay with `ZAVA_MODE=replay` and `ZAVA_TAPE_PATH`

Replay must be read-only, quota-independent and safe with Functions and the
actor world disabled.

### 5.2 Recording command

Add a Fashion-owned runner that:

1. boots the isolated Fashion stack
2. arms the recorder before the trading event
3. starts the scenario
4. resolves configured persona gates through the real authority path
5. waits for all eight terminal workflows and story KPI evaluation
6. shuts down gracefully so the tape is packed
7. boots replay against the generated tape and runs Playwright proof

The runner writes under `proof/fashion-trading-shock/`. Binary tapes remain
release artifacts rather than normal Git source unless Git LFS is explicitly
adopted.

### 5.3 Live fallback

Live fallback uses the same scenario and UI. It runs the deterministic world and
Durable workflows at a configured demo time warp. Live model reasoning is
optional during rehearsal; the customer path never depends on Copilot or model
quota because the approved recording is the default.

## 6. Memory, visibility and evidence

### 6.1 Operational memory

The current Fashion memory write fails because nested outcome objects are passed
as Chroma metadata. Fix the shared, vertical-neutral boundary:

- keep nested evidence in the memory text
- store only scalar metadata values
- JSON-encode structured metadata into explicitly named string fields where
  retrieval needs it
- preserve exact `workflow_id`, `workflow_type` and source

Every completed Fashion workflow must produce at least one memory with an exact
structured workflow-ID match. The Memory page must show all eight domains in
both live and replay.

### 6.2 Execution visibility

Wire `tools/workflow_visibility_proof.py` into the Fashion proof after live
completion and again against the real replay tape. Capture:

- `proof/workflow-details/live`
- `proof/workflow-details/replay`

The same eight workflow IDs must have live/replay parity for status, phases,
decisions, deterministic output, reasoning rows when genuinely generated, tool
calls, MCP calls, errors and retries.

Do not fabricate agent rows. A deterministic phase is labelled deterministic.
Any phase declared as agentic must use `run_agent_session`; the recorded tape
may replay that evidence without making another model call.

### 6.3 UI identity

Resolved feed cards must retain their workflow ID and business title instead of
displaying an em dash. World, journey rail, feed, drawer, Memory, Knowledge,
AG-UI and Constellation must agree on the same identity and terminal outcome.

## 7. Failure handling

- A failed stage stops dependent story stages and marks the story `failed`.
- Independent branches may finish, but the executive outcome never reports
  success when a required branch failed.
- Rejected human decisions produce a valid alternate outcome with an explicit
  KPI consequence.
- Missing workflow, story, memory or graph identity is a proof failure.
- Recorder startup, flush or finalisation failure is fatal to the demo build.
- Replay rejects all writes and cannot silently fall back to live mode.
- Browser, SSE or graph errors are surfaced in proof; no success-shaped
  fallback is allowed.

## 8. Testing and permanent proof

### 8.1 Unit and integration tests

Add tests for:

- deterministic story identity and stage ordering
- dependency and parallel-branch behaviour
- stage failure and decision-rejection propagation
- KPI calculations from world state
- exact story and workflow identity in projections
- scalar-only memory metadata and exact workflow-ID retrieval
- live/replay story-state hydration
- generic story UI rendering and workflow drill-in
- resolved feed-card identity

### 8.2 Playwright proof

The permanent proof must:

1. capture the baseline before the trading shock
2. observe the causal trigger
3. complete all eight workflows through real approval boundaries
4. verify all declared phases and terminal lifecycle rows
5. verify exact IDs in AG-UI, Memory and Knowledge
6. verify KPI before/after deltas
7. capture the live visibility snapshot
8. record and boot the real replay tape
9. verify the same eight IDs and story state in replay
10. run the live/replay visibility comparison
11. assert zero browser errors, zero dropped events and clean teardown
12. produce a polished executive walkthrough video

`proof/manifest.json` may report permanent PASS only when every gate above
passes on the current clean source commit.

## 9. Scope

### In scope

- one connected story using all eight existing Fashion workflows
- executive briefing, KPI ribbon and causal journey rail
- true replay tape and live fallback
- memory repair
- workflow identity polish
- live/replay proof parity
- demo video

### Out of scope

- expanding toward Telco's 37-process catalogue
- named-retailer branding or proprietary data
- autonomous markdown execution
- customer-level personalisation
- replacing the shared world, replay or workflow-detail infrastructure

## 10. Acceptance criteria

The upgrade is complete when:

1. One deterministic trading event visibly causes all eight Fashion workflows.
2. The executive UI explains cause, action, human authority and measured value
   without narration.
3. Every workflow completes and retains exact identity across all surfaces.
4. All eight operational memories exist and replay correctly.
5. A real `ZAVA_MODE=replay` tape renders the full story with live/replay
   visibility parity.
6. The replay is quota-independent, read-only and customer-demo ready.
7. The live fallback executes the same story and outcomes.
8. The permanent Fashion proof and polished Playwright video pass on the current
   source commit.
