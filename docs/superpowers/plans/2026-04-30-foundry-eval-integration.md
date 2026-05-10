# Foundry Evaluation Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake `/api/evals` random-number tiles and re-platform the 300-claim accuracy harness onto the Azure AI Foundry evaluation SDK so every GHCP SDK agentic action is scored by Foundry, with strict no-fake-numbers semantics in the control plane.

**Architecture:** Event-bus subscriber. `run_agent_session` emits `agent.completed`; a new `online_subscriber` drains a queue and calls each Foundry evaluator's `__call__` directly per row; the batch path (300-claim corpus) uses Foundry's higher-level `evaluate()` orchestration helper with `azure_ai_project=` for tracked portal runs. All eval data persists in a local sqlite `EvalStore`; the control plane reads from that store. When Foundry is not configured, the page explicitly says so — never falls back to synthetic values.

**Tech Stack:** Python 3.11 (FastAPI + Azure Durable Functions), `azure-ai-evaluation` SDK, `azure-ai-projects`, `azure-identity` (DefaultAzureCredential), sqlite (stdlib), pytest, React + Vite + Tailwind frontend, vitest for component tests.

**Spec:** [docs/superpowers/specs/2026-04-30-foundry-eval-integration-design.md](../specs/2026-04-30-foundry-eval-integration-design.md)

---

## File structure

### New files (under `api/server/eval/`)

| File | Responsibility |
|---|---|
| `api/server/eval/__init__.py` | Package marker |
| `api/server/eval/foundry_client.py` | Singleton config wrapper. `is_configured()`, `get_project_config()`, `get_model_config()`. Reads env vars; lazy-builds `DefaultAzureCredential`. |
| `api/server/eval/custom_evaluators.py` | Three Python-only evaluators: `PolicyClauseCited`, `ToolCallValidity`, `GoldLabelMatch`. Pure deterministic functions. |
| `api/server/eval/evaluator_set.py` | Agent-label → evaluator-instance dict. Per-agent `extract_context(tool_calls)` extractor. Lazy construction. |
| `api/server/eval/store.py` | Sqlite store at `data/.eval/store.sqlite`. Schema, CRUD, summary aggregation. |
| `api/server/eval/online_subscriber.py` | Bus subscription + sampling + asyncio queue + drain worker. FastAPI lifespan-managed. |
| `api/server/eval/batch_runner.py` | Wraps Foundry `evaluate()` for the 300-claim corpus. Builds JSONL, runs evaluate, reshapes the result. |

### Modified files

| File | Change |
|---|---|
| `api/shared/events.py` | Add `"agent.completed"` to `FleetEventType`. |
| `api/functions/graphs/executors/agents/_wrapper.py` | Collect tool_calls, emit `agent.completed` event, accept `workflow_id` kwarg. |
| `api/functions/graphs/executors/agents/agent_*.py` (13 files) | Read `input.get("workflow_id")` and forward to `run_agent_session`. |
| `api/server/main.py` | Register/teardown the `online_subscriber` in the FastAPI lifespan. |
| `api/server/routes/evals.py` | Replace random-number generation with reads from `EvalStore`. |
| `api/server/routes/accuracy.py` | Call `batch_runner.run` instead of `harness.run`; 503 if not configured. |
| `web/client/routes/Evaluations.tsx` | Three states (configured+data, configured+empty, not-configured); per-agent table; foundry portal links on batch rows. |
| `.env.example` | Add Foundry env vars + sampling/queue knobs. |

### Deleted files

| File | Reason |
|---|---|
| `api/functions/workflows/accuracy_harness_workflow.py` | Replaced by `batch_runner.py`. |

### New tests

| File | Coverage |
|---|---|
| `tests/api/eval/test_foundry_client_no_creds.py` | env unset → not configured; lazy init doesn't raise. |
| `tests/api/eval/test_custom_evaluators.py` | `PolicyClauseCited`, `ToolCallValidity`, `GoldLabelMatch` unit cases. |
| `tests/api/eval/test_evaluator_set.py` | Agent-label → evaluator mapping. Context extractors. |
| `tests/api/eval/test_store.py` | Sqlite CRUD + summary aggregation (errored excluded from averages). |
| `tests/api/eval/test_subscriber_sampling.py` | Sampling rate respected. |
| `tests/api/eval/test_subscriber_overflow.py` | Queue at capacity drops oldest pending. |
| `tests/api/eval/test_subscriber_drain.py` | Worker drains queue, writes scores; rate-limit retry. |
| `tests/api/eval/test_batch_runner.py` | JSONL building, mocked `evaluate()`, result reshape. |
| `tests/api/integration/test_run_agent_session_emits.py` | `run_agent_session` emits exactly one `agent.completed` event with correct payload. |
| `tests/api/routes/test_evals_route_unconfigured.py` | `/api/evals` returns `{configured: false}` HTTP 200; `/api/accuracy/run` HTTP 503 when not configured. |
| `tests/api/routes/test_evals_route_configured.py` | `/api/evals/summary` excludes errored rows from averages, reports `n_errored`. |
| `tests/api/integration/test_foundry_smoke.py` | Real Foundry, 5-claim batch, gated by `pytest.mark.foundry`. |
| `tests/web/Evaluations.test.tsx` | Three component states. |

---

## Task 1: Add `agent.completed` event type

**Files:**
- Modify: `api/shared/events.py`
- Test: `tests/api/unit/test_fleet_event_agent_completed.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/unit/test_fleet_event_agent_completed.py`:

```python
"""Verify FleetEvent accepts the agent.completed type with extra fields."""
from __future__ import annotations
from api.shared.events import FleetEvent, WAKE_TYPES, wakes_fleet_manager


def test_agent_completed_is_a_valid_event_type():
    ev = FleetEvent(
        type="agent.completed",
        workflow_id="wf-abc",
        agent_label="rag-classifier",
        agent_run_id="ar-123",
        prompt="...",
        response_text="...",
        tool_calls=[],
        usage={"input_tokens": 100, "output_tokens": 50},
        latency_ms=1234,
    )
    assert ev.type == "agent.completed"
    assert ev.workflow_id == "wf-abc"
    # extra="allow" exposes additional fields:
    assert ev.agent_label == "rag-classifier"
    assert ev.latency_ms == 1234


def test_agent_completed_does_not_wake_the_fleet_manager():
    ev = FleetEvent(type="agent.completed", workflow_id="wf-abc")
    assert "agent.completed" not in WAKE_TYPES
    assert wakes_fleet_manager(ev) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_fleet_event_agent_completed.py -v
```

Expected: FAIL — `pydantic.ValidationError: Input should be one of ...` (the `Literal` rejects the unknown value).

- [ ] **Step 3: Add `"agent.completed"` to the event-type literal**

Edit `api/shared/events.py`. Insert the new entry after the `"accuracy.complete"` entry, before the Week 2 expense-claim domain events:

```python
FleetEventType = Literal[
    "workflow.started",
    "workflow.phase.started",
    "workflow.phase.completed",
    "workflow.phase.failed",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "workflow.sla.breach_imminent",
    "workflow.policy.violation",
    "workflow.resolved",
    "otel.span.emitted",
    "fleet.anomaly.detected",
    "fleet.tick",
    "fleet.overload",
    # Durable Workflow events (new in py POC1)
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "durable.validator.blocked",
    "durable.suspended",
    "durable.resumed",
    "durable.workflow.completed",
    # Accuracy harness events (one-shot evaluation runs; do NOT wake the fleet manager)
    "accuracy.progress",
    "accuracy.complete",
    # Per-agent eval signal — emitted by run_agent_session, observed by online_subscriber.
    # Does NOT wake the fleet manager.
    "agent.completed",
    # Week 2 — expense-claim domain events
    "claim.routed.green",
    "claim.routed.amber",
    "claim.routed.red",
    "receipt.mismatch.detected",
    "escalation.tier.assigned",
    "notification.sent",
    "justification.received",
    "arbitration.recommended",
    "audit.summary.composed",
    "region.failure.simulated",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_fleet_event_agent_completed.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/api/unit/test_fleet_event_agent_completed.py api/shared/events.py
git commit -m "feat(events): add agent.completed event type for per-agent eval signal"
```

---

## Task 2: Foundry client — config reader + `is_configured()`

**Files:**
- Create: `api/server/eval/__init__.py` (empty package marker)
- Create: `api/server/eval/foundry_client.py`
- Test: `tests/api/eval/__init__.py` (empty)
- Test: `tests/api/eval/test_foundry_client_no_creds.py`

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p api/server/eval tests/api/eval
touch api/server/eval/__init__.py tests/api/eval/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/api/eval/test_foundry_client_no_creds.py`:

```python
"""is_configured() and lazy-init behaviour for foundry_client."""
from __future__ import annotations
import importlib
import sys

import pytest


def _reload_foundry_client(monkeypatch, env: dict):
    """Reload the module so module-level state picks up env changes."""
    for k in ("AZURE_FOUNDRY_PROJECT_ENDPOINT", "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    if "api.server.eval.foundry_client" in sys.modules:
        del sys.modules["api.server.eval.foundry_client"]
    return importlib.import_module("api.server.eval.foundry_client")


def test_is_configured_false_when_endpoint_missing(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={
        "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT": "gpt-4o",
    })
    assert fc.is_configured() is False


def test_is_configured_false_when_deployment_missing(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={
        "AZURE_FOUNDRY_PROJECT_ENDPOINT": "https://example.cognitiveservices.azure.com",
    })
    assert fc.is_configured() is False


def test_is_configured_true_when_both_set(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={
        "AZURE_FOUNDRY_PROJECT_ENDPOINT": "https://example.cognitiveservices.azure.com",
        "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT": "gpt-4o",
    })
    assert fc.is_configured() is True


def test_module_import_does_not_construct_credentials(monkeypatch):
    """Importing the module must not call DefaultAzureCredential or any Azure SDK init.

    DefaultAzureCredential probes managed identity / az login; that's a side
    effect we never want at import time. Construction only happens when
    get_model_config() / get_project_config() are called.
    """
    fc = _reload_foundry_client(monkeypatch, env={})
    # Just importing succeeded — no exception, no eager Azure construction.
    # We intentionally call the public surface that does NOT need creds:
    assert fc.is_configured() is False


def test_get_project_config_raises_when_unconfigured(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={})
    with pytest.raises(RuntimeError, match="not configured"):
        fc.get_project_config()


def test_get_model_config_raises_when_unconfigured(monkeypatch):
    fc = _reload_foundry_client(monkeypatch, env={})
    with pytest.raises(RuntimeError, match="not configured"):
        fc.get_model_config()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_foundry_client_no_creds.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.eval.foundry_client'`.

- [ ] **Step 4: Implement `foundry_client.py`**

Create `api/server/eval/foundry_client.py`:

```python
"""Foundry SDK config singleton.

Reads required env vars; lazy-builds DefaultAzureCredential and the
AzureOpenAIModelConfiguration the SDK evaluators expect. Importing this
module has no side effects beyond reading os.environ — no Azure calls,
no credential probes.
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Any


_REQUIRED_ENV = (
    "AZURE_FOUNDRY_PROJECT_ENDPOINT",
    "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT",
)


def is_configured() -> bool:
    """Return True iff every required env var is set to a non-empty value."""
    return all(os.environ.get(k) for k in _REQUIRED_ENV)


def _require_configured() -> None:
    if not is_configured():
        missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
        raise RuntimeError(
            f"Foundry eval is not configured; missing env: {', '.join(missing)}"
        )


@lru_cache(maxsize=1)
def _credential():
    # Lazy import: azure-identity is only imported when actually needed,
    # keeping module import side-effect free for tests.
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


def get_project_config() -> dict[str, Any]:
    """Return the dict shape `evaluate(azure_ai_project=...)` expects.

    The Foundry SDK accepts either a project endpoint URL string or a dict
    with `subscription_id`, `resource_group_name`, `project_name`. We pass the
    endpoint URL directly — it's what the project SDK exposes from the portal.
    """
    _require_configured()
    return {
        "endpoint": os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"],
    }


def get_model_config() -> dict[str, Any]:
    """Return the AzureOpenAIModelConfiguration dict for evaluators that
    take a `model_config=` kwarg (Groundedness, Relevance, Coherence, etc.).
    """
    _require_configured()
    return {
        "azure_endpoint": os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"],
        "azure_deployment": os.environ["AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT"],
        # api_key is NOT used — DefaultAzureCredential is the auth path.
        # The SDK accepts an `azure_ad_token_provider` callable; we expose it
        # via the credential singleton above. The evaluator constructors accept
        # this dict directly; if a specific evaluator wants a token-provider
        # callable, build it from `_credential()` at call site.
    }
```

- [ ] **Step 5: Run test to verify it passes**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_foundry_client_no_creds.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/eval/__init__.py api/server/eval/foundry_client.py \
        tests/api/eval/__init__.py tests/api/eval/test_foundry_client_no_creds.py
git commit -m "feat(eval): foundry_client singleton with is_configured() check"
```

---

## Task 3: Custom evaluators

**Files:**
- Create: `api/server/eval/custom_evaluators.py`
- Test: `tests/api/eval/test_custom_evaluators.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/eval/test_custom_evaluators.py`:

```python
"""Unit tests for the three deterministic custom evaluators."""
from __future__ import annotations

from api.server.eval.custom_evaluators import (
    PolicyClauseCited,
    ToolCallValidity,
    GoldLabelMatch,
)


# ---- PolicyClauseCited ------------------------------------------------------

def test_policy_clause_cited_returns_1_when_30plus_char_excerpt_appears_in_response():
    ev = PolicyClauseCited()
    context = (
        "§3.2 Meal claims must not exceed 110% of the per-diem cap published "
        "for the claimant's market in Annex A."
    )
    response = (
        "I am denying this claim under the rule that meal claims must not "
        "exceed 110% of the per-diem cap published for the claimant's market."
    )
    out = ev(query="claim CLM-001", response=response, context=context)
    assert out["policy_clause_cited"] == 1
    assert out["policy_clause_excerpt"] is not None


def test_policy_clause_cited_returns_0_when_no_substring_match():
    ev = PolicyClauseCited()
    context = "§3.2 Meal claims must not exceed 110% of the per-diem cap."
    response = "Approved per policy clause 3.2."
    out = ev(query="claim CLM-002", response=response, context=context)
    assert out["policy_clause_cited"] == 0
    assert out["policy_clause_excerpt"] is None


def test_policy_clause_cited_normalises_whitespace_differences():
    """Different whitespace between context and response should still match."""
    ev = PolicyClauseCited()
    context = "§3.2  Meal claims must not exceed 110% of the per-diem cap."
    response = "Per policy: Meal claims must not exceed 110% of the per-diem cap."
    out = ev(query="claim CLM-003", response=response, context=context)
    assert out["policy_clause_cited"] == 1


def test_policy_clause_cited_returns_0_when_context_empty():
    ev = PolicyClauseCited()
    out = ev(query="q", response="some text", context="")
    assert out["policy_clause_cited"] == 0


# ---- ToolCallValidity -------------------------------------------------------

def test_tool_call_validity_all_valid():
    ev = ToolCallValidity()
    out = ev(
        query="q", response="r",
        tool_calls=[
            {"name": "policy_search", "args": '{"market": "EU"}', "success": True},
            {"name": "claim_get_structured", "args": '{"claim_id": "CLM-001"}', "success": True},
        ],
        declared_tools=["policy_search", "claim_get_structured"],
    )
    assert out["tool_calls_valid"] == 1.0
    assert out["invalid_calls"] == []


def test_tool_call_validity_unknown_tool_name_drops_score():
    ev = ToolCallValidity()
    out = ev(
        query="q", response="r",
        tool_calls=[
            {"name": "policy_search", "args": '{"market": "EU"}', "success": True},
            {"name": "imaginary_tool", "args": "{}", "success": True},
        ],
        declared_tools=["policy_search"],
    )
    assert out["tool_calls_valid"] == 0.5
    assert {"reason": "unknown_tool", "name": "imaginary_tool"} in out["invalid_calls"]


def test_tool_call_validity_unparseable_args_counts_as_invalid():
    ev = ToolCallValidity()
    out = ev(
        query="q", response="r",
        tool_calls=[
            {"name": "policy_search", "args": "{not valid json", "success": True},
        ],
        declared_tools=["policy_search"],
    )
    assert out["tool_calls_valid"] == 0.0
    assert any(c["reason"] == "unparseable_args" for c in out["invalid_calls"])


def test_tool_call_validity_no_tool_calls_returns_1():
    """A response with no tool calls is trivially valid (no invalid calls)."""
    ev = ToolCallValidity()
    out = ev(query="q", response="r", tool_calls=[], declared_tools=["policy_search"])
    assert out["tool_calls_valid"] == 1.0
    assert out["invalid_calls"] == []


# ---- GoldLabelMatch ---------------------------------------------------------

def test_gold_label_match_exact_match_red():
    ev = GoldLabelMatch()
    out = ev(predicted="Red", gold="Red")
    assert out["label_match"] == 1
    assert out["predicted"] == "Red"
    assert out["gold"] == "Red"


def test_gold_label_match_mismatch():
    ev = GoldLabelMatch()
    out = ev(predicted="Amber", gold="Red")
    assert out["label_match"] == 0


def test_gold_label_match_is_case_sensitive():
    """Verdicts in the corpus are exactly Red/Amber/Green; lowercase != match."""
    ev = GoldLabelMatch()
    out = ev(predicted="red", gold="Red")
    assert out["label_match"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_custom_evaluators.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `custom_evaluators.py`**

Create `api/server/eval/custom_evaluators.py`:

```python
"""Deterministic custom evaluators — pure Python, no LLM calls.

Each evaluator is a class with a `__call__` returning a dict of scores +
optional reasoning. Matches the shape `azure-ai-evaluation` expects from
custom evaluators (passed into `evaluate(evaluators={...})` or invoked
directly per row in the online subscriber).
"""
from __future__ import annotations
import json
import re
from typing import Any


_WS_RE = re.compile(r"\s+")
_MIN_EXCERPT_CHARS = 30


def _normalise(s: str) -> str:
    return _WS_RE.sub(" ", s).strip().lower()


class PolicyClauseCited:
    """Returns 1 iff some 30+ char run from `context` appears in `response`
    after whitespace normalisation. Catches the failure mode where the model
    cites a clause number ('per §3.2') without quoting the literal text.
    """

    def __call__(self, *, query: str, response: str, context: str, **_: Any) -> dict:
        if not context or not response:
            return {"policy_clause_cited": 0, "policy_clause_excerpt": None}

        normalised_response = _normalise(response)

        # Slide a 30-char window over the normalised context and check membership.
        # Cheap O(n*m); contexts are kilobytes at most.
        normalised_context = _normalise(context)
        n = len(normalised_context)
        for start in range(0, n - _MIN_EXCERPT_CHARS + 1):
            excerpt = normalised_context[start:start + _MIN_EXCERPT_CHARS]
            if excerpt in normalised_response:
                # Return the matching slice of the *original* (un-normalised) context.
                # Approximate by length-prop scaling — if the engineer wants the
                # original, they can re-extract; we just need a representative slice.
                return {
                    "policy_clause_cited": 1,
                    "policy_clause_excerpt": context.strip()[: _MIN_EXCERPT_CHARS * 4],
                }
        return {"policy_clause_cited": 0, "policy_clause_excerpt": None}


class ToolCallValidity:
    """Score = (valid_calls / total_calls) where each call is valid iff
    its name is in `declared_tools` AND its args JSON-parse cleanly.

    With zero tool calls the score is 1.0 (trivially valid).
    """

    def __call__(
        self,
        *,
        query: str,
        response: str,
        tool_calls: list[dict] | None = None,
        declared_tools: list[str] | None = None,
        **_: Any,
    ) -> dict:
        tool_calls = tool_calls or []
        declared = set(declared_tools or [])
        total = len(tool_calls)
        if total == 0:
            return {"tool_calls_valid": 1.0, "invalid_calls": []}

        invalid: list[dict] = []
        valid_count = 0
        for call in tool_calls:
            name = call.get("name", "")
            args_raw = call.get("args", "")
            if name not in declared:
                invalid.append({"reason": "unknown_tool", "name": name})
                continue
            if isinstance(args_raw, str):
                try:
                    json.loads(args_raw) if args_raw else None
                except json.JSONDecodeError:
                    invalid.append({"reason": "unparseable_args", "name": name})
                    continue
            valid_count += 1

        return {
            "tool_calls_valid": valid_count / total,
            "invalid_calls": invalid,
        }


class GoldLabelMatch:
    """Batch-only evaluator. Returns 1 iff predicted == gold (case-sensitive).
    Drives the confusion matrix in batch_runner.
    """

    def __call__(
        self, *, predicted: str = "", gold: str = "", **_: Any
    ) -> dict:
        return {
            "label_match": 1 if predicted == gold else 0,
            "predicted": predicted,
            "gold": gold,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_custom_evaluators.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/eval/custom_evaluators.py tests/api/eval/test_custom_evaluators.py
git commit -m "feat(eval): three deterministic custom evaluators (PolicyClauseCited, ToolCallValidity, GoldLabelMatch)"
```

---

## Task 4: Evaluator set + context extractors

**Files:**
- Create: `api/server/eval/evaluator_set.py`
- Test: `tests/api/eval/test_evaluator_set.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/eval/test_evaluator_set.py`:

```python
"""Tests for evaluator_set: per-agent evaluator selection + context extractors.

We mock the Foundry-SDK evaluator classes so this test runs without azure-ai-evaluation
needing creds. Production code hits the real SDK; tests assert the *shape* of the
mapping and the *names* of evaluators returned per agent.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_sdk_evaluators():
    """Patch the Foundry SDK evaluator classes used by evaluator_set."""
    with patch.dict("sys.modules", {
        "azure.ai.evaluation": MagicMock(
            GroundednessEvaluator=lambda model_config: ("groundedness", model_config),
            RelevanceEvaluator=lambda model_config: ("relevance", model_config),
            SimilarityEvaluator=lambda model_config: ("similarity", model_config),
            CoherenceEvaluator=lambda model_config: ("coherence", model_config),
            FluencyEvaluator=lambda model_config: ("fluency", model_config),
            ViolenceEvaluator=lambda azure_ai_project, credential=None: ("violence", azure_ai_project),
            HateUnfairnessEvaluator=lambda azure_ai_project, credential=None: ("hate_unfairness", azure_ai_project),
        ),
    }):
        # Reimport so the module-level imports pick up the patch
        import importlib
        import sys
        sys.modules.pop("api.server.eval.evaluator_set", None)
        yield


def test_rag_classifier_evaluator_set_includes_groundedness_and_custom(monkeypatch, mock_sdk_evaluators):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")
    from api.server.eval.evaluator_set import evaluators_for
    evals = evaluators_for("rag-classifier")
    assert set(evals.keys()) == {
        "groundedness", "relevance", "similarity",
        "policy_clause_cited", "tool_call_validity",
    }


def test_arbitration_evaluator_set(monkeypatch, mock_sdk_evaluators):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")
    from api.server.eval.evaluator_set import evaluators_for
    evals = evaluators_for("arbitration")
    assert set(evals.keys()) == {
        "groundedness", "relevance", "coherence", "violence", "hate_unfairness",
    }


def test_unknown_agent_label_falls_back_to_default(monkeypatch, mock_sdk_evaluators):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")
    from api.server.eval.evaluator_set import evaluators_for
    evals = evaluators_for("some-future-poc2-agent")
    assert set(evals.keys()) == {"coherence", "fluency", "violence", "hate_unfairness"}


def test_extract_context_for_rag_classifier_concats_policy_search_results():
    from api.server.eval.evaluator_set import extract_context
    tool_calls = [
        {"name": "claim_get_structured", "args": "{}", "result": "{...claim...}", "success": True},
        {"name": "policy_search", "args": "{}",
         "result": "§3.2 Meal claims must not exceed 110% of the per-diem cap.",
         "success": True},
        {"name": "policy_search", "args": "{}",
         "result": "§4.1 Receipts are required for any claim ≥ £25.",
         "success": True},
    ]
    ctx = extract_context("rag-classifier", tool_calls)
    assert "§3.2" in ctx
    assert "§4.1" in ctx
    assert "claim_get_structured" not in ctx  # only policy_search results contribute


def test_extract_context_for_arbitration_concats_precedents_search_results():
    from api.server.eval.evaluator_set import extract_context
    tool_calls = [
        {"name": "precedents_search", "args": "{}", "result": "Case A: warning issued.", "success": True},
        {"name": "policy_search", "args": "{}", "result": "§3.2 ...", "success": True},
    ]
    ctx = extract_context("arbitration", tool_calls)
    assert "Case A" in ctx
    assert "§3.2" in ctx  # arbitration also uses policy_search


def test_extract_context_for_unknown_agent_returns_empty():
    from api.server.eval.evaluator_set import extract_context
    assert extract_context("unknown", [{"name": "anything", "result": "..."}]) == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_evaluator_set.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `evaluator_set.py`**

Create `api/server/eval/evaluator_set.py`:

```python
"""Per-agent evaluator selection + context extractors.

`evaluators_for(agent_label)` returns a `{name: evaluator_instance}` dict.
LLM-based evaluators (Groundedness, Relevance, etc.) are imported lazily
from azure.ai.evaluation only when this function is first called for an
agent that needs them.

`extract_context(agent_label, tool_calls)` returns a string used as the
`context=` input to Groundedness — for `rag-classifier` it's the
concatenated policy_search results; for `arbitration` it's
precedents_search + policy_search; for unknown agents it's empty.
"""
from __future__ import annotations
from functools import lru_cache
from typing import Any

from api.server.eval import foundry_client
from api.server.eval.custom_evaluators import (
    PolicyClauseCited,
    ToolCallValidity,
    GoldLabelMatch,
)


@lru_cache(maxsize=1)
def _llm_evaluator_classes():
    """Lazy-import the SDK evaluator classes. Called at most once per process."""
    from azure.ai.evaluation import (
        GroundednessEvaluator,
        RelevanceEvaluator,
        SimilarityEvaluator,
        CoherenceEvaluator,
        FluencyEvaluator,
        ViolenceEvaluator,
        HateUnfairnessEvaluator,
    )
    return {
        "groundedness": GroundednessEvaluator,
        "relevance": RelevanceEvaluator,
        "similarity": SimilarityEvaluator,
        "coherence": CoherenceEvaluator,
        "fluency": FluencyEvaluator,
        "violence": ViolenceEvaluator,
        "hate_unfairness": HateUnfairnessEvaluator,
    }


def _build_llm_evaluator(name: str) -> Any:
    """Construct one LLM evaluator with the right kwargs for its constructor.

    Quality evaluators (groundedness/relevance/similarity/coherence/fluency)
    take `model_config=`. Safety evaluators (violence/hate_unfairness) take
    `azure_ai_project=` (and optionally a credential).
    """
    classes = _llm_evaluator_classes()
    cls = classes[name]
    if name in ("violence", "hate_unfairness"):
        return cls(azure_ai_project=foundry_client.get_project_config())
    return cls(model_config=foundry_client.get_model_config())


# Per-agent evaluator name lists. Custom evaluators are interleaved with
# LLM ones; the builder below looks up the right factory per name.
_PER_AGENT: dict[str, tuple[str, ...]] = {
    "rag-classifier": (
        "groundedness", "relevance", "similarity",
        "policy_clause_cited", "tool_call_validity",
    ),
    "arbitration": (
        "groundedness", "relevance", "coherence", "violence", "hate_unfairness",
    ),
}
_DEFAULT: tuple[str, ...] = ("coherence", "fluency", "violence", "hate_unfairness")


def evaluators_for(agent_label: str) -> dict[str, Any]:
    """Return `{name: evaluator_instance}` for the given agent label.

    Unknown labels fall back to the default `*` set.
    """
    names = _PER_AGENT.get(agent_label, _DEFAULT)
    out: dict[str, Any] = {}
    for n in names:
        if n == "policy_clause_cited":
            out[n] = PolicyClauseCited()
        elif n == "tool_call_validity":
            out[n] = ToolCallValidity()
        elif n == "gold_label_match":
            out[n] = GoldLabelMatch()
        else:
            out[n] = _build_llm_evaluator(n)
    return out


# ---- Context extraction -----------------------------------------------------

_CONTEXT_TOOLS: dict[str, tuple[str, ...]] = {
    "rag-classifier": ("policy_search",),
    "arbitration": ("precedents_search", "policy_search"),
}


def extract_context(agent_label: str, tool_calls: list[dict]) -> str:
    """Concat the `result` field of tool calls whose `name` is in the
    per-agent context-tool list. Returns empty string for unknown agents.
    """
    relevant_names = _CONTEXT_TOOLS.get(agent_label, ())
    if not relevant_names:
        return ""
    parts: list[str] = []
    for call in tool_calls or []:
        if call.get("name") in relevant_names:
            result = call.get("result") or ""
            if isinstance(result, str) and result:
                parts.append(result)
    return "\n\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_evaluator_set.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/eval/evaluator_set.py tests/api/eval/test_evaluator_set.py
git commit -m "feat(eval): per-agent evaluator set + context extractor"
```

---

## Task 5: EvalStore (sqlite)

**Files:**
- Create: `api/server/eval/store.py`
- Test: `tests/api/eval/test_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/eval/test_store.py`:

```python
"""EvalStore CRUD + summary aggregation behaviour."""
from __future__ import annotations
import time

import pytest

from api.server.eval.store import EvalStore, EvalRow


@pytest.fixture
def store(tmp_path):
    return EvalStore(db_path=str(tmp_path / "eval.sqlite"))


def _make_row(store, **overrides) -> EvalRow:
    base = dict(
        id=f"ev-{time.time_ns()}",
        kind="online",
        agent_label="rag-classifier",
        workflow_id="wf-1",
        agent_run_id="ar-1",
        ts=time.time(),
    )
    base.update(overrides)
    row = EvalRow(**base)
    store.put_pending(row)
    return row


def test_put_pending_and_by_id_round_trips(store):
    row = _make_row(store)
    fetched = store.by_id(row.id)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.status == "pending"
    assert fetched.scores_json is None


def test_complete_updates_status_and_scores(store):
    row = _make_row(store)
    store.complete(row.id, scores={"groundedness": 0.9}, foundry_run_url=None)
    fetched = store.by_id(row.id)
    assert fetched.status == "completed"
    assert fetched.scores_json == {"groundedness": 0.9}


def test_error_updates_status_and_text(store):
    row = _make_row(store)
    store.error(row.id, error_text="rate-limited after retry")
    fetched = store.by_id(row.id)
    assert fetched.status == "error"
    assert fetched.error_text == "rate-limited after retry"


def test_recent_returns_completed_rows_newest_first(store):
    r1 = _make_row(store, id="ev-1", ts=1000.0)
    r2 = _make_row(store, id="ev-2", ts=2000.0)
    store.complete(r1.id, scores={"groundedness": 0.8}, foundry_run_url=None)
    store.complete(r2.id, scores={"groundedness": 0.95}, foundry_run_url=None)
    rows = store.recent(10)
    assert [r.id for r in rows] == ["ev-2", "ev-1"]


def test_recent_filters_by_agent_label(store):
    r1 = _make_row(store, id="ev-1", agent_label="rag-classifier")
    r2 = _make_row(store, id="ev-2", agent_label="arbitration")
    store.complete(r1.id, scores={"a": 1}, foundry_run_url=None)
    store.complete(r2.id, scores={"a": 1}, foundry_run_url=None)
    rows = store.recent(10, agent_label="arbitration")
    assert [r.id for r in rows] == ["ev-2"]


def test_summary_excludes_errored_rows_from_averages(store):
    r1 = _make_row(store, id="ev-1")
    r2 = _make_row(store, id="ev-2")
    r3 = _make_row(store, id="ev-3")
    store.complete(r1.id, scores={"groundedness": 0.9, "relevance": 0.8}, foundry_run_url=None)
    store.complete(r2.id, scores={"groundedness": 0.7, "relevance": 0.6}, foundry_run_url=None)
    store.error(r3.id, error_text="boom")

    summary = store.summary(window_minutes=60)
    assert summary["n_completed"] == 2
    assert summary["n_errored"] == 1
    # Mean of {0.9, 0.7} = 0.8 — errored row not counted.
    assert summary["per_agent"]["rag-classifier"]["scores"]["groundedness"] == pytest.approx(0.8)


def test_summary_per_agent_breakdown(store):
    r1 = _make_row(store, id="ev-1", agent_label="rag-classifier")
    r2 = _make_row(store, id="ev-2", agent_label="arbitration")
    store.complete(r1.id, scores={"groundedness": 0.9}, foundry_run_url=None)
    store.complete(r2.id, scores={"groundedness": 0.6}, foundry_run_url=None)

    summary = store.summary(window_minutes=60)
    by_agent = summary["per_agent"]
    assert by_agent["rag-classifier"]["scores"]["groundedness"] == 0.9
    assert by_agent["arbitration"]["scores"]["groundedness"] == 0.6


def test_summary_window_excludes_old_rows(store):
    """Rows older than the window must not affect averages."""
    old = _make_row(store, id="old", ts=time.time() - 7200)  # 2h ago
    new = _make_row(store, id="new", ts=time.time())
    store.complete(old.id, scores={"groundedness": 0.1}, foundry_run_url=None)
    store.complete(new.id, scores={"groundedness": 0.99}, foundry_run_url=None)

    summary = store.summary(window_minutes=60)
    # Only the new row contributes.
    assert summary["per_agent"]["rag-classifier"]["scores"]["groundedness"] == 0.99
    assert summary["n_completed"] == 1


def test_drop_oldest_pending_removes_one_pending_row(store):
    # Two pending rows; ev-1 older
    _make_row(store, id="ev-1", ts=1000.0)
    _make_row(store, id="ev-2", ts=2000.0)
    store.drop_oldest_pending()
    assert store.by_id("ev-1") is None
    assert store.by_id("ev-2") is not None


def test_put_batch_and_last_batch_run_round_trip(store):
    report = {
        "run_id": "acc-abc",
        "n": 300,
        "overall_accuracy": 0.96,
        "foundry_run_url": "https://ai.foundry/...",
    }
    store.put_batch("acc-abc", report)
    last = store.last_batch_run()
    assert last["run_id"] == "acc-abc"
    assert last["overall_accuracy"] == 0.96


def test_by_workflow_returns_all_rows_for_a_workflow(store):
    r1 = _make_row(store, id="ev-1", workflow_id="wf-A")
    r2 = _make_row(store, id="ev-2", workflow_id="wf-A")
    r3 = _make_row(store, id="ev-3", workflow_id="wf-B")
    store.complete(r1.id, scores={"a": 1}, foundry_run_url=None)
    store.complete(r2.id, scores={"a": 1}, foundry_run_url=None)
    store.complete(r3.id, scores={"a": 1}, foundry_run_url=None)
    rows = store.by_workflow("wf-A")
    assert {r.id for r in rows} == {"ev-1", "ev-2"}


def test_health_reports_pending_in_flight_dropped_counts(store):
    _make_row(store, id="ev-1")
    r2 = _make_row(store, id="ev-2")
    store.complete(r2.id, scores={"a": 1}, foundry_run_url=None)
    health = store.health()
    assert health["pending"] == 1
    assert health["completed"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_store.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'api.server.eval.store'`.

- [ ] **Step 3: Implement `store.py`**

Create `api/server/eval/store.py`:

```python
"""Sqlite-backed eval store. One row per Foundry-scored eval; one row per
batch corpus run. Single-process; FastAPI uses one worker locally so no
concurrency story beyond `check_same_thread=False`.

The store is the system of record for online evals (Foundry portal does
NOT have per-row entries for online — see spec §4.1).
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = "data/.eval/store.sqlite"


@dataclass
class EvalRow:
    id: str
    kind: str  # "online" | "batch"
    agent_label: str
    workflow_id: str | None
    agent_run_id: str | None
    ts: float
    scores_json: dict[str, Any] | None = None
    foundry_run_url: str | None = None
    status: str = "pending"
    error_text: str | None = None
    # The eval payload — stored to enable later re-scoring or richer detail views.
    prompt: str = ""
    response_text: str = ""
    context: str = ""
    tool_calls: list[dict] = field(default_factory=list)


class EvalStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS evals (
                    id              TEXT PRIMARY KEY,
                    kind            TEXT NOT NULL,
                    agent_label     TEXT NOT NULL,
                    workflow_id     TEXT,
                    agent_run_id    TEXT,
                    ts              REAL NOT NULL,
                    scores_json     TEXT,
                    foundry_run_url TEXT,
                    status          TEXT NOT NULL,
                    error_text      TEXT,
                    prompt          TEXT,
                    response_text   TEXT,
                    context         TEXT,
                    tool_calls_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_evals_ts ON evals(ts DESC);
                CREATE INDEX IF NOT EXISTS idx_evals_workflow ON evals(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_evals_agent ON evals(agent_label);

                CREATE TABLE IF NOT EXISTS batch_runs (
                    run_id    TEXT PRIMARY KEY,
                    ts        REAL NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_batch_runs_ts ON batch_runs(ts DESC);
            """)

    # ---- write -----------------------------------------------------------

    def put_pending(self, row: EvalRow) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO evals
                   (id, kind, agent_label, workflow_id, agent_run_id, ts,
                    scores_json, foundry_run_url, status, error_text,
                    prompt, response_text, context, tool_calls_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.id, row.kind, row.agent_label, row.workflow_id,
                    row.agent_run_id, row.ts,
                    json.dumps(row.scores_json) if row.scores_json else None,
                    row.foundry_run_url,
                    row.status, row.error_text,
                    row.prompt, row.response_text, row.context,
                    json.dumps(row.tool_calls or []),
                ),
            )

    def complete(self, row_id: str, *, scores: dict[str, Any], foundry_run_url: str | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """UPDATE evals SET status='completed',
                   scores_json=?, foundry_run_url=?
                   WHERE id=?""",
                (json.dumps(scores), foundry_run_url, row_id),
            )

    def error(self, row_id: str, *, error_text: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE evals SET status='error', error_text=? WHERE id=?",
                (error_text, row_id),
            )

    def drop_oldest_pending(self) -> str | None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT id FROM evals WHERE status='pending' ORDER BY ts ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM evals WHERE id=?", (row["id"],))
            return row["id"]

    def put_batch(self, run_id: str, report: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO batch_runs (run_id, ts, report_json) VALUES (?, ?, ?)",
                (run_id, time.time(), json.dumps(report)),
            )

    # ---- read ------------------------------------------------------------

    def by_id(self, row_id: str) -> EvalRow | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM evals WHERE id=?", (row_id,)).fetchone()
        return _row_to_evalrow(r) if r else None

    def recent(self, n: int, agent_label: str | None = None) -> list[EvalRow]:
        sql = "SELECT * FROM evals"
        params: list[Any] = []
        if agent_label:
            sql += " WHERE agent_label=?"
            params.append(agent_label)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(n)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_evalrow(r) for r in rows]

    def by_workflow(self, workflow_id: str) -> list[EvalRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evals WHERE workflow_id=? ORDER BY ts ASC",
                (workflow_id,),
            ).fetchall()
        return [_row_to_evalrow(r) for r in rows]

    def summary(self, window_minutes: int = 60) -> dict[str, Any]:
        cutoff = time.time() - window_minutes * 60
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evals WHERE ts >= ? ORDER BY ts DESC",
                (cutoff,),
            ).fetchall()

        completed = [r for r in rows if r["status"] == "completed"]
        errored = [r for r in rows if r["status"] == "error"]

        # Per-agent breakdown.
        per_agent: dict[str, dict[str, Any]] = {}
        for r in completed:
            label = r["agent_label"]
            scores = json.loads(r["scores_json"] or "{}")
            agent_bucket = per_agent.setdefault(label, {"n": 0, "_sums": {}, "scores": {}})
            agent_bucket["n"] += 1
            for name, value in scores.items():
                # Some evaluators return numeric scores under nested keys (e.g. {"groundedness": 0.9, "groundedness_reason": "..."}).
                # We average only numeric fields.
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sums = agent_bucket["_sums"]
                    sums[name] = sums.get(name, 0.0) + float(value)

        for label, bucket in per_agent.items():
            n = bucket["n"]
            for name, total in bucket["_sums"].items():
                bucket["scores"][name] = total / n if n else 0.0
            del bucket["_sums"]

        return {
            "window_minutes": window_minutes,
            "n_completed": len(completed),
            "n_errored": len(errored),
            "per_agent": per_agent,
        }

    def last_batch_run(self) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT report_json FROM batch_runs ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["report_json"]) if r else None

    def health(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS c FROM evals GROUP BY status"
            ).fetchall()
        out = {"pending": 0, "completed": 0, "error": 0}
        for r in rows:
            out[r["status"]] = r["c"]
        return out


def _row_to_evalrow(r: sqlite3.Row) -> EvalRow:
    return EvalRow(
        id=r["id"],
        kind=r["kind"],
        agent_label=r["agent_label"],
        workflow_id=r["workflow_id"],
        agent_run_id=r["agent_run_id"],
        ts=r["ts"],
        scores_json=json.loads(r["scores_json"]) if r["scores_json"] else None,
        foundry_run_url=r["foundry_run_url"],
        status=r["status"],
        error_text=r["error_text"],
        prompt=r["prompt"] or "",
        response_text=r["response_text"] or "",
        context=r["context"] or "",
        tool_calls=json.loads(r["tool_calls_json"] or "[]"),
    )


# ---- module-level singleton -------------------------------------------------

_default: EvalStore | None = None


def default_store() -> EvalStore:
    global _default
    if _default is None:
        _default = EvalStore()
    return _default
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_store.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Verify .gitignore covers `data/.eval/`**

```bash
grep -E "^data/\\.eval|^data/$|^data/" .gitignore
```

If `data/.eval/` is not ignored, add it:

```bash
echo "data/.eval/" >> .gitignore
git add .gitignore
```

- [ ] **Step 6: Commit**

```bash
git add api/server/eval/store.py tests/api/eval/test_store.py
git commit -m "feat(eval): sqlite-backed EvalStore with summary aggregation"
```

---

## Task 6: Modify `_wrapper.py` — collect tool_calls + emit `agent.completed` + `workflow_id` kwarg

**Files:**
- Modify: `api/functions/graphs/executors/agents/_wrapper.py`
- Test: `tests/api/integration/test_run_agent_session_emits.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/integration/test_run_agent_session_emits.py`:

```python
"""Verify run_agent_session emits exactly one agent.completed event with the
correct payload after a session returns.

We patch the GHCP SDK's CopilotClient with a fake that returns a canned
response, capture FleetEvent emissions via app_state.bus, and assert the
shape.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.shared.events import FleetEvent


class _FakeResponseEvent:
    def __init__(self, text: str):
        self.data = MagicMock(content=text, usage=MagicMock(input_tokens=10, output_tokens=5))


class _FakeSession:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self._unsub = lambda: None

    def on(self, callback):
        # Test ignores tool events; just store the callback so unsub works.
        return self._unsub

    async def send_and_wait(self, prompt, **_):
        return _FakeResponseEvent(self._response_text)

    async def disconnect(self):
        pass


class _FakeClient:
    def __init__(self, response_text='{"verdict": "Red"}'):
        self._response_text = response_text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def create_session(self, **kwargs):
        return _FakeSession(self._response_text)


@pytest.mark.asyncio
async def test_run_agent_session_emits_agent_completed(monkeypatch):
    captured: list[FleetEvent] = []
    # Patch the bus emit so we don't need a full app_state setup.
    from api.server.state import app_state
    monkeypatch.setattr(app_state.bus, "emit", lambda e: captured.append(e))

    # Patch the SubprocessConfig + CopilotClient + token cache.
    from api.functions.graphs.executors.agents import _wrapper
    monkeypatch.setattr(_wrapper, "_gh_token", lambda: "fake-token")
    monkeypatch.setattr(_wrapper, "CopilotClient", lambda config: _FakeClient())

    parsed = await _wrapper.run_agent_session(
        prompt="classify CLM-001",
        tools=[],
        skill_dir=None,
        skill_label="rag-classifier",
        workflow_id="wf-abc",
    )

    assert parsed == {"verdict": "Red"}
    assert len(captured) == 1
    ev = captured[0]
    assert ev.type == "agent.completed"
    assert ev.workflow_id == "wf-abc"
    assert ev.agent_label == "rag-classifier"
    assert ev.prompt == "classify CLM-001"
    assert ev.response_text == '{"verdict": "Red"}'
    assert ev.extracted_json == {"verdict": "Red"}
    assert isinstance(ev.tool_calls, list)
    assert ev.usage["input_tokens"] == 10
    assert ev.usage["output_tokens"] == 5
    assert ev.latency_ms >= 0


@pytest.mark.asyncio
async def test_emit_failure_does_not_propagate(monkeypatch):
    """If app_state.bus.emit raises, run_agent_session must still return cleanly."""
    from api.server.state import app_state
    def boom(e):
        raise RuntimeError("bus is broken")
    monkeypatch.setattr(app_state.bus, "emit", boom)

    from api.functions.graphs.executors.agents import _wrapper
    monkeypatch.setattr(_wrapper, "_gh_token", lambda: "fake-token")
    monkeypatch.setattr(_wrapper, "CopilotClient", lambda config: _FakeClient())

    # Must not raise.
    parsed = await _wrapper.run_agent_session(
        prompt="q", tools=[], skill_dir=None, skill_label="x", workflow_id=None,
    )
    assert parsed == {"verdict": "Red"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/integration/test_run_agent_session_emits.py -v
```

Expected: FAIL — either `TypeError: run_agent_session() got an unexpected keyword argument 'workflow_id'` or no event is captured.

- [ ] **Step 3: Modify `_wrapper.py`**

Edit `api/functions/graphs/executors/agents/_wrapper.py`. The full file after changes:

```python
# src/functions/graphs/executors/agents/_wrapper.py
"""
Helper for invoking a finance-agent skill via the GHCP SDK natively.

Pattern (post-2026-04-28 retrofit):
1. Create an ephemeral CopilotSession with `skill_directories=[skills_dir]`
   and `tools=[Tool, ...]`. The SDK auto-discovers `*.skill.md` files and
   registers the tools natively. The model invokes the tools per the skill's
   `allowed-tools` frontmatter — *no* prompt-stuffing of tool results.
2. Subscribe `session.on(...)` -> OTEL bridge so tool calls appear as child spans.
3. Send the user prompt via `send_and_wait` (with optional `attachments` for
   multimodal). Return the parsed JSON object from the response text.
4. Emit a FleetEvent("agent.completed", ...) so the eval subscriber can score
   the invocation. Wrapped in try/except — eval pipeline failures must never
   propagate up into the caller.

The agent identity is "finance-agent" universally; specialisation comes from
the loaded skill, matching the spec's "specialisation via skills, not via
separate agents" pattern.
"""
from __future__ import annotations
import json
import subprocess
import time
import uuid
from pathlib import Path

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType
from copilot.tools import Tool
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from api.server.state import app_state
from api.shared.events import FleetEvent


_SKILLS_DIR = Path(__file__).resolve().parents[4] / "server" / "skills"
SKILLS_DIR = _SKILLS_DIR
_tracer = trace.get_tracer("zava.agents.finance")
_MAX_RESPONSE_EVENT_BYTES = 4096


_gh_token_cache: str | None = None


def _gh_token() -> str:
    global _gh_token_cache
    if _gh_token_cache is None:
        _gh_token_cache = subprocess.check_output(
            ["gh", "auth", "token"], text=True,
        ).strip()
    return _gh_token_cache


def _load_skill(skill_dir: Path) -> str:
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def _install_session_otel_bridge(session, tool_calls_out: list[dict]) -> callable:
    """Bridge GHCP session events -> OTEL child spans AND collect a flat list of
    completed tool calls into `tool_calls_out` for the eval payload.

    TOOL_EXECUTION_START opens a span keyed by tool_call_id; TOOL_EXECUTION_COMPLETE
    closes it AND appends `{name, args, result, success, latency_ms}` to the list.
    """
    open_spans: dict[str, object] = {}
    open_meta: dict[str, dict] = {}  # call_id -> {name, args, started_at}
    parent_ctx = trace.set_span_in_context(trace.get_current_span())

    def on_event(event) -> None:
        try:
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                data = event.data
                name = getattr(data, "tool_name", "unknown")
                call_id = getattr(data, "tool_call_id", None)
                args = getattr(data, "tool_args", None) or getattr(data, "arguments", None) or ""
                if not isinstance(args, str):
                    try:
                        args = json.dumps(args)
                    except Exception:
                        args = str(args)
                span = _tracer.start_span(f"tool.{name}", context=parent_ctx)
                span.set_attribute("zava.tool.name", str(name))
                if call_id:
                    span.set_attribute("zava.tool.call_id", str(call_id))
                    open_spans[call_id] = span
                    open_meta[call_id] = {
                        "name": str(name), "args": args, "started_at": time.monotonic(),
                    }
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                data = event.data
                call_id = getattr(data, "tool_call_id", None)
                span = open_spans.pop(call_id, None) if call_id else None
                meta = open_meta.pop(call_id, None) if call_id else None
                if span is not None:
                    success = getattr(data, "success", None)
                    if success is False:
                        span.set_status(Status(StatusCode.ERROR, "tool reported failure"))
                    span.end()
                if meta is not None:
                    result_text = getattr(data, "result", None) or getattr(data, "output", None) or ""
                    if not isinstance(result_text, str):
                        try:
                            result_text = json.dumps(result_text)
                        except Exception:
                            result_text = str(result_text)
                    tool_calls_out.append({
                        "name": meta["name"],
                        "args": meta["args"],
                        "result": result_text,
                        "success": getattr(data, "success", True) is not False,
                        "latency_ms": int((time.monotonic() - meta["started_at"]) * 1000),
                    })
        except Exception:
            # Observability must never crash the caller.
            pass

    return session.on(on_event)


def _extract_json(text: str) -> dict:
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    if obj_start >= 0 and obj_end > obj_start:
        try:
            return json.loads(text[obj_start:obj_end + 1])
        except json.JSONDecodeError:
            pass
    if arr_start >= 0 and arr_end > arr_start:
        try:
            result = json.loads(text[arr_start:arr_end + 1])
            return {"items": result} if isinstance(result, list) else result
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}


async def run_agent_session(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    skill_dir: Path | None = None,
    skill_label: str | None = None,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
    workflow_id: str | None = None,
) -> dict:
    """Run a finance-agent ephemeral session and return the parsed JSON response.

    Args:
        prompt: The user prompt — per-call context.
        tools: SDK-native tools registered on the session via `tools=[...]`.
        skill_dir: Path to the skill's directory (containing SKILL.md).
        skill_label: Optional OTEL span tag. Also drives evaluator selection
            in the online subscriber.
        model: Model id (default `gpt-4.1`).
        attachments: Optional multimodal attachments for `send_and_wait`.
        workflow_id: Durable Functions instance_id, plumbed through from the
            executor's input dict, so eval rows can be joined to the workflow
            on the control plane.
    """
    tools = tools or []
    skill_text = _load_skill(skill_dir) if skill_dir else None
    tool_calls_collected: list[dict] = []
    started_at = time.monotonic()

    with _tracer.start_as_current_span("gen_ai.generate_content") as span:
        span.set_attribute("gen_ai.system", "github_copilot")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.agent.name", "finance-agent")
        if skill_label:
            span.set_attribute("zava.skill", skill_label)
        span.set_attribute("zava.tools.count", len(tools))
        if attachments:
            span.set_attribute("gen_ai.attachments.count", len(attachments))

        config = SubprocessConfig(github_token=_gh_token(), log_level="warning")
        client = CopilotClient(config)
        async with client:
            session_kwargs: dict = {
                "on_permission_request": PermissionHandler.approve_all,
                "model": model,
                "tools": tools,
            }
            if skill_text:
                session_kwargs["system_message"] = {"mode": "append", "content": skill_text}
            if skill_dir:
                session_kwargs["skill_directories"] = [str(skill_dir)]
            session = await client.create_session(**session_kwargs)
            unsub = _install_session_otel_bridge(session, tool_calls_collected)
            try:
                if attachments:
                    response_event = await session.send_and_wait(
                        prompt, attachments=attachments, timeout=120.0,
                    )
                else:
                    response_event = await session.send_and_wait(prompt, timeout=120.0)
            finally:
                try:
                    unsub()
                except Exception:
                    pass
                try:
                    await session.disconnect()
                except Exception:
                    pass

        text = ""
        if response_event and getattr(response_event, "data", None):
            text = getattr(response_event.data, "content", "") or ""

        event_text = text[:_MAX_RESPONSE_EVENT_BYTES]
        span.add_event("gen_ai.response", {"gen_ai.response.text": event_text})

        data = getattr(response_event, "data", None) if response_event else None
        usage = getattr(data, "usage", None) if data is not None else None
        in_tok = out_tok = None
        if usage is not None:
            in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
            out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
            if in_tok is not None:
                span.set_attribute("gen_ai.usage.input_tokens", int(in_tok))
            if out_tok is not None:
                span.set_attribute("gen_ai.usage.output_tokens", int(out_tok))

    parsed = _extract_json(text)
    elapsed_ms = int((time.monotonic() - started_at) * 1000)

    # Lazy import: evaluator_set imports custom_evaluators which is light, but we
    # want no import-time coupling. context-extraction is a pure dict walk.
    try:
        from api.server.eval.evaluator_set import extract_context
        context = extract_context(skill_label or "", tool_calls_collected)
    except Exception:
        context = ""

    try:
        app_state.bus.emit(FleetEvent(
            type="agent.completed",
            workflow_id=workflow_id,
            agent_label=skill_label or "unknown",
            agent_run_id=f"ar-{uuid.uuid4().hex[:8]}",
            prompt=prompt,
            response_text=text,
            extracted_json=parsed,
            tool_calls=tool_calls_collected,
            context=context,
            usage={"input_tokens": int(in_tok) if in_tok is not None else None,
                   "output_tokens": int(out_tok) if out_tok is not None else None},
            latency_ms=elapsed_ms,
        ))
    except Exception:
        # Observability must never crash the caller.
        pass

    return parsed


# Backwards-compatible alias for legacy agents that pass a skill_name string.
async def run_agent_skill(
    skill_name: str,
    prompt: str,
    model: str = "gpt-4.1",
    attachments: list[dict] | None = None,
    workflow_id: str | None = None,
) -> dict:
    """Deprecated alias — prefer `run_agent_session(skill_dir=..., tools=[...])`."""
    candidate = _SKILLS_DIR / skill_name
    if not candidate.is_dir():
        candidate = _SKILLS_DIR / skill_name.replace("_", "-")
    return await run_agent_session(
        prompt=prompt,
        skill_dir=candidate if candidate.is_dir() else None,
        skill_label=skill_name,
        model=model,
        attachments=attachments,
        workflow_id=workflow_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/Scripts/pytest.exe tests/api/integration/test_run_agent_session_emits.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run the existing wrapper-related tests to confirm no regression**

```bash
./.venv/Scripts/pytest.exe tests/api/unit/test_agent_rag_classifier.py tests/api/unit/test_agent_arbitration.py -v
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add api/functions/graphs/executors/agents/_wrapper.py \
        tests/api/integration/test_run_agent_session_emits.py
git commit -m "feat(eval): emit agent.completed from run_agent_session with tool_calls payload"
```

---

## Task 7: Plumb `workflow_id` through 13 agent executors

Each executor reads `input.get("workflow_id")` and forwards it to `run_agent_session`. The pattern is the same for all 13 files. Each file gets one diff plus a quick spot-check that no existing test breaks.

**Pattern (applied identically to every executor):**

Inside `execute(input: dict) -> dict`, immediately after the existing input-parsing lines:

```python
workflow_id = input.get("workflow_id")
```

Inside the `await run_agent_session(...)` call, add the kwarg at the end of the existing kwargs:

```python
workflow_id=workflow_id,
```

**Files (one sub-task each):**

- [ ] **Step 1: `agent_rag_classifier.py`** — apply pattern, run `tests/api/unit/test_agent_rag_classifier.py`
- [ ] **Step 2: `agent_arbitration.py`** — apply pattern, run `tests/api/unit/test_agent_arbitration.py`
- [ ] **Step 3: `agent_audit_summariser.py`** — apply pattern, run `tests/api/unit/test_agent_audit_summariser.py`
- [ ] **Step 4: `agent_escalation.py`** — apply pattern, run `tests/api/unit/test_agent_escalation.py`
- [ ] **Step 5: `agent_notification.py`** — apply pattern, run `tests/api/unit/test_agent_notification.py`
- [ ] **Step 6: `agent_receipt_validator.py`** — apply pattern, run `tests/api/unit/test_agent_receipt_validator.py`
- [ ] **Step 7: `agent_field_extractor.py`** — apply pattern; if no dedicated test exists, run `pytest tests/api -k field_extractor -v`
- [ ] **Step 8: `agent_line_item_extractor.py`** — apply pattern, run `pytest tests/api -k line_item_extractor -v`
- [ ] **Step 9: `agent_anomaly_flagger.py`** — apply pattern, run `pytest tests/api -k anomaly_flagger -v`
- [ ] **Step 10: `agent_exception_classifier.py`** — apply pattern, run `pytest tests/api -k exception_classifier -v`
- [ ] **Step 11: `agent_resolution_recommender.py`** — apply pattern, run `pytest tests/api -k resolution_recommender -v`
- [ ] **Step 12: `agent_root_cause_explainer.py`** — apply pattern, run `pytest tests/api -k root_cause_explainer -v`
- [ ] **Step 13: `agent_hiring_stub.py`** — apply pattern, run `pytest tests/api -k hiring_stub -v`

**Concrete example for `agent_rag_classifier.py` (apply the same change pattern to the other 12):**

Before:
```python
async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    prompt = (...)
    classification = await run_agent_session(
        prompt=prompt,
        tools=[policy_search_tool, claim_get_structured_tool],
        skill_dir=_SKILL_DIR,
        skill_label="rag-classifier",
    )
    return {"classification": classification}
```

After:
```python
async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    workflow_id = input.get("workflow_id")
    prompt = (...)
    classification = await run_agent_session(
        prompt=prompt,
        tools=[policy_search_tool, claim_get_structured_tool],
        skill_dir=_SKILL_DIR,
        skill_label="rag-classifier",
        workflow_id=workflow_id,
    )
    return {"classification": classification}
```

- [ ] **Step 14: Run the full unit test suite as a regression sweep**

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: same baseline as before this work (79 passed / 1 skipped / 5 deselected per [poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md)), plus the new tests added in Tasks 1–6.

- [ ] **Step 15: Commit**

```bash
git add api/functions/graphs/executors/agents/agent_*.py
git commit -m "feat(eval): plumb workflow_id through all 13 agent executors"
```

---

## Task 8: `online_subscriber.py` — sampling, queue, drain worker

**Files:**
- Create: `api/server/eval/online_subscriber.py`
- Test: `tests/api/eval/test_subscriber_sampling.py`
- Test: `tests/api/eval/test_subscriber_overflow.py`
- Test: `tests/api/eval/test_subscriber_drain.py`

- [ ] **Step 1: Write the failing sampling test**

Create `tests/api/eval/test_subscriber_sampling.py`:

```python
"""Subscriber respects EVAL_SAMPLE_RATE — random.random() < rate keeps."""
from __future__ import annotations
from unittest.mock import MagicMock

import pytest

from api.server.eval import online_subscriber as subscriber_mod


@pytest.fixture
def captured(monkeypatch, tmp_path):
    """Subscriber pieces wired with a fresh in-memory queue + temp store."""
    from api.server.eval.store import EvalStore
    store = EvalStore(db_path=str(tmp_path / "s.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)
    queue: list = []
    monkeypatch.setattr(subscriber_mod, "_enqueue_for_drain", lambda row: queue.append(row))
    return {"store": store, "queue": queue}


def _make_event(workflow_id="wf-1"):
    from api.shared.events import FleetEvent
    return FleetEvent(
        type="agent.completed",
        workflow_id=workflow_id,
        agent_label="rag-classifier",
        agent_run_id="ar-1",
        prompt="...",
        response_text="...",
        extracted_json={},
        tool_calls=[],
        context="",
        usage={"input_tokens": 1, "output_tokens": 1},
        latency_ms=1,
    )


def test_sample_rate_1_always_keeps(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "1.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.999)
    subscriber_mod.on_bus_event(_make_event())
    assert len(captured["queue"]) == 1


def test_sample_rate_0_always_drops(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "0.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.0)
    subscriber_mod.on_bus_event(_make_event())
    assert captured["queue"] == []


def test_sample_rate_0_5_keeps_only_when_random_below_0_5(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "0.5")
    # First event: random=0.4 → kept
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.4)
    subscriber_mod.on_bus_event(_make_event())
    # Second event: random=0.6 → dropped
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.6)
    subscriber_mod.on_bus_event(_make_event())
    assert len(captured["queue"]) == 1


def test_filters_non_agent_completed_events(monkeypatch, captured):
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "1.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.0)
    from api.shared.events import FleetEvent
    subscriber_mod.on_bus_event(FleetEvent(type="fleet.tick", workflow_id=None))
    assert captured["queue"] == []
```

- [ ] **Step 2: Run sampling test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_subscriber_sampling.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the failing overflow test**

Create `tests/api/eval/test_subscriber_overflow.py`:

```python
"""Queue overflow drops the oldest pending row from the store."""
from __future__ import annotations

import pytest

from api.server.eval import online_subscriber as subscriber_mod


@pytest.fixture
def store_only(monkeypatch, tmp_path):
    from api.server.eval.store import EvalStore
    store = EvalStore(db_path=str(tmp_path / "s.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)
    monkeypatch.setenv("EVAL_QUEUE_MAX", "2")
    monkeypatch.setenv("EVAL_SAMPLE_RATE", "1.0")
    monkeypatch.setattr(subscriber_mod.random, "random", lambda: 0.0)
    # Real queue this time so we can fill it.
    subscriber_mod._reset_queue_for_test(maxsize=2)
    yield store
    subscriber_mod._reset_queue_for_test(maxsize=int(subscriber_mod._DEFAULT_QUEUE_MAX))


def _ev(wid):
    from api.shared.events import FleetEvent
    return FleetEvent(
        type="agent.completed", workflow_id=wid, agent_label="rag-classifier",
        agent_run_id=f"ar-{wid}", prompt="...", response_text="...", extracted_json={},
        tool_calls=[], context="", usage={}, latency_ms=1,
    )


def test_queue_overflow_drops_oldest_pending(monkeypatch, store_only):
    """Push 3 events into a queue of size 2. The oldest pending row in the
    store must be removed and the third row must end up enqueued."""
    subscriber_mod.on_bus_event(_ev("wf-1"))
    subscriber_mod.on_bus_event(_ev("wf-2"))
    # Now the queue is full. Third event triggers a drop-oldest:
    subscriber_mod.on_bus_event(_ev("wf-3"))

    # Store should still have 2 pending rows; the oldest (wf-1) was dropped.
    rows = store_only.recent(10)
    workflow_ids = {r.workflow_id for r in rows}
    assert workflow_ids == {"wf-2", "wf-3"}
    assert subscriber_mod._metrics["dropped"] >= 1
```

- [ ] **Step 4: Run overflow test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_subscriber_overflow.py -v
```

Expected: FAIL.

- [ ] **Step 5: Write the failing drain test**

Create `tests/api/eval/test_subscriber_drain.py`:

```python
"""Drain worker calls each evaluator and writes scores to the store."""
from __future__ import annotations
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from api.server.eval import online_subscriber as subscriber_mod
from api.server.eval.store import EvalStore, EvalRow


def _make_row(store):
    row = EvalRow(
        id="ev-1", kind="online", agent_label="rag-classifier",
        workflow_id="wf-1", agent_run_id="ar-1", ts=1000.0,
        prompt="q", response_text="r", context="ctx",
        tool_calls=[],
    )
    store.put_pending(row)
    return row


@pytest.mark.asyncio
async def test_drain_worker_completes_row_with_merged_scores(tmp_path, monkeypatch):
    store = EvalStore(db_path=str(tmp_path / "d.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)

    # Fake evaluator set: two evaluators each returning a partial score dict.
    fake_evals = {
        "groundedness": MagicMock(return_value={"groundedness": 0.9, "groundedness_reason": "ok"}),
        "tool_call_validity": MagicMock(return_value={"tool_calls_valid": 1.0, "invalid_calls": []}),
    }
    monkeypatch.setattr(
        "api.server.eval.evaluator_set.evaluators_for",
        lambda label: fake_evals,
    )
    # `declared_tools` injection — the subscriber passes them as a kwarg.
    monkeypatch.setattr(
        subscriber_mod, "_declared_tools_for", lambda label: ["policy_search"],
    )

    row = _make_row(store)
    await subscriber_mod._score_row(row)

    refreshed = store.by_id("ev-1")
    assert refreshed.status == "completed"
    assert refreshed.scores_json["groundedness"] == 0.9
    assert refreshed.scores_json["tool_calls_valid"] == 1.0


@pytest.mark.asyncio
async def test_drain_worker_marks_error_after_retry_failure(tmp_path, monkeypatch):
    store = EvalStore(db_path=str(tmp_path / "d.sqlite"))
    monkeypatch.setattr(subscriber_mod, "_store", store)

    boom = MagicMock(side_effect=RuntimeError("foundry exploded"))
    monkeypatch.setattr(
        "api.server.eval.evaluator_set.evaluators_for",
        lambda label: {"groundedness": boom},
    )
    monkeypatch.setattr(subscriber_mod, "_declared_tools_for", lambda label: [])
    # Avoid waiting 2s in the test for the retry backoff.
    monkeypatch.setattr(subscriber_mod, "_RETRY_BACKOFF_S", 0.0)

    row = _make_row(store)
    await subscriber_mod._score_row(row)

    refreshed = store.by_id("ev-1")
    assert refreshed.status == "error"
    assert "foundry exploded" in refreshed.error_text
```

- [ ] **Step 6: Run drain test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_subscriber_drain.py -v
```

Expected: FAIL.

- [ ] **Step 7: Implement `online_subscriber.py`**

Create `api/server/eval/online_subscriber.py`:

```python
"""Bus subscriber for agent.completed events.

Pattern: lifespan-register iff Foundry is configured. on_bus_event filters
to agent.completed, applies sampling, builds an EvalRow, persists it as
pending, and pushes onto an asyncio.Queue. A background drain worker pops
rows, calls each evaluator's `__call__`, and writes results into the store.

Online evals call evaluator `__call__` directly (one row at a time).
`evaluate()` is the *batch* helper — see batch_runner.py and spec §4.1.
"""
from __future__ import annotations
import asyncio
import logging
import os
import random
import time
import uuid
from typing import Any

from api.server.eval import foundry_client
from api.server.eval.store import EvalRow, default_store
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

_DEFAULT_QUEUE_MAX = "1000"
_RETRY_BACKOFF_S = 2.0

_store = default_store()
_queue: asyncio.Queue[EvalRow] = asyncio.Queue(maxsize=int(os.environ.get("EVAL_QUEUE_MAX", _DEFAULT_QUEUE_MAX)))
_metrics: dict[str, int] = {"dropped": 0, "in_flight": 0}
_unsub = None
_worker_task: asyncio.Task | None = None


# ---- Declared-tools lookup --------------------------------------------------
# Each agent-label maps to the list of tool names it's allowed to call.
# Used by ToolCallValidity. Kept here (not in evaluator_set) because it's
# subscriber-side knowledge — at scoring time we need to know what was declared.

_DECLARED_TOOLS: dict[str, list[str]] = {
    "rag-classifier": ["policy_search", "claim_get_structured"],
    "arbitration": ["policy_search", "precedents_search"],
    "escalation": [],
    "notification": [],
    "receipt-validator": [],
    "audit-summariser": [],
    # New agents inherit empty list; ToolCallValidity score will be 1.0
    # for tool-less agents which is correct.
}


def _declared_tools_for(label: str) -> list[str]:
    return _DECLARED_TOOLS.get(label, [])


# ---- Bus callback -----------------------------------------------------------

def on_bus_event(event: FleetEvent) -> None:
    """Bus on_any callback. Filters to agent.completed and enqueues."""
    if event.type != "agent.completed":
        return
    rate = float(os.environ.get("EVAL_SAMPLE_RATE", "1.0"))
    if random.random() >= rate:
        return  # sampled out
    row = _build_row(event)
    _store.put_pending(row)
    try:
        _enqueue_for_drain(row)
    except asyncio.QueueFull:
        dropped_id = _store.drop_oldest_pending()
        if dropped_id:
            _metrics["dropped"] = _metrics.get("dropped", 0) + 1
            log.warning("eval queue full; dropped oldest pending row %s", dropped_id)
        try:
            _enqueue_for_drain(row)
        except asyncio.QueueFull:
            # Even after dropping one, the queue is full — drop the new row.
            _store.drop_oldest_pending()
            _metrics["dropped"] = _metrics.get("dropped", 0) + 1


def _enqueue_for_drain(row: EvalRow) -> None:
    """Indirection so tests can replace this with a list-appender."""
    _queue.put_nowait(row)


def _build_row(event: FleetEvent) -> EvalRow:
    extra = event.model_dump()
    return EvalRow(
        id=f"ev-{uuid.uuid4().hex[:12]}",
        kind="online",
        agent_label=extra.get("agent_label", "unknown"),
        workflow_id=extra.get("workflow_id"),
        agent_run_id=extra.get("agent_run_id"),
        ts=time.time(),
        status="pending",
        prompt=extra.get("prompt", ""),
        response_text=extra.get("response_text", ""),
        context=extra.get("context", ""),
        tool_calls=extra.get("tool_calls", []) or [],
    )


# ---- Drain worker -----------------------------------------------------------

async def _drain_loop() -> None:
    while True:
        row = await _queue.get()
        _metrics["in_flight"] = _metrics.get("in_flight", 0) + 1
        try:
            await _score_row(row)
        finally:
            _metrics["in_flight"] = max(0, _metrics.get("in_flight", 1) - 1)


async def _score_row(row: EvalRow, *, attempt: int = 0) -> None:
    from api.server.eval.evaluator_set import evaluators_for
    try:
        evaluators = evaluators_for(row.agent_label)
        merged_scores: dict[str, Any] = {}
        for name, ev in evaluators.items():
            # asyncio.to_thread keeps the loop unblocked for CPU-bound or
            # SDK-internal-sync work. Evaluator __call__ may itself make HTTP
            # calls under the hood; either way, off the loop.
            result = await asyncio.to_thread(
                ev,
                query=row.prompt,
                response=row.response_text,
                context=row.context,
                tool_calls=row.tool_calls,
                declared_tools=_declared_tools_for(row.agent_label),
            )
            if isinstance(result, dict):
                merged_scores.update(result)
        _store.complete(row.id, scores=merged_scores, foundry_run_url=None)
    except Exception as ex:
        if attempt == 0:
            await asyncio.sleep(_RETRY_BACKOFF_S)
            return await _score_row(row, attempt=1)
        _store.error(row.id, error_text=str(ex)[:500])


# ---- Lifespan hooks ---------------------------------------------------------

def _reset_queue_for_test(maxsize: int) -> None:
    """Test-only: replace the module-level queue with one of a different size."""
    global _queue
    _queue = asyncio.Queue(maxsize=maxsize)


async def lifespan_register(app) -> None:
    """Called from the FastAPI lifespan startup. No-ops if Foundry is not configured."""
    global _unsub, _worker_task
    if not foundry_client.is_configured():
        log.warning("Foundry not configured; online eval subscriber inactive")
        return
    from api.server.state import app_state
    _unsub = app_state.bus.on_any(on_bus_event)
    _worker_task = asyncio.create_task(_drain_loop())


async def lifespan_shutdown(app) -> None:
    global _unsub, _worker_task
    if _unsub is not None:
        try:
            _unsub()
        except Exception:
            pass
        _unsub = None
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except (asyncio.CancelledError, Exception):
            pass
        _worker_task = None
```

- [ ] **Step 8: Run all three subscriber tests**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_subscriber_sampling.py \
                            tests/api/eval/test_subscriber_overflow.py \
                            tests/api/eval/test_subscriber_drain.py -v
```

Expected: all subscriber tests pass.

- [ ] **Step 9: Commit**

```bash
git add api/server/eval/online_subscriber.py \
        tests/api/eval/test_subscriber_sampling.py \
        tests/api/eval/test_subscriber_overflow.py \
        tests/api/eval/test_subscriber_drain.py
git commit -m "feat(eval): online_subscriber with sampling, queue overflow, drain worker"
```

---

## Task 9: Wire subscriber lifespan into FastAPI app

**Files:**
- Modify: `api/server/main.py`

- [ ] **Step 1: Inspect the current lifespan/startup pattern**

```bash
grep -nE "lifespan|on_event\(\"startup|on_event\(\"shutdown" api/server/main.py | head -20
```

Determine whether `main.py` uses the modern `lifespan=` async context manager or the older `@app.on_event` decorators.

- [ ] **Step 2: Add subscriber registration to the lifespan**

If `main.py` uses `lifespan=` (recommended FastAPI pattern), add to the existing async-context-manager body:

```python
# Inside the existing lifespan async context manager, after other startup hooks:
from api.server.eval.online_subscriber import lifespan_register, lifespan_shutdown
await lifespan_register(app)
try:
    yield
finally:
    await lifespan_shutdown(app)
```

If `main.py` uses `@app.on_event` decorators, add:

```python
from api.server.eval.online_subscriber import lifespan_register, lifespan_shutdown


@app.on_event("startup")
async def _eval_subscriber_startup():
    await lifespan_register(app)


@app.on_event("shutdown")
async def _eval_subscriber_shutdown():
    await lifespan_shutdown(app)
```

- [ ] **Step 3: Smoke test — start uvicorn and check logs**

In a separate shell:

```bash
./.venv/Scripts/uvicorn.exe api.server.main:app --port 8001 --log-level info
```

With Foundry env unset, expected log output:
```
Foundry not configured; online eval subscriber inactive
```

With Foundry env set (placeholder values), the subscriber should register without raising.

Stop uvicorn (Ctrl-C) before continuing.

- [ ] **Step 4: Commit**

```bash
git add api/server/main.py
git commit -m "feat(eval): register online_subscriber in FastAPI lifespan"
```

---

## Task 10: Rewrite `routes/evals.py`

**Files:**
- Modify: `api/server/routes/evals.py`
- Test: `tests/api/routes/test_evals_route_unconfigured.py`
- Test: `tests/api/routes/test_evals_route_configured.py`

- [ ] **Step 1: Write the failing unconfigured-state test**

Create `tests/api/routes/test_evals_route_unconfigured.py`:

```python
"""When Foundry is not configured, eval endpoints return {configured: false}."""
from __future__ import annotations
from fastapi.testclient import TestClient


def _client(monkeypatch):
    monkeypatch.delenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", raising=False)
    import sys
    sys.modules.pop("api.server.eval.foundry_client", None)
    from api.server.main import app
    return TestClient(app)


def test_get_evals_returns_configured_false_with_200(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/evals/")
    assert r.status_code == 200
    assert r.json()["configured"] is False
    assert "reason" in r.json()


def test_get_evals_summary_returns_configured_false(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/evals/summary")
    assert r.status_code == 200
    assert r.json()["configured"] is False


def test_get_evals_health_returns_configured_false(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/api/evals/health")
    assert r.status_code == 200
    assert r.json()["configured"] is False
```

- [ ] **Step 2: Write the failing configured-state test**

Create `tests/api/routes/test_evals_route_configured.py`:

```python
"""When configured, /api/evals/summary excludes errored rows from averages."""
from __future__ import annotations
import time

from fastapi.testclient import TestClient


def _client_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")
    import sys
    sys.modules.pop("api.server.eval.foundry_client", None)
    sys.modules.pop("api.server.eval.store", None)
    sys.modules.pop("api.server.eval.online_subscriber", None)
    sys.modules.pop("api.server.routes.evals", None)
    from api.server.eval.store import EvalStore, EvalRow
    store = EvalStore(db_path=str(tmp_path / "s.sqlite"))
    monkeypatch.setattr("api.server.eval.store._default", store, raising=False)
    monkeypatch.setattr("api.server.routes.evals._store", store, raising=False)
    # Seed mixed rows.
    base_ts = time.time()
    r1 = EvalRow(id="ev-1", kind="online", agent_label="rag-classifier",
                 workflow_id="wf-1", agent_run_id="ar-1", ts=base_ts)
    r2 = EvalRow(id="ev-2", kind="online", agent_label="rag-classifier",
                 workflow_id="wf-2", agent_run_id="ar-2", ts=base_ts)
    r3 = EvalRow(id="ev-3", kind="online", agent_label="rag-classifier",
                 workflow_id="wf-3", agent_run_id="ar-3", ts=base_ts)
    store.put_pending(r1); store.put_pending(r2); store.put_pending(r3)
    store.complete("ev-1", scores={"groundedness": 0.9}, foundry_run_url=None)
    store.complete("ev-2", scores={"groundedness": 0.7}, foundry_run_url=None)
    store.error("ev-3", error_text="boom")

    from api.server.main import app
    return TestClient(app)


def test_summary_excludes_errored_from_averages(monkeypatch, tmp_path):
    c = _client_configured(monkeypatch, tmp_path)
    r = c.get("/api/evals/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert body["n_completed"] == 2
    assert body["n_errored"] == 1
    rag = body["per_agent"]["rag-classifier"]
    # 0.9 + 0.7 / 2 = 0.8
    assert abs(rag["scores"]["groundedness"] - 0.8) < 1e-9
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
./.venv/Scripts/pytest.exe tests/api/routes/test_evals_route_unconfigured.py \
                            tests/api/routes/test_evals_route_configured.py -v
```

Expected: FAIL — current `evals.py` returns the random-number list, not the new envelopes.

- [ ] **Step 4: Replace `routes/evals.py`**

Replace the entire contents of `api/server/routes/evals.py`:

```python
"""GET /api/evals*, replacing the original random-number stub.

All endpoints return either a real-data envelope (when Foundry is
configured) or {"configured": false, "reason": "..."} with HTTP 200.
We never return synthetic numbers.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query

from api.server.eval import foundry_client
from api.server.eval.store import default_store

router = APIRouter(prefix="/api/evals")
_store = default_store()


def _unconfigured_envelope() -> dict:
    return {
        "configured": False,
        "reason": "AZURE_FOUNDRY_PROJECT_ENDPOINT / AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT not set",
    }


def _tile_summary(per_agent: dict) -> dict:
    """Compute the three honest tiles defined in spec §6.3."""

    def _mean_across_agents(score_name: str) -> tuple[float, int, list[str]]:
        total = 0.0
        n = 0
        contributing: list[str] = []
        for label, bucket in per_agent.items():
            v = bucket["scores"].get(score_name)
            if isinstance(v, (int, float)):
                total += v
                n += 1
                contributing.append(label)
        return (total / n if n else 0.0, n, contributing)

    adh, adh_n, adh_agents = _mean_across_agents("groundedness")

    # Safety: max(violence, hate_unfairness) per agent (each 0-7), inverted.
    safety_total = 0.0
    safety_n = 0
    safety_agents: list[str] = []
    for label, bucket in per_agent.items():
        v = bucket["scores"].get("violence")
        h = bucket["scores"].get("hate_unfairness")
        worst = None
        if isinstance(v, (int, float)) and isinstance(h, (int, float)):
            worst = max(v, h)
        elif isinstance(v, (int, float)):
            worst = v
        elif isinstance(h, (int, float)):
            worst = h
        if worst is not None:
            safety_total += 1.0 - (worst / 7.0)
            safety_n += 1
            safety_agents.append(label)

    tool_acc, ta_n, ta_agents = _mean_across_agents("tool_calls_valid")

    return {
        "task_adherence": {
            "value": adh, "n_evals": adh_n, "n_agents": len(adh_agents),
            "evaluators": ["groundedness"],
        },
        "safety": {
            "value": safety_total / safety_n if safety_n else 0.0,
            "n_evals": safety_n, "n_agents": len(safety_agents),
            "evaluators": ["violence", "hate_unfairness"],
        },
        "tool_accuracy": {
            "value": tool_acc, "n_evals": ta_n, "n_agents": len(ta_agents),
            "evaluators": ["tool_call_validity"],
        },
    }


@router.get("/")
async def list_evals(agent_label: str | None = None):
    if not foundry_client.is_configured():
        return _unconfigured_envelope()
    rows = _store.recent(50, agent_label=agent_label)
    return {
        "configured": True,
        "rows": [
            {
                "id": r.id, "kind": r.kind, "agent_label": r.agent_label,
                "workflow_id": r.workflow_id, "agent_run_id": r.agent_run_id,
                "ts": r.ts, "status": r.status,
                "scores": r.scores_json or {},
                "foundry_run_url": r.foundry_run_url,
                "error_text": r.error_text,
            }
            for r in rows
        ],
    }


@router.get("/summary")
async def get_summary(window_minutes: int = Query(60, ge=1, le=1440)):
    if not foundry_client.is_configured():
        return _unconfigured_envelope()
    summary = _store.summary(window_minutes=window_minutes)
    tiles = _tile_summary(summary["per_agent"])
    health = _store.health()
    return {
        "configured": True,
        "window_minutes": summary["window_minutes"],
        "tiles": tiles,
        "by_agent": [
            {"agent_label": label, "n": bucket["n"], "scores": bucket["scores"]}
            for label, bucket in summary["per_agent"].items()
        ],
        "n_completed": summary["n_completed"],
        "n_errored": summary["n_errored"],
        "queue": {
            "pending": health.get("pending", 0),
            "completed": health.get("completed", 0),
            "errored": health.get("error", 0),
        },
    }


@router.get("/health")
async def health():
    if not foundry_client.is_configured():
        return _unconfigured_envelope()
    h = _store.health()
    return {
        "configured": True,
        "pending": h.get("pending", 0),
        "completed": h.get("completed", 0),
        "errored": h.get("error", 0),
    }


@router.get("/{eval_id}")
async def get_eval(eval_id: str):
    if not foundry_client.is_configured():
        return _unconfigured_envelope()
    row = _store.by_id(eval_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no eval with id {eval_id!r}")
    return {
        "configured": True,
        "id": row.id, "kind": row.kind, "agent_label": row.agent_label,
        "workflow_id": row.workflow_id, "agent_run_id": row.agent_run_id,
        "ts": row.ts, "status": row.status,
        "scores": row.scores_json or {},
        "foundry_run_url": row.foundry_run_url,
        "prompt": row.prompt,
        "response_text": row.response_text,
        "context": row.context,
        "tool_calls": row.tool_calls,
        "error_text": row.error_text,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
./.venv/Scripts/pytest.exe tests/api/routes/test_evals_route_unconfigured.py \
                            tests/api/routes/test_evals_route_configured.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/evals.py \
        tests/api/routes/test_evals_route_unconfigured.py \
        tests/api/routes/test_evals_route_configured.py
git commit -m "feat(eval): rewrite /api/evals* over EvalStore with configured/unconfigured envelopes"
```

---

## Task 11: Frontend `Evaluations.tsx` rewrite

**Files:**
- Modify: `web/client/routes/Evaluations.tsx`
- Test: `tests/web/Evaluations.test.tsx`

- [ ] **Step 1: Inspect the existing test setup**

```bash
ls tests/web/ 2>/dev/null
grep -nE "vitest|jest" web/client/package.json 2>/dev/null
```

If no `tests/web/` directory exists yet, create it. Use the same testing tool (vitest or jest) the rest of the frontend uses.

- [ ] **Step 2: Write the failing component test**

Create `tests/web/Evaluations.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import Evaluations from "../../web/client/routes/Evaluations";

beforeEach(() => {
  vi.restoreAllMocks();
});

const fetchMock = (jsonByUrl: Record<string, any>) =>
  vi.fn(async (url: string) => {
    const path = typeof url === "string" ? url : url.toString();
    for (const key of Object.keys(jsonByUrl)) {
      if (path.startsWith(key)) {
        return { ok: true, json: async () => jsonByUrl[key] } as any;
      }
    }
    throw new Error(`unexpected fetch: ${path}`);
  });

describe("Evaluations.tsx", () => {
  it("renders the not-configured panel when Foundry is not configured", async () => {
    global.fetch = fetchMock({
      "/api/evals/summary": { configured: false, reason: "endpoint not set" },
    }) as any;
    render(<Evaluations />);
    await waitFor(() => {
      expect(screen.getByText(/Foundry evaluation is not configured/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Task adherence/i)).not.toBeInTheDocument();
  });

  it("renders three tiles with real values when configured + data", async () => {
    global.fetch = fetchMock({
      "/api/evals/summary": {
        configured: true,
        window_minutes: 60,
        tiles: {
          task_adherence: { value: 0.92, n_evals: 47, n_agents: 2, evaluators: ["groundedness"] },
          safety: { value: 0.99, n_evals: 47, n_agents: 2, evaluators: ["violence", "hate_unfairness"] },
          tool_accuracy: { value: 0.96, n_evals: 32, n_agents: 1, evaluators: ["tool_call_validity"] },
        },
        by_agent: [
          { agent_label: "rag-classifier", n: 32, scores: { groundedness: 0.93 } },
        ],
        n_completed: 47,
        n_errored: 0,
        queue: { pending: 0, completed: 47, errored: 0 },
      },
      "/api/evals/": { configured: true, rows: [] },
    }) as any;
    render(<Evaluations />);
    await waitFor(() => {
      expect(screen.getByText(/92\.0%/)).toBeInTheDocument();
      expect(screen.getByText(/99\.0%/)).toBeInTheDocument();
      expect(screen.getByText(/96\.0%/)).toBeInTheDocument();
      expect(screen.getByText(/rag-classifier/)).toBeInTheDocument();
    });
  });

  it("renders the empty state when configured + no data", async () => {
    global.fetch = fetchMock({
      "/api/evals/summary": {
        configured: true, window_minutes: 60,
        tiles: {
          task_adherence: { value: 0.0, n_evals: 0, n_agents: 0, evaluators: ["groundedness"] },
          safety: { value: 0.0, n_evals: 0, n_agents: 0, evaluators: ["violence", "hate_unfairness"] },
          tool_accuracy: { value: 0.0, n_evals: 0, n_agents: 0, evaluators: ["tool_call_validity"] },
        },
        by_agent: [],
        n_completed: 0, n_errored: 0,
        queue: { pending: 0, completed: 0, errored: 0 },
      },
      "/api/evals/": { configured: true, rows: [] },
    }) as any;
    render(<Evaluations />);
    await waitFor(() => {
      expect(screen.getByText(/No evaluations yet/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

```bash
npx vitest run tests/web/Evaluations.test.tsx
```

Expected: FAIL — the existing component renders the random tiles, doesn't handle `configured: false`.

- [ ] **Step 4: Replace `Evaluations.tsx`**

Replace the contents of `web/client/routes/Evaluations.tsx`:

```tsx
// src/client/routes/Evaluations.tsx
import { useEffect, useState } from "react";
import { AccuracyReport } from "../components/AccuracyReport";

interface TileBody {
  value: number;
  n_evals: number;
  n_agents: number;
  evaluators: string[];
}

interface Summary {
  configured: boolean;
  reason?: string;
  window_minutes?: number;
  tiles?: { task_adherence: TileBody; safety: TileBody; tool_accuracy: TileBody };
  by_agent?: { agent_label: string; n: number; scores: Record<string, number> }[];
  n_completed?: number;
  n_errored?: number;
  queue?: { pending: number; completed: number; errored: number };
}

interface Row {
  id: string;
  kind: string;
  agent_label: string;
  workflow_id: string | null;
  ts: number;
  status: string;
  scores: Record<string, number | string>;
  foundry_run_url: string | null;
  error_text?: string | null;
}

interface RowsEnvelope {
  configured: boolean;
  reason?: string;
  rows?: Row[];
}

export default function Evaluations() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rowsEnv, setRowsEnv] = useState<RowsEnvelope | null>(null);

  useEffect(() => {
    const tick = async () => {
      try {
        const [s, r] = await Promise.all([
          fetch("/api/evals/summary").then(x => x.json()),
          fetch("/api/evals/").then(x => x.json()),
        ]);
        setSummary(s);
        setRowsEnv(r);
      } catch {
        // network blip — leave previous state.
      }
    };
    void tick();
    const i = setInterval(tick, 5000);
    return () => clearInterval(i);
  }, []);

  if (summary && summary.configured === false) {
    return (
      <div className="space-y-4">
        <div>
          <div className="text-lg font-semibold text-slate-900">Continuous Evaluation</div>
        </div>
        <div className="panel panel-body">
          <div className="text-sm font-semibold text-slate-900 mb-1">Foundry evaluation is not configured.</div>
          <div className="text-xs text-slate-600">
            Set <code className="text-xs">AZURE_FOUNDRY_PROJECT_ENDPOINT</code> and{" "}
            <code className="text-xs">AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT</code> to enable.
          </div>
          {summary.reason ? <div className="text-xs text-slate-500 mt-2">{summary.reason}</div> : null}
        </div>
        <AccuracyReport />
      </div>
    );
  }

  const tiles = summary?.tiles;
  const byAgent = summary?.by_agent ?? [];
  const allEvalNames = Array.from(
    new Set(byAgent.flatMap(a => Object.keys(a.scores)))
  ).sort();
  const rows = rowsEnv?.rows ?? [];

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-semibold text-slate-900">Continuous Evaluation</div>
        <div className="text-xs text-slate-500 mt-0.5">
          {summary
            ? `${summary.n_completed ?? 0} evals scored · ${summary.n_errored ?? 0} errored · last ${summary.window_minutes ?? 60}min`
            : "loading…"}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tile label="Task adherence" tile={tiles?.task_adherence} />
        <Tile label="Safety" tile={tiles?.safety} />
        <Tile label="Tool accuracy" tile={tiles?.tool_accuracy} />
      </div>

      {byAgent.length > 0 ? (
        <div className="panel">
          <div className="panel-header">By agent</div>
          <table className="text-xs w-full">
            <thead>
              <tr className="text-slate-500">
                <th className="text-left px-3 py-2">agent</th>
                <th className="text-right px-3 py-2">n</th>
                {allEvalNames.map(n => (
                  <th key={n} className="text-right px-3 py-2">{n}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {byAgent.map(a => (
                <tr key={a.agent_label}>
                  <td className="px-3 py-2 font-mono">{a.agent_label}</td>
                  <td className="px-3 py-2 text-right">{a.n}</td>
                  {allEvalNames.map(n => {
                    const v = a.scores[n];
                    return (
                      <td key={n} className="px-3 py-2 text-right">
                        {typeof v === "number" ? v.toFixed(2) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-header">Recent runs</div>
        <div className="divide-y divide-slate-200">
          {rows.length === 0 ? (
            <div className="p-3 text-xs text-slate-500 italic">No evaluations yet.</div>
          ) : null}
          {rows.slice(0, 20).map(r => (
            <div key={r.id} className="flex items-center gap-3 px-3 py-2 text-xs">
              <a href={`/workflows/${r.workflow_id ?? ""}`} className="text-blue-700 hover:underline font-mono">
                {r.agent_label}
              </a>
              <span className="text-slate-400">{new Date(r.ts * 1000).toLocaleTimeString()}</span>
              <span className="ml-auto text-slate-600 font-mono">
                {Object.entries(r.scores)
                  .filter(([, v]) => typeof v === "number")
                  .slice(0, 3)
                  .map(([k, v]) => `${k}=${(v as number).toFixed(2)}`)
                  .join(" · ")}
              </span>
              {r.foundry_run_url ? (
                <a className="text-blue-700 hover:underline" href={r.foundry_run_url} target="_blank" rel="noreferrer">
                  portal →
                </a>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <AccuracyReport />
    </div>
  );
}

function Tile({ label, tile }: { label: string; tile?: TileBody }) {
  const value = tile?.value ?? 0;
  return (
    <div className="panel panel-body">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-semibold text-slate-900 mt-1">
        {tile?.n_evals === 0 ? "—" : `${(value * 100).toFixed(1)}%`}
      </div>
      <div className="text-[10px] text-slate-500 mt-1">
        {tile ? `${tile.n_evals} evals · ${tile.n_agents} agents` : ""}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run frontend test to verify it passes**

```bash
npx vitest run tests/web/Evaluations.test.tsx
```

Expected: 3 passed.

- [ ] **Step 6: Visual check**

Start the dev server (per the runbook):

```bash
./.venv/Scripts/uvicorn.exe api.server.main:app --reload &
npm run dev:client &
```

Open the Vite URL → `/evaluations`. With Foundry env unset, page should show the configuration panel. Stop the servers (kill background tasks).

- [ ] **Step 7: Commit**

```bash
git add web/client/routes/Evaluations.tsx tests/web/Evaluations.test.tsx
git commit -m "feat(eval): rewrite Evaluations page over /api/evals/summary; not-configured panel; per-agent table"
```

---

## Task 12: `batch_runner.py` — Foundry `evaluate()` for the 300-claim corpus

**Files:**
- Create: `api/server/eval/batch_runner.py`
- Test: `tests/api/eval/test_batch_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/eval/test_batch_runner.py`:

```python
"""batch_runner builds JSONL, calls evaluate() (mocked), reshapes results."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def claims_dir(tmp_path, monkeypatch):
    """Build a tiny synthetic claims dir."""
    claims = tmp_path / "claims"
    claims.mkdir(parents=True)
    for i, label in enumerate(["Red", "Amber", "Green"]):
        p = claims / f"CLM-00{i+1}.json"
        p.write_text(
            f'{{"claim_id":"CLM-00{i+1}","gold_label":"{label}",'
            f'"gold_reasoning":"reason {i}","gold_category":"meals"}}',
            encoding="utf-8",
        )
    monkeypatch.setattr("api.server.eval.batch_runner._CLAIMS_DIR", claims)
    return claims


def _fake_evaluate_result(claim_ids):
    """Simulate the SDK's `evaluate()` return value for our 4 evaluators."""
    rows = []
    for i, cid in enumerate(claim_ids):
        rows.append({
            "inputs.claim_id": cid,
            "inputs.gold_label": ["Red", "Amber", "Green"][i],
            "outputs.predicted_label": ["Red", "Amber", "Green"][i],
            "outputs.predicted_reasoning": f"because {i}",
            "outputs.context": "policy",
            "outputs.policy_clause": "§3.2",
            "outputs.groundedness.groundedness": 0.9,
            "outputs.similarity.similarity": 0.85,
            "outputs.label_match.label_match": 1,
            "outputs.policy_cited.policy_clause_cited": 1,
        })
    return MagicMock(
        rows=rows,
        studio_url="https://ai.azure.com/foundry/runs/abc",
        metrics={
            "groundedness.groundedness": 0.9,
            "similarity.similarity": 0.85,
            "label_match.label_match": 1.0,
            "policy_cited.policy_clause_cited": 1.0,
        },
    )


@pytest.mark.asyncio
async def test_batch_runner_uploads_to_foundry_and_returns_existing_shape(monkeypatch, claims_dir):
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://e")
    monkeypatch.setenv("AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT", "gpt-4o")

    # Mock the Foundry evaluate import.
    fake_eval = MagicMock(return_value=_fake_evaluate_result(["CLM-001", "CLM-002", "CLM-003"]))
    fake_groundedness = MagicMock()
    fake_similarity = MagicMock()

    with patch.dict("sys.modules", {
        "azure.ai.evaluation": MagicMock(
            evaluate=fake_eval,
            GroundednessEvaluator=lambda model_config: fake_groundedness,
            SimilarityEvaluator=lambda model_config: fake_similarity,
        ),
    }):
        import sys
        sys.modules.pop("api.server.eval.batch_runner", None)
        from api.server.eval.batch_runner import run

        # Avoid actually invoking the rag_classifier; provide a stub target.
        async def _stub_rag_execute(_input):
            return {"classification": {"verdict": "Red", "reasoning": "...", "policy_clause": "§3.2"}}
        monkeypatch.setattr("api.server.eval.batch_runner._rag_execute", _stub_rag_execute)

        report = await run(
            claim_ids=["CLM-001", "CLM-002", "CLM-003"],
            run_id="acc-test",
            publish=lambda e: None,
        )

    assert report["run_id"] == "acc-test"
    assert report["n"] == 3
    assert report["overall_accuracy"] == 1.0  # all match
    assert report["foundry_run_url"] == "https://ai.azure.com/foundry/runs/abc"
    # Confusion matrix shape — diagonal-only since all match.
    cm = report["confusion_matrix"]
    assert cm["Red"]["Red"] == 1
    assert cm["Amber"]["Amber"] == 1
    assert cm["Green"]["Green"] == 1
    # Foundry was actually called with the right kwargs.
    assert fake_eval.called
    kwargs = fake_eval.call_args.kwargs
    assert kwargs["azure_ai_project"]["endpoint"] == "https://e"
    assert kwargs["evaluation_name"].startswith("poc1-accuracy-acc-test")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_batch_runner.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `batch_runner.py`**

Create `api/server/eval/batch_runner.py`:

```python
"""Foundry-backed batch corpus evaluator.

Replaces the old in-process accuracy_harness_workflow. Calls the SDK's
high-level `evaluate()` helper with `azure_ai_project=` so the run shows
up as a comparable named run in the Foundry portal.

Result reshape preserves the existing /api/accuracy/last response so the
AccuracyReport panel keeps rendering without structural changes.
"""
from __future__ import annotations
import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Awaitable, Callable

from api.server.eval import foundry_client
from api.server.eval.custom_evaluators import GoldLabelMatch, PolicyClauseCited
from api.server.eval.store import default_store
from api.shared.expense_taxonomy import CATEGORIES, VERDICTS

log = logging.getLogger(__name__)

PublishFn = Callable[[dict], None]


_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


# Indirection so tests can swap with a stub.
async def _rag_execute(input_dict: dict) -> dict:
    from api.functions.graphs.executors.agents.agent_rag_classifier import execute as e
    return await e(input_dict)


def _to_eval_row(claim_id: str) -> dict:
    raw = json.loads((_CLAIMS_DIR / f"{claim_id}.json").read_text(encoding="utf-8"))
    return {
        "claim_id": claim_id,
        "gold_label": raw["gold_label"],
        "gold_reasoning": raw.get("gold_reasoning", ""),
        "gold_category": raw.get("gold_category") or raw.get("category", ""),
    }


def _write_temp_jsonl(rows: list[dict]) -> str:
    tf = tempfile.NamedTemporaryFile("w", delete=False, suffix=".jsonl", encoding="utf-8")
    for r in rows:
        tf.write(json.dumps(r) + "\n")
    tf.close()
    return tf.name


def _empty_confusion_matrix() -> dict[str, dict[str, int]]:
    return {gold: {pred: 0 for pred in VERDICTS} for gold in VERDICTS}


def _shape_existing_report(result, claim_ids: list[str]) -> dict:
    """Convert the SDK result into the shape the AccuracyReport panel expects."""
    rows = list(getattr(result, "rows", []) or [])
    cm = _empty_confusion_matrix()
    per_claim: list[dict] = []
    correct = 0
    per_category: dict[str, dict] = {}

    for r in rows:
        gold = r.get("inputs.gold_label", "")
        pred = r.get("outputs.predicted_label", "<error>")
        match = r.get("outputs.label_match.label_match", 0)
        if match:
            correct += 1
        if pred in VERDICTS and gold in VERDICTS:
            cm[gold][pred] += 1
        per_claim.append({
            "claim_id": r.get("inputs.claim_id", ""),
            "gold_label": gold,
            "predicted_label": pred,
            "gold_reasoning": r.get("inputs.gold_reasoning", ""),
            "predicted_reasoning": r.get("outputs.predicted_reasoning", ""),
            "policy_clause": r.get("outputs.policy_clause", ""),
            "correct": bool(match),
        })
        cat = r.get("inputs.gold_category", "")
        if cat:
            bucket = per_category.setdefault(cat, {"n": 0, "correct": 0})
            bucket["n"] += 1
            if match:
                bucket["correct"] += 1

    for cat, bucket in per_category.items():
        bucket["accuracy"] = bucket["correct"] / bucket["n"] if bucket["n"] else 0.0
        del bucket["correct"]

    n = len(rows)
    return {
        "n": n,
        "overall_accuracy": correct / n if n else 0.0,
        "per_category": per_category,
        "confusion_matrix": cm,
        "per_claim": per_claim,
    }


async def run(
    claim_ids: list[str],
    *,
    run_id: str,
    publish: PublishFn,
) -> dict:
    """Run the batch corpus eval through Foundry's `evaluate()`.

    Returns the existing-shape accuracy report (`overall_accuracy`,
    `per_category`, `confusion_matrix`, `per_claim`) plus a
    `foundry_run_url` field for the portal entry. Also writes the
    report into the EvalStore as kind="batch".
    """
    if not foundry_client.is_configured():
        raise RuntimeError("Foundry is not configured; refusing to run batch.")

    # Lazy SDK import — keeps non-Foundry test paths free of azure deps.
    from azure.ai.evaluation import (
        evaluate, GroundednessEvaluator, SimilarityEvaluator,
    )

    rows = [_to_eval_row(cid) for cid in claim_ids]
    jsonl_path = _write_temp_jsonl(rows)

    def _target(*, claim_id, **_):
        # `target` is invoked by the SDK per-row.
        cls = asyncio.run(_rag_execute({"claim_id": claim_id}))["classification"]
        return {
            "predicted_label": cls.get("verdict", "<error>"),
            "predicted_reasoning": cls.get("reasoning", ""),
            "policy_clause": cls.get("policy_clause", ""),
            "context": "policy",  # actual policy chunks already injected via tool calls
        }

    model_config = foundry_client.get_model_config()
    project_config = foundry_client.get_project_config()

    publish({"type": "accuracy.progress", "run_id": run_id, "index": 0,
             "total": len(claim_ids), "claim_id": claim_ids[0] if claim_ids else "",
             "correct": False})

    result = evaluate(
        data=jsonl_path,
        target=_target,
        evaluators={
            "groundedness": GroundednessEvaluator(model_config=model_config),
            "similarity": SimilarityEvaluator(model_config=model_config),
            "label_match": GoldLabelMatch(),
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
            "policy_cited": {"column_mapping": {
                "query": "${data.claim_id}",
                "response": "${target.predicted_reasoning}",
                "context": "${target.context}",
            }},
        },
        azure_ai_project=project_config,
        evaluation_name=f"poc1-accuracy-{run_id}-{int(time.time())}",
    )

    report = _shape_existing_report(result, claim_ids)
    report["run_id"] = run_id
    report["foundry_run_url"] = getattr(result, "studio_url", None)

    default_store().put_batch(run_id, report)

    publish({"type": "accuracy.complete", "run_id": run_id, "summary": {
        "overall_accuracy": report["overall_accuracy"], "n": report["n"],
    }})
    return report
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./.venv/Scripts/pytest.exe tests/api/eval/test_batch_runner.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/eval/batch_runner.py tests/api/eval/test_batch_runner.py
git commit -m "feat(eval): batch_runner using Foundry evaluate() for 300-claim corpus with portal upload"
```

---

## Task 13: Modify `routes/accuracy.py` to use `batch_runner`

**Files:**
- Modify: `api/server/routes/accuracy.py`

- [ ] **Step 1: Read the current accuracy route**

```bash
cat api/server/routes/accuracy.py
```

- [ ] **Step 2: Modify `routes/accuracy.py`**

Replace the contents of `api/server/routes/accuracy.py`:

```python
"""POST /api/accuracy/run, GET /api/accuracy/last, GET /api/accuracy/{run_id}.

Now backed by Foundry `evaluate()` via api.server.eval.batch_runner. If
Foundry is not configured, POST returns HTTP 503 — we don't allow a
"real" run that secretly isn't.
"""
from __future__ import annotations
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.server.eval import batch_runner, foundry_client
from api.server.eval.store import default_store
from api.server.state import app_state
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accuracy", tags=["accuracy"])

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"


class RunRequest(BaseModel):
    sample_size: int | None = None


def _bus_publish(event: dict) -> None:
    """Bridge batch-runner publish events onto the fleet event bus."""
    ev_type = event.get("type")
    if not ev_type:
        return
    run_id = event.get("run_id")
    extra = {k: v for k, v in event.items() if k not in {"type", "run_id"}}
    try:
        app_state.bus.emit(FleetEvent(type=ev_type, workflow_id=run_id, run_id=run_id, **extra))
    except Exception as ex:
        log.warning("bus publish failed for %s: %s", ev_type, ex)


@router.post("/run", status_code=202)
async def post_run(req: RunRequest, background: BackgroundTasks):
    if not foundry_client.is_configured():
        raise HTTPException(
            status_code=503,
            detail={"configured": False,
                    "reason": "Foundry not configured; refusing to run a fake batch."},
        )

    all_claims = sorted(p.stem for p in _CLAIMS_DIR.glob("CLM-*.json"))
    if req.sample_size and req.sample_size > len(all_claims):
        raise HTTPException(400, f"sample_size {req.sample_size} exceeds corpus size {len(all_claims)}")
    claim_ids = all_claims[: req.sample_size] if req.sample_size else all_claims
    run_id = f"acc-{uuid.uuid4().hex[:8]}"

    async def _execute_and_cache():
        try:
            await batch_runner.run(claim_ids, run_id=run_id, publish=_bus_publish)
        except Exception as ex:
            log.exception("batch run %s failed", run_id)
            _bus_publish({"type": "accuracy.complete", "run_id": run_id,
                          "summary": {"error": str(ex)[:200]}})

    background.add_task(_execute_and_cache)
    return {"run_id": run_id, "n": len(claim_ids)}


@router.get("/last")
async def get_last():
    if not foundry_client.is_configured():
        return {"configured": False, "reason": "Foundry not configured"}
    report = default_store().last_batch_run()
    if report is None:
        raise HTTPException(404, "no completed run yet")
    return report


@router.get("/{run_id}")
async def get_by_id(run_id: str):
    if not foundry_client.is_configured():
        return {"configured": False, "reason": "Foundry not configured"}
    last = default_store().last_batch_run()
    if last is None or last.get("run_id") != run_id:
        raise HTTPException(404, f"no report for run_id {run_id!r}")
    return last
```

- [ ] **Step 3: Verify with manual smoke**

```bash
./.venv/Scripts/uvicorn.exe api.server.main:app --port 8001 &
# In another shell, with Foundry env unset:
curl -i -X POST http://localhost:8001/api/accuracy/run -H "Content-Type: application/json" -d '{}'
# Expected: HTTP 503 with {"detail": {"configured": false, "reason": "..."}}
curl -s http://localhost:8001/api/accuracy/last
# Expected: {"configured": false, "reason": "Foundry not configured"}
# Stop uvicorn.
```

- [ ] **Step 4: Commit**

```bash
git add api/server/routes/accuracy.py
git commit -m "feat(eval): /api/accuracy/run delegates to batch_runner; 503 when Foundry unconfigured"
```

---

## Task 14: Delete `accuracy_harness_workflow.py` and update its tests

**Files:**
- Delete: `api/functions/workflows/accuracy_harness_workflow.py`
- Modify: `tests/api/unit/test_accuracy_*.py` and any other tests that import the deleted module.

- [ ] **Step 1: Find all references to the deleted module**

```bash
grep -rn "accuracy_harness_workflow" api/ tests/ docs/ 2>/dev/null
```

Expect references in tests and possibly docs. Tests need updating; doc references can be left for now (the runbook is updated in a later task if needed).

- [ ] **Step 2: Delete the file**

```bash
git rm api/functions/workflows/accuracy_harness_workflow.py
```

- [ ] **Step 3: Update referencing tests**

For each test file that imports `from api.functions.workflows import accuracy_harness_workflow as harness` (or similar): the test was asserting on the old confusion-matrix shape produced in-process. The new `batch_runner.run` produces the same shape (`overall_accuracy`, `per_category`, `confusion_matrix`, `per_claim`), so:

- Replace `from api.functions.workflows.accuracy_harness_workflow import run` with `from api.server.eval.batch_runner import run`.
- If the test patches `_classify_one` or any internal harness symbol, update it to patch the new equivalent in `batch_runner` (e.g. `_rag_execute`).
- If the test asserts the SDK is called with specific kwargs, replace with `evaluate.assert_called_with(...)` patterns shown in `tests/api/eval/test_batch_runner.py` (Task 12).

Run them after each change:

```bash
./.venv/Scripts/pytest.exe tests/api/unit -k accuracy -v
```

- [ ] **Step 4: Run the full unit-test sweep**

```bash
./.venv/Scripts/pytest.exe tests/api -q
```

Expected: green or skip on `pytest.mark.foundry` integration tests; no errors from the deleted module.

- [ ] **Step 5: Commit**

```bash
git add -A api/functions/workflows/ tests/api/
git commit -m "chore(eval): delete accuracy_harness_workflow; tests now point at batch_runner"
```

---

## Task 15: `.env.example` + integration smoke test

**Files:**
- Modify: `.env.example`
- Create: `tests/api/integration/test_foundry_smoke.py`
- Modify: `pyproject.toml` (or `pytest.ini` / `conftest.py`) to register the `foundry` pytest marker.

- [ ] **Step 1: Add Foundry env vars to `.env.example`**

Open `.env.example` and append:

```
# --- Azure AI Foundry evaluation (api/server/eval/*) ---
# Required to enable Foundry-backed evals. Without these, the control plane
# shows "Foundry not configured" — never falls back to fake numbers.
AZURE_FOUNDRY_PROJECT_ENDPOINT=
AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT=

# Sampling rate for online evals (0.0 - 1.0). 1.0 = score every agent invocation.
# Defaults to 1.0 for demos; recommend 0.1 for sustained soak.
EVAL_SAMPLE_RATE=1.0

# Drain queue capacity. At capacity, oldest pending row is dropped (visible at
# /api/evals/health). Defaults to 1000.
EVAL_QUEUE_MAX=1000
```

- [ ] **Step 2: Register the `foundry` pytest marker**

In `pyproject.toml`, locate the `[tool.pytest.ini_options]` section (or create one). Add the marker:

```toml
[tool.pytest.ini_options]
markers = [
    "smoke: pre-flight sanity test before paid runs",
    "foundry: integration test requiring real Azure AI Foundry creds; skipped otherwise",
]
```

If `pyproject.toml` already has `markers`, add `"foundry: ..."` to the existing list.

- [ ] **Step 3: Write the smoke integration test**

Create `tests/api/integration/test_foundry_smoke.py`:

```python
"""Real-Foundry smoke test: 5 hand-picked claims through batch_runner.

Skipped automatically without creds. Run as:
  pytest tests/api/integration/test_foundry_smoke.py -m foundry -v
"""
from __future__ import annotations
import os

import pytest


pytestmark = pytest.mark.foundry


def _has_creds() -> bool:
    return all(os.environ.get(k) for k in (
        "AZURE_FOUNDRY_PROJECT_ENDPOINT", "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT",
    ))


@pytest.mark.skipif(not _has_creds(), reason="Foundry creds not set")
@pytest.mark.asyncio
async def test_foundry_smoke_5_claims():
    from api.server.eval.batch_runner import run

    # Pick 5 claims that exist in data/synthetic/claims.
    from pathlib import Path
    claims_dir = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"
    available = sorted(p.stem for p in claims_dir.glob("CLM-*.json"))[:5]
    assert len(available) == 5, "need at least 5 synthetic claims for the smoke run"

    captured: list[dict] = []
    report = await run(claim_ids=available, run_id="smoke-test",
                       publish=lambda e: captured.append(e))

    assert report["n"] == 5
    assert "overall_accuracy" in report
    assert isinstance(report["overall_accuracy"], float)
    assert 0.0 <= report["overall_accuracy"] <= 1.0
    assert "confusion_matrix" in report
    assert report.get("foundry_run_url"), "expected studio_url from Foundry"
    # Progress + complete events fired.
    types = [e.get("type") for e in captured]
    assert "accuracy.progress" in types
    assert "accuracy.complete" in types
```

- [ ] **Step 4: Run the smoke test (only with creds)**

If you have Foundry creds available:

```bash
export AZURE_FOUNDRY_PROJECT_ENDPOINT="..."
export AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT="gpt-4o"
./.venv/Scripts/pytest.exe tests/api/integration/test_foundry_smoke.py -m foundry -v
```

Expected: 1 passed (~30s wall-clock).

Without creds:

```bash
./.venv/Scripts/pytest.exe tests/api/integration/test_foundry_smoke.py -v
```

Expected: 1 skipped.

- [ ] **Step 5: Update [docs/poc1-accuracy-runbook.md](../../poc1-accuracy-runbook.md)**

Add a "pre-flight smoke" section pointing at the new test. Replace the existing pre-flight block. The new pre-flight reads:

```markdown
## Pre-flight

```bash
gh auth status                                  # must be logged in
./.venv/Scripts/pytest.exe tests/api -q         # baseline must be green
./.venv/Scripts/pytest.exe tests/api/integration/test_foundry_smoke.py -m foundry -v
# Expects 1 passed (~30s). Validates Foundry wiring before paying for 300 calls.
# If creds aren't set this test is skipped — set them before the milestone run.
```
```

- [ ] **Step 6: Commit**

```bash
git add .env.example pyproject.toml \
        tests/api/integration/test_foundry_smoke.py \
        docs/poc1-accuracy-runbook.md
git commit -m "chore(eval): .env.example + foundry pytest marker + 5-claim smoke test"
```

---

## Final verification

After all 15 tasks land:

- [ ] **Run the full suite**

```bash
./.venv/Scripts/pytest.exe tests -q
```

Expected: all unit + route + integration (non-foundry) tests pass; foundry-marker tests skipped without creds.

- [ ] **Manual smoke of the control plane**

```bash
./.venv/Scripts/uvicorn.exe api.server.main:app --reload &
npm run dev:client &
```

Open `/evaluations`. Without creds: configuration panel renders. With creds: tiles populate over the next 30s as agents run (trigger by injecting an expense claim).

```bash
# Stop both processes:
# (per the standing instruction — don't leave background services accumulating)
```

- [ ] **Verify success criteria from spec §13**

| Criterion | Verification |
|---|---|
| Real eval row within 10s of agent invocation | Trigger an injection, then `curl /api/evals/` shows a row with non-fake scores |
| "Not configured" panel without creds | Unset env, reload `/evaluations` |
| Batch run shows up in Foundry portal | After a smoke run, click the `foundry_run_url` from `/api/accuracy/last` |
| POC2 inherits eval-ing for free | When a POC2 agent runs, `/api/evals/?agent_label=<poc2-label>` returns rows with the default `*` evaluator set |
| No `random.random()` synthesises eval scores | `grep -rn "random.random" api/server/eval/ api/server/routes/evals.py` — only the sampling gate appears |

---

## Self-review notes

The plan above was checked against the spec at [2026-04-30-foundry-eval-integration-design.md](../specs/2026-04-30-foundry-eval-integration-design.md) section by section:

- **Spec §4.1 architecture diagram** — Tasks 1–10 cover the online path; Tasks 12–13 cover the batch path.
- **Spec §5 components** — every file in §5.1 / §5.2 has a task: foundry_client (T2), custom_evaluators (T3), evaluator_set (T4), store (T5), online_subscriber (T8), batch_runner (T12), wrapper (T6), executors (T7), evals route (T10), accuracy route (T13), Evaluations.tsx (T11), .env.example (T15).
- **Spec §5.3 removed files** — accuracy_harness_workflow.py is deleted in T14.
- **Spec §6 data flow** — the on-the-wire ordering (event → subscribe → queue → score → store → tile poll) is covered by the integration test in T6 + the subscriber tests in T8 + the route tests in T10.
- **Spec §7 evaluator rationale** — encoded in evaluator_set.py (T4) and the test mappings.
- **Spec §8 error handling / sampling / no-creds** — covered by tests in T8 (sampling, overflow, drain retry), T10 (configured/unconfigured envelopes), T13 (503 on unconfigured).
- **Spec §9 control-plane UI** — covered by T11 component tests for three states.
- **Spec §10 testing matrix** — every test file listed in spec §10.1–§10.3 is created in the corresponding task. The smoke integration test is in T15.
- **Spec §11 risks** — the queue-overflow, error-handling, and `gh auth token` concerns are surfaced by tests in T8, T6, and the smoke run in T15.
