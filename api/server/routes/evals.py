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
    """Compute the three honest tiles defined in spec §6.3.

    Task adherence uses groundedness when available (RAG agents), falling
    back to coherence then fluency for non-RAG agents that don't get a
    grounded-context score. Score keys are normalised to 0..1 — the SDK
    LLM-judge evaluators return 1..5 (we divide by 5).
    """

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

    def _normalise_5_to_1(value: float) -> float:
        """LLM-judge scores are 1..5; tiles render as 0..1."""
        return max(0.0, min(1.0, value / 5.0))

    # Quality: prefer groundedness, fall back to coherence then fluency.
    adh = 0.0
    adh_n = 0
    adh_agents: list[str] = []
    adh_evaluators: list[str] = []
    for primary in ("groundedness", "coherence", "fluency"):
        val, n, agents = _mean_across_agents(primary)
        if n > 0:
            adh = _normalise_5_to_1(val)
            adh_n = n
            adh_agents = agents
            adh_evaluators.append(primary)
            break

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
            "evaluators": adh_evaluators or ["groundedness"],
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


@router.get("")
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
