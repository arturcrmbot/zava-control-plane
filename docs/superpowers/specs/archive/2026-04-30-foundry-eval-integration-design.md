# Foundry Evaluation Integration — Design Spec

> **Topic:** Replace the fake `/api/evals` random-number tiles and re-platform the labeled-corpus accuracy harness onto Azure AI Foundry's evaluation SDK, so every GHCP SDK agent invocation is scored by Foundry and the Apex control plane shows only real numbers.
> **Date:** 2026-04-30
> **Status:** Design — awaiting implementation plan
> **Scope:** POC1 (live now) + POC2 (inherits automatically once its agents go through `run_agent_session`).

---

## 1. Context

The control plane currently has two evaluation surfaces:

1. **`/api/evals` — fake.** [api/server/routes/evals.py](../../../api/server/routes/evals.py) returns `random.random()` numbers in the 0.85–1.0 range every 5 seconds. The "Continuous Evaluation" tiles on the Evaluations page (Task adherence / Safety / Tool accuracy) are entirely synthetic. This is dashboard candy from the original POC1 shell.
2. **`/api/accuracy/run` — real.** [api/server/routes/accuracy.py](../../../api/server/routes/accuracy.py) and [api/functions/workflows/accuracy_harness_workflow.py](../../../api/functions/workflows/accuracy_harness_workflow.py) drive a real 300-claim labeled-corpus evaluation against the rag-classifier. Confusion matrix and per-category accuracy are computed in-process by a hand-rolled async fan-out. No Foundry involvement.

Foundry is referenced in architecture docs but no `azure-ai-evaluation` SDK calls exist anywhere. The runbook ([docs/poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md)) explicitly notes Foundry IQ is aspirational ("MCP tools are pure Python in this POC … not wired as live MCP tool servers").

This design moves **all** evaluation onto Azure AI Foundry. GHCP SDK does no scoring. The control plane is a presentation layer over Foundry results, with strict no-fake-numbers semantics — when Foundry is not configured, the control plane explicitly says so rather than rendering zeros or synthetic placeholders.

## 2. Goal

1. Every GHCP SDK agentic action (each `run_agent_session` return) triggers a Foundry evaluation, scored asynchronously against an evaluator set chosen per agent label.
2. The labeled-corpus accuracy harness re-platforms onto Foundry's `evaluate()` SDK call with a real Foundry project run for every batch — visible in the Foundry portal, comparable across runs.
3. The Apex control plane's Evaluations page renders only real numbers from a local store of Foundry-scored rows. When Foundry is not configured, the page says so explicitly. No synthetic fallback at any point.
4. POC2 agents (when they exist) inherit eval-ing automatically because they go through the same `run_agent_session` chokepoint — no POC2-specific eval code.

Non-goals: replacing OTEL spans (those continue as today); changing how agents themselves work; provisioning the Foundry project (already exists); eval scoring on tool calls in isolation (per-agent grain is the chosen surface).

## 3. Approach

**Event-bus subscriber** (Approach 2 of three considered during brainstorm).

The repo already has a fleet event bus (`app_state.bus.emit(FleetEvent(...))` in [api/shared/events.py](../../../api/shared/events.py)). [api/functions/graphs/executors/agents/_wrapper.py](../../../api/functions/graphs/executors/agents/_wrapper.py)'s `run_agent_session` is the single chokepoint every agent invocation passes through. We:

1. Add `"agent.completed"` to `FleetEventType` (not in `WAKE_TYPES` — observation only, doesn't wake the fleet manager).
2. Have `run_agent_session` emit one `FleetEvent("agent.completed", ...)` at the end of every call, carrying the eval payload (prompt, response, tool_calls, usage, latency, workflow_id correlation).
3. Add a new subscriber `online_subscriber.py` that picks up `agent.completed`, applies sampling, queues, drains in a background worker that calls each Foundry evaluator's `__call__` directly (one row at a time), and persists results into a local sqlite `EvalStore`.
4. Rewrite `/api/evals*` to read from the store. Replace the random tiles in `Evaluations.tsx` with real per-evaluator metrics and an explicit "not configured" empty state.
5. Replace the math in the batch accuracy harness with a Foundry `evaluate()` call. Same route surface (`/api/accuracy/run`, `/api/accuracy/last`), same response shape, same AccuracyReport panel — but Foundry computes the scores and the run shows up in the Foundry portal.

Considered and rejected:
- **Decorator/middleware around `run_agent_session`** — couples GHCP plumbing with eval plumbing; fragments across multiple `_wrapper.py`-style helpers.
- **`azure_ai_responses` data source upload** — Foundry's response-shape doesn't fit GHCP SDK output cleanly; per-agent evaluator selection becomes fiddlier; latency from "agent finished" → "score visible" goes from seconds to scheduled-batch.

## 4. Architecture

### 4.1 Overall shape

```
GHCP SDK call site (any agent)
  └─ run_agent_session(prompt, tools, skill_dir, workflow_id)
       └─ emits FleetEvent("agent.completed", {…eval payload})
                              │
                              ▼
                       app_state.bus
                              │
                              ▼
        api/server/eval/online_subscriber.py
          - sampling gate (EVAL_SAMPLE_RATE)
          - asyncio.Queue (max EVAL_QUEUE_MAX)
          - background worker drains → calls each evaluator's
            __call__ directly (Groundedness, Relevance, …)
          - writes rows into EvalStore
                ┌─────────────┴──────────────┐
                ▼                            ▼
     Foundry judge model              EvalStore (sqlite)
     (LLM scoring per evaluator;      (real rows, real numbers;
      no per-row portal upload)        system of record for online)
                                            │
                                            ▼
                                  /api/evals  (rewritten)
                                  /api/evals/summary
                                  /api/evals/{id}
                                  /api/evals/health
                                            │
                                            ▼
                                  Evaluations.tsx (rewritten)
                                   - real per-agent metrics
                                   - "Foundry not configured" panel
                                     when creds missing (no fake nums)
                                   - link out to Foundry portal
```

Two paths share the Foundry judge model and the same evaluator implementations, but use different SDK entry points:

- **Online stream**: `agent.completed` → subscriber → calls each evaluator's `__call__` directly (`Groundedness(model_config)(query=…, response=…, context=…)`) for one row at a time. Real Foundry-judge LLM scoring; result stored in local sqlite. **Not** uploaded as a named run to the Foundry portal — at 1.0 sampling that would create thousands of one-row portal runs which is just noise. Control-plane store is the system of record for online evals.
- **Batch corpus** (the 300-claim harness, re-platformed): uses the higher-level `evaluate()` orchestration helper against the labeled JSONL with `target=` pointing at `agent_rag_classifier.execute` and `azure_ai_project=` set. Foundry uploads the run as a named, comparable entry in the portal. Same store, tagged `kind="batch"`. This is where the "tracked across runs" benefit lives.

### 4.2 Workflow correlation

`run_agent_session` gets a new optional `workflow_id` kwarg. Every Durable workflow executor passing through `agent_rag_classifier.execute`, `agent_arbitration.execute`, etc. plumbs the workflow's id down. Eval rows store both `workflow_id` and `agent_run_id` so the control plane can join on either axis.

This is a small ripple: every executor under [api/functions/graphs/executors/agents/](../../../api/functions/graphs/executors/agents/) gains a `workflow_id` parameter and forwards it.

## 5. Components

### 5.1 New files (under `api/server/eval/`)

#### `foundry_client.py`
Singleton wrapper around `EvaluationClient` and `AIProjectClient`. Reads:
- `AZURE_FOUNDRY_PROJECT_ENDPOINT` (required)
- `AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT` (required — the LLM used by groundedness/relevance/coherence/etc.)
- Credentials via `DefaultAzureCredential`.

Public surface:
- `is_configured() -> bool` — returns False if any required env var is missing.
- `get_project_config() -> dict` — for `evaluate(azure_ai_project=...)`.
- `get_model_config() -> AzureOpenAIModelConfiguration` — for evaluators that take a `model_config`.

If not configured: every other module in `api/server/eval/` checks `is_configured()` and no-ops accordingly. Never falls back to local scoring.

#### `evaluator_set.py`
Agent-label → evaluator list mapping:

| Agent label | Evaluators |
|---|---|
| `rag-classifier` | `Groundedness`, `Relevance`, `Similarity`, `PolicyClauseCited` (custom), `ToolCallValidity` (custom) |
| `arbitration` | `Groundedness`, `Relevance`, `Coherence`, `Violence`, `HateUnfairness` |
| `*` (default for any new agent — including all POC2 agents) | `Coherence`, `Fluency`, `Violence`, `HateUnfairness` |

Public: `evaluators_for(agent_label: str) -> dict[str, Evaluator]`. Built lazily so we don't construct judges at import time.

Also exports a per-agent `extract_context(tool_calls: list[dict]) -> str` extractor map, used to populate the `context` field for groundedness:
- `rag-classifier`: concat `policy_search` tool call results.
- `arbitration`: concat `precedents_search` tool call results.
- default: empty string.

#### `custom_evaluators.py`

- **`PolicyClauseCited`** — for `rag-classifier`. Returns `{policy_clause_cited: 0|1, policy_clause_excerpt: str|None}`. Implementation: substring/normalised-whitespace check that some 30+ char run from `context` (the policy_search results) appears in `response.reasoning`. Catches the failure mode where the model hallucinates a clause number without the literal text.
- **`ToolCallValidity`** — generic. Returns `{tool_calls_valid: 0..1, invalid_calls: [...]}`. Checks each tool call's `name` is in the agent's declared tools, and that each call's `args` JSON-parses cleanly. Cheap, deterministic.
- **`GoldLabelMatch`** — batch-only, for the labeled corpus path. Returns `{label_match: 0|1, predicted, gold}`. Drives the confusion matrix.

Each evaluator is a class with `__call__(self, *, query, response, context=None, ground_truth=None, **kwargs) -> dict` matching the SDK's evaluator protocol.

#### `online_subscriber.py`
FastAPI lifespan-managed. **At startup**: checks `foundry_client.is_configured()`; if False, logs once and returns without subscribing — the bus never emits eval traffic. If True, registers the `agent.completed` callback and starts the drain worker.

Pseudocode:

```python
# Bus uses on_any(callback) — established pattern in fleet_manager_service.py:87
# and main.py:57. We filter on event.type inside the callback.

async def lifespan_register(app):
    if not foundry_client.is_configured():
        log.warning("Foundry not configured; online eval subscriber inactive")
        return
    app.state._eval_unsub = app_state.bus.on_any(on_bus_event)
    app.state._eval_worker = asyncio.create_task(_drain_worker())

async def lifespan_shutdown(app):
    unsub = getattr(app.state, "_eval_unsub", None)
    if unsub:
        unsub()
    worker = getattr(app.state, "_eval_worker", None)
    if worker:
        worker.cancel()

def on_bus_event(event: FleetEvent) -> None:
    if event.type != "agent.completed":
        return
    if random.random() >= float(os.getenv("EVAL_SAMPLE_RATE", "1.0")):
        return  # sampled out
    row = _build_row(event)
    store.put_pending(row)
    try:
        _queue.put_nowait(row)
    except asyncio.QueueFull:
        store.drop_oldest_pending()
        _queue.put_nowait(row)
        _metrics["dropped"] += 1

async def _drain_worker():
    evaluators_cache = {}  # agent_label -> {name: instance}
    while True:
        row = await _queue.get()
        try:
            evaluators = evaluators_cache.setdefault(
                row.agent_label, evaluator_set.evaluators_for(row.agent_label),
            )
            scores = {}
            for name, ev in evaluators.items():
                # Each evaluator returns a dict of scores + reasoning.
                scores[name] = await asyncio.to_thread(
                    ev,
                    query=row.prompt,
                    response=row.response_text,
                    context=row.context,
                    ground_truth=None,  # online has no gold; similarity skipped if None
                )
            store.complete(row.id, scores=scores, foundry_run_url=None)
        except RateLimitError:
            await _retry_with_backoff(row, attempt=…)
        except Exception as ex:
            store.error(row.id, error_text=str(ex)[:500])
```

`foundry_run_url` is `None` for online rows — they are not tracked-as-named-runs in the portal (see §4.1 rationale). Batch rows get a real `foundry_run_url` via `evaluate()`'s `result.studio_url`.

#### `store.py`
Sqlite at `data/.eval/store.sqlite` (path under `data/` so it's ignored by git via existing `.gitignore` patterns; verify and add if needed). Schema:

```sql
CREATE TABLE evals (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL,         -- "online" | "batch"
  agent_label     TEXT NOT NULL,
  workflow_id     TEXT,                  -- nullable (batch rows don't have one)
  agent_run_id    TEXT,
  ts              REAL NOT NULL,         -- unix epoch seconds
  scores_json     TEXT,                  -- nullable until completed
  foundry_run_url TEXT,                  -- nullable
  status          TEXT NOT NULL,         -- "pending" | "completed" | "error"
  error_text      TEXT
);
CREATE INDEX idx_evals_ts ON evals(ts DESC);
CREATE INDEX idx_evals_workflow ON evals(workflow_id);
CREATE INDEX idx_evals_agent ON evals(agent_label);
```

Public API: `put_pending(row)`, `complete(id, scores, foundry_run_url)`, `error(id, error_text)`, `recent(n, agent_label=None)`, `summary(window_minutes)`, `by_id(id)`, `by_workflow(workflow_id)`, `last_batch_run()`, `put_batch(run_id, report)`, `drop_oldest_pending()`, `health()`.

#### `batch_runner.py`
Replaces the math in [api/functions/workflows/accuracy_harness_workflow.py](../../../api/functions/workflows/accuracy_harness_workflow.py):

```python
async def run(claim_ids, run_id, publish):
    rows = [_to_eval_row(cid) for cid in claim_ids]
    jsonl_path = _write_temp_jsonl(rows)

    def target(*, claim_id, **_):
        cls = asyncio.run(rag_execute({"claim_id": claim_id}))["classification"]
        return {
            "predicted_label": cls["verdict"],
            "predicted_reasoning": cls["reasoning"],
            "policy_clause": cls.get("policy_clause", ""),
            "context": _extract_policy_context(claim_id),
        }

    result = evaluate(
        data=jsonl_path,
        target=target,
        evaluators={
            "groundedness": GroundednessEvaluator(model_config),
            "similarity":   SimilarityEvaluator(model_config),
            "label_match":  GoldLabelMatch(),
            "policy_cited": PolicyClauseCited(),
        },
        evaluator_config={
            "groundedness": {"column_mapping": {
                "query": "${data.claim_id}",
                "response": "${target.predicted_reasoning}",
                "context": "${target.context}",
            }},
            "similarity": {"column_mapping": {
                "query": "${data.claim_id}",
                "response": "${target.predicted_reasoning}",
                "ground_truth": "${data.gold_reasoning}",
            }},
            "label_match": {"column_mapping": {
                "predicted": "${target.predicted_label}",
                "gold": "${data.gold_label}",
            }},
        },
        azure_ai_project=foundry_client.get_project_config(),
        evaluation_name=f"poc1-accuracy-{run_id}",
    )

    report = _shape_existing_report(result, claim_ids)
    report["foundry_run_url"] = result.studio_url
    store.put_batch(run_id, report)
    publish({"type": "accuracy.complete", "run_id": run_id, "summary": {…}})
    return report
```

Preserves `/api/accuracy/run`, `/api/accuracy/last`, `/api/accuracy/{run_id}` shapes so [web/client/components/AccuracyReport.tsx](../../../web/client/components/AccuracyReport.tsx) needs no structural changes (only adds a "View in Foundry portal →" link).

`accuracy.progress` events still fire, published from a Foundry SDK row-level callback if the SDK exposes one, otherwise batched (one progress event every N rows) as a fallback.

### 5.2 Modified files

#### [api/shared/events.py](../../../api/shared/events.py)
Add `"agent.completed"` to the `FleetEventType` literal. Not added to `WAKE_TYPES` — observation only.

#### [api/functions/graphs/executors/agents/_wrapper.py](../../../api/functions/graphs/executors/agents/_wrapper.py)
At the very end of `run_agent_session`, emit one `FleetEvent`. Payload shape:

```python
FleetEvent(
    type="agent.completed",
    workflow_id=workflow_id,
    agent_label=skill_label,
    agent_run_id=str(uuid.uuid4()),
    prompt=prompt,
    response_text=text,
    extracted_json=parsed,
    tool_calls=tool_calls_collected,
    context=evaluator_set.extract_context(skill_label, tool_calls_collected),
    usage={"input_tokens": …, "output_tokens": …},
    latency_ms=elapsed_ms,
)
```

The OTEL bridge already records tool calls into `open_spans`; we extend it to also append a flat `tool_calls_collected` list (`name`, `args`, `success`, `latency_ms`). The emit itself is wrapped in `try/except: pass` — same defensive shape as the existing OTEL bridge in `_wrapper.py:97` ("Observability must never crash the caller").

`run_agent_session` gains a `workflow_id: str | None = None` kwarg. Every executor under [api/functions/graphs/executors/agents/](../../../api/functions/graphs/executors/agents/) passes it through.

#### [api/server/routes/evals.py](../../../api/server/routes/evals.py)
Gut the `_evals` random-generation. Three endpoints, all reading from `EvalStore`:

- `GET /api/evals` → `recent(50)`. Honors optional `?agent_label=` filter.
- `GET /api/evals/summary` → tile values + per-agent breakdown + queue health (see §6.1).
- `GET /api/evals/{id}` → single row with full scores and `foundry_run_url`.
- `GET /api/evals/health` → `{configured, pending, in_flight, errored_last_window, dropped_last_window, sample_rate}`.

If `foundry_client.is_configured()` is False, every endpoint returns `{"configured": false, "reason": "..."}` with HTTP 200 (it's "I'm working, just nothing to show" — not an error).

#### [api/server/routes/accuracy.py](../../../api/server/routes/accuracy.py)
`POST /api/accuracy/run` calls `batch_runner.run` instead of `harness.run`. If not configured, returns HTTP 503 with `{"configured": false, "reason": "..."}` — we don't let someone trigger a "real" run that secretly isn't.

#### [web/client/routes/Evaluations.tsx](../../../web/client/routes/Evaluations.tsx)
Full rewrite. See §6.

#### `.env.example`
Add:
```
AZURE_FOUNDRY_PROJECT_ENDPOINT=
AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT=
EVAL_SAMPLE_RATE=1.0
EVAL_QUEUE_MAX=1000
```

### 5.3 Removed
- The whole `_evals: list[dict]` and random-generation block in `routes/evals.py`.
- The asyncio fan-out body of `accuracy_harness_workflow.py:run`. The file becomes a thin shim, or is deleted and tests are updated to point at `batch_runner.run`.

## 6. Data flow

### 6.1 Online path (one expense claim's rag-classifier run)

1. Durable workflow step calls `agent_rag_classifier.execute({"claim_id": "CLM-0042", "workflow_id": "wf-abc"})`.
2. Executor calls `run_agent_session(prompt, tools, skill_dir, skill_label="rag-classifier", workflow_id="wf-abc")`.
3. SDK session runs. OTEL bridge records each tool call into `tool_calls_collected = [{name, args, success, latency_ms}, …]`.
4. Just before `run_agent_session` returns, emits `FleetEvent("agent.completed", …)` with the payload from §5.2.
5. `online_subscriber` callback fires. Sampling gate (`random.random() < EVAL_SAMPLE_RATE`); if kept, push onto queue and write a `pending` row to `EvalStore`.
6. Background worker pops, looks up evaluator set for `rag-classifier`, calls **each evaluator's `__call__` directly** (`Groundedness(model_config)(query=…, response=…, context=…)`, `Relevance(...)`, `PolicyClauseCited()`, `ToolCallValidity()`, etc.). Each evaluator that uses an LLM judge calls Foundry under the hood; deterministic custom evaluators run locally. Single-row online evals do **not** go through `evaluate()` (that's the batch helper) and do **not** create a named run in the Foundry portal — see §4.1 rationale.
7. Worker updates the row: `status="completed"`, `scores_json=<merged dict of evaluator-name → score>`, `foundry_run_url=None` (online rows have no portal entry). Errors → `status="error"`, `error_text=…`, after one retry with 2s backoff.
8. Control plane's polling fetch on `/api/evals/summary` (5s tick) picks it up.

**Invariant**: workflow latency is unaffected by Foundry. The wrapper emits and returns. If Foundry is slow or down, agent execution is unaffected.

### 6.2 Batch path (the 300-claim corpus)

1. UI/curl hits `POST /api/accuracy/run`. Route generates `run_id`, calls `batch_runner.run(claim_ids, run_id)` as a background task. Returns 202 immediately.
2. `batch_runner` builds a JSONL of `{claim_id, gold_label, gold_reasoning, gold_category}` rows.
3. Calls Foundry `evaluate()` with `target=` pointing at a wrapper around `rag_execute`, evaluators = groundedness + similarity + label_match + policy_cited, `azure_ai_project=` configured.
4. SDK calls our target N times (Foundry handles concurrency), scores each row, uploads aggregate run to the Foundry project, returns a result object.
5. `batch_runner` builds the existing-shape report (`overall_accuracy`, `per_category`, `confusion_matrix`, `per_claim`) by extracting `label_match` results — same data the AccuracyReport panel already consumes. Adds `foundry_run_url`.
6. Stored in `EvalStore` with `kind="batch"`. `/api/accuracy/last` reads from there.
7. Bus events `accuracy.progress` / `accuracy.complete` continue to fire.

### 6.3 Tile roll-up (the three Evaluations tiles)

`/api/evals/summary` defines:

- **Task adherence** = `mean(groundedness)` across all rows in the window. If an agent has no groundedness evaluator (e.g. POC2 default-set agents), it's *excluded* from the mean — never substituted.
- **Safety** = `1 - mean(max(violence_score, hate_unfairness_score) / 7)` across all rows in the window. (Foundry safety scores are 0–7 with 7 worst — invert and normalise.)
- **Tool accuracy** = `mean(tool_call_validity)` across all rows in the window.

Each tile's response body includes `n_evals`, `n_agents`, and `evaluators` so the UI can render the denominator. **No black-box composites.**

## 7. Evaluator selection rationale

For `rag-classifier`:
- **Groundedness** answers: does the verdict's reasoning trace to retrieved policy text? (Catches policy hallucination.)
- **Relevance** answers: is the response actually about the claim? (Catches off-topic drift.)
- **Similarity** answers: does the predicted reasoning align with the gold reasoning we have on labeled corpus rows? (Online traffic doesn't have gold; this evaluator is skipped at runtime if `ground_truth` is None.)
- **PolicyClauseCited** (custom) answers: did the response include a literal substring from the policy? Cheap, deterministic, catches the specific failure mode where the model says "per clause 3.2.1" without quoting the clause.
- **ToolCallValidity** (custom) answers: did the model call valid tools with parseable args? This is the "tool accuracy" tile's underlying signal.

For `arbitration`:
- **Groundedness** + **Relevance** for substantive correctness against retrieved precedents.
- **Coherence** for response quality (arbitration produces multi-sentence recommendations, not a JSON verdict).
- **Violence** + **HateUnfairness** for safety floor.

For `*` (default, including POC2 agents): just the safety floor + coherence + fluency. POC2 agents get tighter sets as their behaviour solidifies — this is intentionally minimal so POC2 inherits eval-ing automatically without requiring per-agent design.

## 8. Error handling, sampling, no-creds behavior

### 8.1 No-creds (`is_configured()` returns False)
- All eval-writing paths no-op. No queueing, no events stored, no fake fallback.
- `GET /api/evals*` and `GET /api/accuracy/last` return `{"configured": false, "reason": "..."}` with HTTP 200.
- `POST /api/accuracy/run` returns HTTP 503 with the same envelope. We don't allow a "real" run that secretly isn't.
- `Evaluations.tsx` shows a single explicit panel: *"Foundry evaluation is not configured. Set `AZURE_FOUNDRY_PROJECT_ENDPOINT` and `AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT` to enable."* No tiles, no zeros, no skeletons that look like loading.
- The `agent.completed` event still fires (workflows continue exactly as today). The subscriber's lifespan-register hook checks `is_configured()` at startup and skips registration entirely when False — the bus has no eval listener attached, so emit is just a no-op fan-out.

### 8.2 Sampling (`EVAL_SAMPLE_RATE`)
- Defaults to `1.0`. Subscriber rolls `random.random() < rate` per event; below threshold, drop without queueing.
- Sampling is per-event, not per-workflow — a workflow's 4 agent invocations may have a mixed sample. That's correct: per-agent metrics are what matter.
- Drop counter exposed at `/api/evals/health`: *"12 events sampled out / 18 enqueued / 6 in flight"*.

### 8.3 Foundry call failures
- Single retry with 2s backoff. If the second attempt fails: write `status="error"` row with `error_text=str(exc)[:500]`. **No silent drop.**
- Error rows are *included* in `/api/evals` listings (visible) but *excluded* from `/api/evals/summary` averages. Summary endpoint returns `n_completed` and `n_errored` separately. **Explicit choice**: alternative is "include errored rows as 0", which is more conservative-pessimistic, but a Foundry rate-limit shouldn't make displayed groundedness drop from 0.92 to 0.61 — that *is* a misleading number.
- Rate-limit (HTTP 429) is special: row stays `pending`, requeued with longer backoff (5s × attempt, max 3). After max attempts, becomes an `error` row.

### 8.4 Queue overflow
- `EVAL_QUEUE_MAX=1000` (env-tunable). At capacity, drop-oldest pending row, increment `dropped_count`, log warning. Drop is visible in `/api/evals/health`.
- Right policy because the control plane wants *recent* signal, not a stale 30-min-old eval finishing while live data piles up.

### 8.5 Workflow-side guarantee
- The `agent.completed` emit at the end of `run_agent_session` is wrapped in `try/except: pass`. **An eval-pipeline failure must never propagate up into the agent's caller.** Same defensive shape as the existing OTEL bridge in `_wrapper.py:97`.

### 8.6 Local dev story
- `.env.example` ships with the Foundry env vars commented out. Default state: not configured. Page renders the "not configured" panel. Tests pass.
- Dev workflow: copy creds from your Foundry project, uncomment, restart uvicorn. Real evals start flowing on the next agent invocation.
- Smoke test (`tests/api/integration/test_foundry_smoke.py`): skipped unless env vars set; runs 5-claim batch + asserts shape. Gated on `pytest.mark.foundry` so CI without secrets stays green.

## 9. Control plane (UI surface)

### 9.1 Evaluations page rewrite

- **Top row — three honest tiles**, same labels as today (Task adherence / Safety / Tool accuracy), but each clickable. Click expands to show: which evaluators feed this tile, how many evals contributed, link to recent rows.
- **Per-agent table** — one row per agent label, columns are the union of evaluators across all agents (with `—` where an evaluator doesn't apply). This is where regressions become visible — `rag-classifier groundedness` dropping from 0.93 → 0.74 is one cell.
- **Recent runs list** — rewritten from current code. Each row: timestamp, agent_label (link to workflow), each score, `foundry_run_url` link out **when present** (only batch rows have one; online rows show no link, which is correct).
- **Health strip** — small text only when something's off: *"3 evals in flight · 0 errored in last 60min · sampling at 100%"* renders only on hover or when error/dropped > 0.
- **AccuracyReport panel** (the batch-eval surface, lower on the page) — keep as-is structurally. Add one new line: *"Run in Foundry portal →"* linking to `foundry_run_url` from the last batch result.
- **"Not configured" state** — replaces everything (tiles, table, list) with a single configuration panel. No half-rendered skeletons.

### 9.2 Workflow detail page

Existing `/workflows/{workflowId}` route gets an "Evaluations" subpanel showing eval rows with `workflow_id == this`. One per agent invocation in the workflow. Per-agent grain pays off here — a user looking at one claim's workflow sees that the rag-classifier scored 0.93 groundedness while the arbitration agent scored 0.74, both for this specific claim.

### 9.3 Out of scope
[web/client/components/apex/PhaseRibbon.tsx](../../../web/client/components/apex/PhaseRibbon.tsx) is currently in the working tree as a modified file but is unrelated to this work. Not touched.

## 10. Testing

### 10.1 Unit tests (no Foundry creds, run in CI)

- `tests/api/eval/test_evaluator_set.py` — `evaluators_for("rag-classifier")` returns the 5-evaluator set; `evaluators_for("arbitration")` returns its set; unknown labels get `*`.
- `tests/api/eval/test_custom_evaluators.py` — parameterised cases for `PolicyClauseCited`, `ToolCallValidity`, `GoldLabelMatch`. Whitespace-normalised matching for clause cited; unknown-tool-name and unparseable-args for validity; case-sensitive Red/Amber/Green for label match.
- `tests/api/eval/test_subscriber_sampling.py` — monkeypatch `random.random`, vary `EVAL_SAMPLE_RATE`, assert queue puts and drops match expectation.
- `tests/api/eval/test_subscriber_overflow.py` — fill queue to max, emit one more, assert oldest pending row dropped, `dropped_count` incremented, warning logged.
- `tests/api/eval/test_store.py` — sqlite CRUD: `recent`, `summary` (errored excluded from averages but counted in `n_errored`), `by_id`, `last_batch_run`. Use temp dir.
- `tests/api/eval/test_foundry_client_no_creds.py` — env unset → `is_configured()` False; lazy init doesn't raise.
- `tests/api/routes/test_evals_route_unconfigured.py` — Foundry not configured: `/api/evals` returns `{configured: false}` with HTTP 200; `/api/accuracy/run` returns HTTP 503.
- `tests/api/routes/test_evals_route_configured.py` — Foundry configured (mocked client), seed store with mixed completed/errored rows, hit `/api/evals/summary`, assert summary excludes errored from averages and reports `n_errored`.
- `tests/api/integration/test_run_agent_session_emits.py` — patch `app_state.bus.emit` to a list-collector, drive a fake `CopilotClient` returning a canned response, assert exactly one `agent.completed` event fires with documented payload shape.

### 10.2 Integration tests (require Foundry creds, gated by `@pytest.mark.foundry`)

- `tests/api/integration/test_foundry_smoke.py` — runs `evaluate()` against 5 hand-picked claims with the real SDK, asserts result has expected score keys present and within 0–1 (or 0–7 for safety) ranges, asserts `studio_url` populated. Wall-clock ~30s. Documented in the runbook as the pre-flight check before the full 300-claim run.
- `tests/api/integration/test_online_subscriber_e2e.py` — real Foundry, manually emit one `agent.completed` event, wait up to 30s for the row to flip from `pending` → `completed` in the store, assert scores landed.

### 10.3 Frontend tests

- `tests/web/Evaluations.test.tsx` — three states: configured + data (tiles render real values, per-agent table renders); configured + empty (empty state, no zeros); not configured (configuration panel only).

### 10.4 Out of scope for tests
- The Foundry SDK itself.
- Snapshot-test of dashboard pixel output. Component-level state-rendering coverage is enough.
- A "300-claim accuracy ≥95%" pass-fail CI test. Manual gate per the runbook — wall-clock and cost preclude per-PR runs.

### 10.5 Smoke run as part of demo prep
Per the no-full-corpus-runs-during-build rule: just `test_foundry_smoke.py` (5 claims) before any milestone. Full 300-claim run only at milestone boundaries.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Foundry rate-limits during demo at 1.0 sampling | `EVAL_SAMPLE_RATE` knob; rate-limit-aware retry; visible queue health |
| Cost: 5 evaluators × N agent invocations × judge calls adds up | `EVAL_SAMPLE_RATE` defaults 1.0 for demos; recommend 0.1 for sustained soak (note in runbook, not code default) |
| Eval queue worker dies silently | Subscriber lifecycle hooked into FastAPI lifespan; `/api/evals/health` shows last-tick ts |
| Foundry portal URL format changes | `foundry_run_url` is a passthrough from `result.studio_url`; rendered as a plain `<a>` |
| 79 tests in `tests/api/` referencing `accuracy_harness_workflow.run()` shape break | Update tests to point at `batch_runner.run` with same input/output contract; tracked in plan as a single test-update task |
| `gh auth token` cache (load-bearing for the 300-claim run) regresses | Untouched by this work; smoke test exercises the path |

## 12. Open questions

None at design-approval time. Dependencies on Foundry portal URL field naming and SDK row-callback availability resolved during implementation by reading the SDK directly via context7 and adjusting if shapes drift.

## 13. Success criteria

1. With Foundry creds set: every agent invocation produces a real eval row in `EvalStore` within 10s of the invocation completing (sampling permitting). Tiles, per-agent table, and recent-runs list all populate from real numbers.
2. Without Foundry creds: page shows the "not configured" panel; no fake fallback anywhere; tests pass; agent workflows are unaffected.
3. The 300-claim batch run completes successfully and shows up as a single comparable run in the Foundry portal. AccuracyReport panel renders the same shape as today plus a "View in Foundry portal" link.
4. POC2 agents, when added, produce eval rows with the default `*` evaluator set with zero POC2-specific eval code.
5. No synthesised eval scores anywhere — the only legitimate `random.random()` use in the eval surface is the sampling gate in `online_subscriber.py`. `api/server/routes/evals.py` no longer generates any number; every value the control plane shows comes from a row Foundry actually scored.
