"""Foundry-backed batch corpus evaluator.

Pattern (per Azure AI Evaluation SDK docs): pre-build a JSONL where each row
already contains both the inputs and the model's outputs (predicted_label,
predicted_reasoning, context). `evaluate()` is called with **no target** —
it just runs the evaluators against the pre-computed rows.

We do NOT use `target=` to re-run the rag classifier per row through Foundry's
batch worker. That pattern is for "queries without responses"; we have
responses already (online classifications, or a one-shot pre-classify
done outside this function).

The caller is responsible for producing classifications and passing them
in via `pre_classified` (a list of dicts, one per claim). For demos, this
is a tiny set; for the 300-claim corpus, it's pre-computed offline.
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


def _load_claim(claim_id: str) -> dict:
    return json.loads((_CLAIMS_DIR / f"{claim_id}.json").read_text(encoding="utf-8"))


def _write_temp_jsonl(rows: list[dict]) -> str:
    tf = tempfile.NamedTemporaryFile("w", delete=False, suffix=".jsonl", encoding="utf-8")
    for r in rows:
        tf.write(json.dumps(r) + "\n")
    tf.close()
    return tf.name


def _empty_confusion_matrix() -> dict[str, dict[str, int]]:
    return {gold: {pred: 0 for pred in VERDICTS} for gold in VERDICTS}


def _shape_existing_report(result, rows_in: list[dict]) -> dict:
    """Convert the SDK result dict into the AccuracyReport shape.

    `result["rows"]` carries `inputs.*` (from the JSONL) and `outputs.<eval_name>.*`
    (from each evaluator). The SDK returns a plain dict with keys `rows`, `metrics`,
    `studio_url` — NOT an object with attributes.
    """
    out_rows = list(result.get("rows", []) or [])
    cm = _empty_confusion_matrix()
    per_claim: list[dict] = []
    correct = 0
    per_category: dict[str, dict] = {}

    for r in out_rows:
        gold = r.get("inputs.gold_label", "")
        pred = r.get("inputs.predicted_label", "<error>")
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
            "predicted_reasoning": r.get("inputs.predicted_reasoning", ""),
            "policy_clause": r.get("inputs.policy_clause", ""),
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

    n = len(out_rows)
    return {
        "n": n,
        "overall_accuracy": correct / n if n else 0.0,
        "per_category": per_category,
        "confusion_matrix": cm,
        "per_claim": per_claim,
    }


def _build_jsonl_rows(pre_classified: list[dict]) -> list[dict]:
    """Merge gold labels (from synthetic corpus) with the caller's classifications."""
    out: list[dict] = []
    for c in pre_classified:
        claim_id = c["claim_id"]
        raw = _load_claim(claim_id)
        out.append({
            "claim_id": claim_id,
            "gold_label": raw["gold_label"],
            "gold_reasoning": raw.get("gold_reasoning", ""),
            "gold_category": raw.get("gold_category") or raw.get("category", ""),
            "predicted_label": c.get("predicted_label", "<error>"),
            "predicted_reasoning": c.get("predicted_reasoning", ""),
            "policy_clause": c.get("policy_clause", ""),
            "context": c.get("context", ""),
        })
    return out


async def run(
    pre_classified: list[dict],
    *,
    run_id: str,
    publish: PublishFn,
) -> dict:
    """Run evaluators against pre-classified rows via Foundry `evaluate()`.

    Args:
        pre_classified: List of dicts, one per claim, each with at minimum
            `claim_id`, `predicted_label`, `predicted_reasoning`, `policy_clause`,
            `context`. Gold labels are loaded from data/synthetic/claims.
        run_id: Stable identifier for this batch run (used in evaluation_name
            and as the EvalStore key).
        publish: Callback for accuracy.progress / accuracy.complete events.

    Returns the accuracy report (n, overall_accuracy, per_category,
    confusion_matrix, per_claim) plus `foundry_run_url` and `run_id`.
    Raises RuntimeError if Foundry is not configured.
    """
    if not foundry_client.is_configured():
        raise RuntimeError("Foundry is not configured; refusing to run batch.")

    from azure.ai.evaluation import (
        evaluate, GroundednessEvaluator, SimilarityEvaluator,
    )

    rows = _build_jsonl_rows(pre_classified)
    jsonl_path = _write_temp_jsonl(rows)

    model_config = foundry_client.get_model_config()
    project_config = foundry_client.get_project_config()

    publish({"type": "accuracy.progress", "run_id": run_id, "index": 0,
             "total": len(rows),
             "claim_id": rows[0]["claim_id"] if rows else "",
             "correct": False})

    # `evaluate()` is synchronous + blocks while it streams batch progress.
    # Run it on a worker thread so the event loop stays free.
    result = await asyncio.to_thread(
        evaluate,
        data=jsonl_path,
        # No `target=` — the JSONL already has predicted_label/reasoning/context.
        evaluators={
            "groundedness": GroundednessEvaluator(model_config=model_config),
            "similarity": SimilarityEvaluator(model_config=model_config),
            "label_match": GoldLabelMatch(),
            "policy_cited": PolicyClauseCited(),
        },
        evaluator_config={
            "groundedness": {"column_mapping": {
                "query": "${data.claim_id}",
                "response": "${data.predicted_reasoning}",
                "context": "${data.context}",
            }},
            "similarity": {"column_mapping": {
                "query": "${data.claim_id}",
                "response": "${data.predicted_reasoning}",
                "ground_truth": "${data.gold_reasoning}",
            }},
            "label_match": {"column_mapping": {
                "predicted": "${data.predicted_label}",
                "gold": "${data.gold_label}",
            }},
            "policy_cited": {"column_mapping": {
                "query": "${data.claim_id}",
                "response": "${data.predicted_reasoning}",
                "context": "${data.context}",
            }},
        },
        azure_ai_project=project_config,
        evaluation_name=f"poc1-accuracy-{run_id}-{int(time.time())}",
    )

    report = _shape_existing_report(result, rows)
    report["run_id"] = run_id
    report["foundry_run_url"] = result.get("studio_url")

    default_store().put_batch(run_id, report)

    publish({"type": "accuracy.complete", "run_id": run_id, "summary": {
        "overall_accuracy": report["overall_accuracy"], "n": report["n"],
    }})
    return report
