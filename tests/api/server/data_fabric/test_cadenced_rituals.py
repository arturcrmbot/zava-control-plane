"""Registry tests for cadenced rituals — pitch-e5."""
from __future__ import annotations

from croniter import croniter

from api.server.data_fabric.cadenced_rituals import (
    CADENCED_RITUALS,
    CadencedRitual,
)
from api.shared.domains import DOMAINS


def test_registry_non_empty():
    assert len(CADENCED_RITUALS) >= 5
    assert all(isinstance(r, CadencedRitual) for r in CADENCED_RITUALS)


def test_each_ritual_references_real_domain():
    missing = [r.workflow_type for r in CADENCED_RITUALS
               if r.workflow_type not in DOMAINS]
    assert not missing, f"unknown workflow_type(s): {missing}"


def test_every_cron_parses():
    for r in CADENCED_RITUALS:
        assert croniter.is_valid(r.cron_like), \
            f"ritual {r.name} cron {r.cron_like!r} invalid"


def test_descriptions_non_empty():
    for r in CADENCED_RITUALS:
        assert isinstance(r.description, str) and r.description.strip(), \
            f"ritual {r.name} has empty description"


def test_names_unique():
    names = [r.name for r in CADENCED_RITUALS]
    assert len(names) == len(set(names))
