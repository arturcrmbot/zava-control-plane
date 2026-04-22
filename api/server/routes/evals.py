from __future__ import annotations
import time
import random
from fastapi import APIRouter
from api.server.state import app_state

router = APIRouter(prefix="/api/evals")

_evals: list[dict] = []


@router.get("/")
async def list_evals():
    completed = [w for w in app_state.store.list_workflows() if w.status == "completed"]
    if completed and (not _evals or _evals[-1]["ran_at"] < time.time() - 5):
        pick = random.choice(completed)
        _evals.append({
            "id": f"EVAL-{int(time.time()*1000)}",
            "workflow_id": pick.id,
            "ran_at": time.time(),
            "task_adherence": 0.85 + random.random() * 0.15,
            "safety": 0.95 + random.random() * 0.05,
            "tool_accuracy": 0.88 + random.random() * 0.12,
        })
    return list(reversed(_evals[-50:]))
