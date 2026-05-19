from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.partitioner import CorpusPartitioner
from api.server.services.dream_pass.policy import PromotionPolicy
from api.server.services.dream_pass.proposer import LessonProposer, ProposalContext
from api.server.services.dream_pass.types import DreamPassResult, DreamSkill, Experiment
from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons import Lesson, LessonGovernor, LessonProvenance
from api.server.services.lessons.working_memory_types import WorkingNote
from api.server.services.scoring.types import Rubric


class DreamPassOrchestrator:
    """Closed-loop proposer -> experiment -> policy -> governor flow."""

    def __init__(
        self,
        *,
        governor: LessonGovernor,
        proposer: LessonProposer,
        partitioner: CorpusPartitioner,
        experiment_runner: ExperimentRunner,
        policy: PromotionPolicy,
        list_persona_ids: Callable[[str], list[str]],
        load_cvs: Callable[[tuple[str, ...]], list[dict[str, Any]]],
        load_active_lessons: Callable[[str], list[Any]],
        load_recent_runs: Callable[[str], list[dict[str, Any]]],
        load_working_notes: Callable[[tuple[str, ...]], list[WorkingNote]],
        rubric: Rubric,
        mark_working_note_consumed: Callable[[str, str], None] | None = None,
        graph: EntityGraph | None = None,
    ) -> None:
        self._governor = governor
        self._proposer = proposer
        self._partitioner = partitioner
        self._experiment_runner = experiment_runner
        self._policy = policy
        self._list_persona_ids = list_persona_ids
        self._load_cvs = load_cvs
        self._load_active_lessons = load_active_lessons
        self._load_recent_runs = load_recent_runs
        self._load_working_notes = load_working_notes
        self._rubric = rubric
        self._mark_working_note_consumed = mark_working_note_consumed
        self._graph = graph

    async def run_pass(self, *, skill: DreamSkill, sample_size: int) -> DreamPassResult:
        dream_pass_id = f'dream-pass:{skill.domain}:{uuid.uuid4()}'
        active_lessons = self._load_active_lessons(skill.domain)
        recent_runs = self._load_recent_runs(skill.domain)
        working_notes = self._load_working_notes(('interview-recommender',))
        candidates = await self._propose(
            ProposalContext(
                skill=skill,
                working_notes=working_notes,
                recent_runs=recent_runs,
                active_lessons=[{'body': _lesson_body(item)} for item in active_lessons],
            )
        )
        available_ids = self._list_persona_ids(skill.domain)
        experiments: list[Experiment] = []
        promoted: list[str] = []
        rejected: list[str] = []
        flagged: list[str] = []

        self._record_dream_pass_start(
            dream_pass_id=dream_pass_id,
            domain=skill.domain,
            skill_version=skill.version,
        )

        for candidate in candidates[: skill.max_candidates_per_pass]:
            if len(experiments) >= skill.max_experiments_per_pass:
                break
            try:
                split = self._partitioner.next_split(available=available_ids, n=sample_size)
            except ValueError:
                break
            cvs = self._load_cvs(split.held_out_ids)
            experiment_id = f'EXP-{uuid.uuid4()}'
            experiment = await self._experiment_runner.run(
                experiment_id=experiment_id,
                candidate_lesson_id=candidate.id,
                candidate_body=candidate.body,
                cvs=cvs,
                active_lessons=[_lesson_body(item) for item in active_lessons],
                rubric=self._rubric,
            )
            self._partitioner.mark_used(
                experiment_id=experiment.id,
                persona_ids=split.held_out_ids,
                arm='control',
            )
            self._partitioner.mark_used(
                experiment_id=experiment.id,
                persona_ids=split.held_out_ids,
                arm='treatment',
            )
            experiments.append(experiment)

            decision = self._policy.evaluate(
                domain=skill.domain,
                candidate=candidate,
                experiment=experiment,
                active_lessons=active_lessons,
                promoted_this_pass=len(promoted),
            )
            if decision.verdict == 'promote':
                lesson = Lesson(
                    id=candidate.id,
                    body=candidate.body,
                    scope=candidate.scope,
                    provenance=LessonProvenance(
                        proposed_by=candidate.proposed_by,
                        run_ids=_recent_run_ids(recent_runs),
                        rubric_score_delta=experiment.delta,
                        experiment_n=experiment.n_samples,
                        promoted_at=datetime.now(timezone.utc),
                    ),
                )
                self._governor.write(lesson)
                promoted.append(candidate.id)
                self._record_experiment(
                    dream_pass_id=dream_pass_id,
                    experiment=experiment,
                    verdict='promote',
                    lesson_id=lesson.id,
                )
            elif decision.verdict == 'reject':
                rejected.append(candidate.id)
                self._record_experiment(
                    dream_pass_id=dream_pass_id,
                    experiment=experiment,
                    verdict='reject',
                    lesson_id=None,
                )
            elif decision.verdict == 'flagged':
                self._governor.write_flagged_candidate(
                    candidate=candidate,
                    experiment_id=experiment.id,
                    delta=experiment.delta,
                    n=experiment.n_samples,
                    flag_reason=decision.reason,
                )
                flagged.append(candidate.id)
                self._record_experiment(
                    dream_pass_id=dream_pass_id,
                    experiment=experiment,
                    verdict='flagged',
                    lesson_id=None,
                )
            else:
                self._record_experiment(
                    dream_pass_id=dream_pass_id,
                    experiment=experiment,
                    verdict='inconclusive',
                    lesson_id=None,
                )

        if self._mark_working_note_consumed is not None:
            for note in working_notes:
                self._mark_working_note_consumed(note.id, dream_pass_id)

        self._record_dream_pass_complete(
            dream_pass_id=dream_pass_id,
            proposed=len(candidates[: skill.max_candidates_per_pass]),
            promoted=len(promoted),
        )
        return DreamPassResult(
            dream_pass_id=dream_pass_id,
            domain=skill.domain,
            experiments=tuple(experiments),
            promoted_lesson_ids=tuple(promoted),
            rejected_lesson_ids=tuple(rejected),
            flagged_lesson_ids=tuple(flagged),
        )

    async def _propose(self, ctx: ProposalContext):
        propose_async = getattr(self._proposer, 'propose_async', None)
        if callable(propose_async):
            result = propose_async(ctx)
            if inspect.isawaitable(result):
                return await result
        return self._proposer.propose(ctx)

    def _record_dream_pass_start(self, *, dream_pass_id: str, domain: str, skill_version: str) -> None:
        if self._graph is None:
            return
        now = datetime.now(timezone.utc)
        self._graph.query(
            """
            MERGE (d:DreamPass {id: $id})
            SET d.domain = $domain,
                d.skill_version = $skill_version,
                d.started_at = $now,
                d.status = 'running',
                d.candidates_proposed = 0,
                d.candidates_promoted = 0
            """,
            {'id': dream_pass_id, 'domain': domain, 'skill_version': skill_version, 'now': now},
        )

    def _record_dream_pass_complete(self, *, dream_pass_id: str, proposed: int, promoted: int) -> None:
        if self._graph is None:
            return
        now = datetime.now(timezone.utc)
        self._graph.query(
            """
            MATCH (d:DreamPass {id: $id})
            SET d.completed_at = $now,
                d.status = 'complete',
                d.candidates_proposed = $proposed,
                d.candidates_promoted = $promoted
            """,
            {'id': dream_pass_id, 'now': now, 'proposed': proposed, 'promoted': promoted},
        )

    def _record_experiment(
        self,
        *,
        dream_pass_id: str,
        experiment: Experiment,
        verdict: str,
        lesson_id: str | None,
    ) -> None:
        if self._graph is None:
            return
        now = datetime.now(timezone.utc)
        self._graph.query(
            """
            MERGE (e:Experiment {id: $id})
            SET e.dream_pass_id = $dream_pass_id,
                e.candidate_lesson_id = $candidate_lesson_id,
                e.control_score = $control_score,
                e.treatment_score = $treatment_score,
                e.delta = $delta,
                e.n_samples = $n_samples,
                e.verdict = $verdict,
                e.run_at = $run_at
            """,
            {
                'id': experiment.id,
                'dream_pass_id': dream_pass_id,
                'candidate_lesson_id': experiment.candidate_lesson_id,
                'control_score': experiment.control_score,
                'treatment_score': experiment.treatment_score,
                'delta': experiment.delta,
                'n_samples': experiment.n_samples,
                'verdict': verdict,
                'run_at': experiment.run_at,
            },
        )
        if lesson_id:
            self._graph.query(
                """
                MATCH (e:Experiment {id: $eid}), (l:Lesson {id: $lid})
                CREATE (e)-[:EXPERIMENT_FOR_LESSON {recorded_at: $now}]->(l)
                """,
                {'eid': experiment.id, 'lid': lesson_id, 'now': now},
            )


def _lesson_body(item: Any) -> str:
    return str(getattr(item, 'body', item))


def _recent_run_ids(recent_runs: list[dict[str, Any]]) -> tuple[str, ...]:
    ids: list[str] = []
    for row in recent_runs:
        workflow_id = row.get('workflow_id') or row.get('id')
        if workflow_id:
            ids.append(str(workflow_id))
    return tuple(ids[:3])
