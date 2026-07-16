from pathlib import Path

from verticals._helpers import empty_lifecycle as start


_REPO_ROOT = Path(__file__).resolve().parents[2]


def bootstrap(state) -> None:
    if not hasattr(state, "entities"):
        return
    state.entities.bootstrap_from_fixtures(
        employees_path=_REPO_ROOT / "data" / "synthetic" / "employees.json",
        vendors_path=_REPO_ROOT / "api" / "server" / "fixtures" / "vendors.json",
        agencies_path=_REPO_ROOT / "api" / "server" / "fixtures" / "agencies.json",
    )

__all__ = ["bootstrap", "start"]
