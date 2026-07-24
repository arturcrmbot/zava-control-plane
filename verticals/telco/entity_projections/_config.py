from __future__ import annotations

import os

_GRAPH_DETAIL_CAP_ENV = "TELCO_GRAPH_DETAIL_CAP"
_DEFAULT_GRAPH_DETAIL_CAP = 25


def graph_detail_cap() -> int:
    raw = os.environ.get(_GRAPH_DETAIL_CAP_ENV)
    if raw is None:
        return _DEFAULT_GRAPH_DETAIL_CAP
    try:
        cap = int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"{_GRAPH_DETAIL_CAP_ENV} must be a positive integer; got {raw!r}"
        ) from exc
    if cap <= 0:
        raise ValueError(
            f"{_GRAPH_DETAIL_CAP_ENV} must be a positive integer; got {raw!r}"
        )
    return cap
