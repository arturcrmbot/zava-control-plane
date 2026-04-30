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
from typing import Callable

from api.server.eval import foundry_client
from api.server.eval.custom_evaluators import GoldLabelMatch, PolicyClauseCited
from api.server.eval.store import default_store
from api.shared.expense_taxonomy import VERDICTS

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

    from azure.ai.evaluation import (
        evaluate, GroundednessEvaluator, SimilarityEvaluator,
    )

    rows = [_to_eval_row(cid) for cid in claim_ids]
    jsonl_path = _write_temp_jsonl(rows)

    def _target(*, claim_id, **_):
        cls = asyncio.run(_rag_execute({"claim_id": claim_id}))["classification"]
        return {
            "predicted_label": cls.get("verdict", "<error>"),
            "predicted_reasoning": cls.get("reasoning", ""),
            "policy_clause": cls.get("policy_clause", ""),
            "context": "policy",
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
