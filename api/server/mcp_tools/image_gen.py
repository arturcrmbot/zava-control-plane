"""image_gen MCP tool — Foundry gpt-image-2 image generation.

Mirrors the `avatar_render` pattern (lazy singletons, `is_configured()`,
Pydantic result envelope, Entra-ID-only auth, `traced_tool` for OTEL).

Cached by sha256(prompt|size|model|quality). Blob existence IS the cache —
deterministic blob name from the hash, regenerate the SAS URL on every
return so we never hand out expired links. No sqlite needed.

Behind the `CREATIVE_REAL_FOUNDRY=1` env flag — defaults off so the
canned-fixture path in agent_creative_stub.py stays the dev default.
Per plan/feature-poc3-ai-agency-1.md Phase 3 (TASK-015..TASK-020).

The MCP tool surface itself is shape-identical to what an Adobe Firefly
or Runway / Veo MCP would look like — the v2 swap is "write a new MCP
server, change the env flag, no skill changes". That's the substrate
contract.

Cost spans: emits `tool.server.image_gen` with `tool.cost.usd` attribute
per render, picked up by the credibility-friday Phase-2 economics path
with no extra wiring.

Content-safety rejections from gpt-image-2 (BadRequestError with
content_filter code) are surfaced as result_type="failure" with
error_code="content_safety_rejection" so the orchestrator can raise
a `creative.content_safety.rejected` workflow exception per
TASK-018 (the deliberate Stage-7 demo beat).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

from copilot.tools import ToolResult, define_tool
from openai import AzureOpenAI, BadRequestError
from pydantic import BaseModel, Field

from api.server.services.blob_store import BlobStore

from ._otel import traced_tool


_BLOB_CONTAINER = "creative-campaign-images"
_SAS_TTL_S = 24 * 3600
_DEFAULT_MODEL = "gpt-image-2"
_DEFAULT_SIZE = "1024x1024"
_DEFAULT_QUALITY = "medium"

# Foundry gpt-image-2 list price per output image, by (size, quality).
# Source: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
# Kept as a flat dict so the v2 swap (Firefly / Runway) drops in a sibling
# table; the cost-ledger consumer reads `tool.cost.usd` and doesn't care
# which model produced it.
_PRICE_TABLE_USD: dict[tuple[str, str], float] = {
    ("1024x1024", "low"):    0.011,
    ("1024x1024", "medium"): 0.042,
    ("1024x1024", "high"):   0.167,
    ("1024x1536", "low"):    0.016,
    ("1024x1536", "medium"): 0.063,
    ("1024x1536", "high"):   0.250,
    ("1536x1024", "low"):    0.016,
    ("1536x1024", "medium"): 0.063,
    ("1536x1024", "high"):   0.250,
}


class ImageGenResult(BaseModel):
    """Plain Python return envelope for `image_gen()`.

    Distinct from the MCP `ToolResult` so the creative graph executor
    (and Phase-4 concept-curator / storyboard-curator skills) can read
    structured fields directly without re-parsing JSON.
    """

    result_type: str  # "success" | "failure"
    image_url: str | None = None
    cached: bool = False
    cost_usd: float = 0.0
    prompt_hash: str | None = None
    revised_prompt: str | None = None  # gpt-image-2 echoes the safety-rewritten prompt
    error: str | None = None
    error_code: str | None = None  # "content_safety_rejection" | "unconfigured" | "api_error"


def is_configured() -> bool:
    """True iff CREATIVE_REAL_FOUNDRY=1 AND the Foundry + Storage env are set.

    Default-off so the existing canned-fixture path in agent_creative_stub
    stays the dev / CI default. Demo + production deploys flip the flag.
    """
    if os.environ.get("CREATIVE_REAL_FOUNDRY", "").strip() not in ("1", "true", "TRUE"):
        return False
    return (
        bool(os.environ.get("AZURE_OPENAI_ENDPOINT"))
        and bool(os.environ.get("AZURE_STORAGE_CONNECTION_STRING"))
    )


def _compute_hash(prompt: str, size: str, model: str, quality: str) -> str:
    """Deterministic 16-char hex hash; identical (prompt, size, model, quality)
    gives the same blob, so repeat demo runs don't re-bill Foundry."""
    blob = f"{model}|{size}|{quality}|{prompt}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _cost_for(size: str, quality: str) -> float:
    """Look up the per-image cost. Falls back to the medium 1024 rate if the
    caller asks for an unlisted combination — better to log a sane number
    than to claim $0 on a real render."""
    return _PRICE_TABLE_USD.get((size, quality), _PRICE_TABLE_USD[("1024x1024", "medium")])


# ----------------------------------------------------------- lazy singletons


def _openai_client() -> AzureOpenAI:
    """Entra-ID-only — no API keys. Uses DefaultAzureCredential which picks
    up `az login` locally and managed identity in Container Apps."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=token_provider,
        # gpt-image-2 requires the 2025+ preview API surface; older
        # 2024-10-21 GA only knows about gpt-image-1.
        api_version=os.environ.get(
            "AZURE_OPENAI_IMAGE_API_VERSION", "2025-04-01-preview"
        ),
    )


def _blob_store() -> BlobStore:
    return BlobStore(
        connection_string=os.environ["AZURE_STORAGE_CONNECTION_STRING"],
        container=_BLOB_CONTAINER,
    )


# ----------------------------------------------------------- plain Python entry


def image_gen(
    *,
    prompt: str,
    size: str = _DEFAULT_SIZE,
    quality: str = _DEFAULT_QUALITY,
    model: str | None = None,
) -> ImageGenResult:
    """Plain Python entry point. Used by tests, the creative graph executor,
    and the MCP-tool wrapper below.

    Returns a SAS URL pointing at an Azure Blob containing the rendered PNG.
    On cache hit (same prompt+size+model+quality already rendered), no
    Foundry call is made and `cost_usd=0`, `cached=True`.

    Caller is expected to fall back to a cached SVG fixture on
    `result_type="failure"` (see agent_creative_stub for the pattern).
    The MCP boundary stays clean: this tool only knows about real Foundry,
    fixture knowledge lives in the caller. Same shape Adobe Firefly /
    Runway / Veo will land in.
    """
    chosen_model = model or os.environ.get(
        "AZURE_OPENAI_IMAGE_DEPLOYMENT", _DEFAULT_MODEL
    )

    if not is_configured():
        if os.environ.get("CREATIVE_REAL_FOUNDRY", "").strip() not in (
            "1", "true", "TRUE"
        ):
            return ImageGenResult(
                result_type="failure",
                error="CREATIVE_REAL_FOUNDRY not set — caller should fall back to canned fixtures",
                error_code="unconfigured",
            )
        missing = [
            v
            for v in ("AZURE_OPENAI_ENDPOINT", "AZURE_STORAGE_CONNECTION_STRING")
            if not os.environ.get(v)
        ]
        return ImageGenResult(
            result_type="failure",
            error=f"unconfigured: {', '.join(missing)}",
            error_code="unconfigured",
        )

    sha = _compute_hash(prompt, size, chosen_model, quality)
    bs = _blob_store()
    blob_name = f"{sha}.png"

    # Blob existence IS the cache. No sqlite layer — the SAS URL is
    # regenerated on every call so we never hand back an expired link.
    if bs.exists(blob_name):
        return ImageGenResult(
            result_type="success",
            image_url=bs.sas_url(blob_name, ttl_seconds=_SAS_TTL_S),
            cached=True,
            cost_usd=0.0,
            prompt_hash=sha,
        )

    # Real Foundry call.
    try:
        resp = _openai_client().images.generate(
            model=chosen_model,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
        )
    except BadRequestError as e:
        # gpt-image-2 RAI rejection — surface a structured error code so
        # the orchestrator can raise the `creative.content_safety.rejected`
        # workflow exception (TASK-018, the Stage-7 demo beat).
        # The Foundry SDK puts the safety code in three different places
        # depending on SDK version + how it was raised; sniff all of them.
        msg = str(e) or getattr(e, "message", "") or ""
        body = getattr(e, "body", None) or {}
        body_err = body.get("error", {}) if isinstance(body, dict) else {}
        body_code = (body_err.get("code") or "") if isinstance(body_err, dict) else ""
        sniff = " ".join(str(x) for x in (msg, body_code, getattr(e, "code", "") or ""))
        if (
            "content_filter" in sniff
            or "content_policy" in sniff
            or "moderation" in sniff
            or "safety" in sniff.lower()
        ):
            return ImageGenResult(
                result_type="failure",
                error=f"gpt-image-2 RAI rejected prompt: {msg[:200]}",
                error_code="content_safety_rejection",
                prompt_hash=sha,
            )
        return ImageGenResult(
            result_type="failure",
            error=f"image generation failed: {msg[:200]}",
            error_code="api_error",
            prompt_hash=sha,
        )
    except Exception as e:  # noqa: BLE001 — unknown Foundry SDK errors
        return ImageGenResult(
            result_type="failure",
            error=f"image generation failed: {e}",
            error_code="api_error",
            prompt_hash=sha,
        )

    img = resp.data[0]
    b64 = getattr(img, "b64_json", None)
    if not b64:
        return ImageGenResult(
            result_type="failure",
            error="gpt-image-2 returned no b64_json payload",
            error_code="api_error",
            prompt_hash=sha,
        )
    img_bytes = base64.b64decode(b64)

    bs.put(blob_name, img_bytes, content_type="image/png")
    cost = _cost_for(size, quality)

    return ImageGenResult(
        result_type="success",
        image_url=bs.sas_url(blob_name, ttl_seconds=_SAS_TTL_S),
        cached=False,
        cost_usd=cost,
        prompt_hash=sha,
        revised_prompt=getattr(img, "revised_prompt", None),
    )


# ---------------------------------------------------------------- MCP surface


class _ImageGenParams(BaseModel):
    prompt: str = Field(
        description=(
            "Text prompt for the image. gpt-image-2 follows brand briefs well "
            "but rewrites prompts for safety; check `revised_prompt` in the "
            "response if the output drifted."
        ),
    )
    size: str = Field(
        default=_DEFAULT_SIZE,
        description=(
            "Image size. One of: 1024x1024, 1024x1536 (portrait), 1536x1024 "
            "(landscape). Defaults to 1024x1024."
        ),
    )
    quality: str = Field(
        default=_DEFAULT_QUALITY,
        description=(
            "Render quality: low (~$0.01/img, draft), medium (~$0.04/img, "
            "default for concept tiles), high (~$0.17/img, hero stills only)."
        ),
    )


@define_tool(
    name="image_gen",
    description=(
        "Generate an image with Foundry gpt-image-2 and stash it in Azure Blob. "
        "Returns a 24h SAS URL the Control Plane can render in concept tiles "
        "and storyboard strips. Cached by sha256(prompt|size|model|quality) so "
        "repeat demo runs don't re-bill. Content-safety rejections surface as "
        "`error_code=content_safety_rejection` for the orchestrator to convert "
        "into a workflow exception."
    ),
)
@traced_tool("image_gen")
def image_gen_tool(params: _ImageGenParams) -> ToolResult:
    result = image_gen(
        prompt=params.prompt,
        size=params.size,
        quality=params.quality,
    )
    # Stamp cost on the active span so the credibility-friday economics
    # consumer (Phase 2) sees real $-figures per render.
    try:
        from opentelemetry import trace as _trace
        span = _trace.get_current_span()
        if span and span.is_recording() and result.cost_usd:
            span.set_attribute("tool.cost.usd", float(result.cost_usd))
            span.set_attribute("tool.cache.hit", bool(result.cached))
    except Exception:
        pass

    if result.result_type != "success":
        return ToolResult(
            text_result_for_llm=f"image_gen failed: {result.error}",
            result_type="failure",
            error=result.error,
        )
    return ToolResult(
        text_result_for_llm=json.dumps(
            {
                "image_url": result.image_url,
                "cached": result.cached,
                "cost_usd": result.cost_usd,
                "prompt_hash": result.prompt_hash,
                "revised_prompt": result.revised_prompt,
            }
        )
    )
