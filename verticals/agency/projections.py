from importlib.util import find_spec

from verticals._helpers import lazy_projection
from verticals.agency.domains import AGENCY_DOMAINS


def _projection_module(workflow_type: str) -> str:
    module_name = workflow_type.replace("-", "_")
    pack_local = f"verticals.agency.entity_projections.{module_name}"
    if find_spec(pack_local) is not None:
        return pack_local
    return f"api.server.services.entity_projections.{module_name}"


AGENCY_PROJECTIONS = {
    workflow_type: lazy_projection(_projection_module(workflow_type))
    for workflow_type in AGENCY_DOMAINS
}
