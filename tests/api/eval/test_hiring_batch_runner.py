"""Tests for api.server.eval.hiring_batch_runner.

Per plan/feature-foundry-credibility-friday-1.md TASK-022 (extension).
The live agent invocation is mocked so the test doesn't burn GHCP token
quota; the deterministic evaluators (CV field accuracy, jurisdiction,
shortlist) are exercised end-to-end against real ground truth.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from api.server.eval import hiring_batch_runner
from api.server.eval.custom_evaluators import _load_hiring_cv, _load_hiring_labels


@pytest.fixture(scope="module")
def candidate_id():
    """Pick a real candidate from the corpus that has both labels + CV."""
    labels = _load_hiring_labels()
    for cid in labels.keys():
        if _load_hiring_cv(cid):
            return cid
    pytest.skip("no hiring fixtures available")


@pytest.mark.asyncio
async def test_run_one_candidate_perfect_extraction(candidate_id):
    """Mock the executor to echo the gold profile; expect perfect scores."""
    gold = _load_hiring_cv(candidate_id)
    perfect_profile = {
        "candidate_id": candidate_id,
        "current_title": gold.get("current_title"),
        "tenure_years_total": gold.get("tenure_years_total"),
        "right_to_work": gold.get("right_to_work"),
        "level_target": gold.get("level_target"),
        "jurisdiction": _load_hiring_labels()[candidate_id]["jurisdiction"],
    }

    async def _fake_execute(input):
        cid = input["candidate_id"]
        return {
            "cv_crystalliser": {
                "candidate_id": cid,
                "profile": perfect_profile,
                "extraction_status": "ok",
            }
        }

    events: list[dict] = []
    with patch(
        "api.functions.graphs.executors.agents.agent_cv_crystalliser.execute",
        new=_fake_execute,
    ):
        summary = await hiring_batch_runner.run(
            [candidate_id], run_id="test-1",
            publish=events.append, log_to_foundry=False,
        )

    assert summary["n"] == 1
    assert summary["cv_field_accuracy_avg"] == 1.0
    assert summary["jurisdiction_match_rate"] == 1.0
    assert summary["per_candidate"][0]["cv_field_accuracy"] == 1.0
    assert summary["foundry_run_url"] is None  # log_to_foundry=False
    # Two events (start + complete) at minimum
    assert any(e.get("type") == "hiring_accuracy.complete" for e in events)


@pytest.mark.asyncio
async def test_run_executor_failure_captured(candidate_id):
    async def _explode(input):
        raise RuntimeError("simulated GHCP failure")

    events: list[dict] = []
    with patch(
        "api.functions.graphs.executors.agents.agent_cv_crystalliser.execute",
        new=_explode,
    ):
        summary = await hiring_batch_runner.run(
            [candidate_id], run_id="test-2",
            publish=events.append, log_to_foundry=False,
        )

    assert summary["n"] == 1
    assert summary["errors"] == 1
    assert summary["per_candidate"][0]["_error"]


@pytest.mark.asyncio
async def test_run_partial_extraction(candidate_id):
    """Some fields right, some wrong → between 0 and 1."""
    gold = _load_hiring_cv(candidate_id)
    partial = {
        "candidate_id": candidate_id,
        "current_title": gold.get("current_title"),  # right
        "tenure_years_total": 999,                    # wrong
        "right_to_work": {"jurisdiction": "WRONG", "evidence": "wrong"},
        "level_target": gold.get("level_target"),     # right
    }

    async def _fake_execute(input):
        return {"cv_crystalliser": {
            "candidate_id": candidate_id, "profile": partial,
        }}

    with patch(
        "api.functions.graphs.executors.agents.agent_cv_crystalliser.execute",
        new=_fake_execute,
    ):
        summary = await hiring_batch_runner.run(
            [candidate_id], run_id="test-3",
            publish=lambda e: None, log_to_foundry=False,
        )

    assert 0 < summary["cv_field_accuracy_avg"] < 1.0


@pytest.mark.asyncio
async def test_run_empty_corpus_returns_zero():
    summary = await hiring_batch_runner.run(
        [], run_id="test-empty", publish=lambda e: None, log_to_foundry=False,
    )
    assert summary["n"] == 0
    assert summary["cv_field_accuracy_avg"] == 0.0
