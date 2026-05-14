"""Projection: intercompany-talent-transfer (pitch-c3 + pitch-h5 entanglement).

Emits a Person (the transferring employee) + two Organisations (the
sending and receiving subsidiaries — kept as Organisation kind to
remain compatible with simple ORG- ids; pitch-e3 also adds Subsidiary
nodes for richer geography views) + a DecisionWrite at the
hr_director_signoff gate.

pitch-h5 (entanglement) extends the projection to also emit four child
Workflow nodes + SUB_WORKFLOW_OF rels so a single talent-transfer
rocket visibly cascades into:

* ``it-access-request`` (revoke at the source subsidiary)
* ``it-access-request`` (grant at the destination subsidiary)
* ``employee-onboarding`` (destination subsidiary onboarding)
* ``perf-review`` (reopen the cycle to align comp)

The TalentTransferCascade ambient agent (started from the FastAPI
lifespan) emits matching ``workflow.sub_spawned`` bus events when the
parent workflow completes — both writers MERGE on (parent, child) so
double writes are idempotent.
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "intercompany-talent-transfer"

# (child_workflow_type, suffix) — suffix disambiguates the two
# it-access-request children (revoke vs grant on the same parent id).
CHILD_SPECS: tuple[tuple[str, str], ...] = (
    ("it-access-request", "revoke"),
    ("it-access-request", "grant"),
    ("employee-onboarding", "onb"),
    ("perf-review", "prr"),
)


def child_workflow_id(child_type: str, suffix: str, parent_id: str) -> str:
    return f"WF-{child_type}-{suffix}-{parent_id}"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    t = p.get("transfer") or {}
    employee_id = str(t.get("employee_id") or p.get("employee_id") or workflow.id)
    from_sub = str(t.get("from_subsidiary") or p.get("from_subsidiary") or "unknown-from")
    to_sub = str(t.get("to_subsidiary") or p.get("to_subsidiary") or "unknown-to")

    person_id = f"PERSON-{employee_id}"
    from_id = f"ORG-subsidiary-{slug(from_sub)}"
    to_id = f"ORG-subsidiary-{slug(to_sub)}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs={"transferring": True},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Organisation",
            id=from_id,
            attrs={"name": from_sub, "kind": "subsidiary"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Organisation",
            id=to_id,
            attrs={"name": to_sub, "kind": "subsidiary"},
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": WORKFLOW_TYPE, "status": workflow.status},
            source_workflows=sw,
        ),
    ]
    for child_type, suffix in CHILD_SPECS:
        cid = child_workflow_id(child_type, suffix, workflow.id)
        ops.append(EntityWrite(
            kind="Workflow",
            id=cid,
            attrs={"workflow_type": child_type, "status": "spawned",
                   "cascade_role": suffix},
            source_workflows=(cid,),
        ))
        ops.append(RelWrite(
            src_id=workflow.id,
            rel="SUB_WORKFLOW_OF",
            dst_id=cid,
        ))

    d = build_decision(
        workflow,
        gate_phase="hr_director_signoff",
        persona_role="hr_director",
        source_event="workflow.hitl.requested",
        decided_on=(person_id, from_id, to_id),
        attributes={"employee_id": employee_id, "from": from_sub, "to": to_sub},
    )
    if d is not None:
        ops.append(d)

    return ops
