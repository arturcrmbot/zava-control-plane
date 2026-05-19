# Experimental Dream Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the end-to-end dream-pass loop: an agentic, AGT-gated, **closed-loop experimental** lesson optimiser that proposes candidate lessons from working memory + outcomes, A/B-tests them by re-running an LLM agent twice (control vs treatment) against held-out synthetic personas using the rubric scorer, and auto-promotes winners via policy — no human required in the default path.

**Architecture:** A `DreamPassOrchestrator` runs one pass per (domain, dream-skill). For each pass it:

1. Reads recent **WorkingNotes** for the target agent (Plan 1 working memory tier) and recent runs + their rubric scores.
2. Asks an `LessonProposer` (LLM) for N candidate lessons distilled from those notes. Crucially, proposals are grounded in *what agents actually noticed during real runs*, not invented from outcome data alone.
3. For each candidate, runs A/B experiments by invoking the real agent twice via the existing `run_agent_session` (the GHCP runtime is the LLM). The only difference between the two calls is the lesson context embedded into the agent's prompt: **control** = active lessons only; **treatment** = active + candidate. Sandbox each run by writing to a tmp Kuzu DB so production state is untouched; the LLM is real.
4. Computes score deltas via Plan 2's `RunScorer`.
5. Evaluates promotion against `dream-pass.policy.yaml` (AGT-gated tool calls).
6. Writes winners via Plan 1's `LessonGovernor`. Marks consumed working notes via `WorkingMemoryStore.mark_consumed` so they are not re-distilled by the next pass.

The demo target is `agent_interview_recommender` (in `api/functions/graphs/executors/agents/`). Its `_build_prompt()` gains a `lessons` and `working_notes` slot — that's the only change needed on the agent side. The recruiter persona gets one small change: it consumes `interview_recommender.decision` instead of ignoring it, so a lesson-improved recommendation actually changes the gate outcome (and therefore the rubric score).

**Tech Stack:** Python 3.11, the existing **GHCP runtime** (`api/functions/graphs/executors/agents/runtime_ghcp.py` — your GitHub Copilot seat) for all LLM work, `pyyaml`, plus everything from Plans 1–2. Sandboxes invoke real agents through `run_agent_session`; no `agent-framework`, no fake decision shims.

---

## File Structure

**New files:**
- `api/server/services/dream_pass/__init__.py`
- `api/server/services/dream_pass/types.py` — `DreamSkill`, `CorpusSplit`, `Experiment`, `ExperimentVerdict`, `DreamPassResult`
- `api/server/services/dream_pass/skill_loader.py` — load `skills/dream-passes/<domain>/SKILL.md` with YAML frontmatter
- `api/server/services/dream_pass/partitioner.py` — `CorpusPartitioner` (split a corpus; track rotation in Kuzu so eval samples don't leak)
- `api/server/services/dream_pass/sandbox.py` — `SandboxRunner` Protocol + `InterviewRecommenderSandbox` that invokes `run_agent_session` against the real `interview-recommender` skill with prompt-injected lessons, writing decisions to a tmp Kuzu
- `api/server/services/dream_pass/proposer.py` — `LessonProposer` Protocol + `WorkingMemoryProposer` default impl that reads WorkingNotes via the GHCP runtime
- `api/server/services/dream_pass/experiment.py` — `ExperimentRunner` (control vs treatment → delta)
- `api/server/services/dream_pass/policy.py` — load and evaluate `dream-pass.policy.yaml`
- `api/server/services/dream_pass/orchestrator.py` — `DreamPassOrchestrator` (the loop)
- `data/policies/dream-pass.policy.yaml`
- `skills/dream-passes/hiring/SKILL.md` (frontmatter + body — the dream-pass agent's own prompt)
- `scripts/dream_pass.py` — CLI: `dream_pass.py --domain hiring`
- `tests/api/services/dream_pass/__init__.py`
- `tests/api/services/dream_pass/conftest.py`
- `tests/api/services/dream_pass/test_skill_loader.py`
- `tests/api/services/dream_pass/test_partitioner.py`
- `tests/api/services/dream_pass/test_sandbox.py`
- `tests/api/services/dream_pass/test_proposer.py`
- `tests/api/services/dream_pass/test_experiment.py`
- `tests/api/services/dream_pass/test_policy.py`
- `tests/api/services/dream_pass/test_orchestrator.py`
- `tests/api/services/dream_pass/test_recruiter_consumes_recommender.py`

**Modified files:**
- `api/server/services/entity_graph.py` — add `DreamPass`, `Experiment` node tables + `EXPERIMENT_FOR_LESSON`, `EXPERIMENT_USED_PERSONA` edges
- `data/policies/tools.yaml` — promote `lesson.write` / `lesson.prune` from `audit` to `enforce` enforcement mode now that the dream-pass policy gates them
- `api/functions/graphs/executors/agents/agent_interview_recommender.py` — `_build_prompt` accepts and embeds `lessons: list[str]` and `working_notes: list[str]` (additive; defaults to empty lists so existing call sites keep working)
- `api/server/personae/recruiter/SKILL.md` — `decision_policy:` consumes `interview_recommender.decision` when present, so a lesson-improved recommendation actually changes the gate verdict

---

## Conventions

- Sandboxes are **strict**: an `InterviewRecommenderSandbox` instance owns a tmp Kuzu DB and writes only there. It calls `run_agent_session` with `LLM_RUNTIME=fake` in tests (deterministic, no GHCP cost) and `LLM_RUNTIME=ghcp` in real runs.
- The proposer LLM call is behind a Protocol; tests use a deterministic `StubProposer`. The default impl reads recent working notes via `WorkingMemoryStore` and invokes the dream-pass agent skill via `run_agent_session` against the GHCP runtime.
- The `dream-pass.policy.yaml` evaluation is pure (no I/O); it takes an `Experiment` and returns a verdict.
- The orchestrator is the only thing that talks to `LessonGovernor`. Everything else returns values.
- The two prerequisite tasks (A — agent prompt plumbing, B — persona consumption) MUST land before Task 5, because Task 5's sandbox assertions about lesson influence depend on both.

---

## Task A: Plumb lessons + working_notes into `agent_interview_recommender` prompt

**Files:**
- Modify: `api/functions/graphs/executors/agents/agent_interview_recommender.py` (`_build_prompt`, `execute`)
- Test: extend `tests/api/functions/agents/test_agent_interview_recommender.py` (already exists in repo)

This is the **agent-side injection point** for lessons. Additive: empty lists keep behaviour identical, so no existing call sites break.

- [ ] **Step 0: Read the current `_build_prompt` and `execute` signatures**

Run: `sed -n '1,90p' api/functions/graphs/executors/agents/agent_interview_recommender.py`
Expected: see the current `payload` dict assembled in `_build_prompt(input)` and the `execute(input)` entry-point. Note that `input` is already an opaque dict — adding new optional keys is non-breaking.

- [ ] **Step 1: Write the failing test**

Append to `tests/api/functions/agents/test_agent_interview_recommender.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from api.functions.graphs.executors.agents import agent_interview_recommender


@pytest.mark.asyncio
async def test_build_prompt_includes_lessons_and_working_notes() -> None:
    prompt = agent_interview_recommender._build_prompt({
        "gate": "post_voice",
        "role_title": "Engineer",
        "lessons": ["candidates with tenure < 2y targeting L6 should be re-screened"],
        "working_notes": ["screening flagged employment-date inconsistency"],
    })
    assert "tenure < 2y" in prompt
    assert "employment-date inconsistency" in prompt
    # And the empty-list case is identical to the no-key case (backwards compat).
    prompt_no_lessons = agent_interview_recommender._build_prompt({
        "gate": "post_voice", "role_title": "Engineer",
    })
    prompt_empty_lessons = agent_interview_recommender._build_prompt({
        "gate": "post_voice", "role_title": "Engineer",
        "lessons": [], "working_notes": [],
    })
    assert prompt_no_lessons == prompt_empty_lessons


@pytest.mark.asyncio
async def test_execute_passes_lessons_to_prompt() -> None:
    with patch.object(agent_interview_recommender, "run_agent_session") as ras:
        ras.return_value = {"decision": "advance", "rationale": "x"}
        await agent_interview_recommender.execute({
            "workflow_id": "WF-1",
            "gate": "post_voice",
            "role_title": "Engineer",
            "lessons": ["a specific lesson"],
            "working_notes": [],
        })
    assert "a specific lesson" in ras.call_args.kwargs["prompt"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/functions/agents/test_agent_interview_recommender.py -v -k "lessons or working_notes"`
Expected: FAIL — current `_build_prompt` ignores both keys.

- [ ] **Step 3: Modify `_build_prompt` to embed lessons + working_notes**

In `api/functions/graphs/executors/agents/agent_interview_recommender.py`, replace `_build_prompt` with:

```python
def _build_prompt(input: dict) -> str:
    gate = input.get("gate") or "post_voice"
    role_title = input.get("role_title") or "Candidate"
    role_jurisdiction = input.get("role_jurisdiction") or "—"
    levels = levels_for(role_title)
    lessons = list(input.get("lessons") or [])
    working_notes = list(input.get("working_notes") or [])
    payload = {
        "gate": gate,
        "role_title": role_title,
        "role_jurisdiction": role_jurisdiction,
        "levels_for_role": levels,
        "cv_crystalliser": input.get("cv_crystalliser") or {},
        "screening": input.get("screening") or {},
        "voice_transcript": input.get("voice_transcript") or [],
        "voice_score": input.get("voice_score"),
        "lessons": lessons,
        "working_notes": working_notes,
    }
    return (
        f"Recommend at gate `{gate}` for `{role_title}`. "
        f"Context (JSON):\n```json\n{json.dumps(payload, indent=2)}\n```\n"
        f"You MUST consider any `lessons` and `working_notes` provided — they\n"
        f"are organisational priors from past runs. Apply them when they are\n"
        f"relevant; ignore them when they aren't and say so in your rationale.\n"
        f"Return ONLY the JSON object specified in your skill — no prose, "
        f"no markdown fences."
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/functions/agents/test_agent_interview_recommender.py -v`
Expected: all tests pass, including the new ones.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/agents/agent_interview_recommender.py tests/api/functions/agents/test_agent_interview_recommender.py
git commit -m "feat(dream-pass): agent_interview_recommender accepts lessons + working_notes"
```

---

## Task B: Recruiter persona consumes `interview_recommender.decision`

**Files:**
- Modify: `api/server/personae/recruiter/SKILL.md` (just the `decision_policy:` block body)
- Test: `tests/api/services/dream_pass/test_recruiter_consumes_recommender.py`

The recruiter persona currently ignores the recommender's output and decides on `voice_score >= 0.7`. That makes lesson-driven recommender improvements invisible at the gate. This task makes the persona route on the recommender's `decision` when present, falling back to today's rule when it's not.

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_recruiter_consumes_recommender.py`:

```python
from __future__ import annotations

from api.server.services.persona_responder import PersonaResponder


def _context(recommender_decision: str | None, voice_score: float = 0.75) -> dict:
    base = {
        "gate": "post_voice",
        "workflow_id": "WF-1",
        "candidate_id": "C-001",
        "screening": {"verdict": "borderline"},
        "voice": {"score": voice_score},
    }
    if recommender_decision is not None:
        base["interview_recommender"] = {"decision": recommender_decision}
    return base


def test_recruiter_uses_recommender_reject_over_voice_score() -> None:
    """voice_score=0.75 would normally approve. A recommender 'reject' must win."""
    responder = PersonaResponder()
    result = responder.respond(persona_role="recruiter", context=_context("reject"))
    assert result["decision"] == "reject"


def test_recruiter_uses_recommender_advance_when_present() -> None:
    responder = PersonaResponder()
    result = responder.respond(persona_role="recruiter", context=_context("advance"))
    assert result["decision"] == "approve"


def test_recruiter_falls_back_when_no_recommender() -> None:
    """No recommender output → today's deterministic rule wins."""
    responder = PersonaResponder()
    result = responder.respond(persona_role="recruiter", context=_context(None, voice_score=0.75))
    assert result["decision"] == "approve"  # voice_score >= 0.7 → approve
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_recruiter_consumes_recommender.py -v`
Expected: `test_recruiter_uses_recommender_reject_over_voice_score` FAILS (current rule approves on voice_score alone).

- [ ] **Step 3: Modify the recruiter `decision_policy:` block**

In `api/server/personae/recruiter/SKILL.md`, find the `decision_policy:` YAML block. Immediately after the line setting `voice_score = ...`, insert:

```yaml
    # Recommender override: when an interview_recommender produced a structured
    # decision, trust it. This lets a lesson-improved recommendation actually
    # change the gate outcome. Map recommender vocab onto recruiter vocab:
    #   advance/approve -> approve
    #   reject/no_hire  -> reject
    rec = (context or {}).get("interview_recommender") or {}
    rec_decision = (rec.get("decision") or "").lower()
    if rec_decision in {"advance", "approve"}:
        decision = "approve"
        reason = "deferring to interview_recommender=advance"
        return
    if rec_decision in {"reject", "no_hire"}:
        decision = "reject"
        reason = "deferring to interview_recommender=reject"
        return
    # else: fall through to existing rule below.
```

NOTE: `decision_policy` runs inside a sandboxed exec context where `return` is not legal at module scope. The exact control-flow primitive depends on how `persona_responder._compile_decision_policy` wraps the code. From the file: `def _validate_persona_source(source: str, role: str, kind: str)` followed by compile-into-callable. Inspect `_compile_decision_policy` to confirm whether the block is wrapped in a function (in which case `return` works) or executed at module level (in which case use a guard variable: `_decided = False; ... if rec_decision ...: decision = ...; _decided = True; ...; if not _decided: <existing if/else>`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_recruiter_consumes_recommender.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the broader recruiter/hiring suites to confirm no regression**

Run: `uv run pytest tests/api -k "recruiter or hiring" -v`
Expected: all pass. The change is backwards-compatible (no recommender → old behaviour).

- [ ] **Step 6: Commit**

```bash
git add api/server/personae/recruiter/SKILL.md tests/api/services/dream_pass/test_recruiter_consumes_recommender.py
git commit -m "feat(dream-pass): recruiter persona consumes interview_recommender.decision"
```

---

## Task 1: Extend Kuzu schema for dream-pass evidence

**Files:**
- Modify: `api/server/services/entity_graph.py` (`_NODE_TABLES`, `_REL_TABLES`)
- Test: extend Plan 1's `tests/api/services/lessons/test_kuzu_provenance.py` with two new tests (or co-locate in a new test file under dream_pass; this plan uses the latter for clean separation)

- [ ] **Step 1: Write the failing schema test**

Create `tests/api/services/dream_pass/__init__.py` empty.

Create `tests/api/services/dream_pass/conftest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.entity_graph import EntityGraph


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(str(tmp_path / "dream.kuzu"))
```

Create `tests/api/services/dream_pass/test_schema.py`:

```python
def test_dream_pass_tables_exist(graph) -> None:
    rows = graph.execute_cypher("CALL show_tables() RETURN name")
    names = {row["name"] for row in rows}
    assert "DreamPass" in names
    assert "Experiment" in names
    assert "EXPERIMENT_FOR_LESSON" in names
    assert "EXPERIMENT_USED_PERSONA" in names
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_schema.py -v`
Expected: FAIL on missing tables.

- [ ] **Step 3: Add the tables**

In `api/server/services/entity_graph.py`, in the `_NODE_TABLES` tuple add (after the `Lesson` entry from Plan 1):

```python
        ("DreamPass", "CREATE NODE TABLE IF NOT EXISTS DreamPass (id STRING, domain STRING, skill_version STRING, started_at TIMESTAMP, completed_at TIMESTAMP, status STRING, candidates_proposed INT64, candidates_promoted INT64, PRIMARY KEY (id))"),
        ("Experiment", "CREATE NODE TABLE IF NOT EXISTS Experiment (id STRING, dream_pass_id STRING, candidate_lesson_id STRING, control_score DOUBLE, treatment_score DOUBLE, delta DOUBLE, n_samples INT64, verdict STRING, run_at TIMESTAMP, PRIMARY KEY (id))"),
```

In the `_REL_TABLES` tuple add:

```python
        ("EXPERIMENT_FOR_LESSON", "CREATE REL TABLE IF NOT EXISTS EXPERIMENT_FOR_LESSON (FROM Experiment TO Lesson, recorded_at TIMESTAMP)"),
        ("EXPERIMENT_USED_PERSONA", "CREATE REL TABLE IF NOT EXISTS EXPERIMENT_USED_PERSONA (FROM Experiment TO Person, arm STRING, recorded_at TIMESTAMP)"),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/entity_graph.py tests/api/services/dream_pass/test_schema.py tests/api/services/dream_pass/__init__.py tests/api/services/dream_pass/conftest.py
git commit -m "feat(dream-pass): add DreamPass + Experiment tables to Kuzu schema"
```

---

## Task 2: Dream-pass value types

**Files:**
- Create: `api/server/services/dream_pass/__init__.py`
- Create: `api/server/services/dream_pass/types.py`
- Test: `tests/api/services/dream_pass/test_types.py`

- [ ] **Step 1: Create the package marker**

Create `api/server/services/dream_pass/__init__.py`:

```python
"""Experimental dream pass: AGT-gated closed-loop lesson optimisation."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/api/services/dream_pass/test_types.py`:

```python
from __future__ import annotations

import pytest

from api.server.services.dream_pass.types import (
    CorpusSplit,
    DreamSkill,
    Experiment,
    ExperimentVerdict,
)


def test_dream_skill_minimal() -> None:
    skill = DreamSkill(
        domain="hiring",
        version="1.0",
        max_candidates_per_pass=3,
        max_experiments_per_pass=9,
        body="Look for recurring rejection patterns.",
    )
    assert skill.domain == "hiring"
    assert skill.max_candidates_per_pass == 3


def test_corpus_split_disjoint() -> None:
    split = CorpusSplit(
        held_out_ids=("C-001", "C-002", "C-003"),
        already_used_ids=("C-100", "C-101"),
    )
    assert set(split.held_out_ids).isdisjoint(set(split.already_used_ids))


def test_corpus_split_rejects_overlap() -> None:
    with pytest.raises(ValueError):
        CorpusSplit(held_out_ids=("C-1",), already_used_ids=("C-1",))


def test_experiment_verdict_promote_when_strong() -> None:
    experiment = Experiment(
        id="EXP-1",
        candidate_lesson_id="L-1",
        control_score=0.70,
        treatment_score=0.80,
        n_samples=40,
    )
    assert experiment.delta == pytest.approx(0.10)


def test_experiment_verdict_values() -> None:
    # ExperimentVerdict is a string Literal; assert membership semantically.
    valid: ExperimentVerdict
    valid = "promote"
    valid = "reject"
    valid = "inconclusive"
    valid = "flagged"
    assert valid == "flagged"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_types.py -v`
Expected: FAIL on missing module.

- [ ] **Step 4: Implement the types**

Create `api/server/services/dream_pass/types.py`:

```python
"""Value types for the dream pass."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


ExperimentVerdict = Literal["promote", "reject", "inconclusive", "flagged"]


@dataclass(frozen=True)
class DreamSkill:
    """Loaded from skills/dream-passes/<domain>/SKILL.md frontmatter + body."""
    domain: str
    version: str
    max_candidates_per_pass: int
    max_experiments_per_pass: int
    body: str  # prompt material for the proposer


@dataclass(frozen=True)
class CorpusSplit:
    """A partition of a synthetic corpus for one experiment.

    `held_out_ids` are the candidate ids to use as the eval pool for this
    experiment. `already_used_ids` are ids previously consumed by earlier
    dream passes and tracked in Kuzu, so we don't leak them.
    """
    held_out_ids: tuple[str, ...]
    already_used_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        overlap = set(self.held_out_ids) & set(self.already_used_ids)
        if overlap:
            raise ValueError(f"held-out and already-used must be disjoint; overlap: {sorted(overlap)}")


@dataclass(frozen=True)
class Experiment:
    """Result of one A/B run on a candidate lesson."""
    id: str
    candidate_lesson_id: str
    control_score: float
    treatment_score: float
    n_samples: int
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def delta(self) -> float:
        return self.treatment_score - self.control_score


@dataclass(frozen=True)
class DreamPassResult:
    """Final report of one dream pass run."""
    dream_pass_id: str
    domain: str
    experiments: tuple[Experiment, ...]
    promoted_lesson_ids: tuple[str, ...]
    rejected_lesson_ids: tuple[str, ...]
    flagged_lesson_ids: tuple[str, ...]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_types.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/dream_pass/__init__.py api/server/services/dream_pass/types.py tests/api/services/dream_pass/test_types.py
git commit -m "feat(dream-pass): add DreamSkill/CorpusSplit/Experiment value types"
```

---

## Task 3: Dream skill loader (markdown + YAML frontmatter)

**Files:**
- Create: `api/server/services/dream_pass/skill_loader.py`
- Create: `skills/dream-passes/hiring/SKILL.md`
- Test: `tests/api/services/dream_pass/test_skill_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_skill_loader.py`:

```python
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from api.server.services.dream_pass.skill_loader import (
    DreamSkillLoadError,
    load_dream_skill,
)


def test_load_skill_with_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "SKILL.md"
    p.write_text(dedent("""
        ---
        domain: hiring
        version: 1.0
        max_candidates_per_pass: 3
        max_experiments_per_pass: 9
        ---
        Look for recurring rejection patterns. Propose lessons in present tense.
    """).lstrip())

    skill = load_dream_skill(p)

    assert skill.domain == "hiring"
    assert skill.version == "1.0"
    assert skill.max_candidates_per_pass == 3
    assert "rejection patterns" in skill.body


def test_missing_frontmatter_raises(tmp_path: Path) -> None:
    p = tmp_path / "SKILL.md"
    p.write_text("just a body, no frontmatter")
    with pytest.raises(DreamSkillLoadError, match="frontmatter"):
        load_dream_skill(p)


def test_loads_hiring_dream_skill_from_repo() -> None:
    skill = load_dream_skill(Path("skills/dream-passes/hiring/SKILL.md"))
    assert skill.domain == "hiring"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_skill_loader.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the loader**

Create `api/server/services/dream_pass/skill_loader.py`:

```python
"""Load a dream-pass skill from a markdown file with YAML frontmatter."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from api.server.services.dream_pass.types import DreamSkill


class DreamSkillLoadError(ValueError):
    pass


_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def load_dream_skill(path: Path) -> DreamSkill:
    if not path.exists():
        raise DreamSkillLoadError(f"dream skill file not found: {path}")
    text = path.read_text()
    match = _FRONTMATTER.match(text)
    if match is None:
        raise DreamSkillLoadError(f"dream skill {path}: missing YAML frontmatter")
    fm = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()

    for required in ("domain", "version", "max_candidates_per_pass", "max_experiments_per_pass"):
        if required not in fm:
            raise DreamSkillLoadError(f"dream skill {path}: frontmatter missing '{required}'")

    return DreamSkill(
        domain=str(fm["domain"]),
        version=str(fm["version"]),
        max_candidates_per_pass=int(fm["max_candidates_per_pass"]),
        max_experiments_per_pass=int(fm["max_experiments_per_pass"]),
        body=body,
    )
```

- [ ] **Step 4: Author the hiring dream skill**

Create `skills/dream-passes/hiring/SKILL.md`:

```markdown
---
domain: hiring
version: 1.0
max_candidates_per_pass: 3
max_experiments_per_pass: 9
---
You are a dream-pass agent for the **hiring** domain.

Your job: read recent hiring runs (their decisions, outcomes, ledger entries)
and the active lessons. Identify *recurring* patterns where the workflow
made decisions that disagreed with ground truth, or made compliant
decisions for the wrong reasons.

Propose up to `max_candidates_per_pass` candidate lessons. Each candidate
MUST:

- Be a single concrete sentence in the present tense.
- Name a trigger (a recognisable input pattern) and an action / consideration.
- Be specific enough to be testable on held-out personas, general enough
  to apply to >1 case.
- NOT contradict the active hiring policy bundle. Lessons that need to
  override policy should be flagged for human review (the orchestrator
  will route those to the exceptions queue).

Do NOT propose lessons that:

- Restate the active policy. Those are tautologies; the workflow already
  enforces them via AGT.
- Encode personally identifiable details from a single candidate.
- Expand scope beyond `domain=hiring` without strong cross-domain evidence.

Output each candidate as `{body, rationale}` so the orchestrator can
record both in the experiment evidence.
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_skill_loader.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/dream_pass/skill_loader.py skills/dream-passes/hiring/SKILL.md tests/api/services/dream_pass/test_skill_loader.py
git commit -m "feat(dream-pass): add dream skill loader + hiring skill"
```

---

## Task 4: Corpus partitioner with leakage tracking

**Files:**
- Create: `api/server/services/dream_pass/partitioner.py`
- Test: `tests/api/services/dream_pass/test_partitioner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_partitioner.py`:

```python
from __future__ import annotations

from api.server.services.dream_pass.partitioner import CorpusPartitioner


def test_partition_returns_n_unseen_ids(graph) -> None:
    available = [f"C-{i:03d}" for i in range(50)]
    partitioner = CorpusPartitioner(graph=graph, domain="hiring")

    split = partitioner.next_split(available=available, n=10)

    assert len(split.held_out_ids) == 10
    assert set(split.held_out_ids).issubset(set(available))
    assert split.already_used_ids == ()


def test_partition_excludes_already_used(graph) -> None:
    available = [f"C-{i:03d}" for i in range(50)]
    partitioner = CorpusPartitioner(graph=graph, domain="hiring")

    first = partitioner.next_split(available=available, n=10)
    partitioner.mark_used(experiment_id="EXP-1", persona_ids=first.held_out_ids, arm="control")

    second = partitioner.next_split(available=available, n=10)

    assert set(second.held_out_ids).isdisjoint(set(first.held_out_ids))
    assert set(second.already_used_ids) == set(first.held_out_ids)


def test_partition_raises_when_pool_exhausted(graph) -> None:
    available = ["C-001", "C-002"]
    partitioner = CorpusPartitioner(graph=graph, domain="hiring")
    first = partitioner.next_split(available=available, n=2)
    partitioner.mark_used(experiment_id="EXP-1", persona_ids=first.held_out_ids, arm="control")

    import pytest
    with pytest.raises(ValueError, match="insufficient unseen personas"):
        partitioner.next_split(available=available, n=1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_partitioner.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the partitioner**

Create `api/server/services/dream_pass/partitioner.py`:

```python
"""Partitions a synthetic corpus into unseen held-out subsets.

Tracks usage via Person nodes' EXPERIMENT_USED_PERSONA back-edges in
Kuzu so the dream pass never re-tests on the same persona twice within
the same domain.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api.server.services.dream_pass.types import CorpusSplit
from api.server.services.entity_graph import EntityGraph


class CorpusPartitioner:
    def __init__(self, *, graph: EntityGraph, domain: str) -> None:
        self._graph = graph
        self._domain = domain

    def next_split(self, *, available: list[str], n: int) -> CorpusSplit:
        used = self._used_ids()
        unseen = [pid for pid in available if pid not in used]
        if len(unseen) < n:
            raise ValueError(
                f"insufficient unseen personas: need {n}, have {len(unseen)} "
                f"({len(used)} already used in domain={self._domain})"
            )
        return CorpusSplit(
            held_out_ids=tuple(unseen[:n]),
            already_used_ids=tuple(used),
        )

    def mark_used(
        self,
        *,
        experiment_id: str,
        persona_ids: tuple[str, ...],
        arm: str,
    ) -> None:
        for pid in persona_ids:
            self._graph.execute_cypher(
                """
                MERGE (p:Person {id: $pid})
                ON CREATE SET p.name = $pid, p.role = 'synthetic'
                """,
                {"pid": pid},
            )
            self._graph.execute_cypher(
                """
                MATCH (e:Experiment {id: $eid}), (p:Person {id: $pid})
                CREATE (e)-[:EXPERIMENT_USED_PERSONA {arm: $arm, recorded_at: $now}]->(p)
                """,
                {
                    "eid": experiment_id,
                    "pid": pid,
                    "arm": arm,
                    "now": datetime.now(timezone.utc),
                },
            )

    def _used_ids(self) -> set[str]:
        rows = self._graph.execute_cypher(
            """
            MATCH (e:Experiment)-[:EXPERIMENT_USED_PERSONA]->(p:Person)
            RETURN DISTINCT p.id AS pid
            """,
        )
        return {row["pid"] for row in rows}
```

- [ ] **Step 4: Run the test to verify it passes — but `mark_used` will fail because no Experiment node exists.**

The test does `partitioner.mark_used(experiment_id="EXP-1", ...)` without first creating an Experiment node. The `MATCH (e:Experiment {id: $eid})` will return no rows and the CREATE will be a no-op, which means `_used_ids` returns empty and the second `next_split` won't actually exclude. Fix this by having `mark_used` upsert the Experiment node itself:

Replace the `mark_used` method body with:

```python
    def mark_used(
        self,
        *,
        experiment_id: str,
        persona_ids: tuple[str, ...],
        arm: str,
    ) -> None:
        self._graph.execute_cypher(
            """
            MERGE (e:Experiment {id: $eid})
            ON CREATE SET e.dream_pass_id = '', e.candidate_lesson_id = '',
                          e.control_score = 0.0, e.treatment_score = 0.0,
                          e.delta = 0.0, e.n_samples = 0, e.verdict = 'inconclusive',
                          e.run_at = $now
            """,
            {"eid": experiment_id, "now": datetime.now(timezone.utc)},
        )
        for pid in persona_ids:
            self._graph.execute_cypher(
                """
                MERGE (p:Person {id: $pid})
                ON CREATE SET p.name = $pid, p.role = 'synthetic'
                """,
                {"pid": pid},
            )
            self._graph.execute_cypher(
                """
                MATCH (e:Experiment {id: $eid}), (p:Person {id: $pid})
                CREATE (e)-[:EXPERIMENT_USED_PERSONA {arm: $arm, recorded_at: $now}]->(p)
                """,
                {
                    "eid": experiment_id,
                    "pid": pid,
                    "arm": arm,
                    "now": datetime.now(timezone.utc),
                },
            )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_partitioner.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/services/dream_pass/partitioner.py tests/api/services/dream_pass/test_partitioner.py
git commit -m "feat(dream-pass): add CorpusPartitioner with Kuzu leakage tracking"
```

---

## Task 5: Sandbox runner (real agent, sandboxed Kuzu)

**Files:**
- Create: `api/server/services/dream_pass/sandbox.py`
- Test: `tests/api/services/dream_pass/test_sandbox.py`

The sandbox runs the **real** `interview-recommender` agent skill via `run_agent_session`, with `lessons` + `working_notes` injected through the prompt-plumbing from Task A. Decisions land in a tmp Kuzu DB so production state is untouched. Tests use `LLM_RUNTIME=fake` to keep them deterministic and free.

- [ ] **Step 0: Confirm the existing FakeRuntime + run_agent_session shape**

Run: `grep -n "def run_session\|class FakeRuntime\|def fixed_response" api/functions/graphs/executors/agents/runtime_fake.py | head -20`
Expected: confirm how `FakeRuntime` is seeded with canned responses (typically `FakeRuntime(scripted_responses=[...])` or via an env var). The test below assumes a `scripted_responses` list keyed off the prompt content; adapt to the actual API.

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_sandbox.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from api.server.services.dream_pass.sandbox import InterviewRecommenderSandbox


@pytest.fixture
def fake_session(monkeypatch):
    """Patch run_agent_session so the test never touches GHCP."""
    calls: list[dict] = []

    async def fake_run(*, prompt, tools, skill_dir, skill_label, workflow_id, **kwargs):
        calls.append({"prompt": prompt, "skill_label": skill_label, "workflow_id": workflow_id})
        # Return reject when the prompt contains the sentinel lesson, else approve.
        if "sentinel-reject-lesson" in prompt:
            return {"decision": "reject", "rationale": "sentinel matched"}
        return {"decision": "advance", "rationale": "baseline"}

    monkeypatch.setattr(
        "api.server.services.dream_pass.sandbox.run_agent_session",
        fake_run,
    )
    return calls


@pytest.mark.asyncio
async def test_sandbox_runs_real_agent_with_empty_lessons(fake_session, tmp_path: Path) -> None:
    cvs = [
        {"candidate_id": "C-001", "role_title": "Engineer"},
        {"candidate_id": "C-002", "role_title": "Engineer"},
    ]
    sandbox = InterviewRecommenderSandbox(kuzu_root=tmp_path / "sb")

    result = await sandbox.run_arm(cvs=cvs, lessons=[], working_notes=[])

    assert len(result.workflow_ids) == 2
    assert all("sentinel-reject-lesson" not in c["prompt"] for c in fake_session)


@pytest.mark.asyncio
async def test_sandbox_lesson_injection_changes_agent_decision(fake_session, tmp_path: Path) -> None:
    cvs = [{"candidate_id": "C-001", "role_title": "Engineer"}]
    sandbox = InterviewRecommenderSandbox(kuzu_root=tmp_path / "sb")

    await sandbox.run_arm(cvs=cvs, lessons=["sentinel-reject-lesson"], working_notes=[])

    # Decision node written into the sandbox graph should reflect the reject.
    rows = sandbox.graph.execute_cypher(
        "MATCH (d:Decision) RETURN d.verdict AS v"
    )
    assert rows[0]["v"] == "reject"


@pytest.mark.asyncio
async def test_sandbox_graph_is_isolated(fake_session, tmp_path: Path) -> None:
    a = InterviewRecommenderSandbox(kuzu_root=tmp_path / "a")
    b = InterviewRecommenderSandbox(kuzu_root=tmp_path / "b")

    await a.run_arm(cvs=[{"candidate_id": "C-001", "role_title": "Engineer"}], lessons=[], working_notes=[])
    rows_b = b.graph.execute_cypher("MATCH (d:Decision) RETURN d.id AS id")

    assert rows_b == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_sandbox.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the sandbox runner**

Create `api/server/services/dream_pass/sandbox.py`:

```python
"""Sandboxed runner for dream-pass experiments.

Invokes the real `interview-recommender` agent skill via the existing
`run_agent_session` wrapper, with `lessons` and `working_notes` injected
through the prompt-plumbing from Task A. Writes the resulting Decision
into a tmp Kuzu so production state is never touched.

The LLM runtime is whatever `LLM_RUNTIME` env var selects:
  - `fake` (tests) — deterministic, no cost
  - `ghcp` (default) — real GitHub Copilot session
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from api.functions.graphs.executors.agents._wrapper import (
    SKILLS_DIR,
    run_agent_session,
)
from api.functions.graphs.executors.agents.agent_interview_recommender import _build_prompt
from api.server.services.entity_graph import EntityGraph


_SKILL_DIR = SKILLS_DIR / "interview-recommender"


@dataclass(frozen=True)
class ArmResult:
    workflow_ids: tuple[str, ...]


class SandboxRunner(Protocol):
    @property
    def graph(self) -> EntityGraph: ...
    async def run_arm(
        self, *, cvs: list[dict], lessons: list[str], working_notes: list[str]
    ) -> ArmResult: ...


class InterviewRecommenderSandbox:
    def __init__(self, *, kuzu_root: Path) -> None:
        kuzu_root.mkdir(parents=True, exist_ok=True)
        self._graph = EntityGraph(str(kuzu_root / "sandbox.kuzu"))

    @property
    def graph(self) -> EntityGraph:
        return self._graph

    async def run_arm(
        self, *, cvs: list[dict], lessons: list[str], working_notes: list[str]
    ) -> ArmResult:
        ids: list[str] = []
        for cv in cvs:
            wf_id = f"WF-SB-{_short_hash(cv, lessons)}"
            prompt = _build_prompt({
                **cv,
                "lessons": lessons,
                "working_notes": working_notes,
            })
            parsed = await run_agent_session(
                prompt=prompt,
                tools=[],
                skill_dir=_SKILL_DIR,
                skill_label="interview_recommender",
                workflow_id=wf_id,
            )
            self._write_decision(
                workflow_id=wf_id,
                candidate_id=cv["candidate_id"],
                verdict=_normalise_verdict((parsed or {}).get("decision", "reject")),
                reason=str((parsed or {}).get("rationale", "")),
            )
            ids.append(wf_id)
        return ArmResult(workflow_ids=tuple(ids))

    def _write_decision(
        self, *, workflow_id: str, candidate_id: str, verdict: str, reason: str
    ) -> None:
        self._graph.execute_cypher(
            "MERGE (p:Person {id: $pid}) ON CREATE SET p.name = $pid, p.role = 'synthetic'",
            {"pid": candidate_id},
        )
        self._graph.execute_cypher(
            """
            CREATE (:Decision {id: $did, workflow_id: $wf,
                               phase: 'post_voice', persona_role: 'recruiter',
                               verdict: $verdict, reason: $reason,
                               decided_at: $now})
            """,
            {
                "did": f"D-SB-{workflow_id}",
                "wf": workflow_id,
                "verdict": verdict,
                "reason": reason,
                "now": datetime.now(timezone.utc),
            },
        )
        self._graph.execute_cypher(
            """
            MATCH (d:Decision {id: $did}), (p:Person {id: $pid})
            CREATE (d)-[:DECIDED_PERSON {decided_at: $now}]->(p)
            """,
            {
                "did": f"D-SB-{workflow_id}",
                "pid": candidate_id,
                "now": datetime.now(timezone.utc),
            },
        )


def _normalise_verdict(raw: str) -> str:
    raw_l = (raw or "").lower()
    if raw_l in {"approve", "advance"}:
        return "approve"
    return "reject"


def _short_hash(cv: dict, lessons: list[str]) -> str:
    payload = repr((cv.get("candidate_id"), tuple(sorted(lessons))))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_sandbox.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/dream_pass/sandbox.py tests/api/services/dream_pass/test_sandbox.py
git commit -m "feat(dream-pass): InterviewRecommenderSandbox runs real agent in tmp Kuzu"
```

---

## Task 6: Lesson proposer (reads working memory as raw material)

**Files:**
- Create: `api/server/services/dream_pass/proposer.py`
- Test: `tests/api/services/dream_pass/test_proposer.py`

The proposer reads recent `WorkingNote` rows for the target agent (from Plan 1's `WorkingMemoryStore`) and asks an LLM (via `run_agent_session` against the dream-pass skill) to distill candidate lessons. Tests use a `StubProposer`.

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_proposer.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.server.services.dream_pass.proposer import (
    GHCPProposer,
    ProposalContext,
    StubProposer,
)
from api.server.services.dream_pass.types import DreamSkill
from api.server.services.lessons.working_memory_types import WorkingNote


def _skill(max_c: int = 2) -> DreamSkill:
    return DreamSkill(
        domain="hiring", version="1.0",
        max_candidates_per_pass=max_c, max_experiments_per_pass=max_c * 3,
        body="distill recurring patterns from working notes",
    )


def _note(body: str, kind: str = "observation") -> WorkingNote:
    return WorkingNote(
        id=f"WN-{body[:6]}", workflow_id="WF-1",
        agent_skill="interview-recommender", kind=kind, body=body,
    )


def test_stub_proposer_returns_configured_candidates() -> None:
    proposer = StubProposer(candidates=[
        ("agency X candidates often miss step 3", "observed in 4 of 5 recent rejections"),
        ("market UK requires extra RTW evidence", "observed in 3 of 5"),
    ])
    ctx = ProposalContext(
        skill=_skill(),
        working_notes=[_note("agency X failed at step 3"), _note("another fail")],
        recent_runs=[{"workflow_id": "WF-1", "score": 0.7}],
        active_lessons=[],
    )
    candidates = proposer.propose(ctx)
    assert len(candidates) == 2
    assert candidates[0].body.startswith("agency X")
    assert candidates[0].scope.domain == "hiring"


def test_stub_proposer_respects_max() -> None:
    proposer = StubProposer(candidates=[("a", "r"), ("b", "r"), ("c", "r")])
    ctx = ProposalContext(skill=_skill(max_c=1), working_notes=[], recent_runs=[], active_lessons=[])
    assert len(proposer.propose(ctx)) == 1


@pytest.mark.asyncio
async def test_ghcp_proposer_embeds_working_notes_in_prompt() -> None:
    sent_prompts: list[str] = []

    async def fake_run(*, prompt, tools, skill_dir, skill_label, workflow_id, **kwargs):
        sent_prompts.append(prompt)
        return [
            {"body": "distilled lesson 1", "rationale": "3 notes mention agency X"},
            {"body": "distilled lesson 2", "rationale": "2 notes mention RTW"},
        ]

    with patch("api.server.services.dream_pass.proposer.run_agent_session", fake_run):
        proposer = GHCPProposer(skill_dir=None)  # None → use embedded body
        ctx = ProposalContext(
            skill=_skill(),
            working_notes=[
                _note("agency X failed at step 3"),
                _note("agency X had inconsistent dates"),
            ],
            recent_runs=[{"workflow_id": "WF-1", "score": 0.7}],
            active_lessons=[],
        )
        candidates = await proposer.propose_async(ctx)

    assert len(candidates) == 2
    assert candidates[0].body == "distilled lesson 1"
    assert "agency X failed at step 3" in sent_prompts[0]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_proposer.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the proposer**

Create `api/server/services/dream_pass/proposer.py`:

```python
"""LessonProposer — distills candidate lessons from working memory.

Working notes are the dream pass's *raw material*. Reading them is
what keeps the proposer grounded in things agents actually noticed,
rather than inventing patterns from outcome data alone.

Default impl uses `run_agent_session` against a dream-pass skill
(GHCP runtime, i.e. your GitHub Copilot seat). Tests use StubProposer.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from api.functions.graphs.executors.agents._wrapper import run_agent_session
from api.server.services.dream_pass.types import DreamSkill
from api.server.services.lessons.types import LessonCandidate, LessonScope
from api.server.services.lessons.working_memory_types import WorkingNote


@dataclass(frozen=True)
class ProposalContext:
    skill: DreamSkill
    working_notes: list[WorkingNote]
    recent_runs: list[dict[str, Any]]
    active_lessons: list[dict[str, Any]]


class LessonProposer(Protocol):
    def propose(self, ctx: ProposalContext) -> list[LessonCandidate]: ...


class StubProposer:
    """Deterministic proposer for tests."""

    def __init__(self, candidates: list[tuple[str, str]]) -> None:
        self._candidates = candidates

    def propose(self, ctx: ProposalContext) -> list[LessonCandidate]:
        out: list[LessonCandidate] = []
        for body, rationale in self._candidates[: ctx.skill.max_candidates_per_pass]:
            out.append(LessonCandidate(
                id=str(uuid.uuid4()),
                body=body,
                scope=LessonScope(domain=ctx.skill.domain),
                proposed_by=f"dream-pass:{ctx.skill.domain}:stub",
                rationale=rationale,
            ))
        return out


class GHCPProposer:
    """Default proposer using `run_agent_session` against a dream-pass skill."""

    def __init__(self, *, skill_dir: Path | None = None) -> None:
        self._skill_dir = skill_dir

    def propose(self, ctx: ProposalContext) -> list[LessonCandidate]:
        return asyncio.run(self.propose_async(ctx))

    async def propose_async(self, ctx: ProposalContext) -> list[LessonCandidate]:
        prompt = self._render_prompt(ctx)
        parsed = await run_agent_session(
            prompt=prompt,
            tools=[],
            skill_dir=self._skill_dir,
            skill_label=f"dream-pass-{ctx.skill.domain}",
            workflow_id=f"dream-pass:{ctx.skill.domain}",
        )
        items = parsed if isinstance(parsed, list) else (parsed or {}).get("candidates") or []
        out: list[LessonCandidate] = []
        for item in items[: ctx.skill.max_candidates_per_pass]:
            out.append(LessonCandidate(
                id=str(uuid.uuid4()),
                body=str(item["body"]),
                scope=LessonScope(domain=ctx.skill.domain),
                proposed_by=f"dream-pass:{ctx.skill.domain}:ghcp",
                rationale=str(item.get("rationale", "")),
            ))
        return out

    @staticmethod
    def _render_prompt(ctx: ProposalContext) -> str:
        notes_payload = [
            {
                "workflow_id": n.workflow_id,
                "kind": n.kind,
                "body": n.body,
            }
            for n in ctx.working_notes
        ]
        return (
            f"You are the dream-pass agent for the `{ctx.skill.domain}` domain.\n\n"
            f"Dream-skill body:\n{ctx.skill.body}\n\n"
            f"Recent working notes ({len(notes_payload)}):\n"
            f"```json\n{json.dumps(notes_payload, indent=2)}\n```\n\n"
            f"Recent run scores:\n```json\n{json.dumps(ctx.recent_runs, indent=2)}\n```\n\n"
            f"Active lessons (do not restate):\n"
            f"```json\n{json.dumps(ctx.active_lessons, indent=2)}\n```\n\n"
            f"Distill up to {ctx.skill.max_candidates_per_pass} candidate lessons.\n"
            f"Return ONLY a JSON array of objects {{body, rationale}}.\n"
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_proposer.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/dream_pass/proposer.py tests/api/services/dream_pass/test_proposer.py
git commit -m "feat(dream-pass): add LessonProposer (StubProposer + GHCPProposer)"
```

---

## Task 7: Experiment runner (control vs treatment)

**Files:**
- Create: `api/server/services/dream_pass/experiment.py`
- Test: `tests/api/services/dream_pass/test_experiment.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_experiment.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.sandbox import ArmResult


@pytest.mark.asyncio
async def test_experiment_returns_positive_delta_when_treatment_better() -> None:
    sandbox_control = MagicMock()
    sandbox_control.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=("WF-C-1",)))
    sandbox_treatment = MagicMock()
    sandbox_treatment.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=("WF-T-1",)))

    scorer_control = MagicMock()
    scorer_control.score.return_value = MagicMock(rollup=lambda _: 0.7)
    scorer_treatment = MagicMock()
    scorer_treatment.score.return_value = MagicMock(rollup=lambda _: 0.85)

    rubric = MagicMock()

    runner = ExperimentRunner(
        sandbox_factory=iter([sandbox_control, sandbox_treatment]).__next__,
        scorer_for=lambda sandbox: scorer_control if sandbox is sandbox_control else scorer_treatment,
    )

    experiment = await runner.run(
        experiment_id="EXP-1",
        candidate_lesson_id="L-1",
        candidate_body="lesson body",
        cvs=[{"candidate_id": "C-001"}],
        active_lessons=["other lesson"],
        rubric=rubric,
    )

    assert experiment.id == "EXP-1"
    assert experiment.control_score == 0.7
    assert experiment.treatment_score == 0.85
    assert experiment.delta == pytest.approx(0.15)
    sandbox_control.run_arm.assert_awaited_once_with(
        cvs=[{"candidate_id": "C-001"}], lessons=["other lesson"], working_notes=[]
    )
    sandbox_treatment.run_arm.assert_awaited_once_with(
        cvs=[{"candidate_id": "C-001"}], lessons=["other lesson", "lesson body"], working_notes=[]
    )


@pytest.mark.asyncio
async def test_experiment_handles_negative_delta() -> None:
    sandbox_a, sandbox_b = MagicMock(), MagicMock()
    sandbox_a.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=("WF-A",)))
    sandbox_b.run_arm = AsyncMock(return_value=ArmResult(workflow_ids=("WF-B",)))
    sc, st = MagicMock(), MagicMock()
    sc.score.return_value = MagicMock(rollup=lambda _: 0.80)
    st.score.return_value = MagicMock(rollup=lambda _: 0.60)

    runner = ExperimentRunner(
        sandbox_factory=iter([sandbox_a, sandbox_b]).__next__,
        scorer_for=lambda s: sc if s is sandbox_a else st,
    )

    experiment = await runner.run(
        experiment_id="EXP-2",
        candidate_lesson_id="L-2",
        candidate_body="harmful",
        cvs=[{"candidate_id": "C-001"}],
        active_lessons=[],
        rubric=MagicMock(),
    )

    assert experiment.delta == pytest.approx(-0.20)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_experiment.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the experiment runner**

Create `api/server/services/dream_pass/experiment.py`:

```python
"""ExperimentRunner — runs one control-vs-treatment A/B for a candidate lesson."""
from __future__ import annotations

from typing import Callable, Protocol

from api.server.services.dream_pass.sandbox import SandboxRunner
from api.server.services.dream_pass.types import Experiment
from api.server.services.scoring.scorer import RunScorer
from api.server.services.scoring.types import Rubric


class _SandboxFactory(Protocol):
    def __call__(self) -> SandboxRunner: ...


class _ScorerFor(Protocol):
    def __call__(self, sandbox: SandboxRunner) -> RunScorer: ...


class ExperimentRunner:
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
        control_arm = await control_sandbox.run_arm(
            cvs=cvs, lessons=active_lessons, working_notes=[]
        )
        control_score = self._mean_score(
            scorer=self._scorer_for(control_sandbox),
            workflow_ids=control_arm.workflow_ids,
            rubric=rubric,
        )

        treatment_sandbox = self._sandbox_factory()
        treatment_arm = await treatment_sandbox.run_arm(
            cvs=cvs, lessons=[*active_lessons, candidate_body], working_notes=[]
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
        )

    def _mean_score(
        self, *, scorer: RunScorer, workflow_ids: tuple[str, ...], rubric: Rubric
    ) -> float:
        if not workflow_ids:
            return 0.0
        rolled = [scorer.score(workflow_id=wf, rubric=rubric).rollup(rubric) for wf in workflow_ids]
        return sum(rolled) / len(rolled)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_experiment.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/dream_pass/experiment.py tests/api/services/dream_pass/test_experiment.py
git commit -m "feat(dream-pass): add ExperimentRunner for control-vs-treatment A/B"
```

---

## Task 8: Promotion policy

**Files:**
- Create: `data/policies/dream-pass.policy.yaml`
- Create: `api/server/services/dream_pass/policy.py`
- Test: `tests/api/services/dream_pass/test_policy.py`

- [ ] **Step 1: Author the policy**

Create `data/policies/dream-pass.policy.yaml`:

```yaml
# Dream-pass autonomous promotion policy.
#
# An experiment passes through this policy AFTER the rubric scorer has
# produced a delta. The policy decides: promote autonomously, reject,
# park as inconclusive, or flag for human review.
#
# Reviewed by api/server/services/dream_pass/policy.py.
domains:
  hiring:
    auto_promote:
      min_delta: 0.05
      min_samples: 40
      max_per_pass: 3
    flag_for_review:
      - kind: scope_expansion
        when: "candidate scope is broader than domain=hiring"
      - kind: implausible_delta
        when: "delta > 0.20"
      - kind: contradicts_active
        when: "candidate contradicts an active lesson"
    reject:
      when_delta_below: 0.0
    kill_switch_id: "dream-pass:hiring"
```

- [ ] **Step 2: Write the failing test**

Create `tests/api/services/dream_pass/test_policy.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from api.server.services.dream_pass.policy import (
    PromotionDecision,
    PromotionPolicy,
)
from api.server.services.dream_pass.types import Experiment
from api.server.services.lessons.types import LessonCandidate, LessonScope


@pytest.fixture
def policy() -> PromotionPolicy:
    return PromotionPolicy.from_file(Path("data/policies/dream-pass.policy.yaml"))


def _candidate(scope_persona: str | None = None) -> LessonCandidate:
    return LessonCandidate(
        id="L-1",
        body="x",
        scope=LessonScope(domain="hiring", persona_role=scope_persona),
        proposed_by="dream-pass:hiring",
        rationale="r",
    )


def _experiment(delta: float, n: int = 40) -> Experiment:
    return Experiment(
        id="EXP-1",
        candidate_lesson_id="L-1",
        control_score=0.7,
        treatment_score=0.7 + delta,
        n_samples=n,
    )


def test_promote_when_delta_above_threshold(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain="hiring",
        candidate=_candidate(),
        experiment=_experiment(delta=0.07),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == "promote"


def test_reject_when_delta_negative(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain="hiring",
        candidate=_candidate(),
        experiment=_experiment(delta=-0.05),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == "reject"


def test_inconclusive_when_n_too_small(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain="hiring",
        candidate=_candidate(),
        experiment=_experiment(delta=0.07, n=10),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == "inconclusive"


def test_flag_when_implausible_delta(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain="hiring",
        candidate=_candidate(),
        experiment=_experiment(delta=0.25),
        active_lessons=[],
        promoted_this_pass=0,
    )
    assert decision.verdict == "flagged"
    assert "implausible_delta" in decision.reason


def test_inconclusive_when_max_per_pass_reached(policy: PromotionPolicy) -> None:
    decision = policy.evaluate(
        domain="hiring",
        candidate=_candidate(),
        experiment=_experiment(delta=0.07),
        active_lessons=[],
        promoted_this_pass=3,  # already at cap
    )
    assert decision.verdict == "inconclusive"
    assert "max_per_pass" in decision.reason
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_policy.py -v`
Expected: FAIL on missing module.

- [ ] **Step 4: Implement the policy**

Create `api/server/services/dream_pass/policy.py`:

```python
"""Promotion policy evaluator. Pure: takes data, returns a decision."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from api.server.services.dream_pass.types import Experiment, ExperimentVerdict
from api.server.services.lessons.types import LessonCandidate


@dataclass(frozen=True)
class PromotionDecision:
    verdict: ExperimentVerdict
    reason: str


class PromotionPolicy:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    @classmethod
    def from_file(cls, path: Path) -> "PromotionPolicy":
        return cls(yaml.safe_load(path.read_text()) or {})

    def evaluate(
        self,
        *,
        domain: str,
        candidate: LessonCandidate,
        experiment: Experiment,
        active_lessons: list[str],
        promoted_this_pass: int,
    ) -> PromotionDecision:
        cfg = ((self._raw.get("domains") or {}).get(domain) or {})
        auto = cfg.get("auto_promote") or {}
        min_delta = float(auto.get("min_delta", 0.05))
        min_samples = int(auto.get("min_samples", 30))
        max_per_pass = int(auto.get("max_per_pass", 3))

        if experiment.delta < 0:
            return PromotionDecision(verdict="reject", reason="delta < 0")

        if experiment.delta > 0.20:
            return PromotionDecision(verdict="flagged", reason="implausible_delta")

        if candidate.scope.domain != domain:
            return PromotionDecision(verdict="flagged", reason="scope_expansion")

        # crude contradiction check: substring match against active lessons
        for active in active_lessons:
            if _contradicts(candidate.body, active):
                return PromotionDecision(verdict="flagged", reason="contradicts_active")

        if experiment.n_samples < min_samples:
            return PromotionDecision(
                verdict="inconclusive",
                reason=f"n_samples {experiment.n_samples} < min_samples {min_samples}",
            )

        if experiment.delta < min_delta:
            return PromotionDecision(
                verdict="reject",
                reason=f"delta {experiment.delta:.3f} < min_delta {min_delta}",
            )

        if promoted_this_pass >= max_per_pass:
            return PromotionDecision(
                verdict="inconclusive",
                reason=f"max_per_pass {max_per_pass} reached",
            )

        return PromotionDecision(verdict="promote", reason="passes all gates")


def _contradicts(a: str, b: str) -> bool:
    """Crude contradiction heuristic: same anchor noun, opposite verb.

    Good-enough for v1; a smarter check is a future plan.
    """
    a_low, b_low = a.lower(), b.lower()
    negations = ("never", "do not", "don't", "must not", "avoid")
    affirmations = ("always", "must", "should", "prefer")
    a_neg = any(n in a_low for n in negations)
    b_neg = any(n in b_low for n in negations)
    a_aff = any(n in a_low for n in affirmations)
    b_aff = any(n in b_low for n in affirmations)
    if (a_neg and b_aff) or (a_aff and b_neg):
        # crude noun overlap (>= 3 shared content words length>=5)
        a_words = {w for w in a_low.split() if len(w) >= 5}
        b_words = {w for w in b_low.split() if len(w) >= 5}
        return len(a_words & b_words) >= 3
    return False
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_policy.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add data/policies/dream-pass.policy.yaml api/server/services/dream_pass/policy.py tests/api/services/dream_pass/test_policy.py
git commit -m "feat(dream-pass): add promotion policy + evaluator"
```

---

## Task 9: Promote `lesson.write` / `lesson.prune` to enforce mode

**Files:**
- Modify: `data/policies/tools.yaml`

Plan 1 registered these tools in `audit` mode. Now that the dream-pass policy is the upstream gate, AGT can enforce.

- [ ] **Step 1: Flip enforcement**

In `data/policies/tools.yaml`, find the `lesson.write` and `lesson.prune` entries (added in Plan 1, Task 6) and change `enforcement: audit` to `enforcement: enforce` on both.

- [ ] **Step 2: Verify the policy bundle still compiles**

Run: `uv run python -c "from api.server.services.governance.policy_compiler import compile_bundle; compile_bundle()"`
Expected: no exception.

- [ ] **Step 3: Confirm Plan 1 governor tests still pass under enforce**

Run: `uv run pytest tests/api/services/lessons/test_governor.py -v`
Expected: all pass — they already assert correct behaviour under `enforcement_mode="enforce"`.

- [ ] **Step 4: Commit**

```bash
git add data/policies/tools.yaml
git commit -m "feat(dream-pass): promote lesson.write/prune to AGT enforce mode"
```

---

## Task 10: Dream pass orchestrator

**Files:**
- Create: `api/server/services/dream_pass/orchestrator.py`
- Test: `tests/api/services/dream_pass/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/services/dream_pass/test_orchestrator.py`:

```python
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.proposer import ProposalContext, StubProposer
from api.server.services.dream_pass.types import DreamSkill, Experiment


@pytest.fixture
def skill() -> DreamSkill:
    return DreamSkill(
        domain="hiring",
        version="1.0",
        max_candidates_per_pass=2,
        max_experiments_per_pass=2,
        body="x",
    )


@pytest.mark.asyncio
async def test_full_pass_promotes_winners_and_rejects_losers(skill: DreamSkill) -> None:
    governor = MagicMock()
    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=("C-001", "C-002"))

    # Build deterministic experiment outcomes per candidate body.
    def fake_run_experiment(*, experiment_id, candidate_lesson_id, candidate_body, cvs, active_lessons, rubric):
        # Experiment.run is now async; the mock is wrapped to AsyncMock at the bottom of this test.
        if "winner" in candidate_body:
            return Experiment(
                id=experiment_id, candidate_lesson_id=candidate_lesson_id,
                control_score=0.70, treatment_score=0.80, n_samples=40,
            )
        return Experiment(
            id=experiment_id, candidate_lesson_id=candidate_lesson_id,
            control_score=0.70, treatment_score=0.65, n_samples=40,
        )
    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(side_effect=fake_run_experiment)

    proposer = StubProposer(candidates=[
        ("winner lesson", "good rationale"),
        ("loser lesson", "poor rationale"),
    ])

    policy = MagicMock()
    policy.evaluate.side_effect = lambda **kw: (
        MagicMock(verdict="promote", reason="ok")
        if "winner" in kw["candidate"].body
        else MagicMock(verdict="reject", reason="delta < 0")
    )

    orchestrator = DreamPassOrchestrator(
        governor=governor,
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=policy,
        load_cvs=lambda ids: [{"candidate_id": cid} for cid in ids],
        load_active_lessons=lambda domain: [],
        load_recent_runs=lambda domain: [],
        load_working_notes=lambda agents: [],
        rubric=MagicMock(min_samples=40),
    )

    result = await orchestrator.run_pass(skill=skill, sample_size=2)

    assert result.domain == "hiring"
    assert len(result.experiments) == 2
    assert len(result.promoted_lesson_ids) == 1
    assert len(result.rejected_lesson_ids) == 1
    governor.write.assert_called_once()
    written = governor.write.call_args[0][0]
    assert written.body == "winner lesson"
    assert written.provenance.rubric_score_delta == pytest.approx(0.10)
    assert written.provenance.experiment_n == 40


@pytest.mark.asyncio
async def test_skill_max_experiments_caps_loop(skill: DreamSkill) -> None:
    governor = MagicMock()
    partitioner = MagicMock()
    partitioner.next_split.return_value = MagicMock(held_out_ids=("C-001",))
    experiment_runner = MagicMock()
    experiment_runner.run = AsyncMock(return_value=Experiment(
        id="EXP-X", candidate_lesson_id="L-X",
        control_score=0.7, treatment_score=0.72, n_samples=40,
    ))
    proposer = StubProposer(candidates=[("a", "r"), ("b", "r"), ("c", "r")])
    policy = MagicMock()
    policy.evaluate.return_value = MagicMock(verdict="reject", reason="x")

    skill_capped = DreamSkill(
        domain="hiring", version="1.0",
        max_candidates_per_pass=3,
        max_experiments_per_pass=2,  # cap below candidates
        body="x",
    )

    orchestrator = DreamPassOrchestrator(
        governor=governor,
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=policy,
        load_cvs=lambda ids: [{"candidate_id": cid} for cid in ids],
        load_active_lessons=lambda domain: [],
        load_recent_runs=lambda domain: [],
        load_working_notes=lambda agents: [],
        rubric=MagicMock(min_samples=40),
    )
    result = await orchestrator.run_pass(skill=skill_capped, sample_size=1)

    assert len(result.experiments) == 2  # capped
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/api/services/dream_pass/test_orchestrator.py -v`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the orchestrator**

Create `api/server/services/dream_pass/orchestrator.py`:

```python
"""DreamPassOrchestrator — the closed-loop optimiser.

Reads → proposes → A/B-tests → applies promotion policy → writes via the
AGT-gated LessonGovernor. Promotion happens autonomously; flagged
candidates are returned in DreamPassResult.flagged_lesson_ids for Plan 4
to surface in the exceptions portal.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.partitioner import CorpusPartitioner
from api.server.services.dream_pass.policy import PromotionPolicy
from api.server.services.dream_pass.proposer import (
    LessonProposer,
    ProposalContext,
)
from api.server.services.dream_pass.types import (
    DreamPassResult,
    DreamSkill,
    Experiment,
)
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.types import (
    Lesson,
    LessonProvenance,
)
from api.server.services.scoring.types import Rubric


class DreamPassOrchestrator:
    def __init__(
        self,
        *,
        governor: LessonGovernor,
        proposer: LessonProposer,
        partitioner: CorpusPartitioner,
        experiment_runner: ExperimentRunner,
        policy: PromotionPolicy,
        load_cvs: Callable[[tuple[str, ...]], list[dict]],
        load_active_lessons: Callable[[str], list[str]],
        load_recent_runs: Callable[[str], list[dict]],
        load_working_notes: Callable[[tuple[str, ...]], list],  # WorkingNote
        rubric: Rubric,
    ) -> None:
        self._governor = governor
        self._proposer = proposer
        self._partitioner = partitioner
        self._experiment_runner = experiment_runner
        self._policy = policy
        self._load_cvs = load_cvs
        self._load_active_lessons = load_active_lessons
        self._load_recent_runs = load_recent_runs
        self._load_working_notes = load_working_notes
        self._rubric = rubric

    async def run_pass(self, *, skill: DreamSkill, sample_size: int) -> DreamPassResult:
        dream_pass_id = f"DP-{uuid.uuid4()}"
        active = self._load_active_lessons(skill.domain)
        recent = self._load_recent_runs(skill.domain)
        # Working notes for the demo agent (hiring -> interview-recommender).
        # In a multi-agent domain, supply the tuple of agent skill names you care about.
        working_notes = self._load_working_notes(("interview-recommender",))

        candidates = self._proposer.propose(ProposalContext(
            skill=skill,
            working_notes=working_notes,
            recent_runs=recent,
            active_lessons=[{"body": b} for b in active],
        ))

        experiments: list[Experiment] = []
        promoted: list[str] = []
        rejected: list[str] = []
        flagged: list[str] = []

        for candidate in candidates:
            if len(experiments) >= skill.max_experiments_per_pass:
                break

            cvs = self._load_cvs(tuple(f"CV-{i}" for i in range(sample_size)))
            # Real impl: caller-supplied load_cvs reads from data/synthetic/hiring/cvs/

            experiment_id = f"EXP-{uuid.uuid4()}"
            experiment = await self._experiment_runner.run(
                experiment_id=experiment_id,
                candidate_lesson_id=candidate.id,
                candidate_body=candidate.body,
                cvs=cvs,
                active_lessons=active,
                rubric=self._rubric,
            )
            experiments.append(experiment)

            decision = self._policy.evaluate(
                domain=skill.domain,
                candidate=candidate,
                experiment=experiment,
                active_lessons=active,
                promoted_this_pass=len(promoted),
            )

            if decision.verdict == "promote":
                lesson = Lesson(
                    id=candidate.id,
                    body=candidate.body,
                    scope=candidate.scope,
                    provenance=LessonProvenance(
                        proposed_by=candidate.proposed_by,
                        run_ids=tuple(getattr(experiment, "workflow_ids", ()) or (dream_pass_id,)),
                        rubric_score_delta=experiment.delta,
                        experiment_n=experiment.n_samples,
                        promoted_at=datetime.now(timezone.utc),
                    ),
                )
                self._governor.write(lesson)
                promoted.append(candidate.id)
            elif decision.verdict == "reject":
                rejected.append(candidate.id)
            elif decision.verdict == "flagged":
                flagged.append(candidate.id)
            else:  # inconclusive
                pass

        return DreamPassResult(
            dream_pass_id=dream_pass_id,
            domain=skill.domain,
            experiments=tuple(experiments),
            promoted_lesson_ids=tuple(promoted),
            rejected_lesson_ids=tuple(rejected),
            flagged_lesson_ids=tuple(flagged),
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/api/services/dream_pass/test_orchestrator.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/server/services/dream_pass/orchestrator.py tests/api/services/dream_pass/test_orchestrator.py
git commit -m "feat(dream-pass): add DreamPassOrchestrator (the closed loop)"
```

---

## Task 11: Package surface + CLI

**Files:**
- Modify: `api/server/services/dream_pass/__init__.py`
- Create: `scripts/dream_pass.py`

- [ ] **Step 1: Re-export the public surface**

Replace `api/server/services/dream_pass/__init__.py` with:

```python
"""Experimental dream pass."""
from api.server.services.dream_pass.experiment import ExperimentRunner
from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator
from api.server.services.dream_pass.partitioner import CorpusPartitioner
from api.server.services.dream_pass.policy import PromotionDecision, PromotionPolicy
from api.server.services.dream_pass.proposer import (
    GHCPProposer,
    InterviewRecommenderSandbox,
    LessonProposer,
    ProposalContext,
    StubProposer,
)
from api.server.services.dream_pass.sandbox import (
    ArmResult,
    InterviewRecommenderSandbox,
    SandboxRunner,
)
from api.server.services.dream_pass.skill_loader import (
    DreamSkillLoadError,
    load_dream_skill,
)
from api.server.services.dream_pass.types import (
    CorpusSplit,
    DreamPassResult,
    DreamSkill,
    Experiment,
    ExperimentVerdict,
)

__all__ = [
    "GHCPProposer",
    "ArmResult",
    "CorpusPartitioner",
    "CorpusSplit",
    "DreamPassOrchestrator",
    "DreamPassResult",
    "DreamSkill",
    "DreamSkillLoadError",
    "Experiment",
    "ExperimentRunner",
    "ExperimentVerdict",
    "InterviewRecommenderSandbox",
    "LessonProposer",
    "ProposalContext",
    "PromotionDecision",
    "PromotionPolicy",
    "SandboxRunner",
    "StubProposer",
    "load_dream_skill",
]
```

- [ ] **Step 2: Implement the CLI**

Create `scripts/dream_pass.py`:

```python
"""Run one dream pass for a domain.

Usage:
    uv run python scripts/dream_pass.py --domain hiring --sample-size 40
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance import kernel
from api.server.services.dream_pass import (
    CorpusPartitioner,
    DreamPassOrchestrator,
    ExperimentRunner,
    InterviewRecommenderSandbox,
    PromotionPolicy,
    StubProposer,
    load_dream_skill,
)
from api.server.services.lessons import (
    KuzuLessonProvenance,
    LessonGovernor,
    Mem0LessonStore,
)
from api.server.services.scoring import (
    HiringLabelsGroundTruth,
    RunScorer,
    load_rubric,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument("--use-stub-proposer", action="store_true", help="bypass LLM; use a built-in stub")
    args = parser.parse_args()

    skill = load_dream_skill(Path(f"skills/dream-passes/{args.domain}/SKILL.md"))
    rubric = load_rubric(Path(f"data/rubrics/{args.domain}.yaml"))
    policy = PromotionPolicy.from_file(Path("data/policies/dream-pass.policy.yaml"))

    # Production wiring: real Kuzu + Mem0.
    graph = EntityGraph("data/portal/entity_graph.kuzu")
    store = Mem0LessonStore()
    provenance = KuzuLessonProvenance(graph)
    governor = LessonGovernor(
        store=store,
        kernel=kernel,
        audit=AuditLogger(),
        provenance=provenance,
        actor=f"dream-pass:{args.domain}",
    )
    partitioner = CorpusPartitioner(graph=graph, domain=args.domain)

    cvs_dir = Path(f"data/synthetic/{args.domain}/cvs")
    def load_cvs(ids):
        cvs: list[dict] = []
        for path in sorted(cvs_dir.glob("*.json"))[: args.sample_size]:
            cvs.append(json.loads(path.read_text()))
        return cvs

    def load_active_lessons(domain: str) -> list[str]:
        from api.server.services.lessons.types import LessonScope
        results = store.search("", scope=LessonScope(domain=domain), top_k=50)
        return [l.body for l in results]

    def load_recent_runs(domain: str) -> list[dict]:
        rows = graph.execute_cypher(
            "MATCH (w:Workflow {workflow_type: $d}) RETURN w.id AS id LIMIT 20",
            {"d": domain},
        )
        return [{"workflow_id": r["id"]} for r in rows]

    def load_working_notes(agent_skills):
        from api.server.services.lessons.working_memory_store import Mem0WorkingMemoryStore
        return Mem0WorkingMemoryStore().list_recent_unconsumed(
            domain_agents=tuple(agent_skills), limit=200,
        )

    def sandbox_factory() -> InterviewRecommenderSandbox:
        return InterviewRecommenderSandbox(kuzu_root=Path(tempfile.mkdtemp(prefix="dream-sb-")))

    truth = HiringLabelsGroundTruth(
        labels_csv=Path("data/synthetic/hiring/labels.csv")
    )

    def scorer_for(sandbox) -> RunScorer:
        return RunScorer(graph=sandbox.graph, ground_truth=truth)

    experiment_runner = ExperimentRunner(
        sandbox_factory=sandbox_factory,
        scorer_for=scorer_for,
    )

    if args.use_stub_proposer:
        proposer = StubProposer(candidates=[
            ("candidates with no recorded reason should be re-screened", "smoke test"),
        ])
    else:
        from api.server.services.dream_pass import GHCPProposer
        proposer = GHCPProposer()

    orchestrator = DreamPassOrchestrator(
        governor=governor,
        proposer=proposer,
        partitioner=partitioner,
        experiment_runner=experiment_runner,
        policy=policy,
        load_cvs=load_cvs,
        load_active_lessons=load_active_lessons,
        load_recent_runs=load_recent_runs,
        load_working_notes=load_working_notes,
        rubric=rubric,
    )

    import asyncio
    result = asyncio.run(orchestrator.run_pass(skill=skill, sample_size=args.sample_size))

    print(f"dream pass:  {result.dream_pass_id}")
    print(f"domain:      {result.domain}")
    print(f"experiments: {len(result.experiments)}")
    print(f"promoted:    {len(result.promoted_lesson_ids)} {list(result.promoted_lesson_ids)}")
    print(f"rejected:    {len(result.rejected_lesson_ids)}")
    print(f"flagged:     {len(result.flagged_lesson_ids)} {list(result.flagged_lesson_ids)}")
    for exp in result.experiments:
        print(f"  EXP {exp.id} delta={exp.delta:+.3f} n={exp.n_samples}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-run the CLI with the stub proposer**

Run: `uv run python scripts/dream_pass.py --domain hiring --sample-size 4 --use-stub-proposer`
Expected: prints a dream-pass report. Whether it promotes or rejects depends on the seeded data, but it must not raise.

- [ ] **Step 4: Commit**

```bash
git add api/server/services/dream_pass/__init__.py scripts/dream_pass.py
git commit -m "feat(dream-pass): add package surface + dream_pass CLI"
```

---

## Task 12: Full suite + regression check

- [ ] **Step 1: Run the dream-pass test suite**

Run: `uv run pytest tests/api/services/dream_pass/ -v`
Expected: all tests pass.

- [ ] **Step 2: Run mypy**

Run: `uv run mypy api/server/services/dream_pass/`
Expected: `Success: no issues found`.

- [ ] **Step 3: Run the full project test suite**

Run: `uv run pytest tests/api -x --tb=short`
Expected: all tests pass. The promotion of `lesson.write` / `lesson.prune` to `enforce` mode is the only behaviour change; Plan 1's governor tests already cover it.

- [ ] **Step 4: Verify killswitch still works against the new actor**

Run: `uv run python -c "from api.server.services.governance.kill_switch import state_store; state_store.kill('dream-pass:hiring'); print(state_store.is_killed('dream-pass:hiring'))"`
Expected: prints `True`. Then unkill: `... state_store.unkill('dream-pass:hiring')`.

---

## Definition of Done

- **Prerequisites (Tasks A and B) landed: `agent_interview_recommender._build_prompt` accepts `lessons` + `working_notes`, and the recruiter persona's `decision_policy` consumes `interview_recommender.decision` when present.**
- A dream pass can be triggered via CLI for a domain, executes end-to-end with no human intervention.
- The sandbox invokes the real `interview-recommender` agent via `run_agent_session` (under `LLM_RUNTIME=fake` in tests, `ghcp` in real runs — your GitHub Copilot seat).
- Promoted lessons are written via `LessonGovernor`, visible in both Mem0 (or the configured `LessonStore`) and the Kuzu `Lesson` node table with `LESSON_FROM_RUN` edges.
- The proposer reads recent `WorkingNote` rows (from Plan 1's `WorkingMemoryStore`) as its raw material — proposals are grounded in what agents actually noticed, not invented from outcome data alone.
- Rejected and flagged candidates are recorded in the result, with flagged ones available for Plan 4 to surface.
- `dream-pass.policy.yaml` is the only place "what to promote" is encoded.
- Every lesson write is a signed AGT ledger entry.
- `agt kill dream-pass:hiring` pauses the next pass at the kernel.
- Existing test suite still passes.
