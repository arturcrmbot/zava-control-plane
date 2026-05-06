"""Creative Campaign activity functions — registered as Azure Durable
Functions activity triggers (see function_app.py). Each runs synchronously
and wraps an async MAF Workflow run inside asyncio.run.
"""
from __future__ import annotations
import asyncio

from api.functions.workflows.activities import _run_workflow
from api.functions.graphs import (
    build_creative_brief_synthesis_workflow,
    build_creative_insight_audience_workflow,
    build_creative_concept_fanout_workflow,
    build_creative_storyboard_render_workflow,
    build_creative_package_handoff_workflow,
)


def creative_brief_synthesis_activity(payload: dict) -> dict:
    """Phase 2 — agent projects transcript + seed brief into structured JSON."""
    return asyncio.run(_run_workflow(
        build_creative_brief_synthesis_workflow,
        payload,
        "Brief Synthesis",
    ))


def creative_insight_audience_activity(payload: dict) -> dict:
    """Phase 4 — fan-out: audience clusters, trend signals, brand recall."""
    return asyncio.run(_run_workflow(
        build_creative_insight_audience_workflow,
        payload,
        "Insight & Audience",
    ))


def creative_concept_fanout_activity(payload: dict) -> dict:
    """Phase 5 — 3 strategic routes × 4 stills each + brand-fit + distinctiveness."""
    return asyncio.run(_run_workflow(
        build_creative_concept_fanout_workflow,
        payload,
        "Concept Fan-out",
    ))


def creative_storyboard_render_activity(payload: dict) -> dict:
    """Phase 7 — 6 storyboard frames for the locked route."""
    return asyncio.run(_run_workflow(
        build_creative_storyboard_render_workflow,
        payload,
        "Storyboard Render",
    ))


def creative_package_handoff_activity(payload: dict) -> dict:
    """Phase 10 — bundle deliverables and push to Figma."""
    return asyncio.run(_run_workflow(
        build_creative_package_handoff_workflow,
        payload,
        "Package & Handoff",
    ))
