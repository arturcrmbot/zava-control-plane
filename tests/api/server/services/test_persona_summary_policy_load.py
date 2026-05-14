"""Phase 3.2 of autonomous-domain-insights v1: summary_policy compile."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr


def _write_skill(path: Path, *, with_summary: bool) -> None:
    summary_block = ""
    if with_summary:
        summary_block = (
            "summary_policy: |\n"
            "    summary = {\n"
            '        "headline": "calm",\n'
            '        "body": "all quiet",\n'
            '        "kpis": {},\n'
            '        "proposed_actions": [],\n'
            '        "fingerprint": "f0",\n'
            "    }\n"
        )
    skill = (
        "---\n"
        f"name: {path.parent.name}\n"
        "description: test\n"
        "allowed-tools:\n"
        "workflow_label: Test\n"
        "external_event: test_signoff_decision\n"
        "decision_policy: |\n"
        '    decision = "approve"\n'
        '    reason = "fixture"\n'
        f"{summary_block}"
        "---\n"
        "\n"
        "# test-fixture\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(skill, encoding="utf-8")


def test_summary_policy_loaded_when_present(
    tmp_path: Path, monkeypatch,
) -> None:
    skill = tmp_path / "test-fixture" / "SKILL.md"
    _write_skill(skill, with_summary=True)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path)
    loaded = pr._load_personae()
    persona = loaded.get("test-fixture")
    assert persona is not None
    assert persona.summarise is not None
    out = persona.summarise({"last_insight": None})
    assert out["fingerprint"] == "f0"
    assert out["headline"] == "calm"


def test_summarise_is_none_when_block_absent(
    tmp_path: Path, monkeypatch,
) -> None:
    skill = tmp_path / "test-fixture" / "SKILL.md"
    _write_skill(skill, with_summary=False)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path)
    loaded = pr._load_personae()
    persona = loaded.get("test-fixture")
    assert persona is not None
    assert persona.summarise is None


def test_personae_with_summary_policy_filter(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_skill(tmp_path / "with-sum" / "SKILL.md", with_summary=True)
    _write_skill(tmp_path / "no-sum" / "SKILL.md", with_summary=False)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path)
    loaded = pr._load_personae()
    monkeypatch.setattr(pr, "PERSONA_DEFINITIONS", loaded)
    roles = sorted(p.role for p in pr.personae_with_summary_policy())
    assert roles == ["with-sum"]
