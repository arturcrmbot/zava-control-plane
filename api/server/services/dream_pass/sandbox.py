from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from api.functions.graphs.executors.agents._wrapper import SKILLS_DIR, run_agent_session
from api.functions.graphs.executors.agents.agent_interview_recommender import _build_prompt
from api.server.services import persona_responder
from api.server.services.entity_graph import EntityGraph


_SKILL_DIR = SKILLS_DIR / 'interview-recommender'


@dataclass(frozen=True)
class ArmResult:
    workflow_ids: tuple[str, ...]


class SandboxRunner(Protocol):
    @property
    def graph(self) -> EntityGraph: ...

    async def run_arm(
        self,
        *,
        cvs: list[dict[str, Any]],
        lessons: list[str],
        working_notes: list[str],
    ) -> ArmResult: ...

    def close(self) -> None: ...


class InterviewRecommenderSandbox:
    """Run the recommender against held-out personas in an isolated tmp graph."""

    def __init__(self, *, kuzu_root: Path) -> None:
        kuzu_root.mkdir(parents=True, exist_ok=True)
        self._graph = EntityGraph(str(kuzu_root / 'sandbox.kuzu'))

    @property
    def graph(self) -> EntityGraph:
        return self._graph

    def close(self) -> None:
        self._graph.close()

    async def run_arm(
        self,
        *,
        cvs: list[dict[str, Any]],
        lessons: list[str],
        working_notes: list[str],
    ) -> ArmResult:
        workflow_ids: list[str] = []
        for cv in cvs:
            workflow_id = f"WF-SB-{_short_hash(cv, lessons)}"
            payload = {
                **cv,
                'gate': cv.get('gate') or 'post_voice',
                'role_title': cv.get('role_title') or cv.get('current_title') or 'Candidate',
                'role_jurisdiction': cv.get('role_jurisdiction')
                or cv.get('jurisdiction_target')
                or cv.get('jurisdiction')
                or '—',
                'screening': cv.get('screening') or {'verdict': 'borderline', 'rationale': 'synthetic eval'},
                'voice_transcript': cv.get('voice_transcript') or [],
                'voice_score': cv.get('voice_score', 0.75),
                'lessons': lessons,
                'working_notes': working_notes,
            }
            parsed = await run_agent_session(
                prompt=_build_prompt(payload),
                tools=[],
                skill_dir=_SKILL_DIR,
                skill_label='interview_recommender',
                workflow_id=workflow_id,
            )
            recommender = _normalise_recommendation(parsed)
            recruiter = _recruiter_decision(
                {
                    'gate': payload['gate'],
                    'screening': payload['screening'],
                    'voice': {'score': payload['voice_score']},
                    'interview_recommender': recommender,
                }
            )
            self._write_decision(
                workflow_id=workflow_id,
                candidate_id=str(cv['candidate_id']),
                verdict=_normalise_verdict(recruiter.get('decision')),
                reason=str(recruiter.get('reason', recommender.get('rationale', ''))),
            )
            workflow_ids.append(workflow_id)
        return ArmResult(workflow_ids=tuple(workflow_ids))

    def _write_decision(
        self,
        *,
        workflow_id: str,
        candidate_id: str,
        verdict: str,
        reason: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._graph.query(
            """
            MERGE (w:Workflow {id: $wf})
            SET w.workflow_type = 'hiring',
                w.status = 'complete',
                w.started_at = $now,
                w.completed_at = $now
            """,
            {'wf': workflow_id, 'now': now},
        )
        self._graph.query(
            """
            MERGE (p:Person {id: $pid})
            SET p.name = $pid,
                p.role = 'synthetic'
            """,
            {'pid': candidate_id},
        )
        decision_id = f'D-SB-{workflow_id}'
        self._graph.query(
            """
            CREATE (:Decision {
                id: $did,
                workflow_id: $wf,
                phase: 'post_voice',
                persona_role: 'recruiter',
                verdict: $verdict,
                reason: $reason,
                decided_at: $now
            })
            """,
            {
                'did': decision_id,
                'wf': workflow_id,
                'verdict': verdict,
                'reason': reason,
                'now': now,
            },
        )
        self._graph.query(
            """
            MATCH (d:Decision {id: $did}), (p:Person {id: $pid})
            CREATE (d)-[:DECIDED_PERSON {decided_at: $now}]->(p)
            """,
            {'did': decision_id, 'pid': candidate_id, 'now': now},
        )


def _recruiter_decision(context: dict[str, Any]) -> dict[str, Any]:
    definitions = persona_responder.PERSONA_DEFINITIONS or persona_responder._load_personae()
    persona_responder.PERSONA_DEFINITIONS = definitions
    recruiter = definitions.get('recruiter')
    if recruiter is None:
        raise RuntimeError('recruiter persona definition not loaded')
    return recruiter.decide(context)


def _normalise_recommendation(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict) or parsed.get('parse_error') or 'decision' not in parsed:
        return {
            'decision': 'advance',
            'rationale': 'sandbox fallback: recommender output missing decision',
            'recommender_status': 'failed',
        }
    return {
        'decision': str(parsed.get('decision') or 'advance'),
        'rationale': str(parsed.get('rationale') or ''),
        'recommender_status': str(parsed.get('recommender_status') or 'ok'),
    }


def _normalise_verdict(raw: Any) -> str:
    lowered = str(raw or '').lower()
    if lowered in {'approve', 'advance'}:
        return 'approve'
    return 'reject'


def _short_hash(cv: dict[str, Any], lessons: list[str]) -> str:
    payload = repr((cv.get('candidate_id'), tuple(sorted(lessons))))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]
