# Recruiter HITL Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace today's stub Phase 7 with three sequential HITL waits — recruiter invites to interview, candidate books a slot, recruiter records post-interview offer/reject + level — all gated by an `interview-recommender` agent that recommends but doesn't decide.

**Architecture:** Add three new Durable external events (`interview_invite`, `interview_booked`, `offer_decision`) to `hiring_orchestration`. One new `book_interview` magic-link scope. One new agent + skill. Four new Functions activities. One new candidate-portal route (`/book`). Two new admin routes. Three new conditional panels in `RecruiterCandidate.tsx` keyed off `awaiting_reason`. Auto-rejection email at both reject paths. Spec lives at [docs/superpowers/specs/2026-05-01-recruiter-hitl-design.md](../specs/2026-05-01-recruiter-hitl-design.md).

**Tech Stack:** Python 3.12 (azure-durable-functions, FastAPI, copilot SDK), TypeScript/React 19 (Vite), pytest + vitest, sqlite (magic_link state), tailwind v4 utility classes.

---

## File Structure

| File                                                                                       | Status   | Responsibility                                              |
|--------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------|
| `api/shared/role_levels.py`                                                                | Create   | Levels-by-role-family lookup; `levels_for(role_title)`.     |
| `api/server/skills/interview-recommender/SKILL.md`                                         | Create   | LLM skill instructions for the recommender agent.           |
| `api/functions/graphs/executors/agents/agent_interview_recommender.py`                     | Create   | Wraps the skill via `_wrapper.run_agent_session`. Returns `{decision, level_suggestion, rationale, talking_points}`. |
| `api/functions/workflows/interview_activities.py`                                          | Create   | 4 new activities: `hiring_interview_recommender_activity`, `issue_book_interview_link_activity`, `send_book_interview_email_activity`, `send_rejection_email_activity`. Mirrors `voice_screen_activities.py` shape. |
| `api/functions/workflows/activities.py`                                                    | Modify   | Re-export the four new activities.                          |
| `function_app.py`                                                                          | Modify   | Register four new `@app.activity_trigger` decorators.       |
| `api/functions/workflows/hiring.py`                                                        | Modify   | Replace stub Phase 7 with the three-wait sequence.          |
| `api/server/routes/portal_interview.py`                                                    | Create   | `GET /resolve` + `POST /book` for the candidate-side booking flow. |
| `api/server/routes/portal_admin_decisions.py`                                              | Create   | `POST /interview-invite` + `POST /post-interview-decision` for the recruiter-side actions. |
| `api/server/main.py`                                                                       | Modify   | Mount the two new routers.                                  |
| `web/portal/src/lib/api.ts`                                                                | Modify   | Add `getBookingResolve`, `postBooking`, `postInterviewInvite`, `postPostInterviewDecision`. |
| `web/portal/src/routes/Book.tsx`                                                           | Create   | `/book?token=…` slot grid + submit.                         |
| `web/portal/src/App.tsx`                                                                   | Modify   | Mount `/book` route.                                        |
| `web/portal/src/routes/RecruiterCandidate.tsx`                                             | Modify   | +3 conditional panels keyed off `awaiting_reason`.          |
| `tests/api/shared/test_role_levels.py`                                                     | Create   | Unit tests for level lookup.                                |
| `tests/api/functions/agents/test_agent_interview_recommender.py`                           | Create   | Unit tests for the recommender executor (mock the wrapper). |
| `tests/api/functions/workflows/test_interview_activities.py`                               | Create   | Unit tests for the four new activities.                     |
| `tests/api/server/routes/test_portal_interview.py`                                         | Create   | Integration tests for `/resolve` + `/book`.                 |
| `tests/api/server/routes/test_portal_admin_decisions.py`                                   | Create   | Integration tests for the two recruiter-decision routes.    |

---

## Task 1: `role_levels` lookup module

**Files:**
- Create: `api/shared/role_levels.py`
- Test: `tests/api/shared/test_role_levels.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/shared/test_role_levels.py
"""Levels-by-role-family lookup. Drives the post-interview form's level
dropdown options and validates the agent's level_suggestion."""
from api.shared.role_levels import DEFAULT_LEVELS, levels_for


def test_data_engineering_levels():
    assert levels_for("Senior Data Engineer") == [
        "Mid-Level", "Senior", "Staff", "Principal",
    ]


def test_creative_director_levels():
    assert levels_for("Creative Director") == [
        "Director", "Senior Director", "VP Creative",
    ]


def test_unknown_role_falls_back_to_default():
    assert levels_for("Brand Strategist") == DEFAULT_LEVELS
    assert DEFAULT_LEVELS == ["Junior", "Mid", "Senior", "Lead"]


def test_none_role_falls_back_to_default():
    assert levels_for(None) == DEFAULT_LEVELS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/api/shared/test_role_levels.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'api.shared.role_levels'`.

- [ ] **Step 3: Write minimal implementation**

```python
# api/shared/role_levels.py
"""Per-role-family seniority ladders. Sole consumer right now is the
post-interview decision form (level dropdown) and the interview-recommender
agent's `level_suggestion` validation. Keep additions here, not inline."""
from __future__ import annotations

DEFAULT_LEVELS: list[str] = ["Junior", "Mid", "Senior", "Lead"]

_LEVELS_BY_TITLE_KEYWORD: dict[str, list[str]] = {
    "data engineer":     ["Mid-Level", "Senior", "Staff", "Principal"],
    "creative director": ["Director", "Senior Director", "VP Creative"],
}


def levels_for(role_title: str | None) -> list[str]:
    """Return the level ladder for `role_title`, or DEFAULT_LEVELS when no
    keyword matches. Match is case-insensitive substring against the keys."""
    if not role_title:
        return DEFAULT_LEVELS
    haystack = role_title.lower()
    for keyword, ladder in _LEVELS_BY_TITLE_KEYWORD.items():
        if keyword in haystack:
            return ladder
    return DEFAULT_LEVELS
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/api/shared/test_role_levels.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/shared/role_levels.py tests/api/shared/test_role_levels.py
git commit -m "feat(hiring): role_levels lookup for post-interview form + recommender"
```

---

## Task 2: `interview-recommender` skill

**Files:**
- Create: `api/server/skills/interview-recommender/SKILL.md`

- [ ] **Step 1: Write the skill instruction file**

```markdown
---
name: interview-recommender
description: Given a candidate's CV profile, screening verdict, voice transcript and role context, recommend whether to advance them (to interview at gate 1, or to offer at gate 2) and at what level. Recommends only — never decides.
allowed-tools:
---

You are a senior recruiter reviewing a candidate at one of two decision points in the hiring pipeline:

1. **Post-voice screen** — should the candidate be invited to a full interview?
2. **Post-interview** — should the candidate receive an offer, and at what level?

You will be told which gate this is. You **recommend** — a human recruiter makes the final call.

## Inputs (always present in the prompt)

- `gate`: `"post_voice"` or `"post_interview"`
- `role_title`, `role_jurisdiction`
- `cv_crystalliser` profile (the structured CV read)
- `screening` verdict from auto-shortlister (`green` / `amber` / `red` plus rationale)
- `voice_transcript` turns + `voice_score` (0..10)
- `levels_for_role`: the valid level ladder for this role family

## Output (strict JSON, no prose, no markdown fences)

```json
{
  "decision": "advance" | "decline",
  "level_suggestion": "Senior" | null,
  "rationale": "2-3 sentences citing specific evidence from the inputs",
  "talking_points": ["probe X", "verify Y"]
}
```

## Rules

- `decision: "advance"` means recommend invite-to-interview (at gate 1) or recommend make-offer (at gate 2). `decline` means recommend rejecting at this gate.
- `level_suggestion` MUST be one of `levels_for_role` or `null`. At gate 1, almost always `null` (interview hasn't happened). At gate 2, populate when you have enough signal — otherwise `null` so the recruiter picks unprompted.
- `rationale` is for the recruiter, not the candidate. Be specific. "Strong on data tooling, vague on stakeholder management — would push on EM experience in interview" beats "looks fine".
- `talking_points` is 2-4 short concrete probes for the next conversation. At gate 2 these should be follow-up checks if offer-bound, or callout reasons if decline-bound.
- Never reference the candidate's age, gender, name origin, or anything else that could imply protected-class reasoning.
- If the inputs are sparse (e.g. extraction failed), set `decision: "decline"` and rationale `"insufficient evidence — need a clean CV read before advancing"`. Do not guess.

Return only the JSON object.
```

- [ ] **Step 2: Commit**

```bash
git add api/server/skills/interview-recommender/SKILL.md
git commit -m "feat(hiring): interview-recommender skill instructions"
```

---

## Task 3: `agent_interview_recommender` executor

**Files:**
- Create: `api/functions/graphs/executors/agents/agent_interview_recommender.py`
- Test: `tests/api/functions/agents/test_agent_interview_recommender.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/functions/agents/test_agent_interview_recommender.py
"""Recommender executor — wraps run_agent_session with the right prompt
shape and returns the parsed JSON. We mock the wrapper so the test doesn't
spin up a GHCP session."""
from unittest.mock import patch, AsyncMock
import pytest

from api.functions.graphs.executors.agents import agent_interview_recommender


@pytest.mark.asyncio
async def test_executor_passes_gate_and_role_in_prompt():
    parsed = {
        "decision": "advance",
        "level_suggestion": None,
        "rationale": "Voice transcript shows depth on Spark.",
        "talking_points": ["pipeline ownership"],
    }
    with patch.object(
        agent_interview_recommender, "run_agent_session",
        new=AsyncMock(return_value=parsed),
    ) as mock:
        out = await agent_interview_recommender.execute({
            "gate": "post_voice",
            "role_title": "Senior Data Engineer",
            "role_jurisdiction": "USA",
            "workflow_id": "WF-1",
            "cv_crystalliser": {"name": "X", "current_title": {"value": "DE"}},
            "screening": {"verdict": "green", "rationale": "ok"},
            "voice_transcript": [{"role": "agent", "text": "hi", "ts": 0.0}],
            "voice_score": 7.5,
        })

    assert out == {"interview_recommender": parsed}
    call = mock.call_args
    prompt = call.kwargs["prompt"]
    # Must declare which gate so the skill picks the right behaviour
    assert "gate=post_voice" in prompt or '"gate": "post_voice"' in prompt
    # Must include the role title so the agent knows the level ladder
    assert "Senior Data Engineer" in prompt
    # Must pass the levels list so the agent can validate level_suggestion
    assert "Mid-Level" in prompt and "Principal" in prompt
    # Skill label drives the agent_reasoning filter on the recruiter UI
    assert call.kwargs["skill_label"] == "interview_recommender"


@pytest.mark.asyncio
async def test_executor_returns_empty_payload_when_no_workflow():
    """No workflow_id → agent shouldn't run (matches cv_crystalliser pattern)."""
    out = await agent_interview_recommender.execute({"gate": "post_voice"})
    assert out == {"interview_recommender": None}


@pytest.mark.asyncio
async def test_executor_handles_parse_error_gracefully():
    """When the wrapper returns parse_error, executor returns a structured
    failure instead of bubbling — recruiter UI shows "rec unavailable"."""
    with patch.object(
        agent_interview_recommender, "run_agent_session",
        new=AsyncMock(return_value={"raw": "blah", "parse_error": True}),
    ):
        out = await agent_interview_recommender.execute({
            "gate": "post_voice",
            "workflow_id": "WF-1",
            "role_title": "Senior Data Engineer",
        })
    rec = out["interview_recommender"]
    assert rec["decision"] == "decline"
    assert rec["recommender_status"] == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/api/functions/agents/test_agent_interview_recommender.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the executor**

```python
# api/functions/graphs/executors/agents/agent_interview_recommender.py
"""POC2 Phase 7 — interview-recommender executor.

Runs at two distinct gates (`post_voice`, `post_interview`) under
current_phase=Interview. Builds a single prompt that names the gate and
forwards all available context, calls the cv-crystalliser-style wrapper,
and returns the structured JSON for the recruiter UI to render.

Failure mode: when the wrapper returns parse_error, we return a synthetic
"recommender_status: failed" payload so the recruiter view paints a
clear "rec unavailable" state instead of either crashing or fabricating
a recommendation.
"""
from __future__ import annotations

import json

from api.shared.role_levels import levels_for

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "interview-recommender"


def _build_prompt(input: dict) -> str:
    gate = input.get("gate") or "post_voice"
    role_title = input.get("role_title") or "Candidate"
    role_jurisdiction = input.get("role_jurisdiction") or "—"
    levels = levels_for(role_title)
    payload = {
        "gate": gate,
        "role_title": role_title,
        "role_jurisdiction": role_jurisdiction,
        "levels_for_role": levels,
        "cv_crystalliser": input.get("cv_crystalliser") or {},
        "screening": input.get("screening") or {},
        "voice_transcript": input.get("voice_transcript") or [],
        "voice_score": input.get("voice_score"),
    }
    return (
        f"Recommend at gate `{gate}` for `{role_title}`. "
        f"Context (JSON):\n```json\n{json.dumps(payload, indent=2)}\n```\n"
        f"Return ONLY the JSON object specified in your skill — no prose, "
        f"no markdown fences."
    )


async def execute(input: dict) -> dict:
    workflow_id = input.get("workflow_id") or input.get("hire_id")
    if not workflow_id:
        return {"interview_recommender": None}

    parsed = await run_agent_session(
        prompt=_build_prompt(input),
        tools=[],
        skill_dir=_SKILL_DIR,
        skill_label="interview_recommender",
        workflow_id=workflow_id,
    )

    parse_failed = (
        not isinstance(parsed, dict)
        or parsed.get("parse_error")
        or "decision" not in parsed
    )
    if parse_failed:
        return {
            "interview_recommender": {
                "decision": "decline",
                "level_suggestion": None,
                "rationale": "Recommender output unparseable — see agent_reasoning trace.",
                "talking_points": [],
                "recommender_status": "failed",
            }
        }

    parsed.setdefault("recommender_status", "ok")
    return {"interview_recommender": parsed}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/api/functions/agents/test_agent_interview_recommender.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/functions/graphs/executors/agents/agent_interview_recommender.py tests/api/functions/agents/test_agent_interview_recommender.py
git commit -m "feat(hiring): interview-recommender agent executor"
```

---

## Task 4: Interview activities — link issuance + emails + recommender wrapper

**Files:**
- Create: `api/functions/workflows/interview_activities.py`
- Test: `tests/api/functions/workflows/test_interview_activities.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/functions/workflows/test_interview_activities.py
"""Phase 7 sub-wait activities. Mirrors voice_screen_activities tests —
direct function calls with monkeypatched app_state so the graph stack
isn't loaded."""
from unittest.mock import MagicMock

import pytest

from api.functions.workflows import interview_activities


@pytest.fixture
def fake_app_state(monkeypatch):
    state = MagicMock()
    state.magic_links.issue.return_value = "TOKEN-123"
    state.email_sender.send.return_value = "msg-id-1"
    state.store.get_candidate.return_value = {
        "id": "C-1", "name": "Alex", "email": "alex@example.com",
    }
    monkeypatch.setattr(
        "api.functions.workflows.interview_activities.app_state",
        state, raising=False,
    )
    # Make the import-time `from api.server.state import app_state` lookup
    # also resolve to our fake.
    import api.server.state as ss
    monkeypatch.setattr(ss, "app_state", state)
    return state


def test_issue_book_interview_link_returns_token_and_url(fake_app_state):
    out = interview_activities.issue_book_interview_link_activity({
        "candidate_id": "C-1",
    })
    fake_app_state.magic_links.issue.assert_called_once()
    kwargs = fake_app_state.magic_links.issue.call_args.kwargs
    assert kwargs["scope"] == "book_interview"
    assert kwargs["single_use"] is True
    assert kwargs["ttl_seconds"] == 7 * 24 * 3600
    assert out["token"] == "TOKEN-123"
    assert out["portal_url"].endswith("/book?token=TOKEN-123")


def test_send_book_interview_email_sends_and_records(fake_app_state):
    out = interview_activities.send_book_interview_email_activity({
        "candidate_id": "C-1",
        "token": "TOKEN-123",
        "portal_url": "http://localhost:5274/book?token=TOKEN-123",
        "role_title": "Senior Data Engineer",
    })
    fake_app_state.email_sender.send.assert_called_once()
    sent = fake_app_state.email_sender.send.call_args.kwargs
    assert sent["to"] == "alex@example.com"
    assert "interview" in sent["subject"].lower()
    assert "TOKEN-123" in sent["html_body"]
    assert "Senior Data Engineer" in sent["html_body"]
    assert out["sent"] is True


def test_send_book_interview_email_no_candidate(fake_app_state):
    fake_app_state.store.get_candidate.return_value = None
    out = interview_activities.send_book_interview_email_activity({
        "candidate_id": "C-MISSING",
        "token": "T",
    })
    assert out == {"sent": False, "reason": "unknown_candidate"}
    fake_app_state.email_sender.send.assert_not_called()


def test_send_rejection_email_interview_gate(fake_app_state):
    out = interview_activities.send_rejection_email_activity({
        "candidate_id": "C-1",
        "gate": "interview",
        "role_title": "Senior Data Engineer",
    })
    sent = fake_app_state.email_sender.send.call_args.kwargs
    assert "Senior Data Engineer" in sent["html_body"]
    assert "interview" in sent["html_body"].lower()
    assert out["sent"] is True


def test_send_rejection_email_offer_gate(fake_app_state):
    interview_activities.send_rejection_email_activity({
        "candidate_id": "C-1",
        "gate": "offer",
        "role_title": "Senior Data Engineer",
    })
    sent = fake_app_state.email_sender.send.call_args.kwargs
    # Offer-gate copy specifically mentions interview-stage feedback
    assert "after the interview" in sent["html_body"].lower() or "interview stage" in sent["html_body"].lower()


def test_recommender_activity_runs_executor(fake_app_state, monkeypatch):
    """Activity is a thin asyncio.run wrapper around the executor — verify it
    forwards payload + returns the executor's dict."""
    async def fake_execute(payload):
        return {"interview_recommender": {"decision": "advance"}}

    import api.functions.graphs.executors.agents.agent_interview_recommender as agent
    monkeypatch.setattr(agent, "execute", fake_execute)

    out = interview_activities.hiring_interview_recommender_activity({
        "workflow_id": "WF", "gate": "post_voice",
    })
    assert out == {"interview_recommender": {"decision": "advance"}}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/api/functions/workflows/test_interview_activities.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the activities module**

```python
# api/functions/workflows/interview_activities.py
"""Phase 7 (Interview) sub-wait activities — runs alongside the existing
voice_screen_activities. Keeping these in their own module so the unit
tests don't pull in the agent-framework graph machinery.

Four activities, all imported and re-exported by activities.py:

  - hiring_interview_recommender_activity — runs the recommender agent at
    gates `post_voice` and `post_interview`.
  - issue_book_interview_link_activity   — mints book_interview scope token.
  - send_book_interview_email_activity   — emails candidate the /book URL.
  - send_rejection_email_activity        — auto-rejection at either reject gate.
"""
from __future__ import annotations
import asyncio
import os

from api.server.services.email_send import EmailSendError


def _portal_base() -> str:
    return os.getenv("PORTAL_BASE_URL", "http://localhost:5274").rstrip("/")


def hiring_interview_recommender_activity(payload: dict) -> dict:
    """Run the interview-recommender executor inside the Functions worker.

    Mirrors hiring_*_activity wrappers — synchronous entry-point that
    `asyncio.run`s the async agent call. Returns whatever the executor
    returned so the orchestrator can stash it on `enriched`.
    """
    from api.functions.graphs.executors.agents import agent_interview_recommender
    return asyncio.run(agent_interview_recommender.execute(payload))


def issue_book_interview_link_activity(payload: dict) -> dict:
    """Mint a `book_interview` scope token for the candidate (single-use, 7d).

    Called from the orchestrator after the recruiter clicks Invite at gate 1.
    Returns {token, candidate_id, portal_url} so the sibling email activity
    can compose the body without another store lookup.
    """
    from api.server.state import app_state
    candidate_id = payload["candidate_id"]
    ttl_seconds = int(payload.get("ttl_seconds") or 7 * 24 * 3600)
    token = app_state.magic_links.issue(
        candidate_id=candidate_id,
        scope="book_interview",
        ttl_seconds=ttl_seconds,
        single_use=True,
    )
    return {
        "token": token,
        "candidate_id": candidate_id,
        "portal_url": f"{_portal_base()}/book?token={token}",
    }


def send_book_interview_email_activity(payload: dict) -> dict:
    """Email the candidate the /book?token=… interview-booking link.

    Best-effort — a send failure must not abort the orchestration since
    the recruiter can copy/paste the link from the recruiter view.
    """
    from api.server.state import app_state
    candidate_id = payload["candidate_id"]
    token = payload["token"]
    role_title = payload.get("role_title") or "the role"
    portal_url = payload.get("portal_url") or f"{_portal_base()}/book?token={token}"
    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        return {"sent": False, "reason": "unknown_candidate"}
    name = candidate.get("name") or "there"
    subject = f"Schedule your {role_title} interview"
    html = (
        f"<p>Hi {name},</p>"
        f"<p>Great news — we'd like to invite you to a full interview for "
        f"the <strong>{role_title}</strong> role.</p>"
        f"<p><a href=\"{portal_url}\">Pick a time that works for you</a> "
        f"— the link works once and expires after 7 days.</p>"
        f"<p>Thanks,<br/>Zava Talent</p>"
    )
    try:
        msg_id = app_state.email_sender.send(
            to=candidate.get("email") or "unknown@example.com",
            subject=subject,
            html_body=html,
        )
    except EmailSendError as exc:  # pragma: no cover
        return {"sent": False, "reason": str(exc)}
    return {"sent": True, "message_id": msg_id, "portal_url": portal_url}


def send_rejection_email_activity(payload: dict) -> dict:
    """Polite auto-rejection email used at both recruiter reject gates.

    `gate` ∈ {"interview", "offer"} only differs in one sentence of body
    copy. We never include the recruiter's free-text reason in the email
    — keeps us out of trouble re: feedback the candidate could quote.
    """
    from api.server.state import app_state
    candidate_id = payload["candidate_id"]
    gate = (payload.get("gate") or "interview").lower()
    role_title = payload.get("role_title") or "the role"
    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        return {"sent": False, "reason": "unknown_candidate"}
    name = candidate.get("name") or "there"
    if gate == "offer":
        bridge = (
            f"After the interview stage we've decided not to move forward "
            f"with the <strong>{role_title}</strong> role at this time."
        )
    else:
        bridge = (
            f"After reviewing your screening for the "
            f"<strong>{role_title}</strong> role, we've decided not to "
            f"move forward at this stage."
        )
    subject = f"Update on your {role_title} application"
    html = (
        f"<p>Hi {name},</p>"
        f"<p>Thanks for taking the time to interview with us. {bridge}</p>"
        f"<p>We'll keep your details on file and be in touch if a better "
        f"fit opens up.</p>"
        f"<p>Best,<br/>Zava Talent</p>"
    )
    try:
        msg_id = app_state.email_sender.send(
            to=candidate.get("email") or "unknown@example.com",
            subject=subject,
            html_body=html,
        )
    except EmailSendError as exc:  # pragma: no cover
        return {"sent": False, "reason": str(exc)}
    return {"sent": True, "message_id": msg_id, "gate": gate}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/api/functions/workflows/test_interview_activities.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Re-export from activities.py + register in function_app.py**

In `api/functions/workflows/activities.py`, add to the existing imports near the top:

```python
from api.functions.workflows.interview_activities import (
    hiring_interview_recommender_activity,
    issue_book_interview_link_activity,
    send_book_interview_email_activity,
    send_rejection_email_activity,
)

__all__ = [
    # ... existing entries ...
    "hiring_interview_recommender_activity",
    "issue_book_interview_link_activity",
    "send_book_interview_email_activity",
    "send_rejection_email_activity",
]
```

(If `__all__` isn't currently defined in activities.py, just add the imports — `function_app.py` imports by name.)

In `function_app.py`, extend the existing import block from `api.functions.workflows.activities` and add four `@app.activity_trigger` registrations near the existing hiring activities (e.g. after `send_screen_email_activity_trigger`):

```python
from api.functions.workflows.activities import (
    # ...existing entries...
    hiring_interview_recommender_activity,
    issue_book_interview_link_activity,
    send_book_interview_email_activity,
    send_rejection_email_activity,
)

# ...later in the file, alongside the other activity_triggers...

@app.activity_trigger(input_name="payload")
def hiring_interview_recommender_activity_trigger(payload: dict) -> dict:
    return hiring_interview_recommender_activity(payload)


@app.activity_trigger(input_name="payload")
def issue_book_interview_link_activity_trigger(payload: dict) -> dict:
    return issue_book_interview_link_activity(payload)


@app.activity_trigger(input_name="payload")
def send_book_interview_email_activity_trigger(payload: dict) -> dict:
    return send_book_interview_email_activity(payload)


@app.activity_trigger(input_name="payload")
def send_rejection_email_activity_trigger(payload: dict) -> dict:
    return send_rejection_email_activity(payload)
```

- [ ] **Step 6: Sanity-check imports**

```bash
python -c "from function_app import app; print('ok')"
```
Expected: `ok` (no ImportError).

- [ ] **Step 7: Commit**

```bash
git add api/functions/workflows/interview_activities.py api/functions/workflows/activities.py function_app.py tests/api/functions/workflows/test_interview_activities.py
git commit -m "feat(hiring): interview-phase activities (recommender, booking link, emails)"
```

---

## Task 5: Orchestrator — replace stub Phase 7 with three sub-waits

**Files:**
- Modify: `api/functions/workflows/hiring.py`

(There's no unit test for the orchestrator itself — Durable Functions orchestrators aren't easily testable in isolation. We'll cover the new flow via integration in Task 9 and end-to-end smoke at the end.)

- [ ] **Step 1: Add timeout constants**

In `api/shared/constants.py`, add (place near `VOICE_SCREEN_TIMEOUT`):

```python
from datetime import timedelta

# Phase 7 (Interview) sub-wait timeouts.
INTERVIEW_INVITE_TIMEOUT  = timedelta(days=3)   # recruiter to invite/reject
INTERVIEW_BOOKING_TIMEOUT = timedelta(days=7)   # candidate to pick a slot
INTERVIEW_DECISION_TIMEOUT = timedelta(days=5)  # recruiter to record post-int decision
```

(Look for existing `VOICE_SCREEN_TIMEOUT` to confirm `timedelta` is already imported; if not, add it.)

- [ ] **Step 2: Find the Phase 7 block in hiring.py**

```bash
grep -n "Phase 7" api/functions/workflows/hiring.py
```
Expected: a single line `# Phase 7: Interview` near line 189.

- [ ] **Step 3: Replace the Phase 7 block**

Locate the section reading:

```python
    # Phase 7: Interview
    interview_result = yield context.call_activity("hiring_interview_activity_trigger", enriched)
    enriched = {**enriched, "interview": interview_result}
```

Replace it with the three-wait sequence below. Keep `enriched["interview"] = ...` populated with whatever advances out of gate 3 so downstream phases see consistent data.

```python
    # Phase 7: Interview — three sequential HITL waits under current_phase=Interview
    # 1) recruiter decides invite-vs-reject (gate "post_voice")
    # 2) candidate books a slot (gate "candidate_booking")
    # 3) recruiter records post-interview decision (gate "post_interview")
    # Each wait races against a timer; timeouts close the workflow as completed(timeout).
    from api.shared.constants import (
        INTERVIEW_INVITE_TIMEOUT,
        INTERVIEW_BOOKING_TIMEOUT,
        INTERVIEW_DECISION_TIMEOUT,
    )

    # Pre-wait: run the recommender so the recruiter sees an AI rec.
    rec_input_gate1 = {
        **enriched,
        "gate": "post_voice",
        "cv_crystalliser": (enriched.get("triage") or {}).get("cv_crystalliser") or {},
        "screening": enriched.get("screening") or {},
        "voice_transcript": (voice_payload or {}).get("transcript") or [],
        "voice_score": (voice_payload or {}).get("score"),
    }
    yield context.call_activity(
        "hiring_interview_recommender_activity_trigger", rec_input_gate1,
    )

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {"reason": "awaiting_interview_invite", "phase": "Interview",
                    "wait_kind": "operator_review"},
    })

    invite_event = context.wait_for_external_event("interview_invite")
    timeout_event = context.create_timer(
        context.current_utc_datetime + INTERVIEW_INVITE_TIMEOUT,
    )
    winner = yield context.task_any([invite_event, timeout_event])
    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "Interview",
                        "gate": "interview_invite"},
        })
        return {"status": "timeout", "phase": "Interview"}
    timeout_event.cancel()

    invite_payload = invite_event.result if hasattr(invite_event, "result") else {}
    invite_decision = (invite_payload.get("decision") or "").lower() if isinstance(invite_payload, dict) else ""

    if invite_decision != "invite":
        # Recruiter rejected at gate 1 — auto-reject email + close workflow.
        yield context.call_activity("send_rejection_email_activity_trigger", {
            "candidate_id": candidate_id,
            "gate": "interview",
            "role_title": (enriched.get("metadata") or {}).get("role_title"),
        })
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "by": invite_payload.get("resolved_by") if isinstance(invite_payload, dict) else None,
                "reason": invite_payload.get("reason") if isinstance(invite_payload, dict) else "recruiter rejected at interview-invite",
                "phase": "Interview",
                "gate": "interview_invite",
            },
        })
        return {"status": "rejected", "phase": "Interview", "gate": "interview_invite"}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "Interview", "gate": "interview_invite",
                    "decision": "invite"},
    })

    # Gate 2: candidate books a slot.
    book_link = yield context.call_activity(
        "issue_book_interview_link_activity_trigger",
        {"candidate_id": candidate_id},
    )
    yield context.call_activity(
        "send_book_interview_email_activity_trigger",
        {
            "candidate_id": candidate_id,
            "token": book_link.get("token"),
            "portal_url": book_link.get("portal_url"),
            "role_title": (enriched.get("metadata") or {}).get("role_title"),
        },
    )

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {"reason": "awaiting_interview_booking", "phase": "Interview",
                    "wait_kind": "external_party"},
    })

    booked_event = context.wait_for_external_event("interview_booked")
    timeout_event = context.create_timer(
        context.current_utc_datetime + INTERVIEW_BOOKING_TIMEOUT,
    )
    winner = yield context.task_any([booked_event, timeout_event])
    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "Interview",
                        "gate": "interview_booking"},
        })
        return {"status": "timeout", "phase": "Interview"}
    timeout_event.cancel()

    booked_payload = booked_event.result if hasattr(booked_event, "result") else {}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "Interview", "gate": "interview_booking",
                    "slot": booked_payload.get("slot")
                    if isinstance(booked_payload, dict) else None},
    })

    # Gate 3: pre-decision recommender, then recruiter records.
    rec_input_gate3 = {
        **rec_input_gate1,
        "gate": "post_interview",
    }
    yield context.call_activity(
        "hiring_interview_recommender_activity_trigger", rec_input_gate3,
    )

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {"reason": "awaiting_interview_complete", "phase": "Interview",
                    "wait_kind": "operator_review"},
    })

    decision_event = context.wait_for_external_event("offer_decision")
    timeout_event = context.create_timer(
        context.current_utc_datetime + INTERVIEW_DECISION_TIMEOUT,
    )
    winner = yield context.task_any([decision_event, timeout_event])
    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "Interview",
                        "gate": "interview_decision"},
        })
        return {"status": "timeout", "phase": "Interview"}
    timeout_event.cancel()

    post_payload = decision_event.result if hasattr(decision_event, "result") else {}
    post_decision = (post_payload.get("decision") or "").lower() if isinstance(post_payload, dict) else ""

    if post_decision != "offer":
        # Recruiter rejected at gate 3 — auto-reject email + close workflow.
        yield context.call_activity("send_rejection_email_activity_trigger", {
            "candidate_id": candidate_id,
            "gate": "offer",
            "role_title": (enriched.get("metadata") or {}).get("role_title"),
        })
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "by": post_payload.get("resolved_by") if isinstance(post_payload, dict) else None,
                "reason": "recruiter declined post-interview",
                "phase": "Interview",
                "gate": "interview_decision",
                "notes": post_payload.get("notes") if isinstance(post_payload, dict) else None,
                "rating": post_payload.get("rating") if isinstance(post_payload, dict) else None,
            },
        })
        return {"status": "rejected", "phase": "Interview", "gate": "interview_decision"}

    interview_result = {
        "decision": "offer",
        "level": post_payload.get("level") if isinstance(post_payload, dict) else None,
        "rating": post_payload.get("rating") if isinstance(post_payload, dict) else None,
        "notes": post_payload.get("notes") if isinstance(post_payload, dict) else None,
        "slot": booked_payload.get("slot") if isinstance(booked_payload, dict) else None,
    }
    enriched = {**enriched, "interview": interview_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "Interview", "gate": "interview_decision",
                    "decision": "offer", "level": interview_result["level"]},
    })
```

- [ ] **Step 4: Verify orchestrator imports cleanly**

```bash
python -c "from api.functions.workflows.hiring import hiring_orchestration; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add api/functions/workflows/hiring.py api/shared/constants.py
git commit -m "feat(hiring): replace stub Phase 7 with three-wait HITL sequence"
```

---

## Task 6: Candidate-portal booking backend (`portal_interview.py`)

**Files:**
- Create: `api/server/routes/portal_interview.py`
- Modify: `api/server/main.py` (register router)
- Test: `tests/api/server/routes/test_portal_interview.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/routes/test_portal_interview.py
"""Candidate-side booking endpoints. Use the existing FastAPI TestClient
fixture pattern from test_portal.py."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    """Each test starts with a fresh in-memory store + a fresh sqlite db."""
    db_path = tmp_path / "ml.sqlite"
    from api.server.services.magic_link import MagicLinkStore
    monkeypatch.setattr(app_state, "magic_links", MagicLinkStore(db_path))
    app_state.store._candidates.clear()  # type: ignore[attr-defined]
    app_state.store._workflows.clear()   # type: ignore[attr-defined]
    yield


def _seed_candidate_with_token(scope: str = "book_interview"):
    cand_id = "C-TEST"
    app_state.store._candidates[cand_id] = {  # type: ignore[attr-defined]
        "id": cand_id, "name": "Alex", "email": "a@e.com",
        "role_id": "REQ-X", "instance_id": "DF-INSTANCE-1",
        "metadata_role_title": "Senior Data Engineer",
    }
    token = app_state.magic_links.issue(
        candidate_id=cand_id, scope=scope, ttl_seconds=3600, single_use=True,
    )
    return cand_id, token


def test_resolve_returns_candidate_role_and_slot_grid():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    resp = client.get(f"/api/portal/interview/resolve?token={token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_id"] == cand_id
    assert "role_title" in body
    # 5 weekdays × 3 slots = 15 entries
    slots = body["slots"]
    assert len(slots) == 15
    assert all("slot_id" in s and "starts_at" in s and "available" in s for s in slots)
    # Deterministic mask: same candidate, same response (modulo time).
    resp2 = client.get(f"/api/portal/interview/resolve?token={token}")
    assert resp.json()["slots"] == resp2.json()["slots"]


def test_resolve_404_on_unknown_token():
    client = TestClient(app)
    resp = client.get("/api/portal/interview/resolve?token=NOT-REAL")
    assert resp.status_code == 404


def test_resolve_404_on_wrong_scope():
    """A status-scope token must not resolve here."""
    _, token = _seed_candidate_with_token(scope="status")
    client = TestClient(app)
    resp = client.get(f"/api/portal/interview/resolve?token={token}")
    assert resp.status_code == 404


def test_book_consumes_token_and_raises_event():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_interview.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/interview/book",
            json={"token": token, "slot_id": "mon-09:00"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_raise.assert_awaited_once()
    args = mock_raise.await_args.args
    assert args[0] == "DF-INSTANCE-1"
    assert args[1] == "interview_booked"
    assert args[2]["candidate_id"] == cand_id
    assert args[2]["slot"]["slot_id"] == "mon-09:00"


def test_book_double_consume_returns_409():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_interview.raise_orchestration_event",
        new=AsyncMock(),
    ):
        client.post("/api/portal/interview/book",
                    json={"token": token, "slot_id": "mon-09:00"})
        resp = client.post("/api/portal/interview/book",
                           json={"token": token, "slot_id": "tue-13:00"})
    assert resp.status_code == 409


def test_book_unknown_slot_id_400():
    cand_id, token = _seed_candidate_with_token()
    client = TestClient(app)
    resp = client.post("/api/portal/interview/book",
                       json={"token": token, "slot_id": "sat-11:00"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/api/server/routes/test_portal_interview.py -v
```
Expected: FAIL — route not mounted (`404` on every endpoint, or `ImportError`).

- [ ] **Step 3: Implement the route module**

```python
# api/server/routes/portal_interview.py
"""Candidate-side interview-booking routes.

Two endpoints, both gated by a `book_interview`-scope magic-link token:

  GET  /api/portal/interview/resolve?token=…
       Peeks the token, returns candidate id + role title + the deterministic
       5×3 slot grid. Drives the /book?token=… page in the candidate portal.

  POST /api/portal/interview/book
       Consumes the token, persists the chosen slot on the candidate dict,
       raises `interview_booked` on the underlying Durable instance so the
       orchestrator resumes from awaiting_interview_booking.
"""
from __future__ import annotations
import hashlib
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.magic_link import (
    MagicLinkAlreadyConsumed,
    MagicLinkExpired,
)
from api.server.state import app_state

router = APIRouter(prefix="/api/portal/interview", tags=["portal", "interview"])

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri"]
_TIME_KEYS = ["09:00", "13:00", "16:00"]


def _slot_grid_for(candidate_id: str) -> list[dict]:
    """Build a deterministic 5×3 mock calendar starting next Monday.

    `available` is True for ~80% of slots, deterministic per-candidate so the
    same candidate sees the same pattern across page refreshes. Past dates
    (rare — only matters if the request lands on Monday before midnight) are
    always unavailable.
    """
    today = date.today()
    # Monday of next week — keeps the demo calendar always-future.
    days_until_monday = (7 - today.weekday()) % 7 or 7
    start = today + timedelta(days=days_until_monday)
    out: list[dict] = []
    for d_idx, day_key in enumerate(_DAY_KEYS):
        the_date = start + timedelta(days=d_idx)
        for t in _TIME_KEYS:
            slot_id = f"{day_key}-{t}"
            digest = hashlib.sha256(f"{candidate_id}:{slot_id}".encode()).hexdigest()
            available = int(digest, 16) % 5 != 0  # ~80% true
            starts_at = datetime.combine(
                the_date, datetime.strptime(t, "%H:%M").time(),
            ).isoformat()
            out.append({
                "slot_id": slot_id,
                "label": f"{the_date.strftime('%a %d %b')} · {t}",
                "starts_at": starts_at,
                "available": available,
            })
    return out


@router.get("/resolve")
async def resolve(token: str):
    """Peek the booking token — does not consume."""
    try:
        payload = app_state.magic_links.peek(token, scope="book_interview")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        # Wrong scope — surface as 404 so we don't leak token existence.
        raise HTTPException(404, "invalid token")
    if payload is None:
        raise HTTPException(404, "invalid token")
    cand = app_state.store.get_candidate(payload["candidate_id"])
    if cand is None:
        raise HTTPException(404, "candidate not found")
    workflow = app_state.store.get_workflow(cand.get("workflow_id", ""))
    role_title = (workflow.metadata if workflow else {}).get("role_title") if workflow else None
    return {
        "candidate_id": cand["id"],
        "role_title": role_title or cand.get("metadata_role_title") or "the role",
        "slots": _slot_grid_for(cand["id"]),
    }


class BookRequest(BaseModel):
    token: str
    slot_id: str


@router.post("/book")
async def book(body: BookRequest):
    """Consume token + raise interview_booked on the Durable instance."""
    grid_ids = {f"{d}-{t}" for d in _DAY_KEYS for t in _TIME_KEYS}
    if body.slot_id not in grid_ids:
        raise HTTPException(400, "unknown slot_id")
    try:
        payload = app_state.magic_links.consume(body.token, scope="book_interview")
    except MagicLinkAlreadyConsumed:
        raise HTTPException(409, "already booked")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        raise HTTPException(404, "invalid token")
    cand = app_state.store.get_candidate(payload["candidate_id"])
    if cand is None:
        raise HTTPException(404, "candidate not found")
    instance_id = cand.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    # Resolve the chosen slot's full record from the deterministic grid so we
    # have starts_at / label (the form only sends slot_id).
    full_slot = next(
        (s for s in _slot_grid_for(cand["id"]) if s["slot_id"] == body.slot_id),
        {"slot_id": body.slot_id},
    )
    cand["interview_slot"] = full_slot
    app_state.store.upsert_candidate(cand)

    await raise_orchestration_event(instance_id, "interview_booked", {
        "candidate_id": cand["id"],
        "slot": full_slot,
    })
    return {"ok": True}
```

- [ ] **Step 4: Mount the router in main.py**

In `api/server/main.py`, find the existing `app.include_router(...)` lines for portal routers and add:

```python
from api.server.routes import portal_interview as _portal_interview
app.include_router(_portal_interview.router)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/api/server/routes/test_portal_interview.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/portal_interview.py api/server/main.py tests/api/server/routes/test_portal_interview.py
git commit -m "feat(portal): /api/portal/interview/{resolve,book} for candidate-side booking"
```

---

## Task 7: Recruiter-side decision routes (`portal_admin_decisions.py`)

**Files:**
- Create: `api/server/routes/portal_admin_decisions.py`
- Modify: `api/server/main.py` (register router)
- Test: `tests/api/server/routes/test_portal_admin_decisions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/routes/test_portal_admin_decisions.py
"""Recruiter-side decision endpoints — the two HITL gates' resume points."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.server.main import app
from api.server.state import app_state


@pytest.fixture(autouse=True)
def reset_state():
    app_state.store._candidates.clear()  # type: ignore[attr-defined]
    yield


def _seed():
    app_state.store._candidates["C-1"] = {  # type: ignore[attr-defined]
        "id": "C-1", "instance_id": "DF-1",
    }


def test_interview_invite_invite_decision_raises_event():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/admin/candidate/C-1/interview-invite",
            json={"decision": "invite", "resolved_by": "recruiter@zava"},
        )
    assert resp.status_code == 200
    args = mock_raise.await_args.args
    assert args[0] == "DF-1"
    assert args[1] == "interview_invite"
    assert args[2]["decision"] == "invite"
    assert args[2]["resolved_by"] == "recruiter@zava"


def test_interview_invite_reject_decision_raises_event():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/admin/candidate/C-1/interview-invite",
            json={"decision": "reject", "reason": "below bar"},
        )
    assert resp.status_code == 200
    assert mock_raise.await_args.args[2]["decision"] == "reject"
    assert mock_raise.await_args.args[2]["reason"] == "below bar"


def test_interview_invite_400_on_invalid_decision():
    _seed()
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-1/interview-invite",
        json={"decision": "maybe"},
    )
    assert resp.status_code == 400


def test_interview_invite_404_on_unknown_candidate():
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-NOPE/interview-invite",
        json={"decision": "invite"},
    )
    assert resp.status_code == 404


def test_post_interview_offer_requires_level():
    _seed()
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-1/post-interview-decision",
        json={"decision": "offer", "notes": "great", "rating": 4},
    )
    assert resp.status_code == 400
    assert "level" in resp.json()["detail"].lower()


def test_post_interview_offer_with_level_raises_event():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ) as mock_raise:
        resp = client.post(
            "/api/portal/admin/candidate/C-1/post-interview-decision",
            json={
                "decision": "offer", "level": "Senior",
                "notes": "strong on Spark", "rating": 5,
                "resolved_by": "recruiter@zava",
            },
        )
    assert resp.status_code == 200
    args = mock_raise.await_args.args
    assert args[1] == "offer_decision"
    assert args[2]["decision"] == "offer"
    assert args[2]["level"] == "Senior"
    assert args[2]["rating"] == 5
    assert args[2]["notes"] == "strong on Spark"


def test_post_interview_reject_no_level_required():
    _seed()
    client = TestClient(app)
    with patch(
        "api.server.routes.portal_admin_decisions.raise_orchestration_event",
        new=AsyncMock(),
    ):
        resp = client.post(
            "/api/portal/admin/candidate/C-1/post-interview-decision",
            json={"decision": "reject", "notes": "weak", "rating": 2},
        )
    assert resp.status_code == 200


def test_post_interview_400_on_invalid_rating():
    _seed()
    client = TestClient(app)
    resp = client.post(
        "/api/portal/admin/candidate/C-1/post-interview-decision",
        json={"decision": "reject", "notes": "x", "rating": 9},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/api/server/routes/test_portal_admin_decisions.py -v
```
Expected: FAIL — routes not mounted.

- [ ] **Step 3: Implement the route module**

```python
# api/server/routes/portal_admin_decisions.py
"""Recruiter-side decision endpoints for the two operator-review HITL gates
in Phase 7 (Interview).

  POST /api/portal/admin/candidate/{candidate_id}/interview-invite
       Resumes the orchestrator's `awaiting_interview_invite` wait by
       raising `interview_invite` with body {decision: invite|reject, ...}.

  POST /api/portal/admin/candidate/{candidate_id}/post-interview-decision
       Resumes `awaiting_interview_complete` by raising `offer_decision`
       with the recruiter's notes + rating + level + decision.

Both endpoints are mounted off /api/portal/admin to mirror the existing
admin-only candidate endpoints. No auth at this layer — the recruiter
view is a private surface in the demo. Engagement-POC hardens this with
real auth.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.server.services.durable_client import raise_orchestration_event
from api.server.state import app_state

router = APIRouter(prefix="/api/portal/admin", tags=["portal", "admin"])


class InterviewInviteRequest(BaseModel):
    decision: str  # "invite" | "reject"
    reason: str | None = None
    resolved_by: str | None = None


@router.post("/candidate/{candidate_id}/interview-invite")
async def interview_invite(candidate_id: str, body: InterviewInviteRequest):
    decision = body.decision.lower()
    if decision not in {"invite", "reject"}:
        raise HTTPException(400, "decision must be invite|reject")
    cand = app_state.store.get_candidate(candidate_id)
    if cand is None:
        raise HTTPException(404, "candidate not found")
    instance_id = cand.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    payload = {
        "candidate_id": candidate_id,
        "decision": decision,
        "resolved_by": body.resolved_by or "recruiter",
        "reason": body.reason,
    }
    await raise_orchestration_event(instance_id, "interview_invite", payload)
    return {"ok": True, "decision": decision}


class PostInterviewRequest(BaseModel):
    decision: str  # "offer" | "reject"
    notes: str = ""
    rating: int = Field(..., ge=1, le=5)
    level: str | None = None
    resolved_by: str | None = None


@router.post("/candidate/{candidate_id}/post-interview-decision")
async def post_interview_decision(candidate_id: str, body: PostInterviewRequest):
    decision = body.decision.lower()
    if decision not in {"offer", "reject"}:
        raise HTTPException(400, "decision must be offer|reject")
    if decision == "offer" and not body.level:
        raise HTTPException(400, "level is required when decision is offer")
    cand = app_state.store.get_candidate(candidate_id)
    if cand is None:
        raise HTTPException(404, "candidate not found")
    instance_id = cand.get("instance_id")
    if not instance_id:
        raise HTTPException(409, "candidate has no orchestration instance")

    # Stash the recruiter's notes/rating on the candidate record so the
    # recruiter view can show them after submission. The orchestrator also
    # gets them via the event payload below for the action ledger.
    cand["interview_notes"] = body.notes
    cand["interview_rating"] = body.rating
    cand["interview_decision"] = decision
    if body.level:
        cand["interview_level"] = body.level
    app_state.store.upsert_candidate(cand)

    payload = {
        "candidate_id": candidate_id,
        "decision": decision,
        "level": body.level,
        "notes": body.notes,
        "rating": body.rating,
        "resolved_by": body.resolved_by or "recruiter",
    }
    await raise_orchestration_event(instance_id, "offer_decision", payload)
    return {"ok": True, "decision": decision}
```

- [ ] **Step 4: Mount the router in main.py**

In `api/server/main.py`, add alongside the other admin router includes:

```python
from api.server.routes import portal_admin_decisions as _portal_admin_decisions
app.include_router(_portal_admin_decisions.router)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/api/server/routes/test_portal_admin_decisions.py -v
```
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add api/server/routes/portal_admin_decisions.py api/server/main.py tests/api/server/routes/test_portal_admin_decisions.py
git commit -m "feat(portal): admin recruiter-decision endpoints for interview HITL gates"
```

---

## Task 8: Frontend — typed API client extensions + `/book` route

**Files:**
- Modify: `web/portal/src/lib/api.ts`
- Create: `web/portal/src/routes/Book.tsx`
- Modify: `web/portal/src/App.tsx`

(Frontend tests are vitest — but the existing portal test suite has pre-existing breakage we know about. New tests are out of scope here; smoke-test via the running app at the end.)

- [ ] **Step 1: Extend `web/portal/src/lib/api.ts`**

Append to the file:

```typescript
// ────────────────────────────────────────────────────────────────────
// Interview booking + recruiter decisions

export type InterviewSlot = {
  slot_id: string;
  label: string;
  starts_at: string;
  available: boolean;
};

export type BookingResolveResponse = {
  candidate_id: string;
  role_title: string;
  slots: InterviewSlot[];
};

export async function getBookingResolve(token: string): Promise<BookingResolveResponse> {
  const resp = await fetch(
    `/api/portal/interview/resolve?token=${encodeURIComponent(token)}`,
  );
  if (resp.status === 410) throw new Error("expired");
  if (!resp.ok) throw new Error(`booking-resolve failed (${resp.status})`);
  return (await resp.json()) as BookingResolveResponse;
}

export async function postBooking(token: string, slotId: string): Promise<void> {
  const resp = await fetch("/api/portal/interview/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, slot_id: slotId }),
  });
  if (resp.status === 409) throw new Error("already-booked");
  if (resp.status === 410) throw new Error("expired");
  if (!resp.ok) throw new Error(`booking failed (${resp.status})`);
}

export async function postInterviewInvite(
  candidateId: string,
  body: { decision: "invite" | "reject"; reason?: string; resolved_by?: string },
): Promise<void> {
  const resp = await fetch(
    `/api/portal/admin/candidate/${encodeURIComponent(candidateId)}/interview-invite`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) throw new Error(`invite-decision failed (${resp.status})`);
}

export async function postPostInterviewDecision(
  candidateId: string,
  body: {
    decision: "offer" | "reject";
    notes: string;
    rating: number;
    level?: string;
    resolved_by?: string;
  },
): Promise<void> {
  const resp = await fetch(
    `/api/portal/admin/candidate/${encodeURIComponent(candidateId)}/post-interview-decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (resp.status === 400) {
    const detail = (await resp.json()).detail ?? "validation error";
    throw new Error(detail);
  }
  if (!resp.ok) throw new Error(`post-interview-decision failed (${resp.status})`);
}
```

- [ ] **Step 2: Create the Book.tsx route**

```typescript
// web/portal/src/routes/Book.tsx
//
// /book?token=xxx — single-use interview-booking magic-link surface.
//
// 1. Resolve the token via GET /api/portal/interview/resolve to get the
//    candidate's role title + the deterministic 5×3 slot grid.
// 2. Render the grid grouped by day. Available slots are clickable,
//    unavailable ones are visibly disabled.
// 3. On click, POST /api/portal/interview/book with {token, slot_id}.
//    On 200: render a "booked" confirmation panel.
//    On 409 ("already booked"): render an explicit error.
import { useEffect, useState } from "react";
import {
  getBookingResolve,
  postBooking,
  type BookingResolveResponse,
  type InterviewSlot,
} from "../lib/api";

export default function Book() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") ?? "";
  const [data, setData] = useState<BookingResolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [bookedSlot, setBookedSlot] = useState<InterviewSlot | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Missing token in URL.");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const body = await getBookingResolve(token);
        if (!cancelled) setData(body);
      } catch (err) {
        if (cancelled) return;
        const msg = (err as Error).message;
        setError(
          msg === "expired"
            ? "This booking link has expired. Please contact your recruiter for a fresh link."
            : `Could not load booking page (${msg}).`,
        );
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  async function pickSlot(slot: InterviewSlot) {
    if (submitting || !slot.available) return;
    setSubmitting(true);
    try {
      await postBooking(token, slot.slot_id);
      setBookedSlot(slot);
    } catch (err) {
      const msg = (err as Error).message;
      setError(
        msg === "already-booked"
          ? "Looks like you've already booked an interview with this link."
          : msg === "expired"
            ? "This booking link expired before you could use it."
            : `Booking failed (${msg}).`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10">
        <div className="panel">
          <div className="panel-header">
            <span><span className="status-dot status-dot-error"/> Booking unavailable</span>
          </div>
          <div className="panel-body text-sm text-red-700">{error}</div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10 text-sm text-slate-500 flex items-center gap-2">
        <span className="spinner"/> Loading booking page…
      </div>
    );
  }

  if (bookedSlot) {
    return (
      <div className="max-w-2xl mx-auto p-6 sm:p-10">
        <div className="panel-elevated">
          <div className="panel-header">
            <span><span className="status-dot status-dot-active"/> Interview booked</span>
            <span className="chip-success">{bookedSlot.label}</span>
          </div>
          <div className="panel-body text-sm text-slate-700 space-y-2">
            <p>
              Thanks — your <strong>{data.role_title}</strong> interview is booked
              for <strong>{bookedSlot.label}</strong>. We'll email a Teams link
              shortly. You can close this tab.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Group slots by day for rendering.
  const byDay = new Map<string, InterviewSlot[]>();
  for (const s of data.slots) {
    const day = s.label.split(" · ")[0];
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(s);
  }

  return (
    <div className="max-w-3xl mx-auto p-6 sm:p-10 space-y-6">
      <div className="hero">
        <div className="hero-eyebrow">Schedule your interview</div>
        <h1 className="hero-title">Pick a time that works for you</h1>
        <p className="hero-subtitle">
          {data.role_title} · single-use link, one selection per booking.
        </p>
      </div>
      <div className="space-y-4" data-testid="slot-grid">
        {Array.from(byDay.entries()).map(([day, slots]) => (
          <div key={day} className="panel">
            <div className="panel-header"><span>{day}</span></div>
            <div className="panel-body grid grid-cols-3 gap-2">
              {slots.map((s) => (
                <button
                  key={s.slot_id}
                  type="button"
                  disabled={!s.available || submitting}
                  onClick={() => pickSlot(s)}
                  className={
                    s.available
                      ? "btn-secondary"
                      : "btn-secondary opacity-40 cursor-not-allowed"
                  }
                >
                  {s.label.split(" · ")[1]}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Mount `/book` in App.tsx**

Find the existing `<Routes>` block in `web/portal/src/App.tsx` and add:

```tsx
import Book from "./routes/Book";
// ...inside <Routes>:
<Route path="/book" element={<Book />} />
```

- [ ] **Step 4: Visual smoke test**

Open `http://localhost:5274/book?token=NOT-REAL` — should see "Booking unavailable" with the 404 message rendered nicely. Confirm Vite HMR'd the new route (no console errors).

- [ ] **Step 5: Commit**

```bash
git add web/portal/src/lib/api.ts web/portal/src/routes/Book.tsx web/portal/src/App.tsx
git commit -m "feat(portal): /book route + typed clients for interview booking + recruiter decisions"
```

---

## Task 9: Recruiter view — three conditional panels keyed off `awaiting_reason`

**Files:**
- Modify: `web/portal/src/routes/RecruiterCandidate.tsx`

This is a single mechanical task: drop a sub-component file in to keep RecruiterCandidate.tsx readable, then mount the panels conditionally.

- [ ] **Step 1: Add a sub-component file for the panels**

Create `web/portal/src/components/InterviewPanels.tsx`:

```typescript
// web/portal/src/components/InterviewPanels.tsx
//
// Three conditional action panels rendered on the recruiter candidate detail
// page when the workflow is parked at one of the Phase 7 sub-waits. Each
// panel reads the latest `interview_recommender` agent_reasoning entry so
// the recruiter sees the AI rec next to their decision controls.
import { useState } from "react";
import {
  postInterviewInvite,
  postPostInterviewDecision,
  type AgentReasoning,
} from "../lib/api";

type RecPayload = {
  decision?: "advance" | "decline";
  level_suggestion?: string | null;
  rationale?: string;
  talking_points?: string[];
  recommender_status?: "ok" | "failed";
};

function latestRec(agent_reasoning: AgentReasoning[]): RecPayload | null {
  const runs = agent_reasoning.filter((r) => r.agent_label === "interview_recommender");
  if (runs.length === 0) return null;
  const latest = runs[runs.length - 1];
  return (latest.extracted_json as RecPayload) ?? null;
}

function RecCard({ rec }: { rec: RecPayload | null }) {
  if (!rec) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
        AI recommendation pending — agent has not completed yet.
      </div>
    );
  }
  if (rec.recommender_status === "failed") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
        <strong>AI recommendation unavailable</strong>
        <p className="text-xs text-slate-700 mt-1">
          {rec.rationale ?? "See agent_reasoning trace for the failing call."}
        </p>
      </div>
    );
  }
  const isAdvance = rec.decision === "advance";
  return (
    <div className={`rounded-lg border p-3 text-sm ${
      isAdvance ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"
    }`}>
      <div>
        <strong>AI recommends:</strong>{" "}
        <span className="capitalize">{rec.decision}</span>
        {rec.level_suggestion && (
          <span className="text-slate-600"> · suggested level: {rec.level_suggestion}</span>
        )}
      </div>
      {rec.rationale && (
        <p className="text-xs text-slate-700 mt-1">{rec.rationale}</p>
      )}
      {rec.talking_points && rec.talking_points.length > 0 && (
        <ul className="text-xs text-slate-700 mt-2 list-disc list-inside">
          {rec.talking_points.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}
    </div>
  );
}

export function InterviewInvitePanel({
  candidateId, agent_reasoning, onSubmitted,
}: {
  candidateId: string;
  agent_reasoning: AgentReasoning[];
  onSubmitted: () => void;
}) {
  const rec = latestRec(agent_reasoning);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(decision: "invite" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await postInterviewInvite(candidateId, {
        decision,
        reason: reason || undefined,
      });
      onSubmitted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span>Decision · invite to interview?</span>
        <span className="chip-info">awaiting recruiter</span>
      </div>
      <div className="panel-body space-y-3">
        <RecCard rec={rec}/>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Optional reason (logged on the workflow ledger; not sent to candidate)"
          className="w-full text-sm border border-slate-200 rounded p-2"
          rows={2}
        />
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => submit("invite")}
            className="btn-primary flex-1"
          >Invite to interview</button>
          <button
            type="button"
            disabled={busy}
            onClick={() => submit("reject")}
            className="btn-danger flex-1"
          >Reject</button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}

export function AwaitingBookingPanel({
  bookingTokenUrl,
}: {
  bookingTokenUrl: string | null;
}) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span><span className="status-dot status-dot-pending"/> Awaiting candidate to book interview</span>
      </div>
      <div className="panel-body text-sm text-slate-700 space-y-2">
        <p>The candidate has been emailed an interview-booking link (single-use, 7-day expiry).</p>
        {bookingTokenUrl && (
          <p className="text-xs">
            Operator copy/paste fallback:{" "}
            <code className="bg-slate-100 px-1 py-0.5 rounded">{bookingTokenUrl}</code>
          </p>
        )}
      </div>
    </div>
  );
}

export function PostInterviewPanel({
  candidateId, agent_reasoning, levelOptions, onSubmitted,
}: {
  candidateId: string;
  agent_reasoning: AgentReasoning[];
  levelOptions: string[];
  onSubmitted: () => void;
}) {
  const rec = latestRec(agent_reasoning);
  const [decision, setDecision] = useState<"offer" | "reject">("offer");
  const [notes, setNotes] = useState("");
  const [rating, setRating] = useState(3);
  const [level, setLevel] = useState<string>(levelOptions[0] ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await postPostInterviewDecision(candidateId, {
        decision,
        notes,
        rating,
        level: decision === "offer" ? level : undefined,
      });
      onSubmitted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span>Post-interview decision</span>
        <span className="chip-info">awaiting recruiter</span>
      </div>
      <div className="panel-body space-y-3">
        <RecCard rec={rec}/>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Interview notes — what did the candidate show? Any concerns?"
          className="w-full text-sm border border-slate-200 rounded p-2"
          rows={4}
        />
        <div className="flex items-center gap-3 text-sm">
          <label>Overall rating:</label>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setRating(n)}
              className={`w-8 h-8 rounded ${
                rating === n ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700"
              }`}
            >{n}</button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-sm">
          <label>Decision:</label>
          <select
            value={decision}
            onChange={(e) => setDecision(e.target.value as "offer" | "reject")}
            className="border border-slate-200 rounded px-2 py-1"
          >
            <option value="offer">Offer</option>
            <option value="reject">Reject</option>
          </select>
          {decision === "offer" && (
            <>
              <label>Level:</label>
              <select
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="border border-slate-200 rounded px-2 py-1"
              >
                {levelOptions.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </>
          )}
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="btn-primary w-full"
        >Submit decision</button>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the panels into RecruiterCandidate.tsx**

Find the existing imports at the top of `web/portal/src/routes/RecruiterCandidate.tsx` and add:

```tsx
import {
  InterviewInvitePanel,
  AwaitingBookingPanel,
  PostInterviewPanel,
} from "../components/InterviewPanels";
```

Add a small `levelsForRole` lookup right above the `RecruiterCandidate` component definition (mirrors the backend constants — keeping it in-file is fine for the demo):

```tsx
const LEVELS_BY_ROLE_TITLE: Record<string, string[]> = {
  "Senior Data Engineer": ["Mid-Level", "Senior", "Staff", "Principal"],
  "Creative Director": ["Director", "Senior Director", "VP Creative"],
};
const DEFAULT_LEVELS = ["Junior", "Mid", "Senior", "Lead"];

function levelsFor(roleTitle: string | undefined | null): string[] {
  if (!roleTitle) return DEFAULT_LEVELS;
  for (const [k, v] of Object.entries(LEVELS_BY_ROLE_TITLE)) {
    if (roleTitle.toLowerCase().includes(k.toLowerCase())) return v;
  }
  return DEFAULT_LEVELS;
}
```

In the component body, find the existing place where `data.workflow.awaiting_reason` is checked (or render at the top of the panels section) and add the conditional panels block right above the existing "What we learned" panel:

```tsx
{w.awaiting_reason === "awaiting_interview_invite" && (
  <InterviewInvitePanel
    candidateId={c.id}
    agent_reasoning={data.agent_reasoning ?? []}
    onSubmitted={() => void refresh()}
  />
)}

{w.awaiting_reason === "awaiting_interview_booking" && (
  <AwaitingBookingPanel
    bookingTokenUrl={
      (() => {
        const tok = data.active_tokens.find((t) => t.scope === "book_interview");
        return tok ? `${window.location.origin}/book?token=${tok.token}` : null;
      })()
    }
  />
)}

{w.awaiting_reason === "awaiting_interview_complete" && (
  <PostInterviewPanel
    candidateId={c.id}
    agent_reasoning={data.agent_reasoning ?? []}
    levelOptions={levelsFor(
      (w.metadata?.role_title as string | undefined) ?? null,
    )}
    onSubmitted={() => void refresh()}
  />
)}
```

- [ ] **Step 3: Visual smoke test**

Open the running portal app, navigate to a candidate parked at any Phase 7 sub-wait — confirm the panel appears, the AI rec card renders, and submit triggers the workflow advancement (or write a manual record).

- [ ] **Step 4: Commit**

```bash
git add web/portal/src/components/InterviewPanels.tsx web/portal/src/routes/RecruiterCandidate.tsx
git commit -m "feat(portal): three conditional Phase 7 panels in recruiter candidate view"
```

---

## Task 10: End-to-end smoke test (manual)

**Files:** none (uses the running stack)

This is the definitive proof the new flow works. Run all the way through with a real apply.

- [ ] **Step 1: Wipe state + restart Python services**

```bash
cd "c:/dev/ghcp sdk stuff"
# stop any FastAPI (3101) + func host (7071) processes
# wipe demo state per existing pattern
rm -f data/portal/magic_links.sqlite
rm -rf azurite-data && mkdir -p azurite-data
find data/synthetic/hiring/cv-pdfs/ -type f -name "*.pdf" \
  ! -regex ".*C-\(CR\|FR\|ME\|SE\|WE\)-.*\.pdf" -delete
# restart azurite (background)
azurite --silent --location azurite-data \
  --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0 > logs/azurite.log 2>&1 &
# restart fastapi
uv run uvicorn api.server.main:app --port 3101 > logs/fastapi.log 2>&1 &
# restart func host
cmd //c "scripts\\run-func.bat" > logs/func.log 2>&1 &
```

Wait for all five ports (10000, 3101, 7071, 5273, 5274) to respond. Then:

- [ ] **Step 2: Apply a synthetic CV via curl**

```bash
curl -s -X POST http://localhost:3101/api/portal/apply \
  -F "role_id=REQ-SDE-USA-DEMO" \
  -F "name=Test E2E" \
  -F "email=test@example.com" \
  -F "cv=@data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf;type=application/pdf"
```

Expected: `{"status":"submitted","candidate_id":"C-XXXXXXXX","workflow_id":"HIRE-DEMO-01"}`. Note the candidate_id.

- [ ] **Step 3: Wait for workflow to reach `awaiting_interview_invite`**

```bash
# poll every 5s until awaiting_reason flips
until curl -s "http://localhost:3101/api/portal/admin/candidate/<CID>" \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d['workflow'].get('awaiting_reason'))" \
  | grep -q awaiting_interview_invite; do sleep 5; done
echo "at gate 1"
```

Expected: `at gate 1` within ~2-3 minutes (depends on cv-crystalliser + screening + voice resume).

Note: voice phase needs the candidate to complete the screen call — for this smoke run, use the canned transcript path:
```bash
# get the screen token from the active links
SCREEN_TOK=$(curl -s http://localhost:3101/api/portal/admin/links \
  | python -c "import sys,json; print([l['token'] for l in json.load(sys.stdin)['links'] if l['scope']=='screen'][0])")
# fire the canned transcript (requires VOICE_TRANSPORT=canned in env)
curl -s -X POST "http://localhost:3101/api/portal/voice/<CID>/canned?token=$SCREEN_TOK"
```

- [ ] **Step 4: Open recruiter view + click Invite**

Open `http://localhost:5274/recruiter`, click into the candidate, confirm the **Decision · invite to interview?** panel shows up with an AI rec card. Click **Invite to interview**.

Expected: panel disappears on next refresh; awaiting_reason flips to `awaiting_interview_booking`; the recruiter view shows the **Awaiting candidate to book interview** panel with an operator-fallback URL.

- [ ] **Step 5: Book a slot as the candidate**

Copy the `book_interview` token from the recruiter view's active-tokens or admin/links endpoint. Open `http://localhost:5274/book?token=<TOKEN>` in a new tab. Pick any available slot.

Expected: confirmation panel renders ("Interview booked").

- [ ] **Step 6: Recruiter records post-interview decision**

Back on the recruiter view, refresh. The **Post-interview decision** panel should now be visible with a *new* AI rec card (gate 2 recommender ran).

Fill: rating=4, decision=Offer, level=Senior, notes="ok in interview". Submit.

Expected: panel disappears, workflow proceeds to Compliance → Phase 9 Offer (candidate accept/decline) → all the way to Onboarding.

- [ ] **Step 7: Run the reject paths once each**

Repeat from step 2 with two more candidates:
- Candidate B: at gate 1, click **Reject**. Expected: workflow status=rejected, rejection email lands in `data/portal/email_outbox/`.
- Candidate C: progress to gate 3, decision=Reject. Expected: same — workflow rejected, rejection email written.

- [ ] **Step 8: Run the full unit + integration suite for the changed surface**

```bash
python -m pytest \
  tests/api/shared/test_role_levels.py \
  tests/api/functions/agents/test_agent_interview_recommender.py \
  tests/api/functions/workflows/test_interview_activities.py \
  tests/api/server/routes/test_portal_interview.py \
  tests/api/server/routes/test_portal_admin_decisions.py \
  -v
```
Expected: all pass.

- [ ] **Step 9: Commit anything that surfaced during smoke testing**

If you fixed something during the smoke run, commit it now with a descriptive message. If nothing needed fixing, skip this step.

- [ ] **Step 10: Push**

```bash
git push origin main
```

---

## Self-review

**Spec coverage check** (against `2026-05-01-recruiter-hitl-design.md`):

- ✅ Phase flow with three sub-waits → Task 5
- ✅ Three new Durable events → Task 5 (orchestrator) + Task 6 (interview_booked) + Task 7 (interview_invite, offer_decision)
- ✅ `book_interview` magic-link scope → Task 4 (issue activity) + Task 6 (consume in /book)
- ✅ `interview-recommender` skill + agent → Task 2 + Task 3
- ✅ 4 new activities → Task 4
- ✅ 2 new candidate-portal routes (`/resolve`, `/book`) → Task 6
- ✅ 2 new admin routes (`/interview-invite`, `/post-interview-decision`) → Task 7
- ✅ 1 new portal frontend route (`/book`) → Task 8
- ✅ 3 new conditional recruiter panels → Task 9
- ✅ Auto-rejection email on both reject paths → Task 4 (template) + Task 5 (called from orchestrator)
- ✅ Levels by role family → Task 1
- ✅ Slot grid 5×3 deterministic per candidate → Task 6 (`_slot_grid_for`)
- ✅ Timeouts (7d booking, 5d post-interview, 3d invite) → Task 5 constants
- ✅ Error handling: parse error fallback → Task 3, expired/double-consume → Task 6, validation → Task 7
- ✅ Integration test for the full happy path → Task 10 step 6

**Type consistency:**
- Event names: `interview_invite`, `interview_booked`, `offer_decision` — used identically in Task 5 (orchestrator), Task 6 (`interview_booked`), Task 7 (`interview_invite`, `offer_decision`) ✓
- Magic link scope: `book_interview` — Task 4 (issue), Task 6 (peek + consume), Task 9 (active-token filter) ✓
- Awaiting reasons: `awaiting_interview_invite`, `awaiting_interview_booking`, `awaiting_interview_complete` — Task 5 (orchestrator) and Task 9 (panel switch) ✓
- Agent label: `interview_recommender` (snake_case) — Task 3 (skill_label kwarg) and Task 9 (`r.agent_label === "interview_recommender"` filter) ✓

**Placeholder scan:** none — all code blocks are complete.

**Scope check:** single-feature, single subsystem (hiring orchestration + portal). Right size for one plan.

