# Blueprint event recordings

This directory holds JSONL files recorded from the in-process event bus,
used by the blueprint observatory's demo trickle to replay real workflow
walks instead of hand-coded synthetic templates.

## File format

One workflow per file. Each line is a single event:

```jsonl
{"ts_offset_ms":0,"event":{"type":"workflow.started","workflow_type":"hiring","workflow_id":"HIRE-DEMO-04"}}
{"ts_offset_ms":1240,"event":{"type":"durable.step.started","skill":"cv-crystalliser","workflow_type":"hiring","workflow_id":"HIRE-DEMO-04"}}
```

`ts_offset_ms` is the millisecond delta from the first event of that
workflow. Playback respects this cadence (clamped to 200ms–4s per gap to
keep the page readable).

## Filename pattern

```
<workflow_type>-<UTC timestamp>-<short workflow_id>.jsonl
```

For example:
```
hiring-20260503T184022-HIRE-7351.jsonl
expense-claim-20260503T184155-CLM-2014.jsonl
fleet-travel-preapproval-20260503T184230-TRVL-9912.jsonl
```

## How to record

Start the FastAPI server with whatever real backend is firing events
(Functions host, mock MCPs, simulator). Then:

```bash
# 1. Start recording
curl -X POST http://localhost:3001/api/blueprint/_recorder/start

# 2. Trigger your real workflows however you do it (simulator inject,
#    portal /apply, real ATS callback, etc.)

# 3. Stop and flush
curl -X POST http://localhost:3001/api/blueprint/_recorder/stop
```

The recorder writes one JSONL file per workflow that completed during
the recording window. In-flight workflows at stop-time are flushed too
(partial recordings — fine for playback, page just stops the workflow
mid-walk).

## How to curate

- Open the JSONL files. Each line is one event. Hand-delete short runs
  or runs with no skill activity if you don't want them in the trickle.
- If you have multiple recordings of the same workflow, the trickle
  picks one at random per spawn — so committing 3 versions of `hiring`
  gives the page more variety than one.
- The trickle prefers recordings over synthetic templates whenever any
  recordings exist. Empty this directory to fall back to synthetic.

## What gets captured

Only events with types the observatory cares about (the `RECORDED_TYPES`
set in `api/server/services/blueprint_recorder.py`):

- workflow.started, durable.workflow.started
- durable.step.started, durable.step.completed
- durable.executor.invoked
- agent.completed
- durable.validator.blocked
- workflow.exception.detected
- workflow.hitl.requested
- durable.suspended
- durable.workflow.completed, workflow.resolved

Events without a `workflow_id` are skipped (the recorder needs to group
events by workflow).

## Why these files are committed

The blueprint deployment uses these recordings to make the live page
look like real activity. They're a deployment artefact, not a test
fixture. Treat them like the Gutenberg PNG: real, regenerable, expensive
enough to want versioned.
