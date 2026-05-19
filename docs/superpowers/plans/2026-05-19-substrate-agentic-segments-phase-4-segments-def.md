# Substrate Agentic Segments — Phase 4: Hiring Segments D / E / F — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Roll out the Segment B pattern (Phase 3) to the remaining hiring segments. Phase A (Budget) and Phase C (Voice) are single-skill and stay as their existing single-activity calls. Segments to convert:

- **D — Interview decisioning** (current Phase 7). Skill: `interview-recommender`.
- **E — Compliance + Offer prep** (current Phases 8 + 9). Skills: `jurisdiction-router`, `betrvg-checker`, `offer-personaliser`. MCP: `policy.search`.
- **F — Onboarding** (current Phase 10). Skill: `onboarding-buddy`. MCP: `avatar.render`. Special: retry-guarded by idempotent-only check because `onboarding-buddy` triggers non-reversible JML/calendar side effects.

**Architecture:** Mirror Phase 3 exactly — `api/functions/segments/hiring_<letter>.py` with `Segment<Letter>Output` Pydantic model, `run_segment_<letter>`, paired Durable activity triggers in `function_app.py`, orchestrator branches in `hiring.py`. Extend `HIRING_SEGMENT_MODE` to accept any comma-separated subset.

**Tech Stack:** Same as Phase 3.

**Spec:** [docs/superpowers/specs/2026-05-19-substrate-agentic-segments-design.md](../specs/2026-05-19-substrate-agentic-segments-design.md) — Phase 4.

**Depends on:** Phase 3 merged. The segment scaffold, prompt builder pattern, validator activity pattern, orchestrator retry pattern, and harness all originate there.

---

## File structure

### Create

```
api/functions/segments/
  hiring_d.py
  hiring_e.py
  hiring_f.py

tests/api/unit/
  test_hiring_segment_d.py
  test_hiring_segment_e.py
  test_hiring_segment_f.py

tmp/
  segment-all-baseline.txt  — A/B harness output with all segments enabled
```

### Modify

```
function_app.py
  — 6 new activity triggers (3 segment + 3 validator)
api/functions/workflows/hiring.py
  — 3 new orchestrator branches for D / E / F
  — F branch has idempotent-only retry guard
scripts/replay_hiring_compare.py
  — accept --mode=all and report end-to-end session totals
```

---

## Phase A — Segment D (Interview decisioning)

### Task 1: `SegmentDOutput` + `run_segment_d` + activity triggers

**Files:**
- Create: `api/functions/segments/hiring_d.py`
- Modify: `function_app.py`
- Test: `tests/api/unit/test_hiring_segment_d.py`

- [ ] **Step 1: Write the failing test**

Copy `tests/api/unit/test_hiring_segment_b.py` to `_d.py`. Replace every `b` with `d`, every `_B` with `_D`, every `SegmentB` with `SegmentD`. Replace the schema-accept fixture to:

```python
{
    "decision": "advance",
    "interview_recommendation": {"format": "panel", "level": "senior"},
    "rationale": "strong screen signals",
}
```

Replace the schema-reject params with:

```python
{"decision": "MAYBE", "interview_recommendation": {}, "rationale": "x"},          # bad literal
{"interview_recommendation": {}, "rationale": "x"},                                # missing decision
{"decision": "advance", "rationale": "x"},                                         # missing interview_recommendation
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/unit/test_hiring_segment_d.py::test_segment_d_output_accepts_valid -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the file**

```python
# api/functions/segments/hiring_d.py
"""Hiring Segment D — interview decisioning."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


_SEGMENT_D_SKILLS: list[str] = ["interview-recommender"]
_SEGMENT_D_MCPS: list[str] = []


class SegmentDOutput(BaseModel):
    decision: Literal["advance", "reject", "escalate"]
    interview_recommendation: dict
    rationale: str


def _skills_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "server" / "skills"


def _build_segment_d_prompt(enriched: dict, prior_validator_error: str | None = None) -> str:
    schema = SegmentDOutput.model_json_schema()
    parts = [
        "You are deciding whether to advance a candidate to interview.",
        "",
        "Context:",
        repr({k: enriched.get(k) for k in ("req_id", "candidate_id", "screening_verdict") if k in enriched}),
        "",
        f"Available skills: {', '.join(_SEGMENT_D_SKILLS)}",
        "",
        "Deliverable — return ONE JSON object matching this schema:",
        repr(schema),
        "",
        "Return only the JSON object. No preamble.",
    ]
    if prior_validator_error:
        parts.extend(["", "Previous attempt failed validation:", prior_validator_error])
    return "\n".join(parts)


async def run_segment_d(input: dict) -> dict:
    from api.functions.graphs.executors.agents._wrapper import run_agent_session
    skills_root = _skills_dir()
    skill_dirs = [skills_root / s for s in _SEGMENT_D_SKILLS]
    prompt = _build_segment_d_prompt(input, prior_validator_error=input.get("prior_validator_error"))
    return await run_agent_session(
        prompt=prompt, tools=[], skill_dir=skill_dirs[0],
        skill_label="hiring-segment-d", workflow_id=input.get("workflow_id"),
        model="gpt-4.1",
    )
```

- [ ] **Step 4: Add activity triggers to `function_app.py`**

```python
@app.activity_trigger(input_name="input")
async def hiring_segment_d_activity_trigger(input: dict) -> dict:
    from api.functions.segments.hiring_d import run_segment_d
    return await run_segment_d(input)


@app.activity_trigger(input_name="payload")
def validate_segment_d_output_activity_trigger(payload: dict) -> dict:
    from api.functions.segments.hiring_d import SegmentDOutput
    from pydantic import ValidationError
    try:
        return {"ok": True, "output": SegmentDOutput.model_validate(payload).model_dump()}
    except ValidationError as e:
        return {"ok": False, "errors": e.errors()}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/api/unit/test_hiring_segment_d.py -v
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add api/functions/segments/hiring_d.py function_app.py tests/api/unit/test_hiring_segment_d.py
git commit -m "feat(segments): hiring Segment D (interview decisioning)"
```

---

## Phase B — Segment E (Compliance + Offer prep)

### Task 2: `SegmentEOutput` + `run_segment_e` + activity triggers

**Files:**
- Create: `api/functions/segments/hiring_e.py`
- Modify: `function_app.py`
- Test: `tests/api/unit/test_hiring_segment_e.py`

- [ ] **Step 1: Write the failing test**

Same pattern as Task 1. Schema-accept fixture:

```python
{
    "offer_letter_id": "OFFER-1",
    "jurisdiction": "USA",
    "compliance_steps": ["EEO checks complete"],
    "policy_citations": ["data/policies/hr/eeo.md#L34"],
    "rationale": "USA jurisdiction routed via offer-personaliser; EEO checks satisfied",
}
```

Schema-reject params:

```python
{"offer_letter_id": "OFFER-1", "jurisdiction": "FR", "compliance_steps": [], "policy_citations": []},   # bad jurisdiction
{"jurisdiction": "USA", "compliance_steps": [], "policy_citations": []},                                # missing offer_letter_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/unit/test_hiring_segment_e.py::test_segment_e_output_accepts_valid -v
```

Expected: FAIL.

- [ ] **Step 3: Write the file**

Mirror Segment D shape. Key fields:

```python
_SEGMENT_E_SKILLS = ["jurisdiction-router", "betrvg-checker", "offer-personaliser"]
_SEGMENT_E_MCPS = ["policy.search"]


class SegmentEOutput(BaseModel):
    offer_letter_id: str
    jurisdiction: Literal["USA", "DE"]
    compliance_steps: list[str]
    policy_citations: list[str]
    rationale: str  # mirrors SegmentB/D for auditability — downstream scorer reads this
```

`run_segment_e` and the prompt builder follow the Segment D pattern exactly.

- [ ] **Step 4: Add activity triggers to `function_app.py`**

Same shape as Segment D — two new `@app.activity_trigger` blocks.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/api/unit/test_hiring_segment_e.py -v
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add api/functions/segments/hiring_e.py function_app.py tests/api/unit/test_hiring_segment_e.py
git commit -m "feat(segments): hiring Segment E (compliance + offer prep)"
```

---

## Phase C — Segment F (Onboarding) with idempotent-only retry guard

### Task 3: `SegmentFOutput` + `run_segment_f` + activity triggers

**Files:**
- Create: `api/functions/segments/hiring_f.py`
- Modify: `function_app.py`
- Test: `tests/api/unit/test_hiring_segment_f.py`

- [ ] **Step 1: Write the failing test**

Same pattern as previous. Schema-accept fixture:

```python
{
    "onboarding_kickoff_id": "ONB-1",
    "avatar_video_url": "https://example.test/avatar.mp4",
    "day1_calendar_id": "MS-INV-1",
    "provisioning_steps": ["JML ticket SN-1234 raised"],
    "rationale": "onboarding-buddy emitted JML + calendar; avatar rendered",
}
```

Schema-reject:

```python
{"onboarding_kickoff_id": None, "provisioning_steps": []},  # required fields missing/null
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/api/unit/test_hiring_segment_f.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write the file**

```python
_SEGMENT_F_SKILLS = ["onboarding-buddy"]
_SEGMENT_F_MCPS = ["avatar.render"]


class SegmentFOutput(BaseModel):
    onboarding_kickoff_id: str
    avatar_video_url: str | None = None
    day1_calendar_id: str | None = None
    provisioning_steps: list[str]
    rationale: str  # mirrors SegmentB/D for auditability — downstream scorer reads this
```

The `run_segment_f` body must also surface the `tool_calls` collected by the runtime so the orchestrator can inspect them for idempotent-only retry gating. Extend the return shape:

```python
async def run_segment_f(input: dict) -> dict:
    from api.functions.graphs.executors.agents._wrapper import run_agent_session
    out = await run_agent_session(
        prompt=_build_segment_f_prompt(input, prior_validator_error=input.get("prior_validator_error")),
        tools=[], skill_dir=_skills_dir() / "onboarding-buddy",
        skill_label="hiring-segment-f", workflow_id=input.get("workflow_id"),
        model="gpt-4.1",
    )
    # run_agent_session already collects tool_calls into the response.
    # Surface a flat list of (tool_name, success) tuples so the
    # orchestrator can gate retry on whether anything irreversible
    # has already fired.
    out["_tool_call_summary"] = [
        {"name": tc.get("name"), "reversible": _is_reversible(tc.get("name"))}
        for tc in (out.get("_raw_tool_calls") or [])
    ]
    return out


def _is_reversible(tool_name: str | None) -> bool:
    """Per data/policies/tools.yaml conventions: *.list_*, *.get_*,
    *.search_*, *.lookup_*, *.query_*, *.find_*, *.check_*,
    *.resolve_* are reversible. Anything else is treated as
    irreversible (the safe default for retry gating)."""
    if not tool_name:
        return True
    safe_verbs = ("list", "get", "search", "lookup", "query", "find", "check", "resolve")
    leaf = tool_name.split(".")[-1].split("_")[0]
    return leaf in safe_verbs
```

- [ ] **Step 4: Add activity triggers to `function_app.py`**

Same shape as previous segments.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/api/unit/test_hiring_segment_f.py -v
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add api/functions/segments/hiring_f.py function_app.py tests/api/unit/test_hiring_segment_f.py
git commit -m "feat(segments): hiring Segment F (onboarding) with reversibility tracking"
```

---

## Phase D — Orchestrator branches for D / E / F

### Task 4: Wire orchestrator branches with retry loops (D and E use Segment B's pattern, F adds idempotent-only guard)

**Files:**
- Modify: `api/functions/workflows/hiring.py`
- Test: extend each segment's test file

- [ ] **Step 1: Write the failing tests**

For each segment letter (`d`, `e`, `f`), add the same four orchestrator-dispatch tests Segment B has, using the same Durable context mock pattern from `test_hiring_voice_phase.py`:

- `test_orchestrator_segment_<letter>_on_replaces_per_phase_activities`
- `test_orchestrator_segment_<letter>_off_keeps_existing_path`
- `test_orchestrator_segment_<letter>_retry_on_validation_failure`
- `test_orchestrator_segment_<letter>_retry_exhaustion`

For Segment F, add one more:

- `test_orchestrator_segment_f_skips_retry_after_irreversible_tool_call` — program `run_segment_f` to return a `_tool_call_summary` containing one `{"name": "servicenow.create_ticket", "reversible": False}` plus an invalid output. Assert the orchestrator does NOT retry; it writes `checkpoint_activity_trigger` of kind `"segment.failed.irreversible"` and surfaces for HITL.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/api/unit/test_hiring_segment_d.py tests/api/unit/test_hiring_segment_e.py tests/api/unit/test_hiring_segment_f.py -v -k orchestrator
```

Expected: FAIL — orchestrator branches not yet added.

- [ ] **Step 3: Edit `api/functions/workflows/hiring.py:hiring_orchestration`**

Locate the Phase 7 block (Interview). Replace with the same `if _segment_enabled("d", ...)` guard as Segment B uses. The retry loop body is identical to Segment B's; only the activity names and segment letter change.

Locate the Phase 8 + 9 block (Compliance + Offer). Wrap both phases in `if _segment_enabled("e", ...)`. The `else` branch keeps both `call_activity` lines verbatim.

Locate the Phase 10 block (Onboarding). Wrap in `if _segment_enabled("f", ...)`. Inside the retry loop, add the idempotent-only guard:

```python
# Segment F retry gate: refuse to retry if any irreversible tool has
# already fired. Onboarding has external side effects (ServiceNow JML,
# Graph calendar invites, avatar render) that cannot safely be re-run.
if not validator.get("ok"):
    irreversibles = [
        tc for tc in (segment_result.get("_tool_call_summary") or [])
        if not tc.get("reversible")
    ]
    if irreversibles:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": context.instance_id,
            "kind": "segment.failed.irreversible",
            "segment": "f",
            "irreversible_tools": [tc["name"] for tc in irreversibles],
            "errors": validator.get("errors"),
        })
        raise RuntimeError(
            "Segment F validation failed after irreversible tool calls; HITL required"
        )
    # else fall through to normal retry
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/api/unit/test_hiring_segment_*.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add api/functions/workflows/hiring.py tests/api/unit/test_hiring_segment_*.py
git commit -m "feat(hiring): orchestrator branches for Segments D, E, F"
```

---

## Phase E — End-to-end harness with `--mode=all`

### Task 5: Extend `scripts/replay_hiring_compare.py`

**Files:**
- Modify: `scripts/replay_hiring_compare.py`
- Create: `tmp/segment-all-baseline.txt`

- [ ] **Step 1: Extend the script**

Add CLI flag `--mode` defaulting to `b`. When `--mode=all`, drive the full segment set (b + d + e + f), summing `FakeRuntime.call_count` across all four segments per record. The per-phase baseline counts 10 sessions per record (one per current phase).

- [ ] **Step 2: Run the harness**

```bash
python scripts/replay_hiring_compare.py -n 5 --mode=all | tee tmp/segment-all-baseline.txt
```

Expected: under `--mode=all`, sessions-per-record ≤ 6 (vs 10 baseline). Overall reduction ≥ 40%.

- [ ] **Step 3: Commit**

```bash
git add scripts/replay_hiring_compare.py tmp/segment-all-baseline.txt
git commit -m "feat(segments): end-to-end A/B harness with HIRING_SEGMENT_MODE=all"
```

---

## Acceptance

- [ ] `pytest tests/api/unit/test_hiring_segment_*.py -v` — all green (D, E, F)
- [ ] `pytest tests/api/server/services/governance/test_permission_handler.py tests/api/functions/agents/test_runtime_protocol.py tests/api/unit/test_hiring_segment_b.py -v` — Phase 1/2/3 regressions still green
- [ ] `python scripts/replay_hiring_compare.py -n 5 --mode=all` shows ≤ 6 sessions per record (baseline 10)
- [ ] Segment F retry path is gated on `_tool_call_summary` — irreversible calls block retry
- [ ] `HIRING_SEGMENT_MODE=b,e` enables only B and E; the others stay on the per-phase path

---

## Risks

- **R1**: Segment E composes three skills; skill bleed is the recurring risk. Mitigation: tighten the three SKILL.md `description` fields before Phase E run.
- **R2**: Segment F's `_tool_call_summary` depends on `_wrapper.py` exposing the runtime's collected tool_calls in the return shape. Phase 2 wired this via `LLMRuntimeResult.tool_calls`; verify it propagates through `run_agent_session` into the dict that `run_segment_f` receives. If it doesn't, extend `_wrapper.py` to surface `_raw_tool_calls` on the return dict.
- **R3**: Single-skill segments (D, F) are wrapped in the segment scaffold for structural consistency. The cost is one file each and one Durable activity round-trip per phase — accepted because future SKILL additions are likely to grow these into multi-skill segments.
