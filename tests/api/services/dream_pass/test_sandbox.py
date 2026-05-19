from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.dream_pass.sandbox import InterviewRecommenderSandbox


@pytest.fixture
def fake_session(monkeypatch):
    calls: list[dict] = []

    async def fake_run(*, prompt, tools, skill_dir, skill_label, workflow_id, **kwargs):
        calls.append({'prompt': prompt, 'skill_label': skill_label, 'workflow_id': workflow_id})
        if 'sentinel-reject-lesson' in prompt:
            return {'decision': 'decline', 'rationale': 'sentinel matched'}
        return {'decision': 'advance', 'rationale': 'baseline'}

    monkeypatch.setattr('api.server.services.dream_pass.sandbox.run_agent_session', fake_run)
    return calls


@pytest.mark.asyncio
async def test_sandbox_runs_real_agent_with_empty_lessons(fake_session, tmp_path: Path) -> None:
    cvs = [
        {'candidate_id': 'C-001', 'role_title': 'Engineer'},
        {'candidate_id': 'C-002', 'role_title': 'Engineer'},
    ]
    sandbox = InterviewRecommenderSandbox(kuzu_root=tmp_path / 'sb')
    try:
        result = await sandbox.run_arm(cvs=cvs, lessons=[], working_notes=[])
    finally:
        sandbox.close()

    assert len(result.workflow_ids) == 2
    assert all('sentinel-reject-lesson' not in call['prompt'] for call in fake_session)


@pytest.mark.asyncio
async def test_sandbox_lesson_injection_changes_final_decision(fake_session, tmp_path: Path) -> None:
    sandbox = InterviewRecommenderSandbox(kuzu_root=tmp_path / 'sb')
    try:
        await sandbox.run_arm(
            cvs=[{'candidate_id': 'C-001', 'role_title': 'Engineer'}],
            lessons=['sentinel-reject-lesson'],
            working_notes=[],
        )
        rows = sandbox.graph.query('MATCH (d:Decision) RETURN d.verdict AS verdict')
    finally:
        sandbox.close()

    assert rows[0]['verdict'] == 'reject'


@pytest.mark.asyncio
async def test_sandbox_graph_is_isolated(fake_session, tmp_path: Path) -> None:
    sandbox_a = InterviewRecommenderSandbox(kuzu_root=tmp_path / 'a')
    sandbox_b = InterviewRecommenderSandbox(kuzu_root=tmp_path / 'b')
    try:
        await sandbox_a.run_arm(
            cvs=[{'candidate_id': 'C-001', 'role_title': 'Engineer'}],
            lessons=[],
            working_notes=[],
        )
        rows_b = sandbox_b.graph.query('MATCH (d:Decision) RETURN d.id AS id')
    finally:
        sandbox_a.close()
        sandbox_b.close()

    assert rows_b == []
