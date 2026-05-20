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

    result = await consolidate_memories(
        domain_memory=store,
        llm_consolidate=_build_llm_consolidator(body.domain),
    )
    _dream_history.appendleft(result)
    return result


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
