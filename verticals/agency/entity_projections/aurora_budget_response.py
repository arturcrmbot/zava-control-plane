from __future__ import annotations

from api.shared.types import Workflow


def project(workflow: Workflow) -> tuple:
    """Aurora writes its governed policy Decision at approval time.

    The root workflow has no additional business entity to materialise; its
    budget signal links existing Money and Brand nodes directly.
    """
    return ()
