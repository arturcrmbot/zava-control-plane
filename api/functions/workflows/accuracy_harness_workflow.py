"""Accuracy harness — parallel-fan-out workflow over the claim corpus.

Pregel-style shape:
    claim_splitter → [concurrency × classifier] → confusion_matrix_aggregator

asyncio.Semaphore for fan-out concurrency. The shape (splitter / parallel
workers / aggregator) is preserved so a Pregel-graph swap is mechanical later.

Publish callback is injected so tests can assert event emission without
standing up the global event bus, and the route layer can wire the callback
to `app_state.bus.emit(FleetEvent(type="accuracy.progress", ...))`.
"""
from __future__ import annotations
import asyncio
from typing import Awaitable, Callable, Optional

from api.server.mcp_tools.claim_get_structured import get_structured
from api.shared.expense_taxonomy import CATEGORIES, VERDICTS

ClassifierFn = Callable[[str], Awaitable[dict]]
PublishFn = Callable[[dict], None]


def _empty_confusion_matrix() -> dict[str, dict[str, int]]:
    return {gold: {pred: 0 for pred in VERDICTS} for gold in VERDICTS}


def _noop_publish(_event: dict) -> None:
    pass


async def _classify_one(
    claim_id: str,
    classifier: ClassifierFn,
    sem: asyncio.Semaphore,
    run_id: str,
    idx: int,
    total: int,
    publish: PublishFn,
) -> dict:
    async with sem:
        gold = get_structured(claim_id, include_gold=True)
        prediction = await classifier(claim_id)
        record = {
            "claim_id": claim_id,
            "gold_label": gold["gold_label"],
            "gold_category": gold.get("category"),
            "predicted_label": prediction.get("verdict", "<error>"),
            "gold_reasoning": gold["gold_reasoning"],
            "predicted_reasoning": prediction.get("reasoning", ""),
            "policy_clause": prediction.get("policy_clause", ""),
            "correct": prediction.get("verdict") == gold["gold_label"],
            "confidence": prediction.get("confidence"),
        }
        try:
            publish({
                "type": "accuracy.progress",
                "run_id": run_id,
                "index": idx,
                "total": total,
                "claim_id": claim_id,
                "correct": record["correct"],
            })
        except Exception:
            pass
        return record


async def run(
    claim_ids: list[str],
    classifier: ClassifierFn,
    concurrency: int = 8,
    run_id: str = "harness-default",
    publish: Optional[PublishFn] = None,
) -> dict:
    """Run the accuracy harness over claim_ids; return a confusion-matrix report.

    `publish` (optional) is invoked with `{type, run_id, index, total, claim_id, correct}`
    on each completion and `{type, run_id, summary}` once the aggregator finalises.
    Tests pass a list-appender; routes pass a bus-emit callback. Defaults to no-op.
    """
    publish = publish or _noop_publish

    sem = asyncio.Semaphore(concurrency)
    total = len(claim_ids)
    tasks = [
        _classify_one(cid, classifier, sem, run_id, i, total, publish)
        for i, cid in enumerate(claim_ids)
    ]
    records = await asyncio.gather(*tasks)

    cm = _empty_confusion_matrix()
    for rec in records:
        gold = rec["gold_label"]
        if rec["predicted_label"] in VERDICTS:
            cm[gold][rec["predicted_label"]] += 1
        # Malformed predictions sit outside the matrix (counted as misses via `correct=False`).

    correct = sum(1 for r in records if r["correct"])
    overall = correct / total if total else 0.0

    per_category: dict[str, dict] = {}
    for cat in CATEGORIES:
        rows = [r for r in records if r.get("gold_category") == cat]
        if rows:
            per_category[cat] = {
                "n": len(rows),
                "accuracy": sum(1 for r in rows if r["correct"]) / len(rows),
            }

    report = {
        "run_id": run_id,
        "n": total,
        "overall_accuracy": overall,
        "per_category": per_category,
        "confusion_matrix": cm,
        "per_claim": records,
    }
    try:
        publish({"type": "accuracy.complete", "run_id": run_id, "summary": {
            "overall_accuracy": overall, "n": total,
        }})
    except Exception:
        pass
    return report
