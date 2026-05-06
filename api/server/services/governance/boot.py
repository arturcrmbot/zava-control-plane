"""Governance startup hook.

Called once from FastAPI's ``lifespan`` ([api/server/main.py](../../main.py))
and once at Functions worker module load ([function_app.py](../../../../function_app.py)).
Idempotent: subsequent calls return the existing singleton.

Phase 1 scope: log the kernel construction (AGT version, policy_version,
enforcement_mode) so a boot failure surfaces immediately. Compilation +
real policy load arrives in Phase 2 (TASK-014).
"""
from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version as _pkg_version

from .kernel import GovernanceKernel, kernel

log = logging.getLogger(__name__)


def _agt_version() -> str:
    try:
        return _pkg_version("agent-governance-toolkit")
    except PackageNotFoundError:  # pragma: no cover — install probe handles this
        return "unknown"


def init_governance() -> GovernanceKernel:
    """Construct (or return) the kernel singleton and log its identity.

    Safe to call multiple times — both the FastAPI lifespan and the
    Functions worker module load invoke this on independent processes,
    and tests may invoke it as well. Returns the singleton so callers
    that want to hold a local reference (e.g. for benchmarking) can.
    """
    k = kernel()
    log.info(
        "governance: kernel ready, agt_version=%s, policy_version=%s, enforcement=%s",
        _agt_version(),
        k.policy_version,
        k.enforcement_mode,
    )
    return k
