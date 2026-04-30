# src/functions/graphs/executors/agents/agent_cv_crystalliser.py
"""POC2 Phase 4 (Triage) — cv-crystalliser executor.

Wraps the existing hiring stub for now (real GHCP SDK call lands per Track A
in `agent_cv_crystalliser_real.py`). The job here is to honour the canonical
output shape from `api/server/skills/cv-crystalliser/SKILL.md` — including
the new `component_spec` field — and lift it onto the workflow ledger so
WorkflowDetail can render the AG-UI scorecard (POC2 §4.21).

The executor emits an `agent.output` webhook event (kind `agent_output`)
which `api/server/routes/internal_durable_event.py` routes into
`StateStore.append_agent_output(...)`. This crosses the Functions-host →
FastAPI process boundary the same way `agent.completed` does.
"""
from __future__ import annotations

from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.webhook import emit


def _pick_component_spec(profile: dict) -> list[dict]:
    """Per-role component_spec selection, mirroring SKILL.md.

    SDE / engineer / developer titles → fact_grid + skill_chips.
    Creative / Director / Designer / Brand titles → fact_grid + portfolio_gallery.
    Default → fact_grid only.
    Plus a warn callout if `inconsistencies` is non-empty.
    """
    title_raw = profile.get("current_title")
    if isinstance(title_raw, dict):
        title = (title_raw.get("value") or "").lower()
    else:
        title = (title_raw or "").lower()

    tenure_raw = profile.get("tenure_years_total")
    if isinstance(tenure_raw, dict):
        tenure = tenure_raw.get("value")
    else:
        tenure = tenure_raw

    rtw = (profile.get("right_to_work") or {}).get("evidence") or "unknown"

    facts = [
        {"label": "Current role", "value": profile.get("current_title", {}).get("value")
            if isinstance(profile.get("current_title"), dict) else (profile.get("current_title") or "—")},
        {"label": "Total tenure", "value": f"{tenure} yrs" if tenure is not None else "—"},
        {"label": "Right to work", "value": rtw},
    ]
    fact_grid = {"kind": "fact_grid", "title": "Profile", "facts": facts}

    is_engineering = any(k in title for k in ("engineer", "developer", "sde"))
    is_creative = any(k in title for k in ("director", "designer", "brand", "creative"))

    spec: list[dict] = [fact_grid]
    if is_engineering:
        skills = list(profile.get("skills") or [])[:6]
        spec.append({"kind": "skill_chips", "title": "Top skills", "skills": skills})
    elif is_creative:
        cid = profile.get("candidate_id") or "unknown"
        urls = profile.get("portfolio_image_urls") or [
            f"data/synthetic/hiring/portfolios/{cid}/01.jpg",
            f"data/synthetic/hiring/portfolios/{cid}/02.jpg",
            f"data/synthetic/hiring/portfolios/{cid}/03.jpg",
        ]
        spec.append({"kind": "portfolio_gallery", "title": "Portfolio", "image_urls": urls[:6]})

    inconsistencies = profile.get("inconsistencies") or []
    if inconsistencies:
        spec.append({
            "kind": "callout",
            "tone": "warn",
            "text": f"{len(inconsistencies)} CV/LinkedIn inconsistencies — see Inconsistencies tab",
        })

    return spec


async def execute(input: dict) -> dict:
    """Run the cv-crystalliser step and persist component_spec on the workflow.

    For the spine: delegate the actual crystallisation to the stub agent and
    synthesise the agent output payload from the workflow's seeded candidate
    profile (in `input["candidate_profile"]` if the loader injected one) so
    the AG-UI scorecard has data even before a real GHCP SDK call lands.
    """
    stub_result = await agent_hiring_stub.execute(input)

    # Prefer an explicit profile injected by the loader / upstream phase;
    # fall back to whatever the agent JSON declared (real-skill path) and
    # finally an empty profile so the workflow never breaks.
    profile = (
        input.get("candidate_profile")
        or stub_result.get("profile")
        or {}
    )
    component_spec = stub_result.get("component_spec") or _pick_component_spec(profile)
    inconsistencies = profile.get("inconsistencies") or stub_result.get("inconsistencies") or []

    agent_output = {
        "candidate_id": profile.get("candidate_id") or input.get("candidate_id"),
        "profile": profile,
        "component_spec": component_spec,
        "inconsistencies": inconsistencies,
    }

    workflow_id = input.get("workflow_id") or input.get("hire_id") or "?"
    instance_id = input.get("instance_id")
    await emit(workflow_id, instance_id, "agent_output", {
        "agent": "cv_crystalliser",
        "output": agent_output,
    })

    # Forward the result so downstream nodes can also see it.
    return {**stub_result, "cv_crystalliser": agent_output}
