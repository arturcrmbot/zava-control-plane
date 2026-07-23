from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_shared_world_substrate_contains_no_fashion_branch() -> None:
    shared_sources = (
        "api/server/main.py",
        "api/server/routes/world.py",
        "api/server/world/service.py",
        "web/client/routes/World.tsx",
        "web/client/hooks/useWorldSimulation.ts",
    )

    leaked = [
        path
        for path in shared_sources
        if "fashion" in (ROOT / path).read_text(encoding="utf-8").lower()
    ]

    assert leaked == []

