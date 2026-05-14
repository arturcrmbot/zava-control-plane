"""Projection: media-pitch-to-win (pitch-c2 meta-workflow).

Emits a single Workflow node — the parent stamp. Per-child
SUB_WORKFLOW_OF rels are owned by api.server.services.meta_workflow_reflector,
which subscribes to the workflow.sub_spawned bus events emitted by the
spawn function.
"""
from __future__ import annotations

from api.server.services.entity_projections import EntityWrite
from api.shared.types import Workflow

WORKFLOW_TYPE = "media-pitch-to-win"


def project(workflow: Workflow) -> list[EntityWrite]:
    return [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={"workflow_type": WORKFLOW_TYPE, "status": workflow.status},
            source_workflows=(workflow.id,),
        ),
    ]
