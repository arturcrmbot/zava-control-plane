"""Generator-driven test of Phase 6 voice screen suspend/resume.

Mirrors the pattern in `test_expense_claim_orchestration.py`: hand-rolled
DurableOrchestrationContext stub drives the hiring orchestration step by
step. Goal: prove that when a candidate_id is bound to the workflow input,
the orchestration

  1. issues a screen-scope magic link via `issue_screen_link_activity_trigger`
  2. emails the candidate the call URL via `send_screen_email_activity_trigger`
  3. suspends on `wait_for_external_event("voice_complete")` raced
     against `create_timer(...)` for VOICE_SCREEN_TIMEOUT
  4. on timer-win, completes with status=timeout, phase=Voice
  5. on event-win, runs the existing voice activity with the score in
     scope and continues to Phase 7
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable

from api.functions.workflows.hiring import hiring_orchestration


class _StubTimerEvent:
    def __init__(self, fire_at):
        self.fire_at = fire_at
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _StubExternalEvent:
    def __init__(self, name, result=None):
        self.name = name
        self.result = result


class _StubContext:
    """DurableOrchestrationContext stub for the 10-phase hiring flow."""

    def __init__(
        self,
        *,
        candidate_id: str | None = None,
        screening_verdict: str = "borderline",
        budget_decision: dict | None = None,
        offer_decision: dict | None = None,
        voice_event: dict | None = None,
        voice_times_out: bool = False,
        invite_decision: dict | None = None,
        booked_decision: dict | None = None,
        post_decision: dict | None = None,
    ):
        self.instance_id = "instance-hire-1"
        self.current_utc_datetime = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
        self._candidate_id = candidate_id
        self._screening_verdict = screening_verdict
        self._budget_decision = budget_decision or {"decision": "approve"}
        self._offer_decision = offer_decision or {"decision": "approve"}
        self._voice_event = voice_event
        self._voice_times_out = voice_times_out
        # New Phase-7 HITL events introduced in 1b7c8bc4 ("replace stub
        # Phase 7 with three-wait HITL sequence"). Default to the green
        # path so existing voice/legacy tests continue to reach status=
        # completed without having to spell every gate out.
        self._invite_decision = invite_decision or {"decision": "invite"}
        self._booked_decision = booked_decision or {"slot": "2026-05-01T10:00Z"}
        self._post_decision = post_decision or {"decision": "offer", "level": "L4", "rating": 4}
        self.calls: list[tuple[str, dict]] = []

    def get_input(self):
        # candidate_id only present when the orchestration was started by
        # the candidate-portal /apply path; legacy seeded workflows omit it.
        out: dict[str, Any] = {"workflow_id": "HIRE-1"}
        if self._candidate_id is not None:
            out["candidate_id"] = self._candidate_id
        return out

    def call_activity(self, name: str, payload: dict):
        self.calls.append((name, payload))
        if name == "issue_screen_link_activity_trigger":
            return {
                "token": "tok-screen-1",
                "candidate_id": payload.get("candidate_id"),
                "portal_url": f"http://localhost:5174/screen?token=tok-screen-1",
            }
        if name == "send_screen_email_activity_trigger":
            return {"sent": True, "message_id": "m1"}
        if name == "hiring_screening_activity_trigger":
            return {"verdict": self._screening_verdict}
        # Most activities just return an empty dict — orchestration only
        # needs flow-control here, not a realistic spine result.
        return {}

    def wait_for_external_event(self, name: str):
        if name == "budget_approval":
            return _StubExternalEvent(name, self._budget_decision)
        if name == "offer_approval":
            return _StubExternalEvent(name, self._offer_decision)
        if name == "voice_complete":
            return _StubExternalEvent(name, self._voice_event)
        if name == "interview_invite":
            return _StubExternalEvent(name, self._invite_decision)
        if name == "interview_booked":
            return _StubExternalEvent(name, self._booked_decision)
        if name == "offer_decision":
            return _StubExternalEvent(name, self._post_decision)
        return _StubExternalEvent(name)

    def create_timer(self, fire_at):
        return _StubTimerEvent(fire_at)

    def task_any(self, awaitables: Iterable):
        evs = list(awaitables)
        # `voice_times_out=True` means we want the timer to win for the
        # voice race specifically. Detect by inspecting whether any of the
        # awaitables is the voice_complete external event.
        names = {e.name for e in evs if isinstance(e, _StubExternalEvent)}
        if "voice_complete" in names and self._voice_times_out:
            for e in evs:
                if isinstance(e, _StubTimerEvent):
                    return e
        for e in evs:
            if isinstance(e, _StubExternalEvent):
                return e
        return evs[-1] if evs else None


def _drive(ctx: _StubContext) -> dict | None:
    gen = hiring_orchestration(ctx)  # type: ignore[arg-type]
    sent: Any = None
    while True:
        try:
            target = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            return stop.value
        sent = target


def test_phase6_with_candidate_issues_link_and_suspends_until_voice_complete():
    ctx = _StubContext(
        candidate_id="C-VVVVVVVV",
        voice_event={"score": 8.2, "duration_s": 145.0,
                     "candidate_id": "C-VVVVVVVV"},
    )
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    # Voice-screen plumbing fires before any voice-screener activity.
    assert "issue_screen_link_activity_trigger" in activities
    assert "send_screen_email_activity_trigger" in activities
    # The actual screening agent runs AFTER the suspend resolves.
    issue_idx = activities.index("issue_screen_link_activity_trigger")
    voice_idx = activities.index("hiring_voice_activity_trigger")
    assert voice_idx > issue_idx
    # Orchestration completes (offer approved by default).
    assert result["status"] == "completed"
    # Score from the external-event payload is folded onto voice_result.
    assert result["voice"].get("score") == 8.2


def test_phase6_voice_timeout_completes_with_status_timeout():
    ctx = _StubContext(
        candidate_id="C-TIMEOUT1",
        voice_times_out=True,
    )
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    # Issue + email still happened.
    assert "issue_screen_link_activity_trigger" in activities
    assert "send_screen_email_activity_trigger" in activities
    # The voice-screener activity DID NOT run because the timer won.
    assert "hiring_voice_activity_trigger" not in activities
    # Orchestration short-circuits with status=timeout.
    assert result["status"] == "timeout"
    assert result["phase"] == "Voice"


def test_phase6_without_candidate_id_runs_legacy_synchronous_path():
    """Spine / legacy tests don't bind a candidate_id; we should NOT issue
    a magic link in that case (would explode against the real magic-link
    store anyway). Instead, fall back to the synchronous voice activity."""
    ctx = _StubContext(candidate_id=None)
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "issue_screen_link_activity_trigger" not in activities
    assert "send_screen_email_activity_trigger" not in activities
    assert "hiring_voice_activity_trigger" in activities
    assert result["status"] == "completed"


def test_phase6_skipped_on_low_screening_verdict_so_no_link_issued():
    """Auto-drop verdict short-circuits before Phase 6 — must NOT send the
    candidate a screening link they'll never use."""
    ctx = _StubContext(
        candidate_id="C-AUTODROP",
        screening_verdict="auto-drop",
    )
    result = _drive(ctx)
    activities = [c[0] for c in ctx.calls]
    assert "issue_screen_link_activity_trigger" not in activities
    assert "send_screen_email_activity_trigger" not in activities
    assert "hiring_voice_activity_trigger" not in activities
    assert result["status"] == "auto_dropped"
