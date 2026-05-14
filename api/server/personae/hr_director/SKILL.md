---
name: hr_director
description: HR Director; sign-off authority for senior HR matters; escalates strategic decisions to the CPO.
allowed-tools:
workflow_label: People & HR — director
external_event: hr_director_decision
decision_policy: |
    payload = (context or {}).get("invoice") or (context or {}).get("claim") or (context or {}).get("contract") or (context or {}).get("request") or {}
    value_raw = payload.get("amount_gbp") or payload.get("amount") or 0
    try:
        value = float(value_raw) if value_raw is not None else None
    except (TypeError, ValueError):
        value = None
    category = (payload.get("category") or "standard")
    action = (context or {}).get("action") or "hr_director_decision"

    auth = authority_check(
        role="hr_director",
        action=action,
        value=value,
        category=category,
    )

    rule = str(auth.get("governing_rule_id") or "n/a")
    if auth.get("allowed"):
        decision = "approve"
        reason = (
            "within hr_director delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
        )
    else:
        decision = "escalate"
        reason = (
            "outside hr_director delegation per matrix rule " + rule
            + ": " + str(category) + " GBP " + str(value)
            + " — " + str(auth.get("reason") or "")
        )
summary_policy: |
    # Phase B1 of autonomous-domain-insights v1.1: per-department attrition
    # watch over Person nodes. Two cypher queries (Kuzu 0.6.1 doesn't do
    # GROUP BY on a derived column gracefully) joined in Python.
    #
    # Known limitation: departments are stored as a STRING attr on Person,
    # not as their own node kind. active_policies_for needs a real node id
    # to match on, so we use the synthetic id "DEPT:<dept>" against the
    # Organisation kind. In production no Organisation row carries that id
    # so freeze-detection is effectively a no-op until v1.2 introduces a
    # first-class Department node. Tests pre-seed the Organisation row to
    # exercise the skip path.
    current_rows = graph.query(
        "MATCH (p:Person) "
        "WHERE p.department IS NOT NULL AND p.employed_to IS NULL "
        "RETURN p.department AS dept, count(p) AS n "
        "ORDER BY p.department"
    )
    leaver_rows = graph.query(
        "MATCH (p:Person) "
        "WHERE p.department IS NOT NULL AND p.employed_to IS NOT NULL "
        "RETURN p.department AS dept, count(p) AS n"
    )

    current_by_dept = {}
    for r in current_rows:
        dept = r["dept"]
        if dept is None:
            continue
        current_by_dept[dept] = int(r["n"] or 0)

    leavers_by_dept = {}
    for r in leaver_rows:
        dept = r["dept"]
        if dept is None:
            continue
        leavers_by_dept[dept] = int(r["n"] or 0)

    all_depts = []
    seen = {}
    for d in current_by_dept:
        if d not in seen:
            seen[d] = True
            all_depts.append(d)
    for d in leavers_by_dept:
        if d not in seen:
            seen[d] = True
            all_depts.append(d)
    # Manual selection-sort over all_depts (sorted() not in sandbox).
    n_depts = len(all_depts)
    i = 0
    while i < n_depts:
        j = i + 1
        while j < n_depts:
            if all_depts[j] < all_depts[i]:
                tmp = all_depts[i]
                all_depts[i] = all_depts[j]
                all_depts[j] = tmp
            j = j + 1
        i = i + 1

    persons_total = 0
    leavers_total = 0
    for d in all_depts:
        persons_total = persons_total + current_by_dept.get(d, 0) + leavers_by_dept.get(d, 0)
        leavers_total = leavers_total + leavers_by_dept.get(d, 0)
    overall_pct = 0.0
    if persons_total > 0:
        overall_pct = leavers_total / persons_total
    overall_stressed = overall_pct > 0.12

    stressed = []
    proposed_actions = []
    fingerprint_parts = []

    for dept in all_depts:
        cur = current_by_dept.get(dept, 0)
        lev = leavers_by_dept.get(dept, 0)
        denom = cur + lev
        if denom <= 0:
            continue
        pct = lev / denom
        pct_int = int(pct * 100)
        synthetic_org_id = "DEPT:" + dept
        has_freeze = len(active_policies_for(
            graph,
            scope_kind="Organisation",
            scope_id=synthetic_org_id,
            verdict="freeze",
        )) > 0
        fingerprint_parts.append(
            "(" + dept + "," + str(pct_int) + "," + str(has_freeze) + ")"
        )
        is_stressed = pct > 0.15 or (overall_stressed and pct > 0)
        if is_stressed:
            stressed.append({
                "dept": dept,
                "pct": pct,
                "pct_int": pct_int,
                "has_freeze": has_freeze,
            })
            if not has_freeze:
                slug = dept.lower().replace(" ", "-")
                proposed_actions.append({
                    "id": "freeze-hiring-" + slug,
                    "label": "Pause new hires in " + dept + " for 30 days",
                    "kind": "policy_set",
                    "verdict": "freeze",
                    "decided_on": [synthetic_org_id],
                    "attributes": {"expiry_days": 30, "scope": "hiring"},
                    "reason": (
                        dept + " attrition at " + str(pct_int)
                        + "% — review before adding load"
                    ),
                })

    stressed_count = len(stressed)
    if stressed_count == 0:
        headline = "Headcount steady across all departments"
    else:
        headline = (
            str(stressed_count)
            + " department(s) under attrition stress — recommend hiring pauses"
        )

    body = " | ".join(
        s["dept"] + ": " + str(s["pct_int"]) + "%" for s in stressed
    )

    fp = "hr_director:" + ",".join(fingerprint_parts)
    if len(fp) > 256:
        fp = fp[:256]

    summary = {
        "headline": headline,
        "body": body,
        "kpis": {
            "persons_total": persons_total,
            "departments": len(all_depts),
            "stressed_departments": stressed_count,
            "overall_attrition_pct": float(overall_pct),
        },
        "proposed_actions": proposed_actions,
        "fingerprint": fp,
    }
voice_render: |
    k = summary.get("kpis") or {}
    n_stress = k.get("stressed_departments", 0)
    overall = k.get("overall_attrition_pct", 0.0)
    if n_stress == 0:
        body = (
            "Headcount steady across all departments — overall attrition "
            "sitting at " + str(int(overall*100)) + "%. We're hiring "
            "into vacancy as needed."
        )
    else:
        acts = summary.get("proposed_actions") or []
        depts = ", ".join((a.get("decided_on") or [""])[0].replace("DEPT:", "") for a in acts[:3])
        body = (
            str(n_stress) + " department(s) showing attrition stress: "
            + depts + ". I want to pause net-new reqs for 30 days and "
            "focus on retention conversations first. Approve and I'll "
            "redirect open recs to internal candidates."
        )
personality:
  risk_appetite: balanced
  thoroughness: medium
  escalation_style: standard
---

# hr_director

You are the **hr_director** for the **People & HR — director** workflow.

## Decision policy

Approve when the delegated-authority matrix confirms this role is the
matched approver for the action+value+category triple. Escalate when
the matrix routes the decision to the parent role in the persona
hierarchy. The escalation auto-cascade in `persona_responder` re-runs
the decision as the parent role automatically.

Thresholds live in `api/shared/authority.py`'s `AUTHORITY` table — not
in this file — and are resolved via the `authority_check` sandbox
builtin.

## When this fires

The orchestrator parks at the matching HITL gate and emits a
`workflow.hitl.requested` FleetEvent carrying:

- `persona: "hr_director"`
- `external_event: "hr_director_decision"`
- `context`: payload with at minimum `amount` (GBP) and `category`

## Summary policy

On every insight cadence tick the HR Director observes per-department
headcount over `Person` nodes and computes attrition as
`leavers / (current + leavers)` where a "leaver" is any Person with
`employed_to` populated. Departments with attrition > 15% (or every
department with any leavers when the overall figure exceeds 12%) are
flagged "stressed" and — if no active hiring-freeze policy already
covers them — get a `policy_set` proposed action labelled
"Pause new hires in &lt;dept&gt; for 30 days".

The fingerprint is a deterministic tuple-string
`hr_director:(dept, pct_int, has_active_freeze)…` in alpha-sorted
department order so the cadence loop only writes a new Insight when at
least one department's pct (rounded to integer) or freeze-state
actually changed.

Known limitation: departments are stored as a string attr on
`Person`, not as their own node kind, so the proposed `decided_on` uses
a synthetic id `"DEPT:<dept>"` against `scope_kind="Organisation"`.
In production no Organisation row exists with that id, so freeze
detection short-circuits until v1.2 introduces a first-class
`Department` node kind.

## How a real human resolves the same gate

When `hr_director` is NOT in `PERSONA_AUTO_CLOSE`, the gate stays open
indefinitely.
