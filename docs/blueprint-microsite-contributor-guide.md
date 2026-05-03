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
mind-map understands.

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

There are two paths.

### Path A: real workflow events

If the new domain's orchestrator already emits `FleetEvent`s with
`workflow_type` set to the manifest's value, you don't need to do
anything. The blueprint observatory will see them on the bus and
forward them to the page.

### Path B: dev demo trickle (for desk demos before the orchestrator is built)

To make the always-on stream include your new domain, append a workflow
template to `_STREAM_TEMPLATES` in
[`api/server/routes/blueprint.py`](../../api/server/routes/blueprint.py).

Each template is an ordered list of dicts. Every dict needs `type` and
`workflow_type`; `skill` and `tool` are optional but recommended:

```python
# Travel pre-approval — short walk
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

After adding the template, restart FastAPI (the stream loop reads it on
boot). The next time someone clicks **Wake the observatory**, your
domain becomes one of the workflows in flight.

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
| A new domain | `DOMAINS` list in `blueprint_inventory.py` (optional: stream template in `blueprint.py`) |

Three files at most. No frontend edits needed for new content.

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

---

## Reference

- **Spec**: [`docs/superpowers/specs/2026-05-03-blueprint-microsite-design.md`](../superpowers/specs/2026-05-03-blueprint-microsite-design.md)
- **Inventory module**: [`api/server/services/blueprint_inventory.py`](../../api/server/services/blueprint_inventory.py)
- **Routes**: [`api/server/routes/blueprint.py`](../../api/server/routes/blueprint.py)
- **Frontend types**: [`web/blueprint/src/lib/types.ts`](../../web/blueprint/src/lib/types.ts)
