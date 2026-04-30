# HeyGen (real avatar) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the canned-mp4 stub in `mocks/heygen-mcp` (or its MCP-tool consumer `heygen_render`) with a real call to the HeyGen API. Preserve the existing MCP tool contract so that `onboarding-buddy` SKILL.md is unchanged. Cache rendered videos in Azure Blob keyed by sha256(script) + avatar_id; surface the resulting URL on the workflow so the candidate portal `/portal?token=xxx` can play it at Onboarding phase.

**Architecture:** The MCP tool is the seam. `api/server/mcp_tools/heygen_render.py` is rewritten to: (1) cache lookup by content hash; (2) on miss, POST to HeyGen render endpoint, poll until complete, download mp4; (3) upload to Azure Blob; (4) return SAS URL. The `mocks/heygen-mcp` Node mock stays in the repo as a test/dev fallback gated by `HEYGEN_TRANSPORT=mock|real`.

**Tech Stack:** HeyGen REST API (v2 streaming-avatar or render API — confirm in Phase 0), `httpx` for HTTP, `azure-storage-blob` for upload, sha256 cache key.

**Master spec:** [docs/superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md) §6

---

## Phase 0 — Discovery

### Task 0.1: Read the HeyGen API docs

- [ ] **Use Context7** to fetch the latest HeyGen API docs (`mcp__plugin_context7_context7__resolve-library-id` for "heygen", then query-docs). Confirm:
  - Render endpoint path + auth (API-key header)
  - Request shape: `{script, avatar_id, voice_id?, ...}`
  - Response shape: synchronous (returns mp4 URL) or asynchronous (returns job_id, poll a status endpoint)?
  - Polling cadence + typical render time (the user has hands-on familiarity — note their ballpark)
  - Webhook callback support (preferred over polling if available)
  - Rate limits / cost per render
  - Avatar id to use for the demo (default vs custom)

- [ ] **Confirm API key from the user**

  > Ask once: "Drop the HeyGen API key into `.env` as `HEYGEN_API_KEY` — let me know when it's set."

  Do NOT echo the key in the plan; do NOT commit `.env`.

- [ ] **Decide: poll or webhook?**

  If poll: typical timeout? max attempts? backoff?
  If webhook: where does the callback land — new FastAPI route `/api/heygen/render-complete/{job_id}`? Then we need a render-job tracking table.

- [ ] **Capture decisions inline below in Phase 1 tasks before writing code.**

### Task 0.2: Read the existing MCP tool

- [ ] **Read `api/server/mcp_tools/ocr_extract.py`** as the canonical pattern — it's the most recent "MCP tool wrapping a real Azure service with sha256-cache" example. Mirror its shape.

- [ ] **Read `api/server/mcp_tools/__init__.py`** to confirm registration pattern.

- [ ] **Read the existing `mocks/heygen-mcp/index.js`** (if it's a Node mock) or whatever the current `heygen_render` MCP tool is. Note the request/response shape it currently honours so the new real version matches.

- [ ] **Document the current MCP tool's Pydantic schema** — in `api/server/mcp_tools/heygen_render.py` if it exists today, or in `mocks/heygen-mcp/` if it lives there.

---

## Phase 1 — Backend implementation

### Task 1: Render-cache table (TDD)

**Files:**
- Modify: `api/server/services/eval_store.py` OR create a new `api/server/services/render_cache.py` (decide based on whether sqlite consolidation matters)
- Test: `tests/api/server/services/test_render_cache.py`

(Recommend a separate `render_cache.py` since render entries are unrelated to evals — stay focused.)

- [ ] **Step 1: Write tests**

```python
# tests/api/server/services/test_render_cache.py
def test_lookup_miss_returns_none(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    assert cache.lookup(content_hash="abc", avatar_id="welcome-default") is None

def test_put_then_lookup_hits(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(content_hash="abc", avatar_id="welcome-default", blob_name="abc.mp4", blob_url="https://...")
    row = cache.lookup(content_hash="abc", avatar_id="welcome-default")
    assert row["blob_url"].startswith("https://")
```

- [ ] **Step 2: Implement `RenderCache`** — single-table sqlite, schema `(content_hash, avatar_id, blob_name, blob_url, rendered_at)` with primary key `(content_hash, avatar_id)`.

- [ ] **Step 3: Tests pass; commit**

```
git commit -m "feat(heygen): sqlite-backed render cache by sha256+avatar_id"
```

### Task 2: HeyGen client (TDD with respx)

**Files:**
- Create: `api/server/services/heygen_client.py`
- Test: `tests/api/server/services/test_heygen_client.py`

The exact shape depends on Phase 0 discovery; below assumes the **async-job + polling** pattern (most likely for video render).

- [ ] **Step 1: Write tests with respx**

```python
import respx, httpx
from api.server.services.heygen_client import HeyGenClient

@respx.mock
def test_render_polls_until_complete_and_returns_mp4_bytes():
    respx.post("https://api.heygen.com/v2/video/generate").mock(
        return_value=httpx.Response(200, json={"data": {"video_id": "vid-1"}}),
    )
    statuses = iter([
        httpx.Response(200, json={"data": {"status": "processing"}}),
        httpx.Response(200, json={"data": {"status": "processing"}}),
        httpx.Response(200, json={"data": {"status": "completed", "video_url": "https://example/v.mp4"}}),
    ])
    respx.get("https://api.heygen.com/v1/video_status.get").mock(side_effect=lambda req: next(statuses))
    respx.get("https://example/v.mp4").mock(return_value=httpx.Response(200, content=b"\x00\x00\x00\x18ftyp"))

    client = HeyGenClient(api_key="x", poll_interval_s=0.0, max_polls=10)
    mp4 = client.render(script="welcome", avatar_id="default")
    assert mp4.startswith(b"\x00\x00\x00\x18ftyp")

@respx.mock
def test_render_raises_on_render_failure():
    respx.post(...).mock(return_value=httpx.Response(200, json={"data": {"video_id": "vid-x"}}))
    respx.get(...).mock(return_value=httpx.Response(200, json={"data": {"status": "failed", "error": "bad input"}}))
    with pytest.raises(HeyGenRenderError):
        HeyGenClient(api_key="x", poll_interval_s=0.0).render(script="x", avatar_id="d")

@respx.mock
def test_render_raises_on_poll_timeout():
    respx.post(...).mock(return_value=httpx.Response(200, json={"data": {"video_id": "vid-x"}}))
    respx.get(...).mock(return_value=httpx.Response(200, json={"data": {"status": "processing"}}))
    with pytest.raises(HeyGenRenderTimeout):
        HeyGenClient(api_key="x", poll_interval_s=0.0, max_polls=2).render(script="x", avatar_id="d")
```

- [ ] **Step 2: Implement `HeyGenClient`** per the docs read in Phase 0. Concrete URLs/payload shapes get plugged in once docs confirmed.

```python
# api/server/services/heygen_client.py
from __future__ import annotations
import time
import httpx


class HeyGenRenderError(Exception): ...
class HeyGenRenderTimeout(Exception): ...


class HeyGenClient:
    def __init__(self, *, api_key: str, base_url: str = "https://api.heygen.com",
                 poll_interval_s: float = 5.0, max_polls: int = 60):
        self._api_key = api_key
        self._base = base_url
        self._poll = poll_interval_s
        self._max_polls = max_polls
        self._http = httpx.Client(headers={"X-Api-Key": api_key}, timeout=30.0)

    def render(self, *, script: str, avatar_id: str, voice_id: str | None = None) -> bytes:
        payload = {"video_inputs": [{"avatar": {"avatar_id": avatar_id, "voice_id": voice_id}, "script": {"type": "text", "input": script}}]}
        r = self._http.post(f"{self._base}/v2/video/generate", json=payload)
        r.raise_for_status()
        video_id = r.json()["data"]["video_id"]

        for _ in range(self._max_polls):
            status_r = self._http.get(f"{self._base}/v1/video_status.get", params={"video_id": video_id})
            status_r.raise_for_status()
            data = status_r.json()["data"]
            if data["status"] == "completed":
                mp4 = self._http.get(data["video_url"]).content
                return mp4
            if data["status"] == "failed":
                raise HeyGenRenderError(data.get("error", "render failed"))
            time.sleep(self._poll)
        raise HeyGenRenderTimeout(video_id)
```

(Adjust URL paths and payload shape per Phase 0 docs read.)

- [ ] **Step 3: Tests pass; commit**

```
git commit -m "feat(heygen): HTTP client wrapping the render API with polling"
```

### Task 3: MCP tool — `heygen_render`

**Files:**
- Modify or create: `api/server/mcp_tools/heygen_render.py`
- Test: `tests/api/server/mcp_tools/test_heygen_render.py`
- Modify: `api/server/mcp_tools/__init__.py` (registration if needed)

- [ ] **Step 1: Read `api/server/mcp_tools/ocr_extract.py`** as the pattern. It exposes `@define_tool`, has `is_configured()`, and returns Pydantic-modelled results.

- [ ] **Step 2: Write tests**

```python
def test_heygen_render_cache_hit_returns_blob_url_without_calling_api(monkeypatch):
    """Cache hit → no HTTP, no Blob put, just return URL."""
    cache = RenderCache(...); cache.put(content_hash=..., avatar_id=..., blob_name=..., blob_url="https://cached")
    monkeypatch.setattr("api.server.mcp_tools.heygen_render._render_cache", lambda: cache)
    monkeypatch.setattr("api.server.mcp_tools.heygen_render._heygen_client", lambda: pytest.fail("should not be called"))
    result = heygen_render(script="welcome", avatar_id="default")
    assert result.video_url == "https://cached"
    assert result.cached is True

def test_heygen_render_cache_miss_renders_uploads_caches(monkeypatch, tmp_path):
    """Cache miss → render → upload to blob → cache → return URL."""
    ...

def test_heygen_render_returns_failure_when_unconfigured():
    """No HEYGEN_API_KEY → return failure result, not raise."""
    ...
```

- [ ] **Step 3: Implement**

```python
# api/server/mcp_tools/heygen_render.py
"""HeyGen video-avatar render — MCP tool surface.

Cached by sha256(script) + avatar_id. Cache hit → return the existing Blob
SAS URL. Cache miss → render via HeyGen API, upload mp4 to Azure Blob,
persist cache entry, return the new SAS URL.
"""
from __future__ import annotations
import hashlib
import os
from copilot.tools import define_tool
from pydantic import BaseModel

from api.server.services.heygen_client import HeyGenClient, HeyGenRenderError, HeyGenRenderTimeout
from api.server.services.blob_store import BlobStore
from api.server.services.render_cache import RenderCache


class HeyGenRenderResult(BaseModel):
    result_type: str       # "success" | "failure"
    video_url: str | None = None
    cached: bool = False
    error: str | None = None


_BLOB_CONTAINER = "heygen-renders"
_SAS_TTL_S = 24 * 3600


def is_configured() -> bool:
    return bool(os.environ.get("HEYGEN_API_KEY")) and bool(os.environ.get("AZURE_STORAGE_CONNECTION_STRING"))


@define_tool(name="heygen_render", description="Render an avatar video from script + avatar_id. Returns a video URL.")
def heygen_render(script: str, avatar_id: str = "welcome-default") -> HeyGenRenderResult:
    if not is_configured():
        return HeyGenRenderResult(result_type="failure", error="HEYGEN_API_KEY or AZURE_STORAGE_CONNECTION_STRING not set")

    sha = hashlib.sha256(script.encode("utf-8")).hexdigest()[:16]
    cache = _render_cache()
    blob_name = f"{sha}-{avatar_id}.mp4"
    cached = cache.lookup(content_hash=sha, avatar_id=avatar_id)
    if cached is not None:
        return HeyGenRenderResult(result_type="success", video_url=cached["blob_url"], cached=True)

    try:
        mp4 = _heygen_client().render(script=script, avatar_id=avatar_id)
    except HeyGenRenderError as e:
        return HeyGenRenderResult(result_type="failure", error=f"render failed: {e}")
    except HeyGenRenderTimeout as e:
        return HeyGenRenderResult(result_type="failure", error=f"render timeout: {e}")

    bs = _blob_store()
    bs.put(blob_name, mp4, content_type="video/mp4")
    sas = bs.sas_url(blob_name, ttl_seconds=_SAS_TTL_S)
    cache.put(content_hash=sha, avatar_id=avatar_id, blob_name=blob_name, blob_url=sas)
    return HeyGenRenderResult(result_type="success", video_url=sas, cached=False)


# Lazy singletons — avoid import-time side effects so unconfigured envs don't crash.
def _heygen_client():
    return HeyGenClient(api_key=os.environ["HEYGEN_API_KEY"])

def _blob_store():
    return BlobStore(connection_string=os.environ["AZURE_STORAGE_CONNECTION_STRING"], container=_BLOB_CONTAINER)

def _render_cache():
    from api.server.services.render_cache import RenderCache
    return RenderCache(db_path="data/.heygen/cache.sqlite")
```

- [ ] **Step 4: Register the tool** alongside `ocr_extract` in `mcp_tools/__init__.py`.

- [ ] **Step 5: Tests pass; commit**

```
git commit -m "feat(heygen): real HeyGen MCP tool with sha256+blob cache"
```

### Task 4: `onboarding-buddy` skill — no contract change

**Files:** `api/server/skills/onboarding-buddy/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md.** Confirm `allowed-tools: heygen_render, ...` already lists the tool. If yes — **no edits needed**. The skill becomes more powerful for free.

- [ ] **Step 2: If the skill currently calls a `heygen_render` mock-shaped tool with a different signature**, adapt one or the other to match. Prefer adapting the skill (caller side).

- [ ] **Step 3: Commit if any edits were needed**

### Task 5: Phase 10 onboarding graph stores `video_url` on workflow

**Files:** `api/functions/graphs/onboarding.py`

- [ ] **Step 1: Read the current graph.** Identify the executor that calls `heygen_render`.

- [ ] **Step 2: Capture the `video_url` from the tool result and write it onto the workflow ledger** so the portal can read it via `/api/portal/status/{token}`:

```python
# inside onboarding graph executor — pseudo-code
result = ctx.tools.heygen_render(script=welcome_script, avatar_id=avatar_for_role(role))
if result.result_type == "success":
    ctx.state["onboarding_video_url"] = result.video_url
else:
    ctx.state["onboarding_video_url"] = None
    log.warning("HeyGen render failed: %s", result.error)
```

- [ ] **Step 3: Tests + commit**

```
git commit -m "feat(heygen): Phase 10 persists video_url for portal display"
```

---

## Phase 2 — Demo robustness

### Task 6: Pre-render hook for demo cache warming

**Files:** New script `scripts/prewarm_heygen.py`

- [ ] **Step 1: Write a CLI** that takes `(script, avatar_id)` pairs from a fixture file (`data/synthetic/hiring/onboarding_scripts.json`) and calls `heygen_render` for each, populating the cache.

- [ ] **Step 2: Document in `docs/poc2-DEMO.md` §0 Pre-flight**

```
# Pre-render demo onboarding videos (cache warm)
python scripts/prewarm_heygen.py
```

- [ ] **Step 3: Commit**

```
git commit -m "feat(heygen): pre-warm script for demo cache"
```

### Task 7: Failure surface

**Files:** `docs/poc2-DEMO.md`

- [ ] Add row to §3 Failure surfaces:

```
| HeyGen render fails / times out | Real HeyGen API issue | Fall back to canned mp4 by setting HEYGEN_TRANSPORT=mock; restart the workflow's onboarding phase. |
```

- [ ] Add `HEYGEN_TRANSPORT` env var support to the MCP tool — short-circuit the `is_configured()` path to the existing mock when `HEYGEN_TRANSPORT=mock`.

---

## Acceptance criteria

- [ ] `is_configured()` returns true when `HEYGEN_API_KEY` + `AZURE_STORAGE_CONNECTION_STRING` are set
- [ ] Cache hit returns the cached blob URL without calling HeyGen
- [ ] Cache miss renders, uploads to Blob, persists cache, returns SAS URL
- [ ] `onboarding-buddy` SKILL.md unchanged; the skill produces a real avatar mp4 URL on Phase 10 entry
- [ ] Portal `/portal?token=xxx` plays the video at Onboarding phase
- [ ] `HEYGEN_TRANSPORT=mock` falls back to the existing canned mp4
- [ ] `scripts/prewarm_heygen.py` populates the cache for the demo's expected scripts

## Out of scope

- HeyGen interactive avatar (live two-way) — out for this engagement; pre-rendered video is enough for Onboarding
- Custom avatar training
- Multi-language avatars (single locale for the demo)
- Avatar lip-sync customisation beyond defaults

## Dependencies on other streams

- **Candidate portal** owns `/portal?token=xxx` rendering of the video — needs to read `onboarding_video_url` from `/api/portal/status/{token}`. The portal stream already wires that.
- **Voice real** is independent.
- **AG-UI render** is independent.
- **Blob storage service** (`api/server/services/blob_store.py`) — owned by the candidate portal stream as Task 3 there. This stream consumes it. If the portal stream lands first, no extra work; if not, this stream may need to land `blob_store.py` itself.
