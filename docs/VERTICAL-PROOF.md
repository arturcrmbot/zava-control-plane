# Vertical Proof

**Contract version:** `1.0.0`

This document defines the permanent evidence requirements that must be
satisfied before a vertical is considered shippable. Every requirement is
deterministic and repeatable: the same commands, on a clean checkout, must
produce the same pass/fail verdict. References to "Telco" below name the first
vertical to pass this bar; they are illustrative, not prescriptive.

---

## 1. Proof chain

A complete proof walks the following chain **in order**, collecting labelled
evidence at each node:

```
actor world
  └─ sensor fires
       └─ objective registered
            └─ Durable orchestration started
                 └─ HITL gate raised (where workflow declares one)
                      └─ typed command issued by persona
                           └─ world mutation written (entity-graph + store)
                                └─ evaluation: assertions pass
```

Every node that does not apply to a given workflow (e.g. a workflow with no
HITL gate) is marked **N/A** and skipped. All other nodes are **mandatory**.
At every HITL node, additionally prove that the real governance authority
matrix allows the emitted action/category/value and that the suspended Workflow
API record persists `payload.hitl_context` for recovery sweeps.

---

## 2. Identity consistency requirement

After the chain runs, the following surfaces must report the **same workflow
ID and the same terminal outcome** with no discrepancy:

| Surface | How to verify |
|---|---|
| World (actor world event log) | `GET /api/world/events?workflow_id=<id>` |
| Workflow API | `GET /api/workflows/<id>` — `status`, `current_phase` |
| Drawer (UI workflow detail) | Open workflow card; confirm phase ribbon matches API |
| Memory (vector store) | `GET /api/memory/search?q=<id>` returns ≥1 result |
| Knowledge (graph) | Cypher: `MATCH (w {id: "<id>"}) RETURN w.status` |
| AG-UI event stream | Confirm `workflow.completed` event carries correct `workflow_id` |
| Graph projection | Entity nodes written; `MATCH (w)-[:HAS_PHASE]->()` returns expected count |
| Constellation | Workflow appears in Constellation view with correct phase sequence |

Any surface that disagrees is a **blocking failure**.

---

## 3. Replay probes

After the forward chain passes, run two replay probes:

### 3a — Functions disabled

Shut down the Azure Functions host while the server is running. Trigger the
workflow again. The workflow must **not** appear in the feed (no phantom
`workflow.started` event), and no `500` error must propagate to the browser.
Restart the Functions host and confirm normal operation resumes.

### 3b — Actor world disabled

Stop the actor world process. Trigger the workflow via the direct API path
(POST to the pack-owned simulator/diagnostic route). The Durable orchestration
must complete without the actor world, all API surfaces must agree, and no dead
letter entries must appear. The diagnostic must preserve its real source
sensor input and must not claim a world mutation while the world is disabled.
Restart the actor world and confirm the full chain works again.

---

## 4. Browser error gate

Open the browser DevTools console before starting any proof run. After the
run completes:

- **Zero console errors** are allowed. Warnings are acceptable only if they
  are pre-existing and tracked. Zero browser errors means zero — not "low".
- **Zero dropped workflow events** — the AG-UI event stream must show a
  contiguous sequence from `workflow.started` to `workflow.completed` with no
  gaps or out-of-order frames.
- **Clean teardown** — after stopping the stack, no orphan processes on the
  Functions or FastAPI ports (`7071`, `3101`, `5273`). Verify with
  `lsof -ti :<port>` returning empty.
- **Click-to-first-visible latency** — every named scenario must render its
  first journal/state change within one second of the browser click. Time the
  browser, not only the POST response.
- **Backend restart recovery** — keep the page mounted while restarting or
  resetting the actor-world backend. If the new journal's `latest_seq` is lower
  than the client's cursor, the client must replay from `after=0`; no manual
  page refresh is allowed.
- **HITL completion latency** — with `PERSONA_AUTO_CLOSE=*`, every generated
  HITL gate must show a persona decision, `durable.resumed`, and terminal
  workflow state within 15 seconds. A gate that only times out is a failure.

---

## 5. Hero and shared-engine distinction

Some verticals ship a **hero workflow** (the primary showcase, e.g. Telco's
`network-incident`) and one or more **shared-engine workflows** that reuse the
same runtime infrastructure. Each requires **distinct** proof evidence:

| Dimension | Hero | Shared-engine |
|---|---|---|
| Trigger | Unique ambient trigger or simulator route | Same infrastructure; different `workflow_type` |
| Profile | Must have a named profile in `scripts/` | May use the same profile with a different `ZAVA_VERTICAL` env var |
| Command | Distinct typed command; different payload schema | Must not accept the hero's command shape |
| World case | Named scenario in the actor world config | Named scenario; actor world must not conflate the two |
| Success evidence | Terminal state, phase ribbon, entity nodes | Terminal state, phase ribbon, entity nodes — collected separately |

Sharing evidence between hero and shared-engine is not permitted. Each must
pass the §2 identity consistency table independently.

---

## 5a. Blocking execution-visibility gate

Actual execution evidence must be visible and self-consistent. Every active
non-stub workflow type has at least one inspected instance:

1. Its timeline is non-empty, with exactly one `workflow.started` row and one
   terminal lifecycle row matching the final status.
2. Observed phase rows are non-empty and use only declared phases. Conditional
   branches may omit phases; terminal workflows leave observed rows terminal or
   explicitly skipped.
3. Canonical `agent.completed` reasoning rows, when present, have stable run
   identity, completion time, and declared phase provenance. A domain declaring
   agent/graph work needs at least one reasoning row total.
4. Only tool calls that occurred are checked. Reasoning tool IDs, canonical
   `mcpCalls`, and Tool timeline rows match exactly by persistent ID,
   `request`, `response`, `statusCode`, and `durationMs`.
5. Observed HITL decisions have a persona, verdict, and reason, and that persona
   resolves in the active pack. Observed lineage, deterministic output, errors,
   and retries are shape-valid.
6. Live and replay source modes have full user-visible parity.

Use `run_agent_session` for generated agent work. Never fabricate an Agent row
or other evidence.

After all live workflows are terminal, capture and run the full checker:

```bash
ZAVA_VERTICAL=<vertical> .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical <vertical> --base-url http://localhost:3101 \
  --save-dir proof/workflow-details/live
```

Switch the server to replay, then capture every same workflow ID and run the
same checker on both snapshots:

```bash
ZAVA_VERTICAL=<vertical> .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical <vertical> --base-url http://localhost:3101 \
  --compare-dir proof/workflow-details/live \
  --save-dir proof/workflow-details/replay
```

Online capture always reads `/api/replay/meta`. Snapshot schema v2 persists its
`sourceMode`: the first pass must be `live`, the compared pass must be `replay`,
and directory names cannot override provenance. For offline comparison, replace
the second command's `--base-url` with
`--details-dir proof/workflow-details/replay`; both snapshots must retain their
explicit live/replay modes.

Parity uses a stable projection of every visible timeline row, in endpoint
order, plus workflow status/current phase and exact MCP payloads in endpoint
order. It includes phase status, Agent messages/output/tool refs/tokens/model,
decisions and evidence, deterministic outputs, child IDs/types, and ledger
errors/retries. The only exclusions are
workflow create/update/start/completion timestamps, timeline timestamps (`ts`,
`timestamp`, started/completed aliases), non-canonical row latency/duration,
and MCP `timestamp`; canonical Tool/MCP duration remains exact, so live and
replay agree through the terminal event. Workflow SLA remains exact. The
ignored `proof/` snapshots may contain workflow
payloads; do not print or commit them.

---

## 6. Completion criteria

A vertical proof is **complete** when:

1. The §1 proof chain passes for every workflow declared in the pack's
   `domains.py`.
2. The §2 identity consistency table passes for every workflow.
3. Both §3 replay probes pass.
4. The §4 browser error gate passes.
5. Hero and every shared-engine workflow each have distinct §5 evidence.
6. Every HITL action passes the real authority-matrix check and every suspended
   workflow persists `payload.hitl_context`.
7. The graduate.sh validation step (`step 6/6`) exits 0 on a clean run:
   `ZAVA_VERTICAL=<vertical> bash <run-id>/graduate.sh`
8. A recorded walk (`data/blueprint-recordings/<wt>-*.jsonl`) exists for
   every workflow, committed to the repository.
9. The §5a blocking execution-visibility gate passes for every active non-stub
   workflow type.

**Do not claim a vertical is shipped until all nine criteria are met.**

---

## 6a. Readiness vocabulary

- **Build ready** means all applicable machine completion criteria above pass.
- **Demo ready** means build-ready evidence plus a human seller review of reset,
  pacing, visual quality, and story coherence.
- **Deployed** is a separate state reached only through an approved deployment
  mode and its preflight and post-deploy checks.

Machine proof reports the machine result and leaves seller review pending until
a human completes it.

This contract version does not change `proof/manifest.json`. Manifest schema,
repeatability-ledger, and deployment-preflight changes require a later
versioned contract.

---

## 7. Reference implementation

The Telco vertical (`verticals/telco/`) is the canonical passing example.
Use its proof run as a template — not a literal copy-paste script — when
authoring proof for a new vertical. Key paths:

- World config: `verticals/telco/world.yaml`
- Pack domains: `verticals/telco/domains.py`
- Recorded walks: `data/blueprint-recordings/` (files prefixed with Telco
  workflow types)
- Proof smoke commands: printed by `graduate.sh` step 6 after a successful
  run
