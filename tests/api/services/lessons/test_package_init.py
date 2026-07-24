from __future__ import annotations

import sys


def test_build_default_memory_is_lazy_export(monkeypatch) -> None:
    sys.modules.pop("api.server.services.lessons.mem0_store", None)
    sys.modules.pop("api.server.services.lessons", None)

    import api.server.services.lessons  # noqa: F401

    assert "api.server.services.lessons.mem0_store" not in sys.modules

    from api.server.services.lessons import build_default_memory

    assert build_default_memory.__name__ == "build_default_memory"
    assert "api.server.services.lessons.mem0_store" in sys.modules
