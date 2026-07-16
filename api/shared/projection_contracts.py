from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from api.shared.types import Workflow


ProjectionFn = Callable[[Workflow], Sequence[Any]]
