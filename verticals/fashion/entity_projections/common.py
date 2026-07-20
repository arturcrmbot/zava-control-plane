from __future__ import annotations

import json

from api.server.services.entity_projections import EntityWrite, slug
from api.shared.types import Workflow
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES


def project(workflow: Workflow) -> list[EntityWrite]:
    profile = FASHION_PROCESS_PROFILES[workflow.type]
    observation = (workflow.payload or {}).get("process_case") or {}
    case = observation.get("case") or observation
    case_id = str(case.get("id") or workflow.id)
    outcome = case.get("outcome") or {}
    return [
        EntityWrite(
            kind="Workflow",
            id=workflow.id,
            attrs={
                "workflow_type": workflow.type,
                "status": workflow.status,
                "terminal_phase": profile.phases[-1].name,
            },
            source_workflows=(workflow.id,),
        ),
        EntityWrite(
            kind="Asset",
            id=f"ASSET-fashion-case-{slug(case_id)}",
            attrs={
                "kind": "fashion-process-case",
                "identifier": case_id,
                "workflow_type": workflow.type,
                "status": str(case.get("status") or workflow.status),
                "mutation_family": str(
                    outcome.get("mutation_family")
                    or profile.mutation_family
                ),
                "attributes": json.dumps(
                    {
                        "subject_ids": case.get("subject_ids") or [],
                        "outcome": outcome,
                    },
                    sort_keys=True,
                    default=str,
                ),
            },
            source_workflows=(workflow.id,),
        ),
    ]
