"""Deterministic non-LLM ExperimentRunner used by orchestrator wiring tests.

Production wiring (api/server/services/dream_pass/wiring.py) constructs a
real ExperimentRunner backed by an InterviewRecommenderSandbox; that path
requires a live Kuzu graph + candidate pool + ground-truth labels and is
unsuitable for fast unit tests of the orchestrator wiring itself.

Tests that exercise wiring/orchestrator plumbing (proposer + partitioner +
policy + governor + bus chain) — but explicitly do NOT exercise the real
experiment runner — should inject an instance of ``StubExperimentRunner``
via the ``experiment_runner=`` kwarg of ``build_demo_orchestrator``.

The stub returns deterministic ``Experiment`` records derived from a
SHA-256 of the candidate id, so two runs of the same test produce the
same numbers.
"""
from __future__ import annotations

import hashlib

from api.server.services.dream_pass.types import Experiment


class StubExperimentRunner:
    """Deterministic ExperimentRunner stand-in for wiring tests."""

    async def run(
        self,
        *,
        experiment_id: str,
        candidate_lesson_id: str,
        candidate_body: str,
        cvs: list[dict],
        active_lessons: list[str],
        rubric,
    ) -> Experiment:
        del candidate_body, active_lessons, rubric  # not used by the stub
        h = int(hashlib.sha256(candidate_lesson_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        treatment = 0.65 + 0.20 * h
        control = 0.70
        return Experiment(
            id=experiment_id,
            candidate_lesson_id=candidate_lesson_id,
            control_score=control,
            treatment_score=treatment,
            n_samples=max(10, len(cvs)),
            workflow_ids=tuple(c.get("candidate_id", "") for c in cvs if c.get("candidate_id")),
        )
