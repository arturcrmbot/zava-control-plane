# Blueprint microsite — contributor guide

The blueprint microsite (`web/blueprint/`, served on `:5175`) renders the
case of type as you build it. New domains, skills and MCPs feed into the
visualisation automatically — provided you use the contract this guide
describes.

This is the doc to hand to any process (human or agent) that adds new
agentic work to the repo and wants it to show up on the page without a
separate UI edit.

---

## Where the page draws its data from

The page makes one network call on load:

```
GET /api/blueprint/composition
```

That endpoint (`api/server/routes/blueprint.py`) returns a JSON tree
built by [`api/server/services/blueprint_inventory.py`](../../api/server/services/blueprint_inventory.py).
The tree is rebuilt at request time by:

1. Walking `api/server/skills/*/SKILL.md` for every skill on disk.
2. Walking `api/server/mcp_tools/*.py` for every MCP tool.
3. Reading the hand-declared `DOMAINS` manifest in `blueprint_inventory.py`
   for the business-domain layer.

Plus one live SSE stream:

```
GET /api/blueprint/stream
```

That feed forwards a curated subset of `FleetEvent`s (defined in
`api/shared/events.py`) and translates them into the visual vocabulary the
mind-map understands. The events come from one of three sources, in
order of preference: real workflow events on the in-process bus,
recordings of past real walks replayed from
`data/blueprint-recordings/*.jsonl`, or hand-coded synthetic templates
as a last-resort fallback. See the "make the new domain light up" section
below.

---

## To add a new skill

A skill is just a markdown file with frontmatter. The page picks it up
the next time `/api/blueprint/composition` is requested — no other change
needed.

1. Create `api/server/skills/<your-skill-name>/SKILL.md`.
2. Frontmatter must include at minimum:

   ```yaml
   ---
   name: your-skill-name
   description: What this skill does, in one sentence.
   allowed-tools: tool_one, tool_two
   ---
   ```

   `allowed-tools` can be a comma-separated string or a YAML list. Both
   are parsed.

3. Tool names listed in `allowed-tools` are normalised — `policy_search`,
   `policy.search` and `policy-search` all match the `policy_search.py`
   MCP tool. The page only draws an edge if the normalised name matches
   an existing module under `api/server/mcp_tools/`.

4. To make the new skill appear under a domain in the **case of type**
   section and in the **compounding** chart, add its `name` to the
   relevant domain's `skills` list in `DOMAINS` (see next section). A
   skill not listed under any domain is still parsed and counted, but
   has no domain badge.

5. To label the skill on the **mind-map orbit** when the runtime emits
   it, add a `phase_aliases` entry under its domain (see next section).
   A skill without a phase alias still appears as a node, just unlabeled.

That's it. The page reads the SKILL.md frontmatter every request.

---

## To add a new MCP tool

1. Create `api/server/mcp_tools/<your_tool>.py`. The filename (minus
   `.py` and any leading underscore) is the tool's display name.
2. Files starting with `_` (e.g. `_otel.py`) and `__init__.py` are
   skipped — same convention the runtime uses.
3. Skills that allow-list this tool (via the `allowed-tools` frontmatter)
   will draw edges to it in section 4 (case of type) and in section 3
   (architecture diagram).
4. The architecture diagram's MCPs row currently surfaces a hand-picked
   sample (4 names + "+ N more"). To put a new MCP in the sample,
   edit the `MCPS` array in
   `web/blueprint/src/components/ArchitectureDiagram.tsx`. It is a
   visual narrative choice, not data. The page still counts every MCP
   in the totals.

---

## To add a new domain

This is the only place the contract genuinely matters.

Edit the `DOMAINS` list in
[`api/server/services/blueprint_inventory.py`](../../api/server/services/blueprint_inventory.py).
Each entry is a single dict with this shape:

```python
{
    "name": "Travel pre-approval",            # displayed verbatim
    "status": "live",                         # "live" or "aspirational"
    "workflow_type": "fleet-travel-preapproval",
    "skills": [
        "fleet-travel-preapproval-policy-fit-checker",
        # ... more skill names matching api/server/skills/*/SKILL.md
    ],
    "phase_aliases": {
        "fleet-travel-preapproval-policy-fit-checker": "Policy fit",
        # skill name -> phase label shown on the mind-map orbit
    },
},
```

Field-by-field:

- **`name`**: the human label shown on the page. Pick something
  short; it appears in the centre badge of the mind-map and as a
  column heading in the compounding chart.
- **`status`**: `live` (drawn solid, included in counters) or
  `aspirational` (drawn with diagonal stripes, present as a "next
  domain" placeholder). Use `aspirational` for domains you want to
  show on the roadmap but haven't built yet.
- **`workflow_type`**: the string the runtime emits as
  `workflow_type` on `FleetEvent`s for this domain. The mind-map uses
  this to decide which domain badge to light up when an event arrives.
  Set to `None` for aspirational domains.
- **`skills`**: a list of skill names (matching the `name:` field in
  each `SKILL.md`, or the directory name as fallback). Order matters
  for readability in the case-of-type section but does not affect
  layout. Skills that don't exist on disk are silently ignored.
- **`phase_aliases`**: a `{skill_name: phase_label}` map used by the
  mind-map to label nodes on the phase orbit. Skills that fire at
  runtime without an entry here will still appear as nodes, just
  without a phase label. Multiple skills can map to the same phase
  (e.g. `field-extractor` and `line-item-extractor` both → `Intake`).

Order of entries in `DOMAINS` matters for two views:

1. The **compounding chart** walks domains in declaration order and
   marks each skill as `new` the first time it appears, `reused`
   thereafter. Put live domains in chronological build order, then
   aspirational ones at the end.
2. The chart auto-resizes to N columns based on `len(DOMAINS)`.

---

## To make the new domain light up on the live mind-map

Three paths, in order of preference.

### Path A: real workflow events on the bus (preferred for local dev)

If the new domain's orchestrator emits `FleetEvent`s with `workflow_type`
set to the manifest's value, you don't need to do anything else. The
blueprint observatory subscribes to the in-process bus and forwards
matching events to the page.

This is what runs when you're sitting at your desk with the full stack up
(`make up` or equivalent — FastAPI + Functions host + your real workflows
firing).

### Path B: capture real events to JSONL, replay them in deployment (preferred for deploys)

For an external demo URL, the page can't connect to your live laptop.
Capture real walks once, commit the JSONL files, deploy with them baked
into the image. Playback uses the same SSE plumbing as Path A — the page
can't tell the difference.

```bash
# 1. Boot the full stack with the real backend firing events.
make up

# 2. Start the recorder.
curl -X POST http://localhost:3001/api/blueprint/_recorder/start

# 3. Run your real workflows however you trigger them
#    (simulator inject, portal /apply, persona responder, real API).

# 4. Watch them complete. The recorder auto-flushes each workflow on
#    durable.workflow.completed; partial walks are flushed on stop.

# 5. Stop and check what landed.
curl -X POST http://localhost:3001/api/blueprint/_recorder/stop
ls -la data/blueprint-recordings/
```

Files land at `data/blueprint-recordings/<workflow_type>-<UTC>-<id>.jsonl`,
one workflow per file. Inspect them — hand-delete short or weird runs.
Multiple recordings of the same `workflow_type` are fine; the playback
loop picks one at random per spawn, which gives the page variety.

```bash
# 6. Commit them.
git add data/blueprint-recordings/*.jsonl
git commit -m "record: <domain> walks for blueprint trickle"
```

The next time anyone hits `/api/blueprint/_demo_stream/start` (or clicks
**Wake the observatory** on the page), the trickle replays the recordings
at their original cadence (clamped to 200ms–4s per gap to keep it
readable), substituting a fresh `workflow_id` per spawn so multiple
in-flight copies don't collide.

What gets captured: only the events the observatory cares about (the
`RECORDED_TYPES` set in
[`api/server/services/blueprint_recorder.py`](../../api/server/services/blueprint_recorder.py)),
and only events that carry a `workflow_id`. Everything else is dropped at
capture time so you don't accumulate noise.

What gets recorded with the event:

- The full event payload as the bus carries it.
- A millisecond offset from the workflow's first event (`ts_offset_ms`),
  used to pace the playback.

There is no `_recorder/status` UI on the page — it's a developer endpoint
only. Hit `GET /api/blueprint/_recorder/status` from curl if you want to
check whether a session is currently running.

### Path C: hand-coded synthetic template (fallback when no recordings exist)

If there are no recordings for a domain yet, the trickle falls back to
hand-coded templates in `_STREAM_TEMPLATES` in
[`api/server/routes/blueprint.py`](../../api/server/routes/blueprint.py).
These are the events the page emitted before the recorder existed; they
cover hiring, expense-claim, and onboarding.

Adding a new synthetic template is fine for early-days domains where the
real orchestrator isn't shipped yet but you want the page to show
*something*. Each template is an ordered list of dicts. Every dict needs
`type` and `workflow_type`; `skill` and `tool` are optional but
recommended:

```python
# Travel pre-approval — short synthetic walk
[
    {"type": "workflow.started", "workflow_type": "fleet-travel-preapproval"},
    {"type": "durable.step.started",
     "skill": "fleet-travel-preapproval-policy-fit-checker",
     "workflow_type": "fleet-travel-preapproval"},
    {"type": "durable.executor.invoked",
     "skill": "fleet-travel-preapproval-policy-fit-checker",
     "tool": "policy_search",
     "workflow_type": "fleet-travel-preapproval"},
    {"type": "agent.completed",
     "skill": "fleet-travel-preapproval-policy-fit-checker",
     "workflow_type": "fleet-travel-preapproval"},
    {"type": "workflow.hitl.requested",
     "workflow_type": "fleet-travel-preapproval"},
    {"type": "durable.workflow.completed",
     "workflow_type": "fleet-travel-preapproval"},
],
```

Optional: extend `_PREFIX_BY_TYPE` so the demo workflow IDs read like
`TRVL-1234` instead of the default `WF-1234`. Pure cosmetics.

**Important:** the trickle only falls back to `_STREAM_TEMPLATES` when
the recordings directory is empty. If you have **any** recordings
committed, synthetic templates are ignored entirely. So once you've
recorded for a domain, treat that as the canonical source — don't
maintain both.

---

## What the live observatory understands

`api/server/routes/blueprint.py` filters the bus to a curated set of
event types. If your runtime emits something outside this set, the page
ignores it. The forwarded set:

- `workflow.started`, `durable.workflow.started`
- `durable.step.started`, `durable.step.completed`
- `durable.executor.invoked`
- `agent.completed`
- `durable.validator.blocked`
- `workflow.exception.detected`
- `workflow.hitl.requested`
- `durable.suspended`
- `durable.workflow.completed`, `workflow.resolved`

For each forwarded event the page extracts (in order of preference, all
optional except `type`):

- **`skill`**: from any of `skill`, `skill_name`, `agent`, `agent_skill`,
  `name`, `executor`. The first non-empty value wins.
- **`tool`**: from any of `tool`, `tool_name`, `mcp_tool`.
- **`workflow_id`**: from any of `workflow_id`, `workflowId`,
  `instance_id`, `instanceId`.
- **`workflow_type`**: from `workflow_type` or `workflowType`.
- **`ts`**: from `ts`, otherwise `time.time()` at forward time.

If you emit any of these fields under a non-standard name, the page
won't see them. Add a parallel field with one of the names above and
the renderer will pick it up.

---

## Things you don't need to touch

- **`web/blueprint/src/components/MindMap.tsx`** — phase labels and
  domain names are read from the composition tree at runtime. No
  edits needed when adding a domain or skill.
- **`web/blueprint/src/components/CompoundingDiagram.tsx`** — column
  count and ordering are derived from `DOMAINS`. No edits needed.
- **`api/server/routes/blueprint.py`** `_domain_from_workflow_type` —
  reads from `DOMAINS`, no edits needed.
- **CSS** — `web/blueprint/src/styles.css` is content-agnostic.

---

## What you do need to touch (in summary)

| Adding | Edit |
|---|---|
| A new skill | `api/server/skills/<name>/SKILL.md` (and the parent domain's `skills` + `phase_aliases` in `blueprint_inventory.py`) |
| A new MCP tool | `api/server/mcp_tools/<name>.py` (optional: add to `MCPS` sample in `ArchitectureDiagram.tsx`) |
| A new domain | `DOMAINS` list in `blueprint_inventory.py` |
| Live activity for a new domain (deploy) | Record real walks via `/api/blueprint/_recorder/{start,stop}`, commit the JSONL files |
| Live activity for a new domain (no orchestrator yet) | Add a synthetic template to `_STREAM_TEMPLATES` in `blueprint.py` |

For static content (skills, MCPs, domains) at most three files. No
frontend edits needed for new content. For live activity you have one
command and a `git add` once the workflow runs locally.

---

## How to verify your change

1. Restart FastAPI: `scripts/run-fastapi-blueprint.sh` (re-runs uvicorn
   on `:3001`, logs to `/tmp/fastapi-blueprint.log`).
2. Hard-refresh `http://localhost:5175/`.
3. Hover the new tile in the case-of-type section to see its edges.
4. Click **Wake the observatory** to see the live trickle. Your new
   workflow should rotate through as one of the three in flight.

If the page doesn't pick up your change:

- Check the SKILL.md frontmatter parses: `curl -s http://localhost:3001/api/blueprint/composition | python -m json.tool | grep your-skill-name`
- Check `workflow_types` includes your new domain's runtime string:
  `curl -s http://localhost:3001/api/blueprint/composition | python -c "import sys, json; print(json.load(sys.stdin)['workflow_types'])"`
- Check the recorder isn't holding stale state from a prior session:
  `curl -s http://localhost:3001/api/blueprint/_recorder/status`
- Check whether playback is using recordings or synthetic templates:
  `ls -la data/blueprint-recordings/*.jsonl` — if any JSONL is present,
  the trickle uses recordings exclusively. To force synthetic, move the
  JSONL files out of the directory.

---

## Reference

- **Spec**: [`docs/superpowers/specs/2026-05-03-blueprint-microsite-design.md`](../superpowers/specs/2026-05-03-blueprint-microsite-design.md)
- **Inventory module**: [`api/server/services/blueprint_inventory.py`](../../api/server/services/blueprint_inventory.py)
- **Recorder module**: [`api/server/services/blueprint_recorder.py`](../../api/server/services/blueprint_recorder.py)
- **Routes**: [`api/server/routes/blueprint.py`](../../api/server/routes/blueprint.py)
- **Recordings**: [`data/blueprint-recordings/README.md`](../../data/blueprint-recordings/README.md)
- **Frontend types**: [`web/blueprint/src/lib/types.ts`](../../web/blueprint/src/lib/types.ts)
