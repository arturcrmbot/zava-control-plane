"""Single-call factory that constructs the dream-pass + lessons stack
with sensible demo defaults. Used by AppState during startup and by
on-demand routes that need to spin a pass against the live entity graph
without rebuilding the wiring each call.

Why a stub ExperimentRunner: the real ExperimentRunner runs the
interview-recommender in an isolated Kuzu sandbox against held-out
personas. That is slow, expensive, and tied to the hiring-specific
recommender — fine for offline lesson research, wrong for a live
visualisation demo. The stub returns deterministic numbers so the
policy + governor + provenance + bus emit chain runs end-to-end.
"""
from __future__ import annotations

import hashlib
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
from api.server.services.dream_pass.types import CorpusSplit, Experiment
from api.server.services.entity_graph import EntityGraph
from api.server.services.event_bus import EventBus
from api.server.services.governance.kernel import kernel as get_kernel
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.store import InMemoryLessonStore
from api.server.services.lessons.types import LessonScope
from api.server.services.lessons.working_memory_store import InMemoryWorkingMemoryStore
from api.server.services.scoring.ground_truth import HiringLabelsGroundTruth
from api.server.services.scoring.rubric_loader import load_rubric
from api.server.services.scoring.scorer import RunScorer
from api.server.services.scoring.types import Rubric, RubricCheck


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HIRING_RUBRIC_YAML = _REPO_ROOT / "data" / "rubrics" / "hiring.yaml"
_HIRING_LABELS_CSV = _REPO_ROOT / "data" / "synthetic" / "hiring" / "labels.csv"
_DREAM_POLICY_YAML = _REPO_ROOT / "data" / "policies" / "dream-pass.policy.yaml"


# Domain scoping for working-note feeds into the dream-pass proposer.
# Notes whose agent_skill is NOT mapped to the requested domain are
# excluded so a hiring proposer doesn't get bled-through patterns from
# fleet-vendor-kyc or fleet-it-access-request. The set is intentionally
# small: every entry MUST have a corresponding dream-pass SKILL.md
# under api/server/skills/dream-passes/<domain>/.
_DOMAIN_AGENT_SKILLS: dict[str, set[str]] = {
    "hiring": {
        # Legacy single-skill names
        "cv-crystalliser",
        "auto-shortlister",
        "interview-recommender",
        "interview_recommender",
        "jd-drafter",
        "voice-screener",
        "betrvg-checker",
        "sourcing-orchestrator",
        "jurisdiction-router",
        # Agentic-segments refactor — any segment of the hiring workflow
        "hiring-segment-a",
        "hiring-segment-b",
        "hiring-segment-c",
        "hiring-segment-d",
        "hiring-segment-e",
        "hiring-segment-f",
        # Dream-pass agent itself (its own decisions become signal for the next pass)
        "dream-pass-hiring",
    },
}


def _agent_in_domain(agent_skill: str | None, domain: str) -> bool:
    if not agent_skill:
        return False
    allowed = _DOMAIN_AGENT_SKILLS.get(domain)
    if allowed is not None and agent_skill in allowed:
        return True
    # Substring fallback: catches generated-domain segments like
    # hiring-segment-* that won't always be explicitly listed.
    return domain in agent_skill


def _load_real_policy():
    """Load data/policies/dream-pass.policy.yaml so promotion uses the
    real thresholds (min_delta, min_samples, max_per_pass, flag rules)
    instead of PromotionPolicy({}) defaults that promote everything."""
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


# Partitioner needs a domain at construction even though it only uses
# it for log messages — using a sentinel keeps the shared instance
# valid across all demo domains.
_DEMO_PARTITIONER_DOMAIN = "__demo__"


# Synthetic persona ids handed to the partitioner. The stub experiment
# runner ignores their semantics; the partitioner just needs ids that
# aren't already burned in Kuzu. CorpusPartitioner persists used ids to
# Kuzu across calls, so we generate fresh UUID-keyed ids per pass to
# guarantee no collision with prior runs — otherwise a fixed pool would
# be exhausted after one or two passes and every subsequent dream-pass
# would raise ValueError: insufficient unseen personas.
def _fresh_demo_persona_ids() -> list[str]:
    return [f"P-DEMO-{uuid.uuid4().hex[:12]}" for _ in range(200)]


# Only read by _StubExperimentRunner; the real runner builds its own rubric.
_DEMO_RUBRIC = Rubric(
    domain="__demo__",
    promotion_threshold=0.0,
    min_samples=1,
    checks=(
        RubricCheck(name="placeholder", kind="rationale_present", weight=1.0),
    ),
)


_hiring_rubric_cache: dict[str, Any] = {"v": None}


def _load_hiring_rubric():
    """Cached at module level — paid once at first import."""
    if _hiring_rubric_cache["v"] is None:
        try:
            _hiring_rubric_cache["v"] = load_rubric(_HIRING_RUBRIC_YAML)
        except Exception:
            _hiring_rubric_cache["v"] = _DEMO_RUBRIC
    return _hiring_rubric_cache["v"]


def _build_real_hiring_runner(graph_for_scorer) -> ExperimentRunner:
    """Construct a real ExperimentRunner for hiring.

    Each call to .run() spins a fresh InterviewRecommenderSandbox in a
    unique temp directory so concurrent passes don't fight for the
    Kuzu single-writer lock. The scorer reads from the SANDBOX's
    graph (not the live graph) because that's where the sandboxed
    interview-recommender wrote its decisions.
    """
    import tempfile
    import uuid as _uuid

    del graph_for_scorer  # scorer reads from sandbox.graph, not the live graph
    ground_truth = HiringLabelsGroundTruth(_HIRING_LABELS_CSV)

    def sandbox_factory() -> InterviewRecommenderSandbox:
        tmp = Path(tempfile.gettempdir()) / "zava-dream-sandbox" / _uuid.uuid4().hex
        return InterviewRecommenderSandbox(kuzu_root=tmp)

    def scorer_for(sandbox) -> RunScorer:
        return RunScorer(graph=sandbox.graph, ground_truth=ground_truth)

    return ExperimentRunner(sandbox_factory=sandbox_factory, scorer_for=scorer_for)


class _DomainDispatchingRunner:
    """Picks the real experiment runner for hiring; stub for everything else.

    The dream-pass orchestrator only accepts ONE experiment_runner instance
    at construction. This wrapper inspects the rubric the orchestrator
    passes through at run(...) time and forwards to the right backend.
    Falls back to stub on any backend error so a transient GHCP failure
    during a cadence tick doesn't crash the whole pass — the stub returns
    a deterministic placeholder so the policy + governor + bus chain
    still runs.
    """

    def __init__(self, *, real, stub):
        self._real = real
        self._stub = stub
        self._log = __import__("logging").getLogger(__name__)

    async def run(self, **kw):
        try:
            rubric = kw.get("rubric")
            domain = getattr(rubric, "domain", "")
            if domain == "hiring":
                self._log.info(
                    "dream-pass: routing experiment %s to REAL hiring sandbox",
                    kw.get("experiment_id"),
                )
                return await self._real.run(**kw)
            self._log.info(
                "dream-pass: routing experiment %s to STUB (domain=%r)",
                kw.get("experiment_id"), domain,
            )
            return await self._stub.run(**kw)
        except Exception:
            self._log.exception(
                "dream-pass: real runner failed for experiment %s; falling back to STUB",
                kw.get("experiment_id"),
            )
            return await self._stub.run(**kw)


_DEMO_PROPOSER_CANDIDATES: list[tuple[str, str]] = [
    (
        "Trigger: candidate lacks recent leadership signal. "
        "Action: down-weight when role grade is G5 or higher.",
        "demo seed 1",
    ),
    (
        "Trigger: jurisdiction is DE and Betriebsrat consultation missing. "
        "Action: route to gc before any offer.",
        "demo seed 2",
    ),
    (
        "Trigger: budget already at 90% and headcount delta is positive. "
        "Action: require finance_bp endorsement.",
        "demo seed 3",
    ),
]


def build_demo_orchestrator(
    *,
    graph: EntityGraph | None,
    bus: EventBus,
    audit: AuditLogger,
    lesson_store: InMemoryLessonStore | None = None,
    working_memory_store: InMemoryWorkingMemoryStore | None = None,
    proposer: Any = None,
    experiment_runner: Any = None,
    rubric: Any = None,
) -> DreamPassOrchestrator:
    """Wire dream-pass with in-memory stores + StubProposer +
    _StubExperimentRunner. Pass lesson_store / working_memory_store to
    share singletons across the orchestrator and the read-only memory
    route; omit them for unit tests and we'll construct fresh ones."""
    lesson_store = lesson_store or InMemoryLessonStore()
    working_store = working_memory_store or InMemoryWorkingMemoryStore()

    if graph is not None:
        provenance: Any = KuzuLessonProvenance(graph)
        partitioner: Any = CorpusPartitioner(graph=graph, domain=_DEMO_PARTITIONER_DOMAIN)
    else:
        provenance = _NoopProvenance()
        partitioner = _NoopPartitioner()

    governor = LessonGovernor(
        store=lesson_store,
        kernel=get_kernel,
        audit=audit,
        provenance=provenance,
        actor="operator:demo",
    )
    proposer = proposer if proposer is not None else _build_default_proposer()

    if experiment_runner is None:
        try:
            real = _build_real_hiring_runner(graph)
            experiment_runner = _DomainDispatchingRunner(real=real, stub=_StubExperimentRunner())
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Real hiring experiment runner unavailable; using stub only.",
                exc_info=True,
            )
            experiment_runner = _StubExperimentRunner()
    if rubric is None:
        rubric = _load_hiring_rubric()

    def _load_active_lessons(domain: str):
        scope = LessonScope(domain=domain)
        return list(lesson_store.search(query="", scope=scope, top_k=100))

    def _load_working_notes(agents):
        # The orchestrator passes a narrow hardcoded ('interview-
        # recommender',) tuple that doesn't match today's actual
        # hiring-track LLM agent names. Ignore it and instead filter
        # to notes whose agent_skill belongs to the "hiring" domain
        # via _agent_in_domain. The proposer's prompt is scoped to a
        # single domain at construction (only hiring has a dream-pass
        # SKILL.md today) so this single-domain filter is sound until
        # we generalise the orchestrator to thread domain through.
        # TODO: once multi-domain dream passes ship, derive domain from
        # skill.domain via the orchestrator API.
        del agents
        store = working_store
        if not hasattr(store, "_by_id"):
            return []
        unconsumed = [
            n for n in store._by_id.values()  # type: ignore[attr-defined]
            if n.consumed_by_dream_pass is None
            and _agent_in_domain(getattr(n, "agent_skill", None), "hiring")
        ]
        unconsumed.sort(key=lambda n: n.captured_at, reverse=True)
        return unconsumed[:50]

    return DreamPassOrchestrator(
        governor=governor,
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=_load_real_policy(),
        list_persona_ids=lambda domain: _fresh_demo_persona_ids(),
        load_cvs=lambda ids: [{"candidate_id": i} for i in ids],
        load_active_lessons=_load_active_lessons,
        load_recent_runs=lambda domain: [],
        load_working_notes=_load_working_notes,
        rubric=rubric,
        mark_working_note_consumed=lambda note_id, dream_pass_id: working_store.mark_consumed(
            note_id=note_id, dream_pass_id=dream_pass_id,
        ),
        graph=graph,
        bus=bus,
    )


def _build_default_proposer():
    """Construct the runtime-default proposer.

    Prefers GHCPProposer wired to the hiring dream-pass SKILL.md (real
    LLM-driven candidate distillation). Falls back to StubProposer with
    the demo seed candidates when GHCP isn't available (no gh auth,
    sandboxed CI, etc.) so the loop still runs end-to-end with theatre
    candidates instead of crashing.
    """
    try:
        from api.server.services.dream_pass.proposer import GHCPProposer
        from api.server.services.dream_pass.skill_loader import dream_skill_path
        # GHCPProposer takes the *directory* containing SKILL.md.
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


class _StubExperimentRunner:
    """Demo-only ExperimentRunner stand-in. See module docstring."""

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


class _NoopProvenance:
    """Used when graph is None (unit-test path). Mirrors every method
    LessonGovernor calls on its provenance so the no-graph path can't
    AttributeError if the policy ever flips a verdict to flagged/prune."""

    def record(self, lesson) -> None:
        del lesson

    def mark_pruned(self, lesson_id: str, *, reason: str) -> None:
        del lesson_id, reason

    def record_candidate(self, **kwargs) -> None:
        del kwargs

    def fetch_candidate(self, lesson_id: str):
        del lesson_id
        return None


class _NoopPartitioner:
    """Used when graph is None — returns a CorpusSplit from the given ids."""

    def next_split(self, *, available, n) -> CorpusSplit:
        held = tuple(available[:n])
        return CorpusSplit(held_out_ids=held, already_used_ids=())

    def mark_used(self, *, experiment_id, persona_ids, arm) -> None:
        del experiment_id, persona_ids, arm
