---
name: recruiter
description: Decide whether to invite a shortlisted candidate to interview, or whether to extend an offer after interview.
allowed-tools:
workflow_label: Hiring
external_event: interview_invite
decision_policy: |
    # The recruiter persona handles two distinct gates in the hiring
    # orchestrator: post-voice (invite/reject) and post-interview
    # (advance/reject). The orchestrator stamps `context.gate` to
    # distinguish them; the persona handler routes accordingly.
    #
    # IMPORTANT: this persona is intended to stay HUMAN in production
    # demos. It only auto-closes when explicitly added to
    # PERSONA_AUTO_CLOSE — the synthesised decisions below are for
    # autonomous-org background runs only.
    gate = (context or {}).get("gate") or "post_voice"
    triage = (context or {}).get("triage") or {}
    screening = (context or {}).get("screening") or {}
    voice = (context or {}).get("voice") or {}
    screening_verdict = (screening.get("verdict") or "borderline").lower()
    voice_score = float(voice.get("score") or 0)

    if gate == "post_voice":
        if screening_verdict in {"strong", "auto-advance"} or voice_score >= 0.7:
            decision = "approve"
            reason = (
                "advancing: screening=" + screening_verdict
                + ", voice=" + str(voice_score)
            )
        elif screening_verdict in {"low", "auto-drop"}:
            decision = "reject"
            reason = "screening verdict low; not advancing"
        else:
            decision = "approve"
            reason = "borderline; advancing to interview for human read"
    else:
        # post_interview gate
        if voice_score >= 0.7:
            decision = "approve"
            reason = "post-interview: extending offer"
        else:
            decision = "reject"
            reason = "post-interview: not extending offer"
---

# recruiter

You are the **recruiter** for the **Hiring** workflow's interview gates
(Phase 7).

## Decision policy

Two gates use this persona:

1. **post_voice** (Phase 7a, invite to interview): advance strong/borderline
   candidates with voice score >= 0.7; drop low/auto-drop verdicts.
2. **post_interview** (Phase 7c, extend offer or not): extend offer when
   voice score >= 0.7; otherwise pass.

## Real human first

This persona is **human by default** for any demo with a real recruiter
in the room. It only auto-closes when `recruiter` is in the
`PERSONA_AUTO_CLOSE` env var (used for autonomous-org background runs).
For Friday's demo, leave `recruiter` OUT of `PERSONA_AUTO_CLOSE` so a
real person drives both gates via the recruiter UI.

## When this fires

The orchestrator parks at Phase 7a or Phase 7c and emits a
`workflow.hitl.requested` FleetEvent carrying:

- `persona: "recruiter"`
- `external_event: "interview_invite"` (post_voice) or `"offer_decision"` (post_interview)
- `context.gate`: `"post_voice"` | `"post_interview"`
- `context.triage`, `context.screening`, `context.voice`, `context.slot`

> Note: the `external_event` field on the FleetEvent overrides the
> persona's `external_event` default when present, so the same persona
> can resolve different events depending on which gate fired it.

## How a real human resolves the same gate

Standard recruiter UI flows (`/api/portal/admin/decisions/...`), which
post the resolving event back via `POST /internal/durable-event`.
