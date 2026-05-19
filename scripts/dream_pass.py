"""Run one dream pass for a domain.

Usage:
    uv run python scripts/dream_pass.py --domain hiring --sample-size 40
"""
from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass import (
    CorpusPartitioner,
    DreamPassOrchestrator,
    ExperimentRunner,
    GHCPProposer,
    InterviewRecommenderSandbox,
    PromotionPolicy,
    StubProposer,
    dream_skill_path,
    load_dream_skill,
)
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance import kernel
from api.server.services.lessons import (
    InMemoryLessonStore,
    KuzuLessonProvenance,
    LessonGovernor,
    LessonScope,
    Mem0LessonStore,
)
from api.server.services.lessons.working_memory_store import Mem0WorkingMemoryStore
from api.server.services.scoring import HiringLabelsGroundTruth, RunScorer, load_rubric


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--sample-size', type=int, default=40)
    parser.add_argument('--use-stub-proposer', action='store_true')
    parser.add_argument(
        '--kuzu-path',
        default='data/portal/entity_graph.kuzu',
        help='path to the production Kuzu DB',
    )
    args = parser.parse_args()

    skill_path = dream_skill_path(args.domain)
    skill = load_dream_skill(skill_path)
    rubric = load_rubric(Path(f'data/rubrics/{args.domain}.yaml'))
    policy = PromotionPolicy.from_file(Path('data/policies/dream-pass.policy.yaml'))
    graph = EntityGraph(args.kuzu_path)
    try:
        try:
            store = Mem0LessonStore()
        except Exception:
            store = InMemoryLessonStore()
        governor = LessonGovernor(
            store=store,
            kernel=kernel,
            audit=AuditLogger(),
            provenance=KuzuLessonProvenance(graph),
            actor=f'dream-pass:{args.domain}',
        )
        partitioner = CorpusPartitioner(graph=graph, domain=args.domain)
        cv_index = _load_cv_index(Path(f'data/synthetic/{args.domain}/cvs'))

        def list_persona_ids(domain: str) -> list[str]:
            del domain
            return sorted(cv_index)

        def load_cvs(ids: tuple[str, ...]) -> list[dict]:
            return [cv_index[candidate_id] for candidate_id in ids if candidate_id in cv_index]

        def load_active_lessons(domain: str):
            return store.search('', scope=LessonScope(domain=domain), top_k=50)

        def load_recent_runs(domain: str) -> list[dict[str, str]]:
            rows = graph.query(
                """
                MATCH (w:Workflow)
                WHERE w.workflow_type = $domain
                RETURN w.id AS id
                ORDER BY w.started_at DESC
                LIMIT 20
                """,
                {'domain': domain},
            )
            return [{'workflow_id': row['id']} for row in rows if row.get('id')]

        try:
            working_memory_store = Mem0WorkingMemoryStore()

            def load_working_notes(agent_skills: tuple[str, ...]):
                return working_memory_store.list_recent_unconsumed(
                    domain_agents=tuple(agent_skills),
                    limit=200,
                )

            def mark_working_note_consumed(note_id: str, dream_pass_id: str) -> None:
                working_memory_store.mark_consumed(
                    note_id=note_id,
                    dream_pass_id=dream_pass_id,
                )
        except Exception:
            def load_working_notes(agent_skills: tuple[str, ...]):
                del agent_skills
                return []

            mark_working_note_consumed = None

        truth = HiringLabelsGroundTruth(labels_csv=Path('data/synthetic/hiring/labels.csv'))

        def sandbox_factory() -> InterviewRecommenderSandbox:
            return InterviewRecommenderSandbox(
                kuzu_root=Path(tempfile.mkdtemp(prefix='dream-pass-sandbox-'))
            )

        def scorer_for(sandbox: InterviewRecommenderSandbox) -> RunScorer:
            return RunScorer(graph=sandbox.graph, ground_truth=truth)

        experiment_runner = ExperimentRunner(
            sandbox_factory=sandbox_factory,
            scorer_for=scorer_for,
        )
        proposer = (
            StubProposer(candidates=[
                ('candidates with sparse evidence should retain an explicit rationale', 'CLI smoke seed'),
            ])
            if args.use_stub_proposer
            else GHCPProposer(skill_dir=skill_path.parent)
        )
        orchestrator = DreamPassOrchestrator(
            governor=governor,
            proposer=proposer,
            partitioner=partitioner,
            experiment_runner=experiment_runner,
            policy=policy,
            list_persona_ids=list_persona_ids,
            load_cvs=load_cvs,
            load_active_lessons=load_active_lessons,
            load_recent_runs=load_recent_runs,
            load_working_notes=load_working_notes,
            mark_working_note_consumed=mark_working_note_consumed,
            rubric=rubric,
            graph=graph,
        )
        result = asyncio.run(orchestrator.run_pass(skill=skill, sample_size=args.sample_size))
        print(f'dream pass:  {result.dream_pass_id}')
        print(f'domain:      {result.domain}')
        print(f'proposed:    {len(result.experiments)}')
        print(f'rejected:    {len(result.rejected_lesson_ids)}')
        print(f'promoted:    {len(result.promoted_lesson_ids)} {list(result.promoted_lesson_ids)}')
        print(f'flagged:     {len(result.flagged_lesson_ids)} {list(result.flagged_lesson_ids)}')
        for experiment in result.experiments:
            print(f'  EXP {experiment.id} delta={experiment.delta:+.3f} n={experiment.n_samples}')
    finally:
        graph.close()


def _load_cv_index(cvs_dir: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in sorted(cvs_dir.glob('*.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        candidate_id = payload.get('candidate_id') or path.stem
        result[str(candidate_id)] = payload
    return result


if __name__ == '__main__':
    main()
