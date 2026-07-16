from __future__ import annotations

from api.shared.vertical_pack import VerticalRuntime


def current_runtime() -> VerticalRuntime:
    from api.server.state import app_state

    return app_state.runtime
