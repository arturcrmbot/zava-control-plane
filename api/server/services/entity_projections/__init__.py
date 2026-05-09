"""Per-domain projection registry (Phase 1 sub-phase 2 — TASK-009).

A *projection* is a pure function that maps a :class:`Workflow` to a list
of graph-write ops (``EntityWrite`` / ``RelWrite`` / ``DecisionWrite``).
The :class:`EntityReflector` looks up the projection for a workflow's
``type`` in :data:`PROJECTIONS` on every relevant FleetEvent and dispatches
the returned ops to :class:`EntityGraph`.

Registry pattern (CON-001 / TASK-014 contract)
----------------------------------------------

The registry is a plain module-level dict that each domain module mutates
at import time::

    # api/server/services/entity_projections/vendor_kyc.py
    WORKFLOW_TYPE = "vendor-kyc"

    def project(wf: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
        ...

    PROJECTIONS[WORKFLOW_TYPE] = project

Sub-phase 3 will land one such module per domain TASK and uncomment the
matching ``from . import <domain>`` line below. Each missing module is
therefore an explicit ``ImportError`` at boot rather than a silent
no-op — as soon as a line is uncommented, the registry must contain
the corresponding entry once import completes.

Today (sub-phase 2) NO domain modules exist yet, so all imports stay
commented and ``PROJECTIONS == {}``. The reflector handles an empty
registry by silently no-op'ing on every event (REQ: unknown workflow_type
is not an error).
"""
from __future__ import annotations

from typing import Callable

from api.server.services.entity_graph import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
)
from api.shared.types import Workflow

__all__ = [
    "DecisionWrite",
    "EntityWrite",
    "PROJECTIONS",
    "ProjectionFn",
    "RelWrite",
]


ProjectionFn = Callable[[Workflow], list[EntityWrite | RelWrite | DecisionWrite]]

# Registry: workflow_type → projection function. Each domain module
# registers itself at import time via `PROJECTIONS[WORKFLOW_TYPE] = project`.
PROJECTIONS: dict[str, ProjectionFn] = {}


# Sub-phase 3 fills in these imports as each domain module is added.
# Each import has the side effect of registering the domain in PROJECTIONS
# via the module's `WORKFLOW_TYPE → project` binding (each module ends with
# `PROJECTIONS[WORKFLOW_TYPE] = project`).
# from . import ap_invoice            # TASK-015
# from . import contract_renewal      # TASK-016
# from . import contract_review       # TASK-017
# from . import creative_campaign     # TASK-018
# from . import employee_onboarding   # TASK-019
# from . import it_access_request     # TASK-020
# from . import perf_review           # TASK-021
# from . import privacy_dpia          # TASK-022
# from . import purchase_order        # TASK-023
# from . import travel_preapproval    # TASK-024
# from . import treasury_fx           # TASK-025
# from . import vendor_kyc            # TASK-026
