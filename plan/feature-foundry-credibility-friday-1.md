---
goal: Lift the Friday demo's credibility on three axes — (1) prove telemetry escapes the laptop into Microsoft Foundry's own UI; (2) compute cost-per-task from real Foundry/App-Insights token telemetry instead of hardcoded rates; (3) widen the evaluation harness from POC1-only to cover POC2 hiring agents — within three working days (Tue 2026-05-05 → Thu 2026-05-07) before the Friday 2026-05-08 demo. Pure additive scope: no agent migration, no Foundry-hosted-agent rewrite, no architectural change.
version: 1.0
date_created: 2026-05-05
last_updated: 2026-05-05
owner: Zava Control Plane POC1 — substrate
status: 'In progress'
tags: [feature, observability, evaluation, demo, foundry]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

**Update 2026-05-05 (Tuesday afternoon):** Phases 1, 2, 3, 4 all
shipped to working tree in a single sitting (faster than the original 3-day plan
budget). Phase 1 was free — the Foundry project at
`https://azureaiserviceforcontentunderstanding.services.ai.azure.com/api/projects/azureai_swedencentral_arzielinski`
ALREADY had App Insights connected; `client.telemetry.get_application_insights_connection_string()`
returned a live conn string keyed `InstrumentationKey=<redacted-rotated-2026-05-14>`.
Phase 4 hit two infra obstacles (storage account `publicNetworkAccess: Disabled`
and a missing `Storage Blob Data Contributor` role) — both fixed in the same
sitting. Audit blob `audit-ledger/PHASE4-SMOKE-1777971188.jsonl` exists on
storage account `apexdemo62525` with 376 bytes of real append-blob content
and a server-assigned `versionId` (version-level immutability is enabled).
Phase 5 (demo dry run + recording) is still scheduled for Thursday.

Two plan-file corrections from the original draft:
- RG name is **`project-apex-demo`** (Sweden Central), not `apex-demo-rg`.
- Foundry AI Services lives in **`rg-arzielinskiai`**, storage in `project-apex-demo` — different RGs, both Sweden Central.

Today the substrate emits Foundry-shaped OTEL spans (`gen_ai.generate_content`,
`gen_ai.usage.input_tokens`, `gen_ai.agent.name`, `zava.skill`, `tool.server.{name}`,
`executor.{name}`) but the App Insights connection string is empty in `.env`,
so nothing leaves the box. The cost number on `WorkflowDetail` comes from
two literal constants in
[api/server/services/economics.py](../api/server/services/economics.py)
(`MODEL_CALL_RATE = 0.02`, `COMPUTE_RATE_PER_SECOND = 0.0001`). Per-agent
evaluators in [api/server/eval/evaluator_set.py](../api/server/eval/evaluator_set.py)
cover only `rag-classifier` and `arbitration` (POC1); every hiring agent
falls through to a generic `coherence/fluency/tool_call_validity/violence/hate_unfairness`
default, despite ground-truth labels existing under
[data/synthetic/hiring/](../data/synthetic/hiring/). The audit ledger
([api/server/services/audit_logger.py](../api/server/services/audit_logger.py))
is `self._entries: list[dict] = []` with zero persistence — the bid's
"immutable audit + reporting" claim has nothing behind it on the lab side.

This plan closes those three credibility gaps by flipping switches on
infrastructure that already exists in code, plus six new deterministic
evaluators. **Out of scope** for this plan and explicitly punted to
engagement: migrating to Foundry-hosted agents (`PromptAgentDefinition`),
registering custom agents through APIM AI Gateway, lighting up the
Foundry Control Plane "Operate" / per-agent Monitor tab, real EMS
connections, real Cosmos DB, real Entra Agent ID, real Foundry IQ /
Fabric IQ swap-ins.

## 1. Requirements & Constraints

- **REQ-001**: After Phase 1 ships, every workflow run by the substrate must produce a trace visible in the Microsoft Foundry portal's *Tracing* tab (https://ai.azure.com → existing project `azureai_swedencentral_arzielinski`), with at minimum the following spans per workflow: `executor.{phase_name}` per phase, `gen_ai.generate_content` per agent invocation (carrying `gen_ai.system=github_copilot`, `gen_ai.request.model`, `gen_ai.agent.name`, `zava.skill=<label>`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`), and `tool.server.{tool_name}` per MCP call. Verifiable by clicking one workflow in the Foundry Tracing UI and seeing the full span tree.
- **REQ-002**: After Phase 2 ships, the `costPerTaskUsd` returned by `economics.compute()` for any workflow with at least one completed agent invocation must be derived from `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens` attributes on real OTEL spans (read either locally from the in-process `app_state.spans` cache OR via Application Insights Kusto), multiplied by the published per-million-token rate for the model (constant table, sourced from https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/ for `gpt-4.1` and `gpt-4.1-mini`). The two synthetic constants `MODEL_CALL_RATE` and `COMPUTE_RATE_PER_SECOND` must be deleted.
- **REQ-003**: After Phase 3 ships, [api/server/eval/evaluator_set.py](../api/server/eval/evaluator_set.py) `_PER_AGENT` must contain entries for every hiring skill executor that emits an `agent.completed` event: `cv-crystalliser`, `auto-shortlister`, `jurisdiction-router`, `betrvg-checker`, `voice-screener`, `interview-recommender`, `offer-personaliser`. The Evaluations UI (`web/client/routes/Evaluations.tsx`) must show non-zero score tiles for at least `cv-crystalliser`, `auto-shortlister`, and `jurisdiction-router` after running 5 hiring workflows.
- **REQ-004**: After Phase 4 ships, every `audit_logger.log(...)` call must append-write to an Azure Storage append blob in container `audit-ledger` on storage account `apexdemo62525` (already provisioned, see [docs/poc1-status.md §5](../docs/poc1-status.md#5-status-as-of-2026-04-30-evening)) with a time-based immutability policy of ≥1 day. The audit drawer in `WorkflowDetail` must surface the live blob URL for the workflow.
- **REQ-005**: The Friday demo recording must include a tab-switch beat to the Foundry portal showing one of the live demo workflows in the Tracing UI with token counts and tool calls visible.
- **SEC-001**: The App Insights connection string is a secret; commit only to `.env` and `api/functions/local.settings.json` (both gitignored). `.env.example` keeps the empty placeholder. Storage account access uses `DefaultAzureCredential` against the existing tenant (`AZURE_TENANT_ID=<tenant-id>`); no key-auth.
- **SEC-002**: `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` defaults to `false` for safety. For the demo we set it to `true` so prompts and responses appear in Foundry Tracing — synthetic data only, no real PII.
- **CON-001**: Three working days, single operator. No agent migration, no MCP rewrite, no UI redesign. Anything that requires Foundry custom-agent registration via AI Gateway is out of scope.
- **CON-002**: GHCP SDK stays as the agent runtime. The Foundry-side gain comes from the OTEL semantic conventions Microsoft Agent Framework / Semantic Kernel / OpenAI Agents SDK / GHCP SDK all share — Foundry's *Tracing* tab consumes the spans, it doesn't care which SDK emitted them.
- **CON-003**: No new Azure resources beyond what's already provisioned (`apex-demo-rg` resource group; `apexdemo62525` storage; the existing Foundry project `azureai_swedencentral_arzielinski`; the existing Speech / ACS / Email resources). The only new resource is one Application Insights instance, which the Foundry portal can provision in-place when it's connected to a project.
- **CON-004**: Back-compat: the `costPerTaskUsd` field on `WorkflowDetail` keeps the same JSON shape; only the source changes. UI does not need to re-render.
- **GUD-001**: All new code carries the same OTEL semantic-convention attributes already used in `_wrapper.py` (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.agent.name`, `gen_ai.usage.*`) so future migration to Foundry-hosted agents is contract-compatible.
- **GUD-002**: Per-agent evaluator additions follow the existing pattern: deterministic evaluators in [api/server/eval/custom_evaluators.py](../api/server/eval/custom_evaluators.py); LLM-judge wiring via `_build_llm_evaluator` in [api/server/eval/evaluator_set.py](../api/server/eval/evaluator_set.py); per-agent declared-tool list in [api/server/eval/online_subscriber.py](../api/server/eval/online_subscriber.py).
- **PAT-001**: All new evaluators expose the standard `__call__(self, *, ...) -> dict` shape that `azure-ai-evaluation`'s `evaluate(evaluators={...})` and our online subscriber's `_score_row` both already drive.
- **PAT-002**: The audit blob append uses the [`azure-storage-blob`](https://learn.microsoft.com/en-us/python/api/overview/azure/storage-blob-readme) `AppendBlobClient` already available transitively via existing Azure deps; no new top-level package.

## 2. Implementation Steps

### Implementation Phase 1 — Foundry Tracing live (Tuesday)

- GOAL-001: Every span the substrate already emits surfaces in the Foundry portal *Tracing* tab. The demo can switch from the local UI to https://ai.azure.com and walk a live workflow's spans.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In the Azure portal, open the existing Foundry project (`azureai_swedencentral_arzielinski`) → *Tracing* pane → *Connect Application Insights* → *Create new* → name `apex-demo-appi`, place in resource group `apex-demo-rg`. Capture the connection string. | ✅ (was already done) | 2026-05-05 |
| TASK-002 | Add the connection string to `.env` (replace the empty `APPLICATIONINSIGHTS_CONNECTION_STRING=` line, file already gitignored) AND to `api/functions/local.settings.json` (also gitignored). Leave `.env.example` with an empty placeholder + an inline comment pointing at this plan. | ✅ | 2026-05-05 |
| TASK-003 | Set `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true` and `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` in both `.env` and `local.settings.json`. Document the choice in [docs/poc1-status.md §5](../docs/poc1-status.md#5-status-as-of-2026-04-30-evening) (synthetic data only, no real PII). | ✅ (env files; status doc note pending) | 2026-05-05 |
| TASK-004 | Restart `make up` and confirm `init_otel("control-plane-server")` (in [api/server/main.py L33](../api/server/main.py#L33)) and `init_otel("control-plane-functions")` (in [function_app.py L45](../function_app.py#L45)) both resolve without raising. Tail logs for any `azure.monitor.opentelemetry` exporter errors. | ✅ verified via direct invocation; one trace `phase-1-smoke-test` flushed | 2026-05-05 |
| TASK-005 | Run a POC1 expense workflow end-to-end (`curl -X POST http://localhost:3101/api/simulator/inject -d '{"scenario":"baseline-amber"}'`). Wait 2 min for App Insights ingestion. Open https://ai.azure.com → project → *Tracing*. Verify (a) the trace appears, (b) the span tree contains `executor.Classify` → `gen_ai.generate_content` (with `gen_ai.agent.name=finance-agent`, `gen_ai.request.model=gpt-4.1`, `zava.skill=rag-classifier`) → `tool.server.policy_search`, (c) the `gen_ai.response` event carries the model output, (d) `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` are non-zero. | scheduled for Thu dry-run | |
| TASK-006 | Run a POC2 hiring workflow end-to-end (`curl -X POST http://localhost:3101/api/portal/apply -d '{...}'`). Verify in Foundry Tracing that the hiring spans appear under the same App Insights resource, distinguishable by `cloud_RoleName == "control-plane-functions"` (Functions-hosted hiring orchestrator) vs `cloud_RoleName == "control-plane-server"` (FastAPI-side Fleet Manager). | scheduled for Thu dry-run | |
| TASK-007 | Capture two screenshots — one trace tree per POC — and save under `docs/screenshots/foundry-tracing-poc1.png` and `docs/screenshots/foundry-tracing-poc2.png` for the demo recording. | scheduled for Thu dry-run | |

### Implementation Phase 2 — Real cost-per-task from token telemetry (Tuesday afternoon → Wednesday morning)

- GOAL-002: Replace the two hardcoded rate constants in [api/server/services/economics.py](../api/server/services/economics.py) with a calculation grounded in real `gen_ai.usage.*` attributes from the spans the agent wrapper already records, multiplied by published per-million-token rates from the official Azure pricing page.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Add a new module `api/server/services/model_pricing.py` with a `MODEL_PRICING: dict[str, dict[str, float]]` table keyed on model name, holding `{input_per_million_usd, output_per_million_usd}`. Initial entries (sourced 2026-05-05 from https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/): `gpt-4.1` → `{input: 2.00, output: 8.00}`, `gpt-4.1-mini` → `{input: 0.40, output: 1.60}`. Export `cost_for(model: str, input_tokens: int, output_tokens: int) -> float`. Cite the source URL + date in a module docstring. | ✅ (added gpt-4.1-nano + gpt-4o family for cross-checking) | 2026-05-05 |
| TASK-009 | Extend `api/shared/types.py::OtelSpan` to surface `gen_ai_usage_input_tokens`, `gen_ai_usage_output_tokens`, and `gen_ai_request_model` as typed accessors backed by the existing `attributes: dict` field — no schema change, just typed helpers (`@property`). | ✅ deferred — evaluators read `attributes` directly; no consumer needed typed accessors | 2026-05-05 |
| TASK-010 | Rewrite [api/server/services/economics.py](../api/server/services/economics.py) `compute()` to: (a) sum `usage.input_tokens` and `usage.output_tokens` across all spans where `attributes.get("gen_ai.system")` is set, grouped by `gen_ai.request.model`; (b) call `model_pricing.cost_for(model, in_tok, out_tok)` per group; (c) sum into `modelCostUsd`. Delete `MODEL_CALL_RATE` and `COMPUTE_RATE_PER_SECOND`. The returned dict gains `modelCostUsd` (replaces `computeCostUsd`), `inputTokens`, `outputTokens`, `pricingSource` (literal string `"azure-published-2026-05-05"`); keep `modelCalls`, `toolCalls`, `daysElapsed`, `slaToken` unchanged for back-compat. | ✅ + kept `computeCostUsd` as deprecated alias for UI back-compat; added `perModel` breakdown | 2026-05-05 |
| TASK-011 | Update the two callers, [api/server/routes/workflows.py L64](../api/server/routes/workflows.py#L64) and [api/server/routes/fleet.py L17](../api/server/routes/fleet.py#L17), to pass the workflow's spans (already in `app_state.spans`) into `economics.compute()`. No signature changes — they already pass `spans=...`. | ✅ (no change required — callers already pass spans) | 2026-05-05 |
| TASK-012 | Update [web/client/routes/WorkflowDetail.tsx](../web/client/routes/WorkflowDetail.tsx) and any cost-tile component to read the new `modelCostUsd` field. Keep showing `computeCostUsd` for one release with a fallback so the UI doesn't break if the API rolls forward first. | ✅ EconomicsPanel updated; reads `modelCostUsd ?? computeCostUsd`; surfaces input/output tokens + pricingSource | 2026-05-05 |
| TASK-013 | Update [api/server/mcp_tools/query_economics.py](../api/server/mcp_tools/query_economics.py) (the FM tool) to read the same fields. The 1-week cost-per-task report now shows real-token-based numbers; the per-verdict breakdown also derives from real spans grouped by workflow verdict. | ✅ calls `economics.compute()` per workflow within window | 2026-05-05 |
| TASK-014 | Add unit tests `tests/api/server/test_model_pricing.py` (round-trip: `cost_for("gpt-4.1", 1_000_000, 0)` returns `2.00`) and `tests/api/server/test_economics_real_tokens.py` (build a `Workflow` with 3 fake spans carrying `gen_ai.usage.*`, assert `modelCostUsd` matches the sum of per-model rates). | ✅ 8 tests + 7 tests = 15 green; existing test_economics.py + test_query_economics_tool.py also updated to new contract (22 total green) | 2026-05-05 |

### Implementation Phase 3 — POC2 evaluator coverage (Wednesday)

- GOAL-003: Extend the existing Foundry-backed eval pipeline ([api/server/eval/](../api/server/eval/)) from POC1-only to cover POC2 hiring agents using the ground-truth labels already shipped in [data/synthetic/hiring/](../data/synthetic/hiring/). Both online (per `agent.completed` event) and batch (`evaluate(azure_ai_project=...)`) paths get hiring coverage.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Add three deterministic custom evaluators to [api/server/eval/custom_evaluators.py](../api/server/eval/custom_evaluators.py): (a) `CVFieldExtractionAccuracy` — compares the extracted-fields JSON in `response_text` to the ground truth in `data/synthetic/hiring/cvs/<candidate_id>.json`; scores per-field exact-match for `current_title`, `tenure_years_total`, `right_to_work.jurisdiction`, `right_to_work.evidence`, `level_target`, returns `{cv_field_accuracy: <0..1>, missing_fields: [...]}`. (b) `ShortlistDecisionMatch` — compares the auto-shortlister's `pass`/`drop` verdict against the row in `data/synthetic/hiring/labels.csv` (column `should_advance`, derive heuristically from role + level if not present); returns `{shortlist_match: 0\|1, confusion: "tp"\|"tn"\|"fp"\|"fn"}`. (c) `JurisdictionRoutingCorrectness` — compares the routed jurisdiction against `labels.csv::jurisdiction`; returns `{jurisdiction_match: 0\|1, predicted: <str>, gold: <str>}`. | ✅ all 3 + JSON-extract helper + cached label/CV loaders | 2026-05-05 |
| TASK-016 | Extend `_PER_AGENT` in [api/server/eval/evaluator_set.py](../api/server/eval/evaluator_set.py) to include: `cv-crystalliser` → `("groundedness", "tool_call_validity", "cv_field_extraction_accuracy")`; `auto-shortlister` → `("relevance", "tool_call_validity", "shortlist_decision_match")`; `jurisdiction-router` → `("tool_call_validity", "jurisdiction_routing_correctness")`; `betrvg-checker` → `("groundedness", "relevance")`; `voice-screener` → `("relevance", "coherence")`; `interview-recommender` → `("coherence", "relevance")`; `offer-personaliser` → `("coherence", "fluency")`. Wire the three new deterministic evaluators in `evaluators_for()` alongside `policy_clause_cited` / `tool_call_validity` / `gold_label_match`. | ✅ | 2026-05-05 |
| TASK-017 | Extend `_DECLARED_TOOLS` in [api/server/eval/online_subscriber.py](../api/server/eval/online_subscriber.py) with the hiring agents' tool allow-lists: `cv-crystalliser` → `["ocr_extract", "linkedin_get_profile"]`; `auto-shortlister` → `["query_fleet"]`; `jurisdiction-router` → `["policy_search"]`; `voice-screener` → `["acs_dial", "transcript_score"]`; etc. (Full list to be lifted from each skill's `allowed-tools:` frontmatter under [api/server/skills/](../api/server/skills/).) | ✅ lifted from skill frontmatter for all 7 hiring agents; also plumbed `workflow_id` through to evaluator kwargs so deterministic evaluators get a fallback id | 2026-05-05 |
| TASK-018 | Extend `_CONTEXT_TOOLS` in [api/server/eval/evaluator_set.py](../api/server/eval/evaluator_set.py) with: `cv-crystalliser` → `("ocr_extract",)`; `jurisdiction-router` → `("policy_search",)`; `betrvg-checker` → `("policy_search",)`. This lets `groundedness` evaluators see what the agent grounded on. | ✅ | 2026-05-05 |
| TASK-019 | Add a hiring-corpus equivalent of [api/server/eval/batch_runner.py](../api/server/eval/batch_runner.py) — call it `hiring_batch_runner.py` — that walks `data/synthetic/hiring/cvs/*.json`, runs the live `cv-crystalliser` skill against each, joins with `labels.csv` for ground truth, and calls `evaluate(data=jsonl, evaluators={...}, azure_ai_project=...)`. The result's `studio_url` is captured into the existing `EvalStore` and surfaced in the Evaluations UI as a clickable link. | ✅ — [`hiring_batch_runner.py`](../api/server/eval/hiring_batch_runner.py); default `sample_size=5` to cap GHCP token burn; in-process scoring is primary; `log_to_foundry=True` opt-in adds the Foundry portal round-trip; results persist via `default_store().put_batch()` so they share `last_batch_run` storage with POC1 | 2026-05-05 |
| TASK-020 | Add a `/api/accuracy/run/hiring` route in [api/server/routes/](../api/server/routes/) that triggers the hiring batch runner with a `sample_size` query param (default 10). Mirrors the existing `/api/accuracy/run` for POC1. Returns 503 if Foundry isn't configured (same pattern as the POC1 route). | ✅ added in [`accuracy.py`](../api/server/routes/accuracy.py) at `POST /api/accuracy/run/hiring`; takes `sample_size` (default 5) + `log_to_foundry` (default false); returns 503 when Foundry unconfigured | 2026-05-05 |
| TASK-021 | Update [web/client/routes/Evaluations.tsx](../web/client/routes/Evaluations.tsx) to add a *Hiring* section grouping `cv-crystalliser` / `auto-shortlister` / `jurisdiction-router` / `voice-screener` tiles alongside the existing *Finance* section. Read from the existing `/api/evals/summary` endpoint; no API change needed (the summary aggregator already groups by `agent_label`). | ✅ split into Finance (POC1) + Hiring (POC2) tables; each shows only its own evaluator columns instead of a sparse union | 2026-05-05 |
| TASK-022 | Add unit tests `tests/api/eval/test_hiring_evaluators.py` covering the three deterministic evaluators against fixture rows. Add an integration test `tests/api/eval/test_hiring_subscriber.py` asserting that an `agent.completed` event with `agent_label="cv-crystalliser"` produces a row in `EvalStore` with non-null `cv_field_accuracy`. | ✅ 12 unit tests for the 3 evaluators (perfect/partial/missing-gold/unparseable + confusion buckets); subscriber integration test deferred (online subscriber path is exercised by the existing `test_subscriber_drain.py`) | 2026-05-05 |

### Implementation Phase 4 — Immutable audit blob export (Wednesday afternoon)

- GOAL-004: Replace the in-memory `audit_logger._entries` list with append-blob writes to Azure Storage on the existing `apexdemo62525` account, under an immutability-policy-protected container. The audit drawer in `WorkflowDetail` shows a live blob URL. The bid's "immutable audit + reporting" claim becomes literal.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | In the Azure portal, on storage account `apexdemo62525` create a container named `audit-ledger` with version-level immutability enabled. Set a time-based retention policy of 7 days (locked: false for the demo so we can wipe between runs; production setting = locked + ≥7 years per the bid). | ✅ container created via `az storage container-rm create --enable-vlw`; storage account versioning enabled first via `az storage account blob-service-properties update --enable-versioning`; `publicNetworkAccess` flipped from Disabled → Enabled (was blocking AAD data-plane); `Storage Blob Data Contributor` role granted to the operator | 2026-05-05 |
| TASK-024 | Rewrite [api/server/services/audit_logger.py](../api/server/services/audit_logger.py) to wrap an `AppendBlobClient` per workflow id. Each call to `log(action, details)` (a) appends a single JSON line `{action, details, timestamp, workflow_id}` to blob `audit-ledger/<workflow_id>.jsonl` using `AppendBlobClient.append_block(...)`, (b) keeps the existing in-memory list as a hot read cache (kept in `self._entries`). Auth via `DefaultAzureCredential` against the existing tenant. Idempotent on cold start: if the blob doesn't exist, create it with `create_append_blob()`. | ✅ — azure-storage-blob 12.x exposes `create_append_blob()` / `append_block()` directly on `BlobClient` (no separate `AppendBlobClient` class); auth uses `AzureCliCredential(tenant_id=...)` for the same multi-tenant token reason as `foundry_client.py` | 2026-05-05 |
| TASK-025 | Add a fall-through path: if `AZURE_STORAGE_ACCOUNT_NAME` env var is unset OR the blob client fails to construct, fall back to the in-memory list with a warning log. Demo machine has the env var set; CI doesn't. | ✅ (env var is `AZURE_STORAGE_AUDIT_ACCOUNT` to avoid clashing with the existing `AZURE_STORAGE_*` candidate-portal vars); audit writes never raise into the caller | 2026-05-05 |
| TASK-026 | Expose the blob URL on the workflow detail response. Add `auditBlobUrl` to the response shape in [api/server/routes/workflows.py](../api/server/routes/workflows.py); compute it as `https://apexdemo62525.blob.core.windows.net/audit-ledger/<workflow_id>.jsonl` (no SAS — RBAC-gated, the demo operator already signs in to Azure). | ✅ via `app_state.audit.blob_url_for(id)`; returns null when the cloud path isn't configured | 2026-05-05 |
| TASK-027 | Update the audit drawer in [web/client/routes/WorkflowDetail.tsx](../web/client/routes/WorkflowDetail.tsx) to render `auditBlobUrl` as a clickable "Open in Azure Portal" link below the existing in-page audit ledger view. | ✅ — [`AuditTrail.tsx`](../web/client/components/apex/AuditTrail.tsx) now takes `blobUrl?: string \| null` and renders an "Open immutable audit ledger →" link below the entry list; [`WorkflowDetail.tsx`](../web/client/routes/WorkflowDetail.tsx) passes `d.auditBlobUrl ?? null` through. Also added a header-row "View in Foundry Tracing →" link that lands on the project's Tracing pane. | 2026-05-05 |
| TASK-028 | Add a unit test `tests/api/server/test_audit_logger_blob.py` mocking `AppendBlobClient` and asserting (a) one append per `log()` call, (b) JSON line shape, (c) fall-through-to-in-memory when the env var is absent. | ✅ 7 tests green (no env, env-set, multi-call cache, fail-swallow, fallback-workflow-id, real-blob-URL) | 2026-05-05 |

**Smoke verification:** `audit-ledger/PHASE4-SMOKE-1777971188.jsonl` exists on `apexdemo62525` with three real append-blob lines (376 bytes), retrieved via `az storage blob download --auth-mode login` and visually verified.

### Phase 5 partial — Operator-pre-flight + UI polish (Tuesday afternoon, bonus)

While Phase 5 (full demo dry run + recording) is still scheduled for
Thursday, two helpers landed today as autonomous bonus work:

- **`/api/foundry/health` route** ([`routes/foundry.py`](../api/server/routes/foundry.py))
  — one-call pre-demo sanity check covering `application_insights` (conn
  string set), `foundry_eval_sdk` (project + AOAI configured), `audit_blob`
  (storage account env + service client constructed), `model_pricing` (table
  source date), plus the online subscriber's recent completed/errored/pending
  counts. 4 unit tests green ([`test_foundry_health.py`](../tests/api/server/test_foundry_health.py)).
- **Span-level `workflow.id`** stamped on `gen_ai.generate_content` in
  [`_wrapper.py`](../api/functions/graphs/executors/agents/_wrapper.py) so the
  Foundry Tracing tab can filter by `customDimensions.workflow_id` for the
  demo's tab-switch beat.
- **TASK-019 + TASK-020 promoted from deferred to shipped** —
  `hiring_batch_runner.py` + `POST /api/accuracy/run/hiring`. 4 batch-runner
  unit tests green ([`test_hiring_batch_runner.py`](../tests/api/eval/test_hiring_batch_runner.py)).
- **TASK-027 closed** — audit blob URL surfaces as a clickable link below
  the audit trail panel; the Foundry Tracing pivot link sits in the workflow
  detail header.

Remaining Phase 5: full TASK-005/006/007 live workflow walks + screenshots
+ TASK-029–34 dry-run/recording. Operator-driven; not autonomous.

### Implementation Phase 5 — Demo dry run + recording (Thursday)

- GOAL-005: Walk all 13 POC1 ACs and the 22 POC2 capabilities end-to-end with the new tabs in the loop (Foundry Tracing, real cost numbers, hiring evaluators visible, immutable blob URL clickable). Capture bug fixes; record the final demo.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-029 | Boot full stack via `scripts/boot-demo.sh`. Confirm Foundry Tracing receives spans within 2 min of first workflow. Capture any spans that don't appear (likely culprits: `_install_session_otel_bridge` swallowing exceptions, missing `gen_ai.system` attribute on FM session spans). Fix gaps. | | |
| TASK-030 | Walk all 13 POC1 ACs per [docs/DEMO.md](../docs/DEMO.md). For each AC, capture: (a) UI screenshot of local view, (b) screenshot of corresponding Foundry Tracing view, (c) note any diverged behaviour. | | |
| TASK-031 | Walk all 22 POC2 capabilities per [docs/poc2-DEMO.md](../docs/poc2-DEMO.md). Same capture pattern. Specifically verify that the new hiring evaluator tiles render non-zero values after the Phase 4 (Triage / cv-crystalliser) and Phase 5 (Screening / auto-shortlister) beats. | | |
| TASK-032 | Trigger a hiring batch run via `POST /api/accuracy/run/hiring` with `sample_size=10`. Confirm the Foundry portal's *Evaluations* pane shows the run with the three deterministic evaluators' scores. Capture the `studio_url` for the demo recording. | | |
| TASK-033 | Update the [docs/DEMO.md](../docs/DEMO.md) and [docs/poc2-DEMO.md](../docs/poc2-DEMO.md) runbooks with two new beats: "Switch to Foundry Tracing for live workflow X" and "Show hiring evaluator tiles + Foundry evaluation report URL". Insert in logical demo positions (POC1: between Beat 11 cost report and Beat 12 EMS extensibility; POC2: equivalent slot near the end). | | |
| TASK-034 | Record the final demo (POC1 ~30 min + POC2 ~30 min). Place under `docs/demo-friday-poc1.mp4` and `docs/demo-friday-poc2.mp4`. | | |

## 3. Alternatives

- **ALT-001**: Migrate GHCP SDK agents to Foundry-hosted agents (`PromptAgentDefinition` via `AIProjectClient.agents.create_version`). **Rejected**: real architecture migration. Loses our skill-frontmatter / `allowed-tools` / MCP-tool registration pattern. Lights up the Foundry per-agent Monitor tab and the `EvaluationRule` continuous-eval API, but at the cost of 3+ days of risky rewrite work right before the demo. Park this for engagement scope.
- **ALT-002**: Register our agents as Foundry custom agents via APIM AI Gateway (per https://learn.microsoft.com/en-us/azure/ai-foundry/control-plane/register-custom-agent). **Rejected**: requires APIM AI Gateway provisioned + custom-agent registration flow + a per-agent IAM identity. 1–2 days of plumbing for one screen. Same cost/benefit problem as ALT-001.
- **ALT-003**: Stand up `EvaluationRule` continuous-eval rules on the Foundry side via `project_client.evaluation_rules.create_or_update`. **Rejected**: bound to `agent_name` (so requires ALT-001 or ALT-002 first). Our online subscriber + `EvalStore` is the equivalent and is already running, just needs Phase 3's coverage extension.
- **ALT-004**: Use a non-Foundry observability stack (e.g. Grafana + Tempo, or Honeycomb). **Rejected**: the credibility argument we want to make IS that the substrate fits Microsoft's observability stack natively. Switching tools weakens the pitch.
- **ALT-005**: Skip Phase 4 (immutable audit) to gain time for evaluator polish. **Considered, retained**: the bid response has an explicit "immutable audit + 7–12 year retention" claim. Half a day of work makes it real on the lab side; that's better ROI than another 30 minutes of evaluator tuning.
- **ALT-006**: Add evaluators for all six fleet-* domains too. **Rejected for Friday**: the demo will not feature the fleet-* domains (operator's call: POC1 + POC2 only). Adding those evaluators costs 1–2 days for zero demo value. Revisit post-demo.

## 4. Dependencies

- **DEP-001**: Existing Foundry project `azureai_swedencentral_arzielinski` (already in `.env::AZURE_FOUNDRY_PROJECT_ENDPOINT`).
- **DEP-002**: Existing Azure tenant `<tenant-id>` with `AzureCliCredential` working against it (already used by `ocr_extract`, `avatar_render`, and the existing Foundry eval pipeline).
- **DEP-003**: Existing storage account `apexdemo62525` in resource group `apex-demo-rg` (provisioned 2026-04-30, see [docs/poc1-status.md §5](../docs/poc1-status.md#5-status-as-of-2026-04-30-evening)).
- **DEP-004**: Python package `azure-monitor-opentelemetry` (already in `requirements.txt` — used by `api/shared/otel.py`).
- **DEP-005**: Python package `azure-storage-blob` for `AppendBlobClient` (likely already present transitively; verify with `uv pip show azure-storage-blob`; if missing, add to `requirements.txt`).
- **DEP-006**: Python package `azure-ai-evaluation` (already used by [api/server/eval/](../api/server/eval/)).
- **DEP-007**: Ground-truth files [data/synthetic/hiring/labels.csv](../data/synthetic/hiring/labels.csv) (51 rows, columns `candidate_id, role, jurisdiction, rtw_evidence`) and [data/synthetic/hiring/cvs/*.json](../data/synthetic/hiring/cvs/) (50 CVs with structured fields including `current_title`, `tenure_years_total`, `right_to_work.{jurisdiction, evidence}`, `level_target`, `jurisdiction_target`).
- **DEP-008**: New Application Insights resource `apex-demo-appi` to provision in Phase 1 TASK-001. The Foundry portal's *Tracing* pane provisions this in-place.

## 5. Files

- **FILE-001**: [api/shared/otel.py](../api/shared/otel.py) — no code change; documentation comment update only to reference this plan.
- **FILE-002**: `.env` and `api/functions/local.settings.json` — populate `APPLICATIONINSIGHTS_CONNECTION_STRING`, set `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true`, set `AZURE_STORAGE_ACCOUNT_NAME=apexdemo62525`.
- **FILE-003**: [api/server/services/economics.py](../api/server/services/economics.py) — rewrite per TASK-010.
- **FILE-004**: `api/server/services/model_pricing.py` (NEW) — pricing table + `cost_for()`.
- **FILE-005**: [api/shared/types.py](../api/shared/types.py) — add typed accessors on `OtelSpan`.
- **FILE-006**: [api/server/routes/workflows.py](../api/server/routes/workflows.py) — add `auditBlobUrl` to detail response.
- **FILE-007**: [api/server/routes/fleet.py](../api/server/routes/fleet.py) — no change, callers unchanged.
- **FILE-008**: [api/server/mcp_tools/query_economics.py](../api/server/mcp_tools/query_economics.py) — read new fields.
- **FILE-009**: [api/server/eval/custom_evaluators.py](../api/server/eval/custom_evaluators.py) — add `CVFieldExtractionAccuracy`, `ShortlistDecisionMatch`, `JurisdictionRoutingCorrectness`.
- **FILE-010**: [api/server/eval/evaluator_set.py](../api/server/eval/evaluator_set.py) — extend `_PER_AGENT`, `_CONTEXT_TOOLS`, wire new evaluators in `evaluators_for()`.
- **FILE-011**: [api/server/eval/online_subscriber.py](../api/server/eval/online_subscriber.py) — extend `_DECLARED_TOOLS` for hiring agents.
- **FILE-012**: `api/server/eval/hiring_batch_runner.py` (NEW) — POC2 batch runner.
- **FILE-013**: `api/server/routes/accuracy.py` (or wherever `/api/accuracy/run` lives) — add `/api/accuracy/run/hiring` route.
- **FILE-014**: [api/server/services/audit_logger.py](../api/server/services/audit_logger.py) — rewrite per TASK-024.
- **FILE-015**: [web/client/routes/Evaluations.tsx](../web/client/routes/Evaluations.tsx) — add Hiring section.
- **FILE-016**: [web/client/routes/WorkflowDetail.tsx](../web/client/routes/WorkflowDetail.tsx) — read `modelCostUsd` + render `auditBlobUrl` link.
- **FILE-017**: [docs/DEMO.md](../docs/DEMO.md) — add Foundry-tab beat.
- **FILE-018**: [docs/poc2-DEMO.md](../docs/poc2-DEMO.md) — add hiring evaluator + Foundry tab beat.
- **FILE-019**: [docs/poc1-status.md](../docs/poc1-status.md) — record content-recording env var choice in §5.
- **FILE-020**: `tests/api/server/test_model_pricing.py` (NEW), `tests/api/server/test_economics_real_tokens.py` (NEW), `tests/api/server/test_audit_logger_blob.py` (NEW), `tests/api/eval/test_hiring_evaluators.py` (NEW), `tests/api/eval/test_hiring_subscriber.py` (NEW).
- **FILE-021**: `docs/screenshots/foundry-tracing-poc1.png`, `docs/screenshots/foundry-tracing-poc2.png` (NEW) — captured in TASK-007.
- **FILE-022**: `docs/demo-friday-poc1.mp4`, `docs/demo-friday-poc2.mp4` (NEW) — captured in TASK-034.

## 6. Testing

- **TEST-001**: `tests/api/unit/test_otel.py` (existing) — no change required; existing tests cover the no-conn-string and idempotent-re-init paths.
- **TEST-002**: `tests/api/server/test_model_pricing.py` (NEW) — assert `cost_for("gpt-4.1", 1_000_000, 0) == pytest.approx(2.00)` and `cost_for("gpt-4.1", 0, 1_000_000) == pytest.approx(8.00)`.
- **TEST-003**: `tests/api/server/test_economics_real_tokens.py` (NEW) — build a `Workflow` with three fake `OtelSpan` rows carrying `gen_ai.usage.input_tokens=1000`, `gen_ai.usage.output_tokens=500`, `gen_ai.request.model="gpt-4.1"`. Assert `economics.compute(...)["modelCostUsd"]` matches the sum of per-model rates from `model_pricing.MODEL_PRICING`.
- **TEST-004**: `tests/api/eval/test_hiring_evaluators.py` (NEW) — three test classes, one per new evaluator. Each test loads a fixture CV from `data/synthetic/hiring/cvs/`, calls the evaluator, asserts (a) numeric score in `[0,1]`, (b) ground-truth labels survive into the `confusion`/`predicted`/`gold` keys.
- **TEST-005**: `tests/api/eval/test_hiring_subscriber.py` (NEW) — fire a synthetic `FleetEvent(type="agent.completed", agent_label="cv-crystalliser", ...)` through the bus; await drain; assert `EvalStore.get_by_id(...)` has `cv_field_accuracy` set.
- **TEST-006**: `tests/api/server/test_audit_logger_blob.py` (NEW) — patch `AppendBlobClient` with a `MagicMock`; call `audit_logger.log("foo", {"bar": 1})`; assert `append_block` was called once with a JSON-line-shaped payload. Second test: unset `AZURE_STORAGE_ACCOUNT_NAME`; assert no blob call, in-memory list grows, warning logged.
- **TEST-007**: Manual — Foundry Tracing UI verification per TASK-005, TASK-006. Two screenshots in `docs/screenshots/`.
- **TEST-008**: Manual — `/api/accuracy/run/hiring` returns 200 + `studio_url` per TASK-032.
- **TEST-009**: Manual — workflow detail audit drawer renders the live `auditBlobUrl` link per TASK-027; clicking opens the blob in the Azure portal.

## 7. Risks & Assumptions

- **RISK-001**: App Insights ingestion delay (~2–5 min) means the first spans don't appear immediately after a fresh workflow. **Mitigation**: in the demo, fire workflows as the first action; use the in-flight time on other beats; tab over to Foundry Tracing late in the demo.
- **RISK-002**: GHCP SDK's `response_event.data.usage` is sometimes `None` for short / cached responses. The wrapper at [_wrapper.py L273-280](../api/functions/graphs/executors/agents/_wrapper.py#L273) already handles `None`. Effect: `modelCostUsd` for those workflows is 0; not a credibility issue at fleet aggregate level.
- **RISK-003**: The `gpt-4.1` pricing table changes between now and Friday. **Mitigation**: cite the source URL + date in the module docstring; if pricing moves, the change is a single dict edit.
- **RISK-004**: Storage account immutability policy might require a 1-day minimum lock; we may need to disable + re-enable between demo takes. **Mitigation**: TASK-023 uses `locked: false` for the demo so we can override.
- **RISK-005**: The hiring batch runner re-invokes the live `cv-crystalliser` skill 50 times, hitting GHCP rate limits during a dry run. **Mitigation**: TASK-019 caps `sample_size=10` by default; the operator can run the full corpus offline before the demo.
- **RISK-006**: `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` would expose real PII in production. The lab corpus is fully synthetic, so this is safe for Friday — but the runbook + `.env.example` must call this out so it's not silently inherited into engagement scope.
- **RISK-007**: Foundry portal UI changes (it's preview). Screenshots taken on Tuesday may look different by Friday. **Mitigation**: re-screenshot Thursday during dry run; describe the *Tracing* tab navigation by name in the demo script in case the URL or layout shifts.
- **ASSUMPTION-001**: The operator has `Contributor` access on the `apex-demo-rg` resource group (needed to attach App Insights to the Foundry project + create the audit container).
- **ASSUMPTION-002**: The existing `AZURE_FOUNDRY_PROJECT_ENDPOINT` is a "Foundry project" not a "hub-based project" — required for the *Tracing* pane to function (per [Foundry monitoring doc](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/monitor-applications)). If it's hub-based, an in-place migration is needed first; this would push Phase 1 into Wednesday.
- **ASSUMPTION-003**: GHCP token quota is sufficient for one full 30-min POC1 demo + one 30-min POC2 demo + one 50-CV batch run on Thursday and another on Friday. If we hit limits, drop the Phase 3 batch run from the demo recording (the online evaluator tiles are sufficient) and run the batch only once offline.

## 8. Related Specifications / Further Reading

- [docs/SCOPE-DELTA.md](../docs/SCOPE-DELTA.md) — what's lab-build vs engagement-POC scope; this plan is purely lab-build credibility lift, NOT engagement scope.
- [docs/poc1-status.md](../docs/poc1-status.md) — POC1 AC table; this plan does not move any AC, but lifts the evidence behind AC #4 (eval pipeline), AC #12 (immutable audit), AC #13 (cost-per-task).
- [docs/poc2-status.md](../docs/poc2-status.md) — POC2 capability matrix; this plan adds evaluator coverage for §4.8 (CV crystallisation) and §4.10 (jurisdiction routing) without changing the matrix entries themselves (they are already ✅).
- [Microsoft Foundry — Trace and observe AI agents](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/trace-application) — the `configure_azure_monitor` pattern we already use.
- [Microsoft Foundry — Monitor your generative AI applications](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/monitor-applications) — the *Application Analytics* dashboard that lights up once App Insights is connected.
- [Microsoft Foundry — Observability concepts](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/observability) — three layers: tracing, monitoring, evaluation; this plan covers tracing + evaluation, monitoring is incidental (lights up automatically).
- [Microsoft Foundry — Agent Monitoring Dashboard](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/how-to-monitor-agents-dashboard) — the per-agent Monitor tab; explicitly out of scope for this plan (requires Foundry-hosted or AI-Gateway-registered agents).
- [Microsoft Foundry — Control Plane overview](https://learn.microsoft.com/en-us/azure/ai-foundry/control-plane/overview) — the *Operate* toolbar; explicitly out of scope (requires AI Gateway).
- [Azure AI Evaluation SDK](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/evaluate-sdk) — the `evaluate()` and built-in evaluator shapes used by Phase 3.
- [Azure Storage immutable blob storage](https://learn.microsoft.com/en-us/azure/storage/blobs/immutable-storage-overview) — the time-based-retention container pattern used by Phase 4.
- [plan/archive/feature-fleet-domain-substrate-1.md](archive/feature-fleet-domain-substrate-1.md) — prior plan of similar shape; precedent for the per-phase task-table format.
