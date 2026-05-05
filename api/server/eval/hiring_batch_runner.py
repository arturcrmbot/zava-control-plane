"""POC2 hiring batch runner — Foundry-backed CV-extraction accuracy gate.

Sister to [batch_runner.py](batch_runner.py) but for POC2's hiring domain.
Per plan/feature-foundry-credibility-friday-1.md TASK-019.

Walks `data/synthetic/hiring/cvs/<candidate_id>.json`, runs the live
`agent_cv_crystalliser.execute(...)` per candidate, then evaluates the
extracted profile against the canonical CV (and against `labels.csv`)
using the three deterministic evaluators added in
`custom_evaluators.py`. Optionally sends the results through Foundry's
`evaluate()` SDK so the run + per-row scores appear in the Foundry portal
under the project's *Evaluation* pane.

Two reasons we build the JSONL ourselves rather than using `target=` on
`evaluate()`:

1. Mirrors the proven pattern in `batch_runner.py` (POC1) where the
   classifier runs offline first and the rows already carry predicted
   outputs by the time `evaluate()` sees them. This avoids re-running
   the model under Foundry's batch worker (which spawns parallel sessions
   and burns GHCP token quota).
2. Hiring deterministic evaluators are pure-Python and cheap — there's no
   need to incur a Foundry round-trip just to score them. We score
   in-process and OPTIONALLY hand the rows to `evaluate()` for portal
   visibility.

Default `sample_size=5` is intentionally small. The full 50-CV gym takes
~15-20min of GHCP cycles — call with `sample_size=null` only if you have
the budget.
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
from api.server.eval.custom_evaluators import (
    CVFieldExtractionAccuracy,
    JurisdictionRoutingCorrectness,
    ShortlistDecisionMatch,
    _load_hiring_cv,
    _load_hiring_labels,
)
from api.server.eval.store import default_store

log = logging.getLogger(__name__)

PublishFn = Callable[[dict], None]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HIRING_CVS_DIR = _REPO_ROOT / "data" / "synthetic" / "hiring" / "cvs"


def _list_candidate_ids() -> list[str]:
    return sorted(p.stem for p in _HIRING_CVS_DIR.glob("C-*.json"))


async def _crystallise_one(candidate_id: str, *, run_id: str) -> dict:
    """Invoke the live cv-crystalliser executor for one candidate.

    Returns `{candidate_id, response_text, profile, agent_output, error}`.
    Errors are captured rather than raised so a single bad CV doesn't
    abort the whole batch.
    """
    try:
        # Lazy import — avoids loading the agent stack at module import time.
        from api.functions.graphs.executors.agents.agent_cv_crystalliser import (
            execute as crystalliser_execute,
        )
    except ImportError as ex:
        return {"candidate_id": candidate_id, "error": f"import: {ex}",
                "response_text": "", "agent_output": {}}

    gold = _load_hiring_cv(candidate_id) or {}
    role_title = gold.get("current_title") or "Candidate"
    try:
        out = await crystalliser_execute({
            "candidate": {"id": candidate_id, "name": gold.get("name")},
            "candidate_id": candidate_id,
            "role_title": role_title,
            "workflow_id": f"BATCH-{run_id}-{candidate_id}",
        })
    except Exception as ex:
        return {"candidate_id": candidate_id, "error": str(ex)[:200],
                "response_text": "", "agent_output": {}}

    agent_output = (out or {}).get("cv_crystalliser") or {}
    profile = agent_output.get("profile") or {}
    return {
        "candidate_id": candidate_id,
        # The deterministic evaluators parse `response_text` as JSON and
        # extract candidate_id from it; encode the profile into that
        # shape so the same evaluator runs identically online + batch.
        "response_text": json.dumps({"candidate_id": candidate_id, **profile}),
        "agent_output": agent_output,
        "error": None,
    }


def _score_row(row: dict) -> dict:
    """Run the three deterministic evaluators against the row."""
    cv_acc = CVFieldExtractionAccuracy()(
        query="", response=row["response_text"],
        workflow_id=row["candidate_id"],
    )
    juris = JurisdictionRoutingCorrectness()(
        query="", response=row["response_text"],
        workflow_id=row["candidate_id"],
    )
    # ShortlistDecisionMatch needs a verdict in the response — cv-crystalliser
    # doesn't produce one, so this evaluator's score will be `missing` for the
    # batch unless we synthesise a verdict from the profile. We surface the
    # raw output so the operator sees the gap explicitly.
    short = ShortlistDecisionMatch()(
        query="", response=row["response_text"],
        workflow_id=row["candidate_id"],
    )
    return {
        **cv_acc, **juris, **short,
        "_evaluator_set": ["cv_field_extraction_accuracy",
                           "jurisdiction_routing_correctness",
                           "shortlist_decision_match"],
    }


def _summarise(scored_rows: list[dict]) -> dict:
    """Aggregate per-row scores into a corpus-level report."""
    n = len(scored_rows)
    if n == 0:
        return {"n": 0, "cv_field_accuracy_avg": 0.0,
                "jurisdiction_match_rate": 0.0, "shortlist_match_rate": 0.0,
                "errors": 0}

    cv_avg = sum(r.get("cv_field_accuracy", 0.0) for r in scored_rows) / n
    juris_match = sum(r.get("jurisdiction_match", 0) for r in scored_rows) / n
    short_match = sum(r.get("shortlist_match", 0) for r in scored_rows) / n
    errors = sum(1 for r in scored_rows if r.get("_error"))
    return {
        "n": n,
        "cv_field_accuracy_avg": round(cv_avg, 4),
        "jurisdiction_match_rate": round(juris_match, 4),
        "shortlist_match_rate": round(short_match, 4),
        "errors": errors,
    }


async def _maybe_log_to_foundry(
    rows_for_foundry: list[dict], *, run_id: str,
) -> str | None:
    """Optionally call `evaluate()` to log the rows to Foundry's UI.

    Returns the studio_url. Best-effort — failures are logged and swallowed
    so a Foundry hiccup doesn't void the in-process scores the operator
    already has.
    """
    if not foundry_client.is_configured():
        return None

    try:
        from azure.ai.evaluation import evaluate
        from api.server.eval.evaluator_set import _build_llm_evaluator
    except ImportError as ex:
        log.warning("hiring_batch_runner: azure-ai-evaluation missing: %s", ex)
        return None

    tf = tempfile.NamedTemporaryFile(
        "w", delete=False, suffix=".jsonl", encoding="utf-8",
    )
    for r in rows_for_foundry:
        tf.write(json.dumps(r) + "\n")
    tf.close()

    project_config = foundry_client.get_project_config()
    try:
        result = await asyncio.to_thread(
            evaluate,
            data=tf.name,
            evaluators={
                "cv_field_extraction_accuracy": CVFieldExtractionAccuracy(),
                "jurisdiction_routing_correctness": JurisdictionRoutingCorrectness(),
                "shortlist_decision_match": ShortlistDecisionMatch(),
            },
            evaluator_config={
                "cv_field_extraction_accuracy": {"column_mapping": {
                    "query": "${data.candidate_id}",
                    "response": "${data.response_text}",
                }},
                "jurisdiction_routing_correctness": {"column_mapping": {
                    "query": "${data.candidate_id}",
                    "response": "${data.response_text}",
                }},
                "shortlist_decision_match": {"column_mapping": {
                    "query": "${data.candidate_id}",
                    "response": "${data.response_text}",
                }},
            },
            azure_ai_project=project_config,
            evaluation_name=f"poc2-hiring-{run_id}-{int(time.time())}",
        )
        return result.get("studio_url")
    except Exception as ex:
        log.warning("hiring_batch_runner: Foundry evaluate() failed: %s", ex)
        return None


async def run(
    candidate_ids: list[str] | None = None,
    *,
    run_id: str,
    publish: PublishFn,
    log_to_foundry: bool = False,
) -> dict:
    """Run the hiring batch evaluation.

    Args:
        candidate_ids: List of candidate IDs to evaluate. Defaults to all
            CVs under data/synthetic/hiring/cvs/.
        run_id: Stable identifier for this batch run.
        publish: Callback for `hiring_accuracy.progress` /
            `hiring_accuracy.complete` events.
        log_to_foundry: When True, also call `evaluate()` so the run shows
            up in the Foundry portal Evaluation pane. Default False to
            avoid double Foundry traffic — the in-process scores are
            primary; Foundry-side is optional visibility.

    Returns the corpus-level summary plus per-row scores and an optional
    `foundry_run_url`. Raises nothing — single-row failures are captured.
    """
    cids = candidate_ids if candidate_ids is not None else _list_candidate_ids()
    n = len(cids)
    publish({"type": "hiring_accuracy.progress", "run_id": run_id,
             "index": 0, "total": n,
             "candidate_id": cids[0] if cids else "",
             "stage": "starting"})

    rows_for_foundry: list[dict] = []
    scored_rows: list[dict] = []
    for i, cid in enumerate(cids):
        publish({"type": "hiring_accuracy.progress", "run_id": run_id,
                 "index": i, "total": n, "candidate_id": cid,
                 "stage": "crystallising"})
        crystallised = await _crystallise_one(cid, run_id=run_id)
        rows_for_foundry.append({
            "candidate_id": cid,
            "response_text": crystallised["response_text"],
        })
        if crystallised.get("error"):
            scored_rows.append({
                "candidate_id": cid, "_error": crystallised["error"],
                "cv_field_accuracy": 0.0, "jurisdiction_match": 0,
                "shortlist_match": 0, "shortlist_confusion": "missing",
            })
            continue
        scored = _score_row(crystallised)
        scored["candidate_id"] = cid
        scored_rows.append(scored)

    summary = _summarise(scored_rows)
    summary["run_id"] = run_id
    summary["per_candidate"] = scored_rows
    summary["pricing_source"] = "see model_pricing.PRICING_SOURCE_DATE"

    foundry_run_url = None
    if log_to_foundry:
        foundry_run_url = await _maybe_log_to_foundry(
            rows_for_foundry, run_id=run_id,
        )
    summary["foundry_run_url"] = foundry_run_url

    # Persist to the same EvalStore the POC1 batch runner uses so the
    # Evaluations UI's `last_batch_run` surfacing covers both.
    try:
        default_store().put_batch(run_id, summary)
    except Exception as ex:
        log.warning("hiring_batch_runner: put_batch failed: %s", ex)

    publish({"type": "hiring_accuracy.complete", "run_id": run_id,
             "summary": {"n": summary["n"],
                          "cv_field_accuracy_avg": summary["cv_field_accuracy_avg"],
                          "jurisdiction_match_rate": summary["jurisdiction_match_rate"]}})
    return summary
