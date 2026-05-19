from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.sandbox import ArmResult


@pytest.mark.asyncio
async def test_experiment_returns_positive_delta_when_treatment_better() -> None:
    sandbox_control = MagicMock()
    sandbox_control.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=('WF-C-1',)))
    sandbox_control.close = MagicMock()
    sandbox_treatment = MagicMock()
    sandbox_treatment.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=('WF-T-1',)))
    sandbox_treatment.close = MagicMock()

    scorer_control = MagicMock()
    scorer_control.score.return_value = MagicMock(rollup=lambda _: 0.7)
    scorer_treatment = MagicMock()
    scorer_treatment.score.return_value = MagicMock(rollup=lambda _: 0.85)

    runner = ExperimentRunner(
        sandbox_factory=iter([sandbox_control, sandbox_treatment]).__next__,
        scorer_for=lambda sandbox: scorer_control if sandbox is sandbox_control else scorer_treatment,
    )

    experiment = await runner.run(
        experiment_id='EXP-1',
        candidate_lesson_id='L-1',
        candidate_body='lesson body',
        cvs=[{'candidate_id': 'C-001'}],
        active_lessons=['other lesson'],
        rubric=MagicMock(),
    )

    assert experiment.id == 'EXP-1'
    assert experiment.control_score == 0.7
    assert experiment.treatment_score == 0.85
    assert experiment.delta == pytest.approx(0.15)
    sandbox_control.run_arm.assert_awaited_once_with(
        cvs=[{'candidate_id': 'C-001'}],
        lessons=['other lesson'],
        working_notes=[],
    )
    sandbox_treatment.run_arm.assert_awaited_once_with(
        cvs=[{'candidate_id': 'C-001'}],
        lessons=['other lesson', 'lesson body'],
        working_notes=[],
    )


@pytest.mark.asyncio
async def test_experiment_handles_negative_delta() -> None:
    sandbox_a, sandbox_b = MagicMock(), MagicMock()
    sandbox_a.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=('WF-A',)))
    sandbox_a.close = MagicMock()
    sandbox_b.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=('WF-B',)))
    sandbox_b.close = MagicMock()
    scorer_control, scorer_treatment = MagicMock(), MagicMock()
    scorer_control.score.return_value = MagicMock(rollup=lambda _: 0.80)
    scorer_treatment.score.return_value = MagicMock(rollup=lambda _: 0.60)

    runner = ExperimentRunner(
        sandbox_factory=iter([sandbox_a, sandbox_b]).__next__,
        scorer_for=lambda sandbox: scorer_control if sandbox is sandbox_a else scorer_treatment,
    )

    experiment = await runner.run(
        experiment_id='EXP-2',
        candidate_lesson_id='L-2',
        candidate_body='harmful',
        cvs=[{'candidate_id': 'C-001'}],
        active_lessons=[],
        rubric=MagicMock(),
    )

    assert experiment.delta == pytest.approx(-0.20)
