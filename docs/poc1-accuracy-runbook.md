# POC1 Accuracy Harness — Runbook

Week 1 (`v0.6-poc1-accuracy-spine`) landed the full accuracy spine: synthetic policy, 300 labelled claims, R/A/G classifier skill, accuracy harness, AccuracyReport panel, and a live policy-edit-and-rerun route. This runbook is what you do once you want to run the full 300-claim ≥95% accuracy gate (Brief AC #4) end-to-end.

## Quick run (Foundry-backed)

The shortest path from "Foundry resources provisioned" to "AC #4 number on disk":

1. **Env vars** — copy from `.env.example` into `.env`, then fill in:
   - `AZURE_FOUNDRY_PROJECT_ENDPOINT` — Foundry project URI
   - `AZURE_OPENAI_ENDPOINT` — Azure OpenAI base endpoint for the judge model
   - `AZURE_OPENAI_DEPLOYMENT` — judge deployment name (e.g. `gpt-4-1-judge`)
   - `AZURE_OPENAI_API_VERSION` — pinned to `2024-10-21`
   - `AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT` — same as `AZURE_OPENAI_DEPLOYMENT`

   Verify with `uv run python -c "from api.server.eval import foundry_client; print(foundry_client.is_configured())"` — must print `True`.

2. **Pre-classify the 300-claim corpus** (~25 min at concurrency 5):
   ```bash
   uv run python scripts/preclassify_corpus.py --sample-size 300
   ```
   Writes `data/.eval/preclassified-300.jsonl`. This step is the slow part — re-run only when the rag-classifier prompt or retrieval changes.

3. **Run the Foundry batch evaluation** (FastAPI must be up — `./.venv/Scripts/uvicorn.exe api.server.main:app --port 3001 --reload`):
   ```bash
   curl -X POST http://localhost:3001/api/accuracy/run \
     -H 'Content-Type: application/json' \
     -d '{"sample_size": 300}'
   ```
   Returns a `run_id`. Watch progress on `/api/stream/fleet`; fetch the report via `GET /api/accuracy/last` once `accuracy.complete` fires. The result also lands in the Foundry portal (`foundry_run_url` in the report).

The detailed mechanics (alternate triggers, mitigation list, live-policy-edit demo) follow below.

## Pre-flight

```bash
gh auth status                                  # must be logged in
./.venv/Scripts/pytest.exe tests/api -q         # 79 pass / 1 skip / 5 deselected baseline
./.venv/Scripts/pytest.exe tests/api/unit/test_classifier_e2e_smoke.py -m smoke -v
# Expect 5/5 pass. ~2 min wall-clock. Validates GHCP wiring before paying for 300 calls.
```

## Run the full harness

Three terminals (or three `run_in_background` shells):

```bash
# 1) Functions worker (Durable runtime + MAF host)
func start

# 2) FastAPI control plane
./.venv/Scripts/uvicorn.exe api.server.main:app --reload

# 3) Vite dev server
npm run dev:client
```

Two ways to trigger the full 300-claim run:

**A. UI** — open the Vite URL → `/evaluations` → click **Run accuracy harness**. Progress streams over `/api/stream/fleet`; the AccuracyReport panel renders on `accuracy.complete`.

**B. curl** — keep the dev stack up, then:

```bash
curl -X POST http://localhost:8000/api/accuracy/run \
  -H "Content-Type: application/json" -d '{}'
# returns {"run_id":"acc-XXXXXXXX","n":300}

curl -N http://localhost:8000/api/stream/fleet | jq 'select(.type|startswith("accuracy."))'
# in another terminal — watch progress events stream

curl -s http://localhost:8000/api/accuracy/last | python -m json.tool | head -40
# once accuracy.complete fires
```

Wall-clock: ~5–10 min at concurrency 8 depending on model latency.

## Pass / fail

The Week 1 acceptance bar is `overall_accuracy ≥ 0.95`. If the result is below 0.95, work the `§9` mitigation list from the design spec:

1. Open the AccuracyReport panel → click each off-diagonal cell → read predicted vs gold reasoning side by side. Pattern-spot the failure mode.
2. Cheapest fixes first:
   - Tighten `api/server/skills/rag_classifier.skill.md` — clarify the 110% boundary rule, demand literal policy text in `reasoning`.
   - Increase `_TOP_K_POLICY_CHUNKS` in `api/functions/graphs/executors/agents/agent_rag_classifier.py` (default 6 → try 8–10).
   - Re-chunk the policy at paragraph rather than section granularity in `api/server/mcp_tools/policy_search.py::_split_into_sections` (already falls back at >600 chars).
   - Tighten the synthetic generator's amber boundary in `data/synthetic/generate.py` — narrow 100–110% to 100–105%.
3. Re-run the harness after each change. Each iteration is a commit with the new accuracy in the message.

## AC #4 demo — live policy edit

Once the floor holds, demonstrate that classifier behaviour is policy-driven (not code-driven):

1. UI page or `curl -X POST http://localhost:8000/api/policy-md/save -H "Content-Type: application/json" -d "{\"content\": \"<edited policy.md>\"}"`. The save endpoint invalidates the `policy_search` cache.
2. Re-run the harness. Meal-category accuracy in the affected market shifts visibly — previously-Green claims become Amber when the cap drops; previously-Amber claims become Red. **No code changed between the two runs.** Only the policy text moved.
3. Revert with `git checkout data/synthetic/policy.md` and run a final clean baseline:

```bash
curl -s http://localhost:8000/api/accuracy/last > docs/poc1-accuracy-baseline.json
git add docs/poc1-accuracy-baseline.json
git commit -m "evidence: 300-claim accuracy baseline ≥95% with policy-driven reasoning"
```

## Stop the stack

Per house standing instruction, kill `func start`, `uvicorn`, and `npm run dev:client` before walking away — don't leave background services accumulating state.

## Known issues to be aware of when tuning

- **Test-fixture flake on Windows.** `test_synthetic_generate.py` and `test_receipt_generator.py` write to `data/synthetic/claims/` from autouse fixtures. After a full `pytest tests/api -q` the working tree shows ~300 modified claim JSONs (the `receipt_mismatch_flavour` field gets stripped by the synthetic_generate cleanup). Run `git checkout -- data/synthetic/claims/` to restore committed state. Not blocking.
- **MCP tools are pure Python in this POC.** `policy.search` and `claim.getStructured` are resolved in process by `agent_rag_classifier.execute` and embedded in the prompt — not wired as live MCP tool servers. If you swap to a real Foundry IQ or MCP-server binding later, update `agent_rag_classifier.py` accordingly; the skill markdown does not need to change because it already classifies whatever is in the prompt.
