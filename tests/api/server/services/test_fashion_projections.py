from api.server.services.entity_projections import EntityWrite
from api.shared.types import Workflow
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.projections import FASHION_PROJECTIONS


def _workflow(workflow_type: str) -> Workflow:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    return Workflow.model_construct(
        id=f"WF-{workflow_type}",
        type=workflow_type,
        status="completed",
        current_phase=profile.phases[-1].name,
        created_at=0.0,
        sla_due_at=1.0,
        jurisdiction="GB",
        agency="Zava",
        payload={
            "process_case": {
                "case": {
                    "id": profile.case_id,
                    "workflow_type": workflow_type,
                    "status": "completed",
                    "subject_ids": [f"SUBJECT-{workflow_type}"],
                    "outcome": {
                        "action": profile.allowed_actions[1],
                        "mutation_family": profile.mutation_family,
                    },
                }
            }
        },
    )


def test_every_fashion_workflow_projects_terminal_identity_and_case() -> None:
    for workflow_type, profile in FASHION_PROCESS_PROFILES.items():
        operations = FASHION_PROJECTIONS[workflow_type](
            _workflow(workflow_type)
        )
        entities = [
            operation
            for operation in operations
            if isinstance(operation, EntityWrite)
        ]

        workflow_node = next(
            entity for entity in entities if entity.kind == "Workflow"
        )
        case_node = next(
            entity
            for entity in entities
            if entity.attrs.get("kind") == "fashion-process-case"
        )
        assert workflow_node.id == f"WF-{workflow_type}"
        assert workflow_node.attrs == {
            "workflow_type": workflow_type,
            "status": "completed",
            "terminal_phase": profile.phases[-1].name,
        }
        assert case_node.attrs["workflow_type"] == workflow_type
        assert case_node.attrs["mutation_family"] == profile.mutation_family
        assert case_node.source_workflows == (workflow_node.id,)
