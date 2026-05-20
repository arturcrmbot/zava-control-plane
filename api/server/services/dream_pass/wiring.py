"""Single-call factory that constructs the remaining dream-pass stack."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from api.server.services.audit_logger import AuditLogger
from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.partitioner import CorpusPartitioner
from api.server.services.dream_pass.policy import PromotionPolicy
from api.server.services.dream_pass.proposer import StubProposer
from api.server.services.dream_pass.sandbox import InterviewRecommenderSandbox
from api.server.services.dream_pass.types import CorpusSplit, Lesson
from api.server.services.entity_graph import EntityGraph
from api.server.services.event_bus import EventBus
from api.server.services.scoring.ground_truth import HiringLabelsGroundTruth
from api.server.services.scoring.rubric_loader import load_rubric
from api.server.services.scoring.scorer import RunScorer
from api.server.services.scoring.types import Rubric, RubricCheck


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HIRING_RUBRIC_YAML = _REPO_ROOT / "data" / "rubrics" / "hiring.yaml"
_HIRING_LABELS_CSV = _REPO_ROOT / "data" / "synthetic" / "hiring" / "labels.csv"
_DREAM_POLICY_YAML = _REPO_ROOT / "data" / "policies" / "dream-pass.policy.yaml"
_DEMO_PARTITIONER_DOMAIN = "__demo__"

_DEMO_RUBRIC = Rubric(
    domain="__demo__",
    promotion_threshold=0.0,
    min_samples=1,
    checks=(RubricCheck(name="placeholder", kind="rationale_present", weight=1.0),),
)

_hiring_rubric_cache: dict[str, Any] = {"v": None}


def _load_real_policy():
    try:
        return PromotionPolicy.from_file(_DREAM_POLICY_YAML)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "real dream-pass policy YAML failed to load (%s); using empty defaults",
            _DREAM_POLICY_YAML,
            exc_info=True,
        )
        return PromotionPolicy({})


def _fresh_demo_persona_ids() -> list[str]:
    return [f"P-DEMO-{uuid.uuid4().hex[:12]}" for _ in range(200)]


def _load_hiring_rubric():
    if _hiring_rubric_cache["v"] is None:
        try:
            _hiring_rubric_cache["v"] = load_rubric(_HIRING_RUBRIC_YAML)
        except Exception:
            _hiring_rubric_cache["v"] = _DEMO_RUBRIC
    return _hiring_rubric_cache["v"]


def _build_real_hiring_runner(graph_for_scorer) -> ExperimentRunner:
    import tempfile
    import uuid as _uuid

    del graph_for_scorer
    ground_truth = HiringLabelsGroundTruth(_HIRING_LABELS_CSV)

    def sandbox_factory() -> InterviewRecommenderSandbox:
        tmp = Path(tempfile.gettempdir()) / "zava-dream-sandbox" / _uuid.uuid4().hex
        return InterviewRecommenderSandbox(kuzu_root=tmp)

    def scorer_for(sandbox) -> RunScorer:
        return RunScorer(graph=sandbox.graph, ground_truth=ground_truth)

    return ExperimentRunner(sandbox_factory=sandbox_factory, scorer_for=scorer_for)


_DEMO_PROPOSER_CANDIDATES: list[tuple[str, str]] = [
    (
        "Trigger: candidate lacks recent leadership signal. Action: down-weight when role grade is G5 or higher.",
        "demo seed 1",
    ),
    (
        "Trigger: jurisdiction is DE and Betriebsrat consultation missing. Action: route to gc before any offer.",
        "demo seed 2",
    ),
    (
        "Trigger: budget already at 90% and headcount delta is positive. Action: require finance_bp endorsement.",
        "demo seed 3",
    ),
]


def build_demo_orchestrator(
    *,
    graph: EntityGraph | None,
    bus: EventBus,
    audit: AuditLogger,
    proposer: Any = None,
    experiment_runner: Any = None,
    rubric: Any = None,
) -> DreamPassOrchestrator:
    del audit
    partitioner: Any = (
        CorpusPartitioner(graph=graph, domain=_DEMO_PARTITIONER_DOMAIN)
        if graph is not None
        else _NoopPartitioner()
    )
    proposer = proposer if proposer is not None else _build_default_proposer()
    if experiment_runner is None:
        experiment_runner = _build_real_hiring_runner(graph)
    if rubric is None:
        rubric = _load_hiring_rubric()

    return DreamPassOrchestrator(
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=_load_real_policy(),
        list_persona_ids=lambda domain: _fresh_demo_persona_ids(),
        load_cvs=lambda ids: [{"candidate_id": i} for i in ids],
        load_recent_runs=lambda domain: [],
        rubric=rubric,
        persist_promoted_lesson=(lambda lesson: _record_lesson(graph, lesson)) if graph is not None else None,
        persist_flagged_candidate=(
            lambda **kwargs: _record_flagged_candidate(graph=graph, **kwargs)
        ) if graph is not None else None,
        graph=graph,
        bus=bus,
    )


def _record_lesson(graph: EntityGraph, lesson: Lesson) -> None:
    graph.query(
        """
        MERGE (l:Lesson {id: $id})
        SET l.body = $body,
            l.domain = $domain,
            l.persona_role = $persona_role,
            l.market = $market,
            l.status = $status,
            l.proposed_by = $proposed_by,
            l.rubric_score_delta = $delta,
            l.experiment_n = $n,
            l.promoted_at = $promoted_at,
            l.supersedes = $supersedes,
            l.prune_reason = ''
        """,
        {
            "id": lesson.id,
            "body": lesson.body,
            "domain": lesson.scope.domain,
            "persona_role": lesson.scope.persona_role or "",
            "market": lesson.scope.market or "",
            "status": lesson.status,
            "proposed_by": lesson.provenance.proposed_by,
            "delta": lesson.provenance.rubric_score_delta,
            "n": lesson.provenance.experiment_n,
            "promoted_at": lesson.provenance.promoted_at,
            "supersedes": lesson.supersedes or "",
        },
    )


def _record_flagged_candidate(
    *,
    graph: EntityGraph,
    candidate,
    experiment_id: str,
    delta: float,
    n: int,
    flag_reason: str,
) -> None:
    from datetime import datetime, timezone

    graph.query(
        """
        MERGE (l:Lesson {id: $id})
        SET l.body = $body,
            l.domain = $domain,
            l.persona_role = $persona_role,
            l.market = $market,
            l.status = 'candidate',
            l.proposed_by = $proposed_by,
            l.rubric_score_delta = $delta,
            l.experiment_n = $n,
            l.promoted_at = $now,
            l.supersedes = '',
            l.prune_reason = $flag_reason
        """,
        {
            "id": candidate.id,
            "body": candidate.body,
            "domain": candidate.scope.domain,
            "persona_role": candidate.scope.persona_role or "",
            "market": candidate.scope.market or "",
            "proposed_by": candidate.proposed_by,
            "delta": delta,
            "n": n,
            "flag_reason": flag_reason,
            "now": datetime.now(timezone.utc),
        },
    )
    graph.query(
        """
        MERGE (e:Experiment {id: $eid})
        WITH e
        MATCH (l:Lesson {id: $lid})
        CREATE (e)-[:EXPERIMENT_FOR_LESSON {recorded_at: $now}]->(l)
        """,
        {"eid": experiment_id, "lid": candidate.id, "now": datetime.now(timezone.utc)},
    )


def _build_default_proposer():
    try:
        from api.server.services.dream_pass.proposer import GHCPProposer
        from api.server.services.dream_pass.skill_loader import dream_skill_path
        skill_path = dream_skill_path("hiring")
        skill_dir = skill_path.parent if hasattr(skill_path, "parent") else None
        if skill_dir is None or not (skill_dir / "SKILL.md").exists():
            raise RuntimeError(f"dream-pass SKILL.md missing at {skill_dir}")
        return GHCPProposer(skill_dir=skill_dir)
    except Exception as ex:
        import logging
        logging.getLogger(__name__).warning(
            "GHCPProposer unavailable (%s); falling back to StubProposer with seed candidates. "
            "Dream-pass candidates will be hardcoded until this is resolved.",
            ex,
        )
        return StubProposer(candidates=list(_DEMO_PROPOSER_CANDIDATES))


class _NoopPartitioner:
    """Used when graph is None — returns a CorpusSplit from the given ids."""

    def next_split(self, *, available, n) -> CorpusSplit:
        held = tuple(available[:n])
        return CorpusSplit(held_out_ids=held, already_used_ids=())

    def mark_used(self, *, experiment_id, persona_ids, arm) -> None:
        del experiment_id, persona_ids, arm
