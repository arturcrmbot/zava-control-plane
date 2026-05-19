from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from api.server.services.scoring.rubric_loader import (
    RubricLoadError,
    load_rubric,
)


def test_load_minimal_rubric(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text(dedent("""
        domain: demo
        promotion_threshold: 0.05
        min_samples: 20
        checks:
          - name: match
            kind: decision_matches_label
            weight: 1.0
    """))
    rubric = load_rubric(yaml_path)
    assert rubric.domain == "demo"
    assert rubric.promotion_threshold == 0.05
    assert rubric.min_samples == 20
    assert len(rubric.checks) == 1
    assert rubric.checks[0].name == "match"


def test_missing_domain_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text("promotion_threshold: 0.05\nmin_samples: 20\nchecks: []\n")
    with pytest.raises(RubricLoadError, match="domain"):
        load_rubric(yaml_path)


def test_no_checks_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text("domain: x\npromotion_threshold: 0.05\nmin_samples: 20\nchecks: []\n")
    with pytest.raises(RubricLoadError, match="at least one check"):
        load_rubric(yaml_path)


def test_unknown_check_kind_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text(dedent("""
        domain: x
        promotion_threshold: 0.05
        min_samples: 20
        checks:
          - name: x
            kind: bogus_kind
            weight: 1.0
    """))
    with pytest.raises(RubricLoadError, match="bogus_kind"):
        load_rubric(yaml_path)


def test_loads_hiring_rubric_from_repo() -> None:
    rubric = load_rubric(Path("data/rubrics/hiring.yaml"))
    assert rubric.domain == "hiring"
    names = {c.name for c in rubric.checks}
    assert "decision_matches_label" in names
