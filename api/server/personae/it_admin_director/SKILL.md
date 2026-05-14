---
name: it_admin_director
description: IT Admin Director; senior tech sign-off; escalates strategic IT decisions to the CTO.
allowed-tools:
workflow_label: Technology — IT admin
external_event: it_admin_director_decision
decision_policy: |
    payload = (context or {}).get("invoice") or (context or {}).get("claim") or (context or {}).get("contract") or (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = (payload.get("category") or "standard")
    action = (context or {}).get("action") or "it_admin_director_decision"

    auth = authority_check(
        role="it_admin_director",
        action=action,
        value=value,
        category=category,
    )

    rule = str(auth.get("governing_rule_id") or "n/a")
    if auth.get("allowed"):
        decision = "approve"
        reason = (
            "within it_admin_director delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
        )
    else:
        decision = "escalate"
        reason = (
            "outside it_admin_director delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
            + " — " + str(auth.get("reason") or "")
        )
summary_policy: |
    # Phase B5 of autonomous-domain-insights v1.1: IT Admin Director
    # observes recent it-access-request workflow load (last 30 days) and
    # the rate of `escalate` / `reject` Decisions on those workflows
    # (interpreted as "access anomalies"). Proposes a 7-day fast-track
    # freeze that requires manager+IT dual approval on every access
    # request when anomaly rate exceeds 20% on a non-trivial sample
    # (>= 5 recent access requests).
    #
    # Synthetic-id pattern (mirrors hr_director / dpo / gc): proposed
    # `decided_on` uses the synthetic id "IT:access-fast-track" against
    # scope_kind="Organisation". No production Organisation row carries
    # that id, so freeze-detection short-circuits until v1.2 introduces
    # a first-class process / lane node kind. Tests pre-seed the
    # Organisation row to exercise the skip path.
    tot_rows = graph.query(
        "MATCH (w:Workflow) "
        "WHERE w.workflow_type = 'it-access-request' "
        "  AND w.started_at > current_timestamp() - to_interval('30 days') "
        "RETURN count(w) AS n"
    )
    total = 0
    for r in tot_rows:
        total = int(r["n"] or 0)

    an_rows = graph.query(
        "MATCH (d:Decision), (w:Workflow) "
        "WHERE d.workflow_id = w.id "
        "  AND w.workflow_type = 'it-access-request' "
        "  AND d.verdict IN ['escalate', 'reject'] "
        "  AND d.decided_at > current_timestamp() - to_interval('30 days') "
        "RETURN count(d) AS n"
    )
    anomalies = 0
    for r in an_rows:
        anomalies = int(r["n"] or 0)

    if total > 0:
        anomaly_rate = float(anomalies) / float(total)
    else:
        anomaly_rate = 0.0

    freeze_id = "IT:access-fast-track"
    it_freezes = active_policies_for(
        graph,
        scope_kind="Organisation",
        scope_id=freeze_id,
        verdict="freeze",
    )
    has_freeze = len(it_freezes) > 0

    proposed_actions = []
    trip = (anomaly_rate > 0.20) and (total >= 5)
    if trip and not has_freeze:
        proposed_actions.append({
            "id": "freeze-access-broad",
            "label": "Require manager+IT dual approval for all access requests for 7 days",
            "kind": "policy_set",
            "verdict": "freeze",
            "decided_on": [freeze_id],
            "attributes": {"expiry_days": 7, "scope": "access"},
            "reason": (
                "anomaly rate at "
                + str(int(anomaly_rate * 100))
                + "% on "
                + str(total)
                + " recent access requests — pause fast-track until reviewed"
            ),
        })

    if len(proposed_actions) == 0:
        headline = "Access posture stable"
    else:
        headline = "Access anomaly rate elevated — recommend tighter approvals"

    body = (
        str(total) + " recent access request(s); "
        + str(anomalies) + " anomaly Decision(s) ("
        + str(int(anomaly_rate * 100)) + "% rate)"
    )

    fp = (
        "it_admin_director:("
        + str(total) + ","
        + str(anomalies) + ","
        + str(has_freeze)
        + ")"
    )

    summary = {
        "headline": headline,
        "body": body,
        "kpis": {
            "recent_access_requests": total,
            "anomalies": anomalies,
            "anomaly_rate_pct": int(anomaly_rate * 100),
            "active_freeze": has_freeze,
        },
        "proposed_actions": proposed_actions,
        "fingerprint": fp,
    }
personality:
  risk_appetite: balanced
  thoroughness: medium
  escalation_style: standard
---

# it_admin_director

You are the **it_admin_director** for the **Technology — IT admin** workflow.

## Decision policy

Approve when the delegated-authority matrix confirms this role is the
matched approver for the action+value+category triple. Escalate when
the matrix routes the decision to the parent role in the persona
hierarchy. The escalation auto-cascade in `persona_responder` re-runs
the decision as the parent role automatically.

Thresholds live in `api/shared/authority.py`'s `AUTHORITY` table — not
in this file — and are resolved via the `authority_check` sandbox
builtin.

## Summary policy

On every insight cadence tick the IT Admin Director observes the
population of `it-access-request` workflows started in the last 30 days
and the count of `escalate`/`reject` Decisions on those workflows in
the same window (treated as access anomalies). When the anomaly rate
exceeds 20% on a non-trivial sample (>= 5 recent access requests), the
director proposes a `policy_set` action requiring manager+IT dual
approval on every access request for 7 days — unless an active freeze
on the synthetic id `IT:access-fast-track` already covers the same
scope.

The fingerprint is a deterministic tuple-string
`it_admin_director:(total, anomalies, has_freeze)` so the cadence loop
only writes a new Insight when one of the three observable inputs
changes.

Known limitation: there is no first-class node kind for IT process
lanes in v1.1, so `decided_on` uses `"IT:access-fast-track"` against
`scope_kind="Organisation"` (mirrors the hr_director / dpo / gc
synthetic-id pattern). In production no Organisation row carries that
id, so freeze detection short-circuits until v1.2 introduces a
first-class process / lane node kind.

## When this fires

The orchestrator parks at the matching HITL gate and emits a
`workflow.hitl.requested` FleetEvent carrying:

- `persona: "it_admin_director"`
- `external_event: "it_admin_director_decision"`
- `context`: payload with at minimum `amount` (GBP) and `category`

## How a real human resolves the same gate

When `it_admin_director` is NOT in `PERSONA_AUTO_CLOSE`, the gate stays open
indefinitely.
