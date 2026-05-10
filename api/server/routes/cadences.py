"""HTTP surface for the cadence loader — Phase 4 IP7 (TASK-035).

`GET /api/cadences` returns ``[{name, schedule, fires_ambient_agent,
next_run_at}]`` from the in-process cadence loader. ``next_run_at`` is
computed at call time via ``croniter.get_next()`` so it always reflects
"the next fire from right now". Cheap (one cron parse per cadence) —
the page polls this every 5s safely.
"""
from __future__ import annotations

import datetime as _dt

from croniter import croniter
from fastapi import APIRouter

from api.server.state import app_state

router = APIRouter(prefix="/api/cadences")


@router.get("")
@router.get("/", include_in_schema=False)
async def list_cadences():
    cadences = getattr(app_state, "cadences", []) or []
    now = _dt.datetime.now()
    out: list[dict] = []
    for cad in cadences:
        try:
            nxt = croniter(cad.schedule, now).get_next(_dt.datetime)
            next_run = nxt.isoformat()
        except Exception:
            next_run = None
        out.append({
            "name": cad.name,
            "schedule": cad.schedule,
            "fires_ambient_agent": cad.fires_ambient_agent,
            "next_run_at": next_run,
        })
    return out
