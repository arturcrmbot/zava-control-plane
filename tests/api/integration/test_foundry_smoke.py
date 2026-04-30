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
        "AZURE_FOUNDRY_PROJECT_ENDPOINT", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT",
    ))


@pytest.mark.skipif(not _has_creds(), reason="Foundry creds not set")
@pytest.mark.asyncio
async def test_foundry_smoke_eval_only_no_target():
    """Eval-only smoke: pre-built rows → real Foundry → real scores.

    Uses fabricated `predicted_*` so the test doesn't depend on running the
    rag classifier. Confirms wiring: model_config endpoint + api_version,
    project URI shape, JSONL building, dict-shaped result handling.
    """
    from api.server.eval.batch_runner import run

    pre_classified = [
        {"claim_id": "CLM-0000", "predicted_label": "green",
         "predicted_reasoning": "Meal claim is below the per-diem cap.",
         "policy_clause": "Section 3.2",
         "context": "Section 3.2 Meal claims must not exceed the per-diem cap."},
        {"claim_id": "CLM-0001", "predicted_label": "green",
         "predicted_reasoning": "Travel within policy.",
         "policy_clause": "Section 5.1",
         "context": "Section 5.1 Travel must use approved booking."},
    ]

    captured: list[dict] = []
    report = await run(pre_classified, run_id="smoke-test",
                       publish=lambda e: captured.append(e))

    assert report["n"] == 2
    assert isinstance(report["overall_accuracy"], float)
    assert 0.0 <= report["overall_accuracy"] <= 1.0
    assert "confusion_matrix" in report
    assert report.get("foundry_run_url"), "expected studio_url from Foundry"
    types = [e.get("type") for e in captured]
    assert "accuracy.progress" in types
    assert "accuracy.complete" in types
