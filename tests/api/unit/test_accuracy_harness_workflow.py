"""Accuracy harness — uses an injected synchronous fake classifier so we can
assert the splitter/fan-out/aggregator pipeline without making real model calls."""
from __future__ import annotations
import pytest

from api.functions.workflows import accuracy_harness_workflow as harness


@pytest.mark.asyncio
async def test_aggregator_builds_confusion_matrix():
    async def perfect(claim_id: str) -> dict:
        from api.server.mcp_tools.claim_get_structured import get_structured
        gold = get_structured(claim_id, include_gold=True)
        return {
            "verdict": gold["gold_label"],
            "policy_clause": gold["gold_policy_clause"],
            "reasoning": gold["gold_reasoning"],
            "confidence": 0.99,
            "competing_interpretations": [],
        }

    report = await harness.run(
        claim_ids=["CLM-0000", "CLM-0001", "CLM-0002", "CLM-0003"],
        classifier=perfect,
        concurrency=2,
    )
    assert report["overall_accuracy"] == 1.0
    cm = report["confusion_matrix"]
    assert sum(cm[label][label] for label in ("green", "amber", "red")) == 4
    assert all(cm[r][c] == 0 for r in cm for c in cm[r] if r != c)


@pytest.mark.asyncio
async def test_aggregator_handles_misclassification():
    async def always_green(claim_id: str) -> dict:
        return {
            "verdict": "green",
            "policy_clause": "§3.1 Meals",
            "reasoning": "predicted green",
            "confidence": 0.5,
            "competing_interpretations": [],
        }

    report = await harness.run(
        claim_ids=["CLM-0000", "CLM-0007", "CLM-0009"],
        classifier=always_green,
        concurrency=1,
    )
    assert report["overall_accuracy"] < 1.0
    assert report["confusion_matrix"]["green"]["green"] >= 1
    off_diag = [(r, c, v) for r in report["confusion_matrix"] for c, v in report["confusion_matrix"][r].items() if r != c and v > 0]
    assert off_diag


@pytest.mark.asyncio
async def test_per_claim_records_attached():
    async def perfect(claim_id: str):
        from api.server.mcp_tools.claim_get_structured import get_structured
        gold = get_structured(claim_id, include_gold=True)
        return {"verdict": gold["gold_label"], "policy_clause": gold["gold_policy_clause"],
                "reasoning": gold["gold_reasoning"], "confidence": 0.99, "competing_interpretations": []}

    report = await harness.run(claim_ids=["CLM-0000"], classifier=perfect, concurrency=1)
    assert len(report["per_claim"]) == 1
    rec = report["per_claim"][0]
    assert {"claim_id", "gold_label", "predicted_label", "gold_reasoning", "predicted_reasoning",
            "policy_clause", "correct"} <= set(rec)


@pytest.mark.asyncio
async def test_publish_callback_invoked_per_claim_and_at_complete():
    async def perfect(claim_id: str):
        from api.server.mcp_tools.claim_get_structured import get_structured
        gold = get_structured(claim_id, include_gold=True)
        return {"verdict": gold["gold_label"], "policy_clause": gold["gold_policy_clause"],
                "reasoning": gold["gold_reasoning"], "confidence": 0.99, "competing_interpretations": []}

    captured: list[dict] = []
    def publish(event: dict) -> None:
        captured.append(event)

    await harness.run(
        claim_ids=["CLM-0000", "CLM-0001"],
        classifier=perfect,
        concurrency=1,
        publish=publish,
    )
    progress_events = [e for e in captured if e["type"] == "accuracy.progress"]
    complete_events = [e for e in captured if e["type"] == "accuracy.complete"]
    assert len(progress_events) == 2
    assert len(complete_events) == 1
    for e in progress_events:
        assert {"type", "run_id", "index", "total", "claim_id", "correct"} <= set(e)
