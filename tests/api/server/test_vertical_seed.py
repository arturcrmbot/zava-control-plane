from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from verticals.agency import lifecycle as agency_lifecycle
from verticals.telco import lifecycle as telco_lifecycle


class FakeEntities:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def bootstrap_from_fixtures(self, **paths) -> None:
        self.calls.append(paths)


def test_agency_seed_bootstraps_only_agency_fixtures() -> None:
    entities = FakeEntities()
    agency_lifecycle.bootstrap(SimpleNamespace(entities=entities))

    assert len(entities.calls) == 1
    paths = entities.calls[0]
    assert Path(paths["employees_path"]).as_posix().endswith(
        "data/synthetic/employees.json"
    )
    assert Path(paths["vendors_path"]).as_posix().endswith(
        "api/server/fixtures/vendors.json"
    )
    assert Path(paths["agencies_path"]).as_posix().endswith(
        "api/server/fixtures/agencies.json"
    )


def test_telco_seed_does_not_bootstrap_agency_fixtures() -> None:
    entities = FakeEntities()
    telco_lifecycle.bootstrap(SimpleNamespace(entities=entities))

    assert entities.calls == []
