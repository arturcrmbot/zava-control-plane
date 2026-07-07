from __future__ import annotations

from collections.abc import Callable

from api.server.services.dream_pass.sandbox import SandboxRunner
from api.server.services.dream_pass.types import Experiment
from api.server.services.scoring import RunScorer
from api.server.services.scoring.types import Rubric


class ExperimentRunner:
    """Run one control-vs-treatment A/B experiment."""

    def __init__(
        self,
        *,
        sandbox_factory: Callable[[], SandboxRunner],
        scorer_for: Callable[[SandboxRunner], RunScorer],
    ) -> None:
        self._sandbox_factory = sandbox_factory
        self._scorer_for = scorer_for

    async def run(
        self,
        *,
        experiment_id: str,
        candidate_lesson_id: str,
        candidate_body: str,
        cvs: list[dict],
        active_lessons: list[str],
        rubric: Rubric,
    ) -> Experiment:
        control_sandbox = self._sandbox_factory()
        treatment_sandbox = self._sandbox_factory()
        try:
            control_arm = await control_sandbox.run_arm(
                cvs=cvs,
                lessons=active_lessons,
                working_notes=[],
            )
            control_score = self._mean_score(
                scorer=self._scorer_for(control_sandbox),
                workflow_ids=control_arm.workflow_ids,
                rubric=rubric,
            )

            treatment_arm = await treatment_sandbox.run_arm(
                cvs=cvs,
                lessons=[*active_lessons, candidate_body],
                working_notes=[],
            )
            treatment_score = self._mean_score(
                scorer=self._scorer_for(treatment_sandbox),
                workflow_ids=treatment_arm.workflow_ids,
                rubric=rubric,
            )
            return Experiment(
                id=experiment_id,
                candidate_lesson_id=candidate_lesson_id,
                control_score=control_score,
                treatment_score=treatment_score,
                n_samples=len(cvs),
                workflow_ids=treatment_arm.workflow_ids,
            )
        finally:
            control_sandbox.close()
            treatment_sandbox.close()

    @staticmethod
    def _mean_score(
        *, scorer: RunScorer, workflow_ids: tuple[str, ...], rubric: Rubric
    ) -> float:
        if not workflow_ids:
            return 0.0
        rolled = [
            scorer.score(workflow_id=workflow_id, rubric=rubric).rollup(rubric)
            for workflow_id in workflow_ids
        ]
        return sum(rolled) / len(rolled)
