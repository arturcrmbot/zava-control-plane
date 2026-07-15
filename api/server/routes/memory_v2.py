"""Memory layer v2 — Anthropic-style two-tier architecture.

POST /api/memory/v2/recall    — semantic search for agent runtime
GET  /api/memory/v2/memories  — list all for UI / dream input
"""
from __future__ import annotations

import json as _json
import logging
from collections import deque

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.server.state import app_state

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory/v2", tags=["memory-v2"])

# Recent dream results (in-memory ring buffer for UI display)
_dream_history: deque[dict] = deque(maxlen=50)


class _RecallBody(BaseModel):
    domain: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class _DreamBody(BaseModel):
    domain: str = Field(..., min_length=1)


@router.get("/domains")
def list_domains() -> dict:
    return {"domains": sorted(app_state.domain_memories)}


@router.post("/recall")
def recall(body: _RecallBody) -> dict:
    store = app_state.domain_memories.get(body.domain)
    if not store:
        return {"memories": [], "error": f"unknown domain: {body.domain}"}
    try:
        memories = store.recall(query=body.query, top_k=body.top_k)
    except Exception:
        log.exception("memory recall failed for domain=%s", body.domain)
        memories = []
    return {"memories": memories}


@router.get("/memories")
def list_memories(domain: str = Query(..., min_length=1)) -> dict:
    store = app_state.domain_memories.get(domain)
    if not store:
        return {"memories": [], "count": 0, "error": f"unknown domain: {domain}"}
    try:
        memories = store.list_all(limit=200)
        count = len(memories)
    except Exception:
        log.exception("memory list failed for domain=%s", domain)
        memories, count = [], 0
    return {"memories": memories, "count": count}


@router.post("/dream")
async def trigger_dream(body: _DreamBody) -> dict:
    """Trigger a dream consolidation pass for a domain."""
    store = app_state.domain_memories.get(body.domain)
    if not store:
        return {"error": f"unknown domain: {body.domain}"}

    from api.server.routes.dream_pass_pause import is_paused

    if is_paused(body.domain):
        return {"error": "paused", "domain": body.domain}

    from api.server.services.memory.dream_consolidator import consolidate_memories

    # Emit dream.pass.started so the constellation can light up the
    # planet while the consolidation runs.
    try:
        from api.shared.events import FleetEvent as _FE
        app_state.bus.emit(_FE(
            type="dream.pass.started",
            payload={
                "domain": body.domain,
                "trigger": "manual",
                "input_count": store.count_working() if hasattr(store, "count_working") else store.count(),
            },
        ))
    except Exception:
        log.debug("trigger_dream: started emit failed", exc_info=True)

    # Prefer Azure OpenAI when configured, otherwise the deterministic
    # fallback so the demo works without cloud creds.
    import os as _os
    if _os.getenv("AZURE_OPENAI_ENDPOINT"):
        consolidator = _build_llm_consolidator(body.domain)
    else:
        from api.server.services.memory.fallback_consolidator import (
            fallback_consolidate,
        )

        async def _fb(texts: list[str]) -> list[str]:
            return fallback_consolidate(texts)

        consolidator = _fb

    from datetime import datetime as _dt, timezone as _tz
    _started_at = _dt.now(_tz.utc).isoformat()
    result = await consolidate_memories(
        domain_memory=store,
        llm_consolidate=consolidator,
    )
    result.setdefault("trigger", "manual")
    _completed_at = result.get("timestamp") or _dt.now(_tz.utc).isoformat()
    _input_count = int(result.get("input_count", 0) or 0)
    _output_count = int(result.get("output_count", 0) or 0)
    _ui_record = {
        "id": f"dream-{body.domain}-{_started_at}",
        "domain": body.domain,
        "skill_version": result.get("skill_version"),
        "started_at": _started_at,
        "completed_at": _completed_at,
        "status": "completed" if _input_count > 0 else "empty",
        "candidates_proposed": _input_count,
        "candidates_promoted": _output_count,
        "trigger": result.get("trigger", "manual"),
    }
    _dream_history.appendleft(_ui_record)

    # Emit bus events so the constellation can light up.
    try:
        from api.shared.events import FleetEvent as _FE
        app_state.bus.emit(_FE(
            type="dream.pass.finished",
            payload={
                "domain": body.domain,
                "trigger": "manual",
                "input_count": result.get("input_count", 0),
                "output_count": result.get("output_count", 0),
                "timestamp": result.get("timestamp"),
            },
        ))
    except Exception:
        log.debug("trigger_dream: bus emit failed", exc_info=True)

    return result


class _SeedEntry(BaseModel):
    role: str = Field(..., min_length=1)
    verdict: str = Field(..., min_length=1)
    gate: str = Field(..., min_length=1)
    reason: str | None = None
    signals: dict | None = None
    workflow_id: str = ""


class _SeedBody(BaseModel):
    domain: str = Field(..., min_length=1)
    entries: list[_SeedEntry]


@router.post("/seed-demo")
def seed_demo(body: _SeedBody) -> dict:
    """Write demo working-memory entries so a downstream dream pass has
    real signal to consolidate. Used by ``scripts/dream_pass_demo.py``
    and the Playwright E2E.
    """
    store = app_state.domain_memories.get(body.domain)
    if not store:
        return {"error": f"unknown domain: {body.domain}", "written": 0}

    from api.server.services.memory.working_memory_writer import (
        write_decision_memory,
    )

    written = 0
    for e in body.entries:
        ok = write_decision_memory(
            domain=body.domain,
            persona_role=e.role,
            verdict=e.verdict,
            reason=e.reason,
            workflow_id=e.workflow_id or None,
            gate_phase=e.gate,
            signals=e.signals,
        )
        if ok:
            written += 1
    return {"written": written, "domain": body.domain}


@router.get("/dream/history")
def dream_history() -> dict:
    return {"items": list(_dream_history)}


def _build_llm_consolidator(domain: str):
    """Build the async function that calls Azure OpenAI to consolidate."""

    async def consolidate(memory_texts: list[str]) -> list[str]:
        from api.server.services.memory.dream_consolidator import (
            build_consolidation_prompt,
        )

        prompt = build_consolidation_prompt(memory_texts)

        try:
            import os

            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            from openai import AzureOpenAI

            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            client = AzureOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                azure_deployment=deployment,
                azure_ad_token_provider=token_provider,
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
            response = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
            )
            text = response.choices[0].message.content or "[]"
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            consolidated = _json.loads(text)
            if isinstance(consolidated, list):
                return [str(item) for item in consolidated if item]
            return memory_texts
        except Exception:
            log.exception("dream[%s]: LLM consolidation call failed", domain)
            return memory_texts

    return consolidate
