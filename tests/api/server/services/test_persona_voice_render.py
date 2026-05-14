"""v1.2: voice_render block humanises Insight bodies."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph
from api.shared.events import FleetEvent


def _write_skill(tmp_path: Path, *, voice_block: str | None) -> None:
    """Write a fixture persona SKILL.md with an optional voice_render block."""
    skill = tmp_path / "personae" / "test-voice" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    voice_section = ""
    if voice_block is not None:
        voice_section = "voice_render: |\n" + voice_block
    content = (
        "---\n"
        "name: test-voice\n"
        "description: test\n"
        "allowed-tools:\n"
        "workflow_label: Test\n"
        "external_event: test_voice_decision\n"
        "decision_policy: |\n"
        '    decision = "approve"\n'
        '    reason = "fixture"\n'
        "summary_policy: |\n"
        '    summary = {"headline": "h", "body": "structured body", '
        '"kpis": {"x": 1}, "proposed_actions": [], "fingerprint": "fp-1"}\n'
        + voice_section
        + "---\n"
        "\n"
        "# test-voice\n"
    )
    skill.write_text(content, encoding="utf-8")
    pr.PERSONA_DEFINITIONS = pr._load_personae()


def _wire(tmp_path: Path, monkeypatch, *, voice_block: str | None) -> EntityGraph:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    _write_skill(tmp_path, voice_block=voice_block)
    return g


@pytest.mark.asyncio
async def test_voice_render_overrides_body(tmp_path: Path, monkeypatch) -> None:
    g = _wire(tmp_path, monkeypatch, voice_block='    body = "spoken body"\n')
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-voice"}))
    rows = g.query("MATCH (i:Insight {role: 'test-voice'}) RETURN i.body AS b")
    assert len(rows) == 1
    assert rows[0]["b"] == "spoken body"


@pytest.mark.asyncio
async def test_voice_render_falls_through_when_returns_none(
    tmp_path: Path, monkeypatch,
) -> None:
    # voice_render that doesn't set body — structured body wins.
    g = _wire(tmp_path, monkeypatch, voice_block='    pass\n')
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-voice"}))
    rows = g.query("MATCH (i:Insight {role: 'test-voice'}) RETURN i.body AS b")
    assert rows[0]["b"] == "structured body"


@pytest.mark.asyncio
async def test_voice_render_error_falls_through(tmp_path: Path, monkeypatch) -> None:
    g = _wire(tmp_path, monkeypatch, voice_block='    raise ValueError("boom")\n')
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-voice"}))
    rows = g.query("MATCH (i:Insight {role: 'test-voice'}) RETURN i.body AS b")
    assert rows[0]["b"] == "structured body"


def test_personas_with_voice_block_load() -> None:
    """At least 5 real personae should ship a voice_render block in v1.2."""
    defs = pr._load_personae()
    voiced = [p for p in defs.values() if p.voice is not None]
    assert len(voiced) >= 5, (
        f"expected >=5 personae with voice_render, got {len(voiced)}: "
        f"{sorted(p.role for p in voiced)}"
    )


@pytest.mark.asyncio
async def test_no_voice_block_preserves_structured_body(
    tmp_path: Path, monkeypatch,
) -> None:
    """Regression: a persona with no voice_render writes the structured body."""
    g = _wire(tmp_path, monkeypatch, voice_block=None)
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-voice"}))
    rows = g.query("MATCH (i:Insight {role: 'test-voice'}) RETURN i.body AS b")
    assert rows[0]["b"] == "structured body"
