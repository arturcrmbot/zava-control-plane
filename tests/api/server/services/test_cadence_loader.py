"""Tests for the Phase 4 IP1 cadence YAML loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.cadence_loader import (
    Cadence,
    CadenceConfigError,
    load_cadences,
)


def _write(p: Path, body: str) -> Path:
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_valid_yaml(tmp_path: Path):
    _write(tmp_path / "morning-sweep.yaml",
           "name: morning-sweep\nschedule: \"0 9 * * 1-5\"\nfires_ambient_agent: morning-sweep\n")
    cads = load_cadences(tmp_path)
    assert cads == [Cadence(
        name="morning-sweep",
        schedule="0 9 * * 1-5",
        fires_ambient_agent="morning-sweep",
    )]


def test_empty_dir_returns_empty_list(tmp_path: Path):
    assert load_cadences(tmp_path) == []


def test_missing_dir_returns_empty_list(tmp_path: Path):
    assert load_cadences(tmp_path / "does-not-exist") == []


def test_invalid_cron_raises(tmp_path: Path):
    _write(tmp_path / "bad.yaml",
           "name: bad\nschedule: not-a-cron\nfires_ambient_agent: x\n")
    with pytest.raises(CadenceConfigError, match="not a valid cron"):
        load_cadences(tmp_path)


def test_missing_fires_ambient_agent_raises(tmp_path: Path):
    _write(tmp_path / "x.yaml", "name: x\nschedule: \"* * * * *\"\n")
    with pytest.raises(CadenceConfigError, match="fires_ambient_agent"):
        load_cadences(tmp_path)


def test_filename_mismatch_raises(tmp_path: Path):
    _write(tmp_path / "alpha.yaml",
           "name: beta\nschedule: \"* * * * *\"\nfires_ambient_agent: x\n")
    with pytest.raises(CadenceConfigError, match="filename stem"):
        load_cadences(tmp_path)
