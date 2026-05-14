# POC1 Foundry Corpus Run Implementation Plan (AC #4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a documented, repeatable Foundry-backed accuracy run on the 300-claim synthetic corpus that scores ≥95% R/A/G classification and lands the per-evaluator number into `docs/poc1-accuracy-baseline.json`. Closes POC1 AC #4.

**Architecture:** No code changes — the Foundry-backed pipeline already shipped 2026-04-30. This plan provisions the Azure resources, runs the existing `POST /api/accuracy/run` endpoint against the 300-claim corpus, iterates the rag-classifier prompt + retrieval if accuracy is below target, and captures the result.

**Tech Stack:** Azure AI Foundry, Azure OpenAI (judge model), the existing `api/server/eval/batch_runner.py`, the existing `docs/poc1-accuracy-runbook.md`.

**Master spec:** [docs/superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md) §7

---

## Task 1: Provision Azure resources

**Files:** `infra/poc1-foundry.bicep` (NEW) or via Azure portal — pick whichever lands faster.

- [ ] **Step 1: Provision Azure AI Foundry project** in the existing tenant.

  - Resource group: `rg-zava-poc-demo`
  - Region: pick one with gpt-4.1 availability (eastus2, swedencentral)
  - Name: `aifp-zava-poc1-eval`

- [ ] **Step 2: Deploy the judge model** (Azure OpenAI gpt-4.1 or gpt-4.1-mini) inside the Foundry project.

  - Deployment name: `gpt-4-1-judge`

- [ ] **Step 3: Capture endpoints / keys**

  - `AZURE_FOUNDRY_PROJECT_ENDPOINT` — the project URI (bare string, see `foundry_client.py` doc comment)
  - `AZURE_OPENAI_ENDPOINT` — the AOAI base endpoint
  - `AZURE_OPENAI_DEPLOYMENT` — `gpt-4-1-judge`
  - `AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT` — same as above
  - `AZURE_OPENAI_API_VERSION` — `2024-10-21`

- [ ] **Step 4: Add to local `.env`** and to `.env.example` (without secrets — just keys + comments).

- [ ] **Step 5: Verify config**

```bash
uv run python -c "from api.server.eval import foundry_client; print(foundry_client.is_configured())"
```

Expected: `True`.

- [ ] **Step 6: Commit `.env.example` updates** (NOT `.env`).

```
git commit -m "config(eval): document Foundry env vars for AC #4 corpus run"
```

---

## Task 2: Pre-classify the 300-claim corpus

**Files:** `scripts/preclassify_corpus.py` (NEW)

The Foundry batch evaluator runs evaluators against pre-classified rows — see [batch_runner.py docstring](../../../api/server/eval/batch_runner.py) and the docs/poc1-accuracy-runbook.md.

- [ ] **Step 1: Write a CLI** that:

  1. Loads all 300 claims from `data/synthetic/claims/`
  2. For each claim, runs the existing `rag-classifier` skill (via a fresh GHCP SDK session) and captures `{predicted_label, predicted_reasoning, context}`
  3. Joins with the ground-truth labels from `data/synthetic/labels.csv`
  4. Writes `data/.eval/preclassified-300.jsonl`, one row per claim

```python
# scripts/preclassify_corpus.py
"""Run rag-classifier across all 300 claims, output JSONL ready for batch_runner."""
from __future__ import annotations
import asyncio, csv, json
from pathlib import Path
from copilot import CopilotClient

# ... see existing accuracy runbook for the per-claim invocation pattern ...

async def main():
    out_path = Path("data/.eval/preclassified-300.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # ... iterate claims, classify, write rows ...
    print(f"wrote {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the pre-classify** (~25 minutes for 300 claims at typical rag-classifier latency)

```bash
uv run python scripts/preclassify_corpus.py
```

- [ ] **Step 3: Verify** the JSONL has 300 rows with the expected fields.

```bash
wc -l data/.eval/preclassified-300.jsonl
head -1 data/.eval/preclassified-300.jsonl | jq .
```

- [ ] **Step 4: Commit the script** (NOT the JSONL — gitignored by `data/.eval/`).

```
git commit -m "feat(eval): preclassify CLI for the 300-claim corpus"
```

---

## Task 3: Run the Foundry batch evaluation

- [ ] **Step 1: Boot the FastAPI server** (Functions host not strictly required for this — `/api/accuracy/run` runs in FastAPI's BackgroundTasks)

```bash
uv run uvicorn api.server.main:app --port 8000
```

- [ ] **Step 2: Trigger the run**

```bash
curl -X POST http://localhost:8000/api/accuracy/run \
     -H 'Content-Type: application/json' \
     -d '{"sample_size": 300}'
```

Expected: 202 with a `run_id`. The batch runs in background; status flows on `/api/stream/fleet`.

- [ ] **Step 3: Wait for completion** (~5-10 minutes for 300 rows of judge-model evaluation)

- [ ] **Step 4: Inspect results**

```bash
curl http://localhost:8000/api/accuracy/last
```

Expected: `{run_id, status: "completed", per_evaluator: {gold_label_match: 0.X, policy_clause_cited: 0.X, groundedness: ...}, overall_accuracy: 0.X, foundry_run_url: "https://..."}`.

- [ ] **Step 5: Open the Foundry portal URL** and confirm the run shows up with per-row scores.

- [ ] **Step 6: Capture the result**

```bash
cp data/.eval/store.sqlite docs/poc1-foundry-run-{date}.sqlite  # or just record the run_id
```

Update `docs/poc1-accuracy-baseline.json`:

```json
{
  "run_id": "<run_id>",
  "ts": "<iso>",
  "sample_size": 300,
  "overall_accuracy": <number>,
  "per_evaluator": { ... },
  "foundry_run_url": "https://...",
  "model": "gpt-4-1-judge"
}
```

- [ ] **Step 7: Commit the baseline**

```
git commit -m "eval: POC1 corpus run baseline — accuracy=<x>%"
```

---

## Task 4: Iterate if accuracy <95%

If the first run lands below 95%, follow [poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md):

- [ ] **Step 1: Identify the failure modes**

```bash
uv run python -c "
import json
rows = [json.loads(l) for l in open('data/.eval/preclassified-300.jsonl')]
mismatches = [r for r in rows if r['predicted_label'] != r['gold_label']]
print(f'{len(mismatches)}/300 mismatches')
for r in mismatches[:5]:
    print(r['claim_id'], r['gold_label'], '->', r['predicted_label'])
"
```

- [ ] **Step 2: Bucket the failures**

  - Wrong amber/green calls? → tighten the threshold prompt
  - Wrong red calls? → tune the classifier's red-flag list
  - Missing policy citations (low `policy_clause_cited`)? → tighten the "quote the literal text" prompt instruction

- [ ] **Step 3: Edit `api/server/skills/rag-classifier/SKILL.md`** with the targeted fix.

- [ ] **Step 4: Re-run pre-classify** for ONLY the mismatched claims (or all 300 if the change is structural).

- [ ] **Step 5: Re-run the batch evaluation.**

- [ ] **Step 6: Repeat until ≥95%** OR ≥2 iterations have run — at which point escalate to the user; further iteration is a research task, not a build task.

- [ ] **Step 7: Commit the prompt change separately**

```
git commit -m "feat(rag-classifier): tighten <X> for AC #4 corpus accuracy"
```

---

## Task 5: Update poc1-status.md with the final number

**Files:** `docs/poc1-status.md`

- [ ] **Step 1: Update AC #4 row** — flip the 🟡 to ✅ if ≥95%; otherwise update with the achieved number and a note on what's left.

- [ ] **Step 2: Update the "What landed" section** with the final corpus accuracy.

- [ ] **Step 3: Update SCOPE-DELTA.md AC list** to reflect the new state.

- [ ] **Step 4: Commit**

```
git commit -m "docs: POC1 AC #4 — corpus accuracy <X>% on 300 claims via Foundry"
```

---

## Acceptance criteria

- [ ] Azure Foundry project + judge-model deployment provisioned
- [ ] `foundry_client.is_configured()` returns True locally
- [ ] `data/.eval/preclassified-300.jsonl` exists with 300 rows
- [ ] `POST /api/accuracy/run {sample_size: 300}` succeeds (202 → completed in store)
- [ ] Foundry portal shows the run with per-row scores
- [ ] `docs/poc1-accuracy-baseline.json` captures the result
- [ ] `docs/poc1-status.md` and `docs/SCOPE-DELTA.md` updated to reflect the achieved accuracy
- [ ] If <95% on first pass, ≥1 prompt iteration attempted and documented

## Out of scope

- Re-architecting the Foundry pipeline (already shipped)
- Custom evaluator development (the 3 deterministic ones are sufficient)
- Online subscriber tuning (separate concern)

## Dependencies on other streams

- None. This is a fully independent stream.
