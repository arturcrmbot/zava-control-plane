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
