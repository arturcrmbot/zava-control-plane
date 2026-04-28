"""apply_verdict_routing — deterministic Phase 4 router.

Inputs the classifier verdict (from Phase 2) and the escalation tier (when
Amber/Red), plus optional runtime thresholds from the policy page. Outputs
the routing target.

Routing matrix:
  green  -> auto-approve (close workflow, no notification, no review)
  amber  -> reviewer-queue (SSC reviewer takes a look; tier influences SLA)
  red    -> notify (Phase 5 sends an Adaptive Card; HITL wait for justification)

Thresholds are runtime-adjustable via app_state.store autonomy policies (the
existing /api/policy mechanism), and may force a verdict-shift — e.g., the
operator might temporarily route all Amber to auto-approve while fighting a
backlog. The orchestrator preserves the *original* classifier verdict on the
output so audit can show both intent and routing decision.
"""
from __future__ import annotations


async def execute(input: dict) -> dict:
    verdict = input.get("verdict") or "amber"
    escalation = input.get("escalation") or {}
    tier = escalation.get("tier")

    # Optional runtime override (set by /api/policy autonomy slider). The
    # presence of `route_override` in the orchestration payload short-circuits
    # the verdict-driven matrix.
    override = input.get("route_override")
    if override in {"auto-approve", "reviewer-queue", "notify"}:
        return {
            "routed_to": override,
            "verdict": verdict,
            "escalation_tier": tier,
            "override_applied": True,
        }

    if verdict == "green":
        return {
            "routed_to": "auto-approve",
            "verdict": verdict,
            "escalation_tier": None,
        }
    if verdict == "amber":
        return {
            "routed_to": "reviewer-queue",
            "verdict": verdict,
            "escalation_tier": tier,
        }
    # red
    return {
        "routed_to": "notify",
        "verdict": verdict,
        "escalation_tier": tier,
    }
