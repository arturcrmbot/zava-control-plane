"""Phase 4 of autonomous-domain-insights v1: cadence loop."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services import persona_responder as pr


def _write_skill(skill_dir: Path, role: str, with_summary: bool) -> None:
    skill_dir.mkdir(parents=True)
    parts = [
        "---\n",
        f"name: {role}\n",
        "description: test\n",
        "allowed-tools:\n",
        "workflow_label: Test\n",
        "external_event: test_signoff_decision\n",
        "decision_policy: |\n",
        '    decision = "approve"\n',
        '    reason = "fixture"\n',
    ]
    if with_summary:
        parts.extend([
            "summary_policy: |\n",
            "    summary = {\n",
            '        "headline": "calm", "body": "", "kpis": {},\n',
            '        "proposed_actions": [], "fingerprint": "fp-1",\n',
            "    }\n",
        ])
    parts.extend([
        "---\n",
        "\n",
        f"# {role}\n",
    ])
    (skill_dir / "SKILL.md").write_text("".join(parts), encoding="utf-8")


@pytest.mark.asyncio
async def test_loop_emits_one_event_per_summary_persona(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_skill(tmp_path / "personae" / "test-fixture", "test-fixture", True)

    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    pr.PERSONA_DEFINITIONS = pr._load_personae()

    emitted = []

    class FakeBus:
        def emit(self, event):
            emitted.append(event)

    await pr._insight_loop_tick(FakeBus())

    assert len(emitted) == 1
    assert emitted[0].type == "domain.summary.requested"
    assert emitted[0].payload == {"role": "test-fixture"}


@pytest.mark.asyncio
async def test_loop_skips_personas_without_summary_policy(
    tmp_path: Path, monkeypatch,
) -> None:
    for role, with_sum in (("with-sum", True), ("no-sum", False)):
        _write_skill(tmp_path / "personae" / role, role, with_sum)

    monkeypatch.setattr(pr, "PERSONAE_DIR", tmp_path / "personae")
    pr.PERSONA_DEFINITIONS = pr._load_personae()

    emitted = []

    class FakeBus:
        def emit(self, event):
            emitted.append(event)

    await pr._insight_loop_tick(FakeBus())
    roles = sorted(e.payload["role"] for e in emitted)
    assert roles == ["with-sum"]
