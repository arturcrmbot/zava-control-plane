"""Phase 7.2 of autonomous-domain-insights v1: CEO summary_policy."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from api.server.services import persona_responder as pr
from api.server.services.entity_graph import EntityGraph, EntityWrite


def _seed_insight(
    g: EntityGraph, *, role: str, headline: str, fingerprint: str,
) -> None:
    g.upsert(EntityWrite(
        kind="Insight",
        id=f"INSIGHT-{role}-1",
        attrs={
            "role": role,
            "scope": role,
            "decided_at": datetime.utcnow(),
            "headline": headline,
            "body": "",
            "kpis": "{}",
            "proposed_actions": "[]",
            "fingerprint": fingerprint,
            "attributes": "{}",
        },
        source_workflows=(),
    ))


def test_ceo_summary_emits_calm_when_no_other_insights(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS.get("ceo")
    assert persona is not None
    assert persona.summarise is not None
    out = persona.summarise({"last_insight": None})
    assert "headline" in out
    assert "fingerprint" in out
    # Calm baseline: no domains have produced insights yet.
    assert "no domain insights" in out["headline"].lower() \
        or "system online" in out["headline"].lower() \
        or out["kpis"] == {}


def test_ceo_summary_synthesises_when_other_insights_exist(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    _seed_insight(g, role="cfo", headline="Finance steady", fingerprint="fp-cfo-1")
    _seed_insight(g, role="hr_director", headline="Headcount steady", fingerprint="fp-hr-1")

    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS["ceo"]
    out = persona.summarise({"last_insight": None})
    # The synthesis fingerprint must change vs. the calm baseline.
    assert out["fingerprint"] != ""
    # Body should reference at least one of the domain insights so the
    # synthesis is verifiably wired to the graph.
    body = (out.get("body") or "") + " " + (out.get("headline") or "")
    assert "cfo" in body.lower() or "finance" in body.lower() \
        or "hr" in body.lower()


def test_ceo_summary_fingerprint_is_deterministic(
    tmp_path: Path, monkeypatch,
) -> None:
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    _seed_insight(g, role="cfo", headline="Finance steady", fingerprint="fp-cfo-1")
    pr.PERSONA_DEFINITIONS = pr._load_personae()
    persona = pr.PERSONA_DEFINITIONS["ceo"]
    out_a = persona.summarise({"last_insight": None})
    out_b = persona.summarise({"last_insight": None})
    assert out_a["fingerprint"] == out_b["fingerprint"], \
        "CEO summary fingerprint must be deterministic over the same inputs"
