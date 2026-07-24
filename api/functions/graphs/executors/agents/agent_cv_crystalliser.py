# src/functions/graphs/executors/agents/agent_cv_crystalliser.py
"""POC2 Phase 4 (Triage) — cv-crystalliser executor.

Invokes the real cv-crystalliser skill via the GHCP SDK ephemeral session
pattern (`_wrapper.run_agent_session`). The skill loads SKILL.md, reasons
over the candidate's CV, and calls `ocr_extract` to read the PDF. We persist
the structured profile + component_spec onto the workflow ledger so the
recruiter UI's AG-UI scorecard renders, and the agent.completed webhook
(emitted by the wrapper itself) carries the full chat-completion message
stream + tool calls into `StateStore.append_agent_reasoning(...)` for the
recruiter Decisions panel.
"""
from __future__ import annotations

from api.server.mcp_tools.ocr_extract import ocr_extract_tool
from api.functions.webhook import emit

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "cv-crystalliser"


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

    current_role = (
        profile.get("current_title", {}).get("value")
        if isinstance(profile.get("current_title"), dict)
        else (profile.get("current_title") or "—")
    )
    facts = [
        {"label": "Current role", "value": current_role},
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
    """Run the cv-crystalliser skill via the GHCP SDK and lift the result onto
    the workflow ledger.

    The session emits `agent.completed` (via `_wrapper`) carrying the full
    message stream + tool calls; the FastAPI bridge persists that into
    `agent_reasoning` so the recruiter Decisions panel can render real LLM
    output, not synthesised stubs.
    """
    candidate = input.get("candidate") or {}
    candidate_id = (
        candidate.get("id")
        or input.get("candidate_id")
        or (input.get("metadata") or {}).get("candidate_id")
    )
    role_title = input.get("role_title") or (input.get("metadata") or {}).get("role_title") or "Candidate"
    workflow_id = input.get("workflow_id") or input.get("hire_id")
    instance_id = input.get("instance_id")

    if not candidate_id:
        # No candidate attached yet — return an empty stub so the orchestrator
        # graph still progresses. The recruiter view shows "no candidate" until
        # /apply lands one.
        return {"cv_crystalliser": {"profile": None, "component_spec": [], "verdict": None}}

    prompt = (
        f"Crystallise the CV for candidate `{candidate_id}` applying for "
        f"`{role_title}`.\n\n"
        f"Step 1: call `ocr_extract(document_id=\"{candidate_id}\", model=\"prebuilt-layout\")` "
        f"to read the PDF.\n"
        f"Step 2: map the response into the canonical profile shape per your "
        f"skill instructions (work history with dates, education, skills, "
        f"right-to-work evidence, inconsistencies).\n"
        f"Step 3: return ONLY the JSON object specified in your skill — no "
        f"prose, no markdown fences."
    )

    parsed = await run_agent_session(
        prompt=prompt,
        tools=[ocr_extract_tool],
        skill_dir=_SKILL_DIR,
        skill_label="cv_crystalliser",
        workflow_id=workflow_id,
        instance_id=instance_id,
    )

    # Extraction can fail honestly: parse_error from the JSON extractor, or a
    # parsed object that lacks any real profile fields (e.g. when ocr_extract
    # auth failed and the model bailed). Surface that as failure rather than
    # fabricating a "Shortlist 70%" verdict.
    parse_failed = (
        not isinstance(parsed, dict)
        or parsed.get("parse_error")
        or not any(k in parsed for k in ("name", "current_title", "skills", "work_history"))
    )

    if parse_failed:
        agent_output = {
            "candidate_id": candidate_id,
            "profile": {"candidate_id": candidate_id, "name": candidate.get("name"),
                        "_source": "extraction_failed"},
            "component_spec": [],
            "inconsistencies": [],
            "verdict": None,
            "extraction_status": "failed",
            "extraction_error": (
                "cv-crystalliser could not extract a profile — see agent_reasoning "
                "trace for the failing tool call (most likely ocr_extract auth)."
            ),
        }
    else:
        profile = parsed
        component_spec = profile.get("component_spec") or _pick_component_spec(profile)
        inconsistencies = profile.get("inconsistencies") or []
        # Only emit a verdict the model actually produced. No fabricated default.
        agent_output = {
            "candidate_id": profile.get("candidate_id") or candidate_id,
            "profile": profile,
            "component_spec": component_spec,
            "inconsistencies": inconsistencies,
            "verdict": profile.get("verdict"),
            "extraction_status": "ok",
        }

    if workflow_id:
        await emit(workflow_id, instance_id, "agent_output", {
            "agent": "cv_crystalliser",
            "output": agent_output,
        })

    return {"cv_crystalliser": agent_output}
