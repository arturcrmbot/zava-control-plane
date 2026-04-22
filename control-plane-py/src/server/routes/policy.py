from __future__ import annotations
import time
from pathlib import Path
import yaml
from fastapi import APIRouter
from pydantic import BaseModel
from src.server.state import app_state
from src.shared.types import AutonomyPolicy

router = APIRouter(prefix="/api/policy")

_change_requests: list[dict] = []


def _load_policies() -> None:
    path = Path(__file__).resolve().parents[2] / "shared" / "policies.yaml"
    data = yaml.safe_load(path.read_text())
    for p in data["policies"]:
        app_state.store.upsert_policy(AutonomyPolicy(
            id=p["id"], description=p["description"], current_value=p["value"],
            git_sha=p["gitSha"], author=p["author"],
            updated_at=time.mktime(time.strptime(p["updatedAt"], "%Y-%m-%dT%H:%M:%SZ")),
        ))


_load_policies()


class DryRunBody(BaseModel):
    policy_id: str
    proposed_value: float | str | bool
    scope_days: int = 7


class ProposeChangeBody(BaseModel):
    policy_id: str
    proposed_value: float | str | bool
    rationale: str
    proposed_by: str


@router.get("/")
async def list_policies():
    return [p.model_dump(by_alias=True) for p in app_state.store.list_policies()]


@router.post("/dry-run")
async def dry_run(body: DryRunBody):
    from src.server.mcp_tools.dry_run_policy import dry_run_policy_impl
    return dry_run_policy_impl(app_state.store, body.policy_id, body.proposed_value, body.scope_days)


@router.post("/propose-change")
async def propose_change(body: ProposeChangeBody):
    id = f"CR-{int(time.time())}"
    _change_requests.append({"id": id, **body.model_dump(), "created_at": time.time()})
    return {"id": id}


@router.get("/change-requests")
async def list_change_requests():
    return _change_requests
