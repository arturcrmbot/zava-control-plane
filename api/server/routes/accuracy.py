"""POST /api/accuracy/run, GET /api/accuracy/last, GET /api/accuracy/{run_id}."""
from __future__ import annotations
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.functions.graphs.executors.agents.agent_rag_classifier import execute as rag_execute
from api.functions.workflows import accuracy_harness_workflow as harness
from api.server.state import app_state
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accuracy", tags=["accuracy"])

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

# In-memory store: every completed run keyed by run_id; `_last_run_id` points at
# the most recently completed one for /last. Concurrent POSTs each get a unique
# run_id, so neither overwrites the other; /last simply tracks the most recent
# completion.
_reports: dict[str, dict] = {}
_last_run_id: str | None = None


class RunRequest(BaseModel):
    sample_size: int | None = None
    concurrency: int = 8


async def _classifier_adaptor(claim_id: str) -> dict:
    result = await rag_execute({"claim_id": claim_id})
    return result["classification"]


def _bus_publish(event: dict) -> None:
    """Bridge harness publish-callback events onto the fleet event bus."""
    ev_type = event.get("type")
    if not ev_type:
        return
    run_id = event.get("run_id")
    extra = {k: v for k, v in event.items() if k not in {"type", "run_id"}}
    try:
        app_state.bus.emit(FleetEvent(type=ev_type, workflow_id=run_id, run_id=run_id, **extra))
    except Exception as ex:
        log.warning("bus publish failed for %s: %s", ev_type, ex)


async def _run_harness(run_id: str, claim_ids: list[str], concurrency: int) -> dict:
    return await harness.run(
        claim_ids=claim_ids,
        classifier=_classifier_adaptor,
        concurrency=concurrency,
        run_id=run_id,
        publish=_bus_publish,
    )


@router.post("/run", status_code=202)
async def post_run(req: RunRequest, background: BackgroundTasks):
    all_claims = sorted(p.stem for p in _CLAIMS_DIR.glob("CLM-*.json"))
    if req.sample_size and req.sample_size > len(all_claims):
        raise HTTPException(400, f"sample_size {req.sample_size} exceeds corpus size {len(all_claims)}")
    claim_ids = all_claims[: req.sample_size] if req.sample_size else all_claims
    run_id = f"acc-{uuid.uuid4().hex[:8]}"

    async def _execute_and_cache():
        global _last_run_id
        report = await _run_harness(run_id, claim_ids, req.concurrency)
        _reports[run_id] = report
        _last_run_id = run_id

    background.add_task(_execute_and_cache)
    return {"run_id": run_id, "n": len(claim_ids)}


@router.get("/last")
async def get_last():
    if _last_run_id is None:
        raise HTTPException(404, "no completed run yet")
    return _reports[_last_run_id]


@router.get("/{run_id}")
async def get_by_id(run_id: str):
    if run_id not in _reports:
        raise HTTPException(404, f"no report for run_id {run_id!r}")
    return _reports[run_id]
