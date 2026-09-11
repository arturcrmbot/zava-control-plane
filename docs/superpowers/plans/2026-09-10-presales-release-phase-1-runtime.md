# Presales Runtime Contracts Implementation Plan

> **For agentic workers:** Use `executing-plans` after implementation approval. Follow the [master plan](2026-09-10-presales-release-readiness.md). Work in test-first increments; checkpoints do not authorise git commits.

**Goal:** Make the single-replica reference retain operational identity and pending decisions across restarts, and run the required supervisor with the selected provider.

**Architecture:** Preserve the `StateStore` API and current provider boundary. Add a versioned operational repository using atomic local files or conditional Azure Blob writes. Restore state before attaching producers; treat graph state as a reconstructible projection. Keep storage failures visible.

**Tech Stack:** Python, existing Pydantic models, `azure-storage-blob`, `azure-identity`, pytest and existing runtime providers.

**Status:** Superseded by [master plan v2](2026-09-10-presales-release-readiness.md). Reference only; do not execute this phase or its proposed persistence architecture as a requirement.

---

## Task 1.1: Define the operational persistence contract

**Files**

- Create: `api/server/services/workflow_repository.py`
- Modify: `api/server/services/state_store.py`
- Modify: `api/server/state.py`
- Create: `tests/api/server/services/test_workflow_repository.py`
- Modify: `tests/api/server/services/test_state_store.py`
- Modify: `.env.example`

Do not reuse the CV `BlobStore.put()` method for operational state: it unconditionally overwrites and its container setup suppresses failures.

- [ ] Add repository tests for round-trip, duplicate receipt, stale revision, malformed schema, wrong pack fingerprint and storage failure. The required pure contract is:

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class StoredWorkflow:
    workflow_id: str
    revision: str
    payload: bytes

class WorkflowRepository(Protocol):
    def load_all(self) -> list[StoredWorkflow]: ...
    def save(
        self, workflow_id: str, payload: bytes, *,
        expected_revision: str | None,
    ) -> StoredWorkflow: ...
```

`expected_revision=None` means create-only, not overwrite. `save` raises a dedicated conflict exception for an existing/stale revision. Azure maps this to conditional writes; local storage uses one process lock plus write/fsync/atomic replace.

- [ ] Implement and version the JSON aggregate. Schema version `1` contains the workflow replay patch, phases, exceptions including resolution state, spans/MCP evidence, parent/child IDs, original governance-decision evidence and an operation-receipt map. Use the existing model serializers; preserve aliases and `_agentOutputRecordedAt`. Do not replace denied decisions with reconstructed `allowed=True` records.
- [ ] Configure `ZAVA_STATE_BACKEND=memory|file|azure_blob`. `memory` remains the offline-test/default compatibility mode; the private-live deployment rejects it. File mode stores aggregates beneath `active_runtime().data_dir / "workflows"`. Blob mode uses a private `zava-runtime-state` container in the already selected storage account, partitioned by vertical and schema version.
- [ ] Add create-only and ETag-match writes. Use a finite renewable per-vertical writer lease for Azure live startup, renewed before expiry. Loss of lease stops new work and makes readiness false. A second writer cannot become live. Replay acquires no writer lease.
- [ ] Keep blob creation/provisioning outside request handling. Use managed identity in Azure and the existing Azurite connection mechanism locally. Never swallow permission/network/schema errors or silently fall back to memory.
- [ ] Add `make test-presales-runtime` using the existing `HARNESS_PYTEST` environment and the new repository/state tests. Run it red before implementation and green afterwards.

**Acceptance:** reopening the repository reconstructs exactly the accepted aggregate; a stale write fails; failures do not publish a successful checkpoint. The implementation does not introduce a new database service.

## Task 1.2: Wire acknowledgement, restoration and idempotency

**Files**

- Modify: `api/server/services/state_store.py`
- Modify: `api/server/services/workflow_event_ingestor.py`
- Modify: `api/server/routes/exceptions.py`
- Modify: `api/server/routes/internal_durable_event.py`
- Modify: `api/server/main.py`
- Create: `api/server/services/live_state_recovery.py`
- Modify: `api/server/services/replay/hydrate.py` only to extract reusable pure deserializers
- Create: `tests/api/server/services/test_live_state_recovery.py`
- Modify: `tests/api/server/services/test_workflow_event_ingestor.py`

- [ ] Add cases that construct a pending workflow, persist its exception and `payload.hitl_context`, discard application state, reopen the repository and resolve the same exception. Preserve the workflow ID, Durable instance ID, event name, persona, context and decision ID.
- [ ] Extract pure restore functions from existing snapshot/hydration code. They accept explicit stores and data, perform no model/tool calls and do not emit live bus mutations. Do not use replay's permissive decision reconstruction as authoritative recovery.
- [ ] Restore accepted aggregates before seeders, persona sweeps, Fleet Manager, ambient dispatch or HTTP readiness. Rebuild required graph/entity/policy projections from canonical accepted records without repeating external actions. Seed only missing baseline entities; do not overwrite restored policy or business state.
- [ ] Audit direct mutations in the ingestor and exception-resolution path. Commit the aggregate before acknowledging a checkpoint or approval, then publish observable mutations. Keep existing synchronous API compatibility; offload blocking blob work at async request boundaries rather than adding fire-and-forget persistence.
- [ ] Record checkpoint keys using workflow ID plus persistent event/run identity. Record operator-decision keys using workflow ID, phase and decision ID. An exact retry returns the existing receipt; reusing a key with different content returns a conflict.
- [ ] Persist pending external-event delivery before acknowledging an operator action. Recovery retries only that delivery using the same decision ID. The receiving workflow validates expected phase and decision ID; duplicates never become a second business command.
- [ ] Add crash-window cases: before acceptance, after persistence/before response, after external-event send/before receipt, and after command application/before checkpoint acknowledgement. Commands require their own idempotency receipt; do not claim exactly-once effects against arbitrary external systems.
- [ ] Run `make test-presales-runtime` and existing event-ingestor/persona edge-case selectors together. Add the new selectors to `make test-harness` once their isolated run is stable.

**Acceptance:** pending approvals survive API/container replacement; accepted commands do not repeat; an unavailable repository produces an explicit failure. Restore never replays models, notifications or payment-like actions.

**Storage boundary:** no SQLite/Kuzu live writer is assumed safe on Azure Files. Native files may be local caches. If a graph/projection cannot be restored from accepted records, readiness must remain false and the recovery gap must be repaired before Phase 3 acceptance.

## Task 1.3: Complete Fleet Manager's provider boundary

**Files**

- Modify: `api/server/services/fleet_manager_service.py`
- Create: `api/server/services/fleet_manager_runtime.py`
- Modify: `api/server/services/fleet_manager_queue.py` only where lifecycle/error propagation requires it
- Reuse: `api/functions/graphs/executors/agents/runtime.py`
- Reuse: `api/functions/graphs/executors/agents/runtime_aoai.py`
- Reuse: `api/functions/graphs/executors/agents/runtime_ghcp.py`
- Modify: `verticals/agency/lifecycle.py`
- Modify: `tests/api/unit/test_fleet_manager_service.py`
- Create: `tests/api/unit/test_fleet_manager_runtime.py`
- Modify: `docs/runtime-providers.md`

- [ ] Add tests selecting `LLM_RUNTIME=azure` and `aoai` with `gh` absent, no GitHub credentials and mocked Azure authentication. Add the corresponding `ghcp` cases to preserve current behaviour.
- [ ] Introduce a small supervisor-session adapter selected by the existing runtime selector. Reuse provider configuration, tool schema/argument validation, permission handling and canonical tool evidence; do not create another model-selection registry.
- [ ] Keep a persistent logical supervisor conversation across queue batches. Azure may use successive provider calls with bounded message history; it must not silently discard required context or fabricate a completed session.
- [ ] Reuse `LLMRuntime.run_session()`, `_build_skill_text()`, `_on_session_event()` and `LLMRuntimeResult.text` for Azure batches. Keep `FleetManagerQueue` serialized. Document the difference between bounded Azure batch context and the existing persistent GitHub session.
- [ ] Fix the Azure deployment override explicitly: `AOAIRuntime` currently ignores `run_session(model=...)`. Add an optional `azure_deployment` argument at runtime construction. `AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT` selects the FM deployment; when absent, the documented default is `AZURE_OPENAI_DEPLOYMENT`. Keep `FLEET_MANAGER_MODEL` as the GitHub model selector. Cache keys must include the Azure deployment; selecting an FM override must not alter ordinary workflow-agent defaults. Evidence records the actual selected provider/deployment, not an ignored requested model.
- [ ] Limit `_gh_token()` and `CopilotClient` construction to the GitHub implementation. Azure must obtain its token through the existing Azure identity/provider configuration.
- [ ] Make `FleetManagerService.start()` report success/failure explicitly. A required supervisor that fails to start blocks private-live readiness; it must not print an error and leave an apparently healthy application.
- [ ] Test tool denial, required-tool failure, queue arrivals during processing, provider failure, cancellation and shutdown. Keep the existing queue's single processor.
- [ ] Cover `FunctionFleetManager`, which aliases the same service. Do not imply that this implements the separate delegation stub in `api/server/mcp_tools/query_function_fm.py`; keep that limitation in the claim map.
- [ ] Run `make test-presales-runtime`, plus the existing runtime-protocol/AOAI/GitHub/queue selectors in one backend cohort. Document provider requirements and which supervisor paths each provider supports.

**Acceptance:** the Azure reference requires no developer GitHub login; the GitHub reference still works; missing credentials cannot create a false-ready supervisor.

## Phase gate and rollback

- [ ] GATE-A satisfied for file and mocked Azure backends; real Azure persistence is additionally exercised in Phase 3.
- [ ] Persisted schema migration is versioned and non-destructive.
- [ ] Offline and replay modes create no writer lease and no live recovery side effects.

Rollback disables new live starts and selects the previous compatible schema/image pair. It never points an older writer at a newer incompatible state prefix or silently drops back to volatile memory.
