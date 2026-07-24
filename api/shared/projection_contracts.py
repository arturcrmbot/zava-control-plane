from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from api.shared.types import Workflow


ProjectionFn = Callable[[Workflow], Sequence[Any]]

# A pack-owned, industry-neutral hook that assembles a richer, human-
# inspectable detail payload for one workflow than the pure `ProjectionFn`
# contract allows. Unlike `ProjectionFn`, it also receives the live
# `app_state` (its type is intentionally `Any` here -- app_state is a
# server-runtime construct, not a shared contract type) so it may read
# world/objective state a projection cannot. Returns `None` when the given
# workflow's type is not one this pack's hook understands, or when there is
# genuinely nothing yet to report; never a fabricated placeholder. Any
# generic route consuming this (e.g. `GET /api/workflows/{id}`) must merge
# the non-`None` result under one namespaced key (e.g. `"packDetail"`)
# without branching on which vertical produced it.
WorkflowDetailHook = Callable[[Workflow, Any], Mapping[str, Any] | None]
