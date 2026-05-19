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
    # voice may be the agent verdict (no `score`) OR the raw event payload.
    # Fall back to a demo-default 0.75 so post-interview doesn't auto-fail
    # when the score never made it into the parked context.
    voice_score = float(voice.get("score") or 0.75)

    recommender = (context or {}).get("interview_recommender") or {}
    recommender_decision = str(recommender.get("decision") or "").lower()

    if gate == "post_voice":
        if recommender_decision in {"decline", "reject"}:
            decision = "reject"
            reason = "recommender declined advancement at post_voice"
        elif recommender_decision in {"advance", "approve"}:
            decision = "approve"
            reason = "recommender recommended advancement at post_voice"
        elif screening_verdict in {"strong", "auto-advance"} or voice_score >= 0.7:
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
        # post_interview gate — autonomous-mode default is to extend the
        # offer when no strong negative signal is present. Reject only on
        # an explicit low/auto-drop screening signal.
        if screening_verdict in {"low", "auto-drop"}:
            decision = "reject"
            reason = "post-interview: screening signal too weak"
        else:
            decision = "approve"
            reason = "post-interview: extending offer"
summary_policy: |
    # Phase B5 of autonomous-domain-insights v1.1: Recruiter observes
    # hiring-workflow population in the last 60 days and the count of
    # `offer_approval` Decisions with verdict `approve` in the same
    # window (proxy for hires). Computes closure rate = hires/workflows.
    # When closure rate < 30% on a non-trivial sample (>= 5 hiring
    # workflows), proposes a 14-day prioritisation policy that freezes
    # net-new reqs in favour of replacement reqs.
    #
    # Synthetic-id pattern (mirrors hr_director / dpo / gc): proposed
    # `decided_on` uses the synthetic id "HIRING:net-new-reqs" against
    # scope_kind="Organisation". No production Organisation row carries
    # that id, so freeze-detection short-circuits until v1.2 introduces
    # a first-class hiring-lane node kind. Tests pre-seed the
    # Organisation row to exercise the skip path.
    wf_rows = graph.query(
        "MATCH (w:Workflow) "
        "WHERE w.workflow_type = 'hiring' "
        "  AND w.started_at > current_timestamp() - to_interval('60 days') "
        "RETURN count(w) AS n"
    )
    workflows = 0
    for r in wf_rows:
        workflows = int(r["n"] or 0)

    h_rows = graph.query(
        "MATCH (d:Decision), (w:Workflow) "
        "WHERE d.workflow_id = w.id "
        "  AND w.workflow_type = 'hiring' "
        "  AND d.phase = 'offer_approval' "
        "  AND d.verdict = 'approve' "
        "  AND d.decided_at > current_timestamp() - to_interval('60 days') "
        "RETURN count(d) AS n"
    )
    hires = 0
    for r in h_rows:
        hires = int(r["n"] or 0)

    if workflows > 0:
        closure_rate = float(hires) / float(workflows)
    else:
        closure_rate = 0.0

    freeze_id = "HIRING:net-new-reqs"
    rec_freezes = active_policies_for(
        graph,
        scope_kind="Organisation",
        scope_id=freeze_id,
        verdict="freeze",
    )
    has_freeze = len(rec_freezes) > 0

    proposed_actions = []
    trip = (closure_rate < 0.30) and (workflows >= 5)
    if trip and not has_freeze:
        proposed_actions.append({
            "id": "recruit-prioritise-replacements",
            "label": "Prioritise replacement reqs over net-new hires for 14 days",
            "kind": "policy_set",
            "verdict": "freeze",
            "decided_on": [freeze_id],
            "attributes": {"expiry_days": 14, "scope": "hiring"},
            "reason": (
                "closure rate at "
                + str(int(closure_rate * 100))
                + "% on "
                + str(workflows)
                + " recent hiring workflows — focus on replacements only"
            ),
        })

    if len(proposed_actions) == 0:
        headline = "Hiring on track"
    else:
        headline = "Hiring velocity below target — focus on replacements"

    body = (
        str(workflows) + " recent hiring workflow(s); "
        + str(hires) + " hire(s) ("
        + str(int(closure_rate * 100)) + "% closure rate)"
    )

    fp = (
        "recruiter:("
        + str(workflows) + ","
        + str(hires) + ","
        + str(has_freeze)
        + ")"
    )

    summary = {
        "headline": headline,
        "body": body,
        "kpis": {
            "recent_hiring_workflows": workflows,
            "hires": hires,
            "closure_rate_pct": int(closure_rate * 100),
            "active_freeze": has_freeze,
        },
        "proposed_actions": proposed_actions,
        "fingerprint": fp,
    }
personality:
  risk_appetite: aggressive
  thoroughness: low
  escalation_style: quick
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

## Summary policy

On every insight cadence tick the recruiter observes the population of
hiring workflows started in the last 60 days and the count of
`offer_approval` Decisions with verdict `approve` in the same window
(used as a proxy for hires). Computes closure rate = hires/workflows.
When closure rate falls below 30% on a non-trivial sample (>= 5 hiring
workflows), the recruiter proposes a `policy_set` action prioritising
replacement reqs over net-new hires for 14 days — unless an active
freeze on the synthetic id `HIRING:net-new-reqs` already covers the
same scope.

The fingerprint is a deterministic tuple-string
`recruiter:(workflows, hires, has_freeze)` so the cadence loop only
writes a new Insight when one of the three observable inputs changes.

Known limitation: there is no first-class node kind for hiring lanes
in v1.1, so `decided_on` uses `"HIRING:net-new-reqs"` against
`scope_kind="Organisation"` (mirrors the hr_director / dpo / gc
synthetic-id pattern). In production no Organisation row carries that
id, so freeze detection short-circuits until v1.2 introduces a
first-class hiring-lane node kind.

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
