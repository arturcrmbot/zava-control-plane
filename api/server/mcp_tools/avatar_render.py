"""avatar_render MCP tool — Azure AI Speech batch avatar synthesis.

Cached by sha256(voice|script) keyed against (avatar_character). Cache hit
returns the existing Blob SAS URL. Cache miss renders via Azure Speech batch
synthesis, uploads the mp4 to Azure Blob, persists the cache entry, returns
the new SAS URL.

See `api/server/skills/onboarding-buddy/SKILL.md` for the runbook the model
follows when calling this tool.

Mirrors the `ocr_extract` pattern (lazy singletons, `is_configured()`,
Pydantic result envelope, Entra-ID-only auth).
"""
from __future__ import annotations

import hashlib
import json
import os

from copilot.tools import ToolResult, define_tool
from pydantic import BaseModel, Field

from api.server.services.blob_store import BlobStore
from api.server.services.render_cache import RenderCache
from api.server.services.speech_avatar_client import (
    AvatarRenderError,
    AvatarRenderTimeout,
    SpeechAvatarClient,
)

from ._otel import traced_tool


_BLOB_CONTAINER = "avatar-renders"
_SAS_TTL_S = 24 * 3600
_DEFAULT_VOICE = "en-US-JennyNeural"
_CACHE_DB_PATH = "data/.avatar/cache.sqlite"


class AvatarRenderResult(BaseModel):
    """Plain Python return envelope for `avatar_render()`.

    Distinct from the MCP `ToolResult` so the onboarding graph executor can
    read structured fields directly without re-parsing JSON.
    """

    result_type: str  # "success" | "failure"
    video_url: str | None = None
    cached: bool = False
    error: str | None = None


def is_configured() -> bool:
    """True iff both Azure Speech region + Storage connection string are set.

    `AVATAR_TRANSPORT=mock` short-circuits to false so the existing
    `mocks/heygen-mcp` canned-mp4 fallback (or in-process mock) is used.
    """
    if os.environ.get("AVATAR_TRANSPORT", "").lower() == "mock":
        return False
    return bool(os.environ.get("AZURE_SPEECH_REGION")) and bool(
        os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    )


def _compute_hash(script: str, voice: str = _DEFAULT_VOICE) -> str:
    return hashlib.sha256(f"{voice}|{script}".encode("utf-8")).hexdigest()[:16]


# Lazy singletons — keep import-time clean so unconfigured envs don't crash.
def _speech_client() -> SpeechAvatarClient:
    return SpeechAvatarClient(region=os.environ["AZURE_SPEECH_REGION"])


def _blob_store() -> BlobStore:
    return BlobStore(
        connection_string=os.environ["AZURE_STORAGE_CONNECTION_STRING"],
        container=_BLOB_CONTAINER,
    )


def _render_cache() -> RenderCache:
    return RenderCache(db_path=_CACHE_DB_PATH)


def avatar_render(
    *,
    script: str,
    avatar_character: str = "lisa",
    avatar_style: str = "graceful-sitting",
    voice: str = _DEFAULT_VOICE,
) -> AvatarRenderResult:
    """Plain Python entry point. Used by tests, the onboarding graph
    executor, and the MCP-tool wrapper below."""
    if not is_configured():
        missing = [
            v
            for v in ("AZURE_SPEECH_REGION", "AZURE_STORAGE_CONNECTION_STRING")
            if not os.environ.get(v)
        ]
        if os.environ.get("AVATAR_TRANSPORT", "").lower() == "mock":
            return AvatarRenderResult(
                result_type="failure",
                error="AVATAR_TRANSPORT=mock — falling back to mocks/heygen-mcp",
            )
        return AvatarRenderResult(
            result_type="failure",
            error=f"unconfigured: {', '.join(missing)}",
        )

    sha = _compute_hash(script, voice)
    cache = _render_cache()
    blob_name = f"{sha}-{avatar_character}.mp4"
    cached = cache.lookup(content_hash=sha, avatar_id=avatar_character)
    if cached is not None:
        return AvatarRenderResult(
            result_type="success", video_url=cached["blob_url"], cached=True
        )

    try:
        mp4 = _speech_client().render(
            script=script,
            avatar_character=avatar_character,
            avatar_style=avatar_style,
            voice=voice,
        )
    except AvatarRenderError as e:
        return AvatarRenderResult(
            result_type="failure", error=f"render failed: {e}"
        )
    except AvatarRenderTimeout as e:
        return AvatarRenderResult(
            result_type="failure", error=f"render timeout: {e}"
        )

    bs = _blob_store()
    bs.put(blob_name, mp4, content_type="video/mp4")
    sas = bs.sas_url(blob_name, ttl_seconds=_SAS_TTL_S)
    cache.put(
        content_hash=sha,
        avatar_id=avatar_character,
        blob_name=blob_name,
        blob_url=sas,
    )
    return AvatarRenderResult(
        result_type="success", video_url=sas, cached=False
    )


# ---------------------------------------------------------------- MCP surface


class _AvatarRenderParams(BaseModel):
    script: str = Field(
        description="Plain-text script for the avatar to read aloud."
    )
    avatar_character: str = Field(
        default="lisa",
        description=(
            "Prebuilt avatar character. One of: lisa, harry, lori, max, jeff, meg."
        ),
    )
    avatar_style: str = Field(
        default="graceful-sitting",
        description=(
            "Avatar style variant. lisa supports: graceful-sitting, casual-sitting, "
            "technical-sitting, technical-standing."
        ),
    )
    voice: str = Field(
        default=_DEFAULT_VOICE,
        description="Azure Neural voice name (e.g. en-US-JennyNeural).",
    )


@define_tool(
    name="avatar_render",
    description=(
        "Render an avatar video reading the given script. Uses Azure AI Speech "
        "batch avatar synthesis. Returns a video URL the candidate portal can "
        "play. Avatars: lisa, harry, lori, max, jeff, meg. Voices: any Azure "
        "Neural voice (default en-US-JennyNeural). Cached on sha256(voice|"
        "script) + avatar_character so repeat demo runs don't re-bill."
    ),
)
@traced_tool("avatar.render")
def avatar_render_tool(params: _AvatarRenderParams) -> ToolResult:
    result = avatar_render(
        script=params.script,
        avatar_character=params.avatar_character,
        avatar_style=params.avatar_style,
        voice=params.voice,
    )
    if result.result_type != "success":
        return ToolResult(
            text_result_for_llm=f"avatar render failed: {result.error}",
            result_type="failure",
            error=result.error,
        )
    return ToolResult(
        text_result_for_llm=json.dumps(
            {
                "video_url": result.video_url,
                "cached": result.cached,
            }
        )
    )
