"""Phase 3.3 of autonomous-domain-insights v1: end-to-end summary handling."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph
from api.shared.events import FleetEvent


def _write_persona_skill(
    tmp_path: Path, *, fingerprint: str, headline: str = "calm",
) -> None:
    """Write/overwrite the test-fixture SKILL.md and reload personae."""
    skill = tmp_path / "personae" / "test-fixture" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    # Flush-left construction: avoid textwrap.dedent + f-string interpolation
    # whose embedded values may collapse the common-leading-whitespace count.
    content = (
        "---\n"
        "name: test-fixture\n"
        "description: test\n"
        "allowed-tools:\n"
        "workflow_label: Test\n"
        "external_event: test_signoff_decision\n"
        "decision_policy: |\n"
        '    decision = "approve"\n'
        '    reason = "fixture"\n'
        "summary_policy: |\n"
        f'    summary = {{"headline": "{headline}", "body": "fixture body", '
        f'"kpis": {{}}, "proposed_actions": [], "fingerprint": "{fingerprint}"}}\n'
        "---\n"
        "\n"
        "# test-fixture\n"
    )
    skill.write_text(content, encoding="utf-8")
    pr.PERSONA_DEFINITIONS = pr._load_personae()


def _make_fixture_persona(
    tmp_path: Path, monkeypatch, *, fingerprint: str, headline: str = "calm",
) -> EntityGraph:
    """Wire a tmp graph + a single fixture persona with a summary_policy
    that returns the given fingerprint + headline. Returns the graph for
    caller assertions.
    """
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    _write_persona_skill(tmp_path, fingerprint=fingerprint, headline=headline)
    return g


@pytest.mark.asyncio
async def test_first_summary_writes_insight(tmp_path: Path, monkeypatch) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))
    rows = g.query(
        "MATCH (i:Insight {role: 'test-fixture'}) RETURN i.headline AS h, i.fingerprint AS f")
    assert len(rows) == 1
    assert rows[0]["h"] == "calm"
    assert rows[0]["f"] == "fp-1"


@pytest.mark.asyncio
async def test_no_change_does_not_write(tmp_path: Path, monkeypatch) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))
    rows = g.query("MATCH (i:Insight) RETURN count(i) AS n")
    assert rows[0]["n"] == 1, "second tick with same fingerprint must not write"


@pytest.mark.asyncio
async def test_changed_fingerprint_writes_new_insight(
    tmp_path: Path, monkeypatch,
) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))

    # Rewrite the SKILL.md with a different fingerprint and reload (reusing
    # the same graph; reopening Kuzu at the same path would create a second
    # writer).
    _write_persona_skill(tmp_path, fingerprint="fp-2", headline="alarm")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "test-fixture"}))

    rows = g.query(
        "MATCH (i:Insight) RETURN i.fingerprint AS f, i.headline AS h ORDER BY i.decided_at")
    assert [r["f"] for r in rows] == ["fp-1", "fp-2"]
    assert [r["h"] for r in rows] == ["calm", "alarm"]


@pytest.mark.asyncio
async def test_unknown_role_is_no_op(tmp_path: Path, monkeypatch) -> None:
    g = _make_fixture_persona(tmp_path, monkeypatch, fingerprint="fp-1")
    await pr._handle_summary_request(
        FleetEvent(type="domain.summary.requested", payload={"role": "nonexistent"}))
    rows = g.query("MATCH (i:Insight) RETURN count(i) AS n")
    assert rows[0]["n"] == 0
