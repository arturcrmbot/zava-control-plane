# src/functions/graphs/executors/agents/agent_exception_classifier.py
from __future__ import annotations
import json
import logging

from ._wrapper import run_agent_skill

log = logging.getLogger(__name__)


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    workflow_id = input.get("workflow_id")
    # pitch-i3: short-circuit on signature match so the substrate avoids
    # repeat LLM round-trips for semantically equivalent unmatched items.
    from api.server.services import classifier_cache

    signature = classifier_cache.signature_for(
        {"kind": "exception_classifier", "unmatched_item": item}
    )
    cached = classifier_cache.lookup(signature)
    if cached is not None:
        try:
            from api.server.state import app_state
            from api.shared.events import FleetEvent

            app_state.bus.emit(
                FleetEvent(
                    type="classifier.cache_hit",
                    workflow_id=workflow_id,
                    signature=signature,
                    skill="exception_classifier",
                )
            )
        except Exception:
            log.debug(
                "classifier_cache: cache_hit emit failed (swallowed)",
                exc_info=True,
            )
        return {"exception_classification": dict(cached)}

    prompt = (
        f"Unmatched item: {json.dumps(item)}\n\n"
        f"Classify per your role."
    )
    resolution = await run_agent_skill(
        "exception_classifier", prompt, workflow_id=workflow_id
    )
    try:
        if isinstance(resolution, dict):
            classifier_cache.remember(signature, resolution)
    except Exception:
        log.debug(
            "classifier_cache: remember failed (swallowed)", exc_info=True
        )
    return {"exception_classification": resolution}
