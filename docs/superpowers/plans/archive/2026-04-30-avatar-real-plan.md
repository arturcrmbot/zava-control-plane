# Avatar (real, via Azure AI Speech batch synthesis) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the canned-mp4 stub in `mocks/heygen-mcp` with a real call to Azure AI Speech batch avatar synthesis, behind a new `avatar_render` MCP tool. Preserve the contract that `onboarding-buddy` skill expects (text-script-in, video-URL-out). Cache rendered videos in Azure Blob keyed by sha256(script) + avatar character + voice. Surface the resulting URL on the workflow so the candidate portal `/portal?token=xxx` plays it at the Onboarding phase.

**Architecture:** The MCP tool is the seam. `api/server/mcp_tools/avatar_render.py` is a new tool that: (1) cache lookup by content hash; (2) on miss, POST to Azure Speech batch-synthesis endpoint, poll until complete, download mp4; (3) upload to Azure Blob; (4) return SAS URL. Auth uses `DefaultAzureCredential` consistent with `ocr_extract` (tenant policy disables key auth on Cognitive Services). The existing `mocks/heygen-mcp` Node mock stays as a test/dev fallback gated by `AVATAR_TRANSPORT=mock|real`.

**Tech Stack:** Azure AI Speech batch avatar synthesis REST API (under Azure Cognitive Services), `httpx` for HTTP, `azure-identity` for `DefaultAzureCredential` (already in deps), `azure-storage-blob` for upload (added in pre-scaffolding commit), sha256 cache key.

**Why Azure Speech (not HeyGen):** All-Microsoft narrative for the Zava demo; same Azure subscription, same auth (Entra ID via `DefaultAzureCredential`); no third-party API key. Tradeoff: avatar polish slightly behind HeyGen's premium tier, but more than enough for a 30-second onboarding welcome video.

**Master spec:** [docs/superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md) §6

---

## Phase 0 — Discovery

### Task 0.1: Verify the Azure Speech batch avatar API contract

The exact endpoint paths, payload shape, and response schema MUST be confirmed before writing code. The plan uses placeholder URLs that work as of late 2025; verify against current docs.

- [ ] **Use Context7** to fetch Azure Speech docs: `mcp__plugin_context7_context7__resolve-library-id` for "azure-cognitiveservices-speech" or "azure-speech-services", then query-docs for "batch avatar synthesis". If Context7 doesn't have it, WebFetch:
  - https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-synthesis-avatar
  - https://learn.microsoft.com/en-us/azure/ai-services/speech-service/text-to-speech-avatar/batch-synthesis-avatar-properties

- [ ] **Confirm the URL shape.** As of late 2025 the batch endpoint is roughly:
  - Submit job: `POST https://{region}.api.cognitive.microsoft.com/avatar/batchsyntheses/{job_id}?api-version=2024-08-01` (PUT with a server-assigned id is also valid)
  - Poll status: `GET https://{region}.api.cognitive.microsoft.com/avatar/batchsyntheses/{job_id}?api-version=2024-08-01`
  - Download: when `status == "Succeeded"`, the response includes `outputs.result` with a SAS-protected mp4 URL

- [ ] **Confirm payload shape:**

```json
{
  "synthesisConfig": {
    "voice": "en-US-JennyNeural"
  },
  "inputKind": "PlainText",
  "inputs": [{"content": "Welcome to your new role at Zava, Alice. ..."}],
  "avatarConfig": {
    "talkingAvatarCharacter": "lisa",
    "talkingAvatarStyle": "graceful-sitting",
    "videoFormat": "mp4",
    "videoCodec": "h264",
    "subtitleType": "soft_embedded"
  }
}
```

  Adjust per actual docs.

- [ ] **Confirm available avatars.** Prebuilt as of 2025: `lisa`, `harry`, `lori`, `max`, `jeff`, `meg`. Each has style variants (e.g. lisa supports `graceful-sitting`, `casual-sitting`, `technical-sitting`, `technical-standing`).

- [ ] **Confirm auth model.** Cognitive Services in Microsoft tenant has key-auth disabled by tenant policy (per the `ocr_extract` precedent). So:
  - Use `DefaultAzureCredential` from `azure-identity` (already a dep)
  - Get a token for resource `https://cognitiveservices.azure.com/.default`
  - Pass as `Authorization: Bearer <token>` header
  - The signed-in identity (or managed identity in cloud) needs the **"Cognitive Services Speech User"** role on the resource

- [ ] **Confirm typical render latency.** Per docs, batch synthesis for a 30-second avatar segment typically completes in 1-3 minutes wall-clock. Plan poll cadence accordingly (e.g. 10s interval, 60 max polls = 10 min ceiling).

- [ ] **Confirm cost.** Azure AI Speech batch avatar synthesis is billed per character (text input) and per second of output. Document in the plan for the demo's expected scripts (~150 chars × 6 candidates × 1 render each ≈ trivial).

- [ ] **Capture any deviations** from the plan's assumed contract inline below in Phase 1 tasks before writing code.

### Task 0.2: Read the existing MCP-tool patterns

- [ ] **Read `api/server/mcp_tools/ocr_extract.py`** as the canonical pattern. It's the most recent "MCP tool wrapping a real Azure Cognitive Service with Entra-ID auth + sha256-cache" example. Mirror its shape (lazy singletons, `is_configured()`, Pydantic result envelope).

- [ ] **Read `api/server/mcp_tools/__init__.py`** to confirm registration pattern.

- [ ] **Read the existing `mocks/heygen-mcp/index.js`** — note the request/response shape it currently honours so the new real tool stays compatible enough that `onboarding-buddy` doesn't need rewiring.

- [ ] **Read `api/server/skills/onboarding-buddy/SKILL.md`** — note which tool name it calls (`heygen_render` historically, will become `avatar_render`). The skill's `allowed-tools:` frontmatter needs to match.

---

## Phase 1 — Backend implementation

### Task 1: Render-cache table (TDD)

**Files:**
- Modify: `api/server/services/render_cache.py` (currently a skeleton from pre-scaffolding commit 42713b07)
- Test: `tests/api/server/services/test_render_cache.py` (NEW)

- [ ] **Step 1: Write tests**

```python
# tests/api/server/services/test_render_cache.py
from api.server.services.render_cache import RenderCache


def test_lookup_miss_returns_none(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    assert cache.lookup(content_hash="abc", avatar_id="lisa") is None


def test_put_then_lookup_hits(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(
        content_hash="abc", avatar_id="lisa",
        blob_name="abc.mp4", blob_url="https://example/abc.mp4",
    )
    row = cache.lookup(content_hash="abc", avatar_id="lisa")
    assert row["blob_url"] == "https://example/abc.mp4"


def test_put_overwrites_same_key(tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(content_hash="abc", avatar_id="lisa", blob_name="x.mp4", blob_url="u1")
    cache.put(content_hash="abc", avatar_id="lisa", blob_name="x.mp4", blob_url="u2")
    assert cache.lookup(content_hash="abc", avatar_id="lisa")["blob_url"] == "u2"
```

- [ ] **Step 2: Run tests — confirm FAIL (NotImplementedError)**

- [ ] **Step 3: Implement `RenderCache`**

Single-table sqlite, schema `(content_hash, avatar_id, blob_name, blob_url, rendered_at)` with primary key `(content_hash, avatar_id)`. Upsert semantics on `put`.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```
git commit -m "feat(avatar): sqlite-backed render cache by sha256+avatar_id"
```

### Task 2: Azure Speech client (TDD with respx)

**Files:**
- Create: `api/server/services/speech_avatar_client.py`
- Test: `tests/api/server/services/test_speech_avatar_client.py`

- [ ] **Step 1: Write tests**

```python
import json
from unittest.mock import patch
import pytest
import respx
import httpx

from api.server.services.speech_avatar_client import (
    SpeechAvatarClient, AvatarRenderError, AvatarRenderTimeout,
)


_REGION = "eastus"
_BASE = f"https://{_REGION}.api.cognitive.microsoft.com"


@respx.mock
def test_render_polls_until_succeeded_and_returns_mp4_bytes():
    # PUT submits the job
    respx.put(url__regex=rf"{_BASE}/avatar/batchsyntheses/.+").mock(
        return_value=httpx.Response(201, json={"id": "job-1", "status": "NotStarted"}),
    )
    # GET polls status — three calls: Running, Running, Succeeded
    statuses = iter([
        httpx.Response(200, json={"id": "job-1", "status": "Running"}),
        httpx.Response(200, json={"id": "job-1", "status": "Running"}),
        httpx.Response(200, json={"id": "job-1", "status": "Succeeded",
            "outputs": {"result": "https://blob/example.mp4?sig=..."}}),
    ])
    respx.get(url__regex=rf"{_BASE}/avatar/batchsyntheses/.+").mock(
        side_effect=lambda req: next(statuses),
    )
    # The mp4 download
    respx.get(url__startswith="https://blob/").mock(
        return_value=httpx.Response(200, content=b"\x00\x00\x00\x18ftyp"),
    )

    with patch.object(SpeechAvatarClient, "_token", lambda self: "fake-token"):
        client = SpeechAvatarClient(region=_REGION, poll_interval_s=0.0, max_polls=10)
        mp4 = client.render(script="welcome", avatar_character="lisa", voice="en-US-JennyNeural")

    assert mp4.startswith(b"\x00\x00\x00\x18ftyp")


@respx.mock
def test_render_raises_on_failed_status():
    respx.put(url__regex=rf"{_BASE}/avatar/.+").mock(
        return_value=httpx.Response(201, json={"id": "j", "status": "NotStarted"}),
    )
    respx.get(url__regex=rf"{_BASE}/avatar/.+").mock(
        return_value=httpx.Response(200, json={"id": "j", "status": "Failed",
            "properties": {"error": {"code": "BadRequest", "message": "voice not available"}}}),
    )
    with patch.object(SpeechAvatarClient, "_token", lambda self: "x"):
        with pytest.raises(AvatarRenderError):
            SpeechAvatarClient(region=_REGION, poll_interval_s=0.0).render(
                script="x", avatar_character="lisa", voice="en-US-JennyNeural")


@respx.mock
def test_render_raises_on_poll_timeout():
    respx.put(url__regex=rf"{_BASE}/avatar/.+").mock(
        return_value=httpx.Response(201, json={"id": "j", "status": "NotStarted"}),
    )
    respx.get(url__regex=rf"{_BASE}/avatar/.+").mock(
        return_value=httpx.Response(200, json={"id": "j", "status": "Running"}),
    )
    with patch.object(SpeechAvatarClient, "_token", lambda self: "x"):
        with pytest.raises(AvatarRenderTimeout):
            SpeechAvatarClient(region=_REGION, poll_interval_s=0.0, max_polls=2).render(
                script="x", avatar_character="lisa", voice="en-US-JennyNeural")
```

- [ ] **Step 2: Implement `SpeechAvatarClient`**

```python
# api/server/services/speech_avatar_client.py
"""Azure AI Speech batch avatar synthesis client.

Submit a script + avatar character + voice. Poll until Succeeded. Download
the resulting mp4. Auth via DefaultAzureCredential (Entra ID) — tenant policy
disables key-auth on Cognitive Services, so we follow the same pattern as
ocr_extract.py.

Reference:
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/batch-synthesis-avatar
"""
from __future__ import annotations
import time
import uuid

import httpx
from azure.identity import DefaultAzureCredential


_API_VERSION = "2024-08-01"
_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


class AvatarRenderError(Exception): ...
class AvatarRenderTimeout(Exception): ...


class SpeechAvatarClient:
    def __init__(
        self,
        *,
        region: str,
        poll_interval_s: float = 10.0,
        max_polls: int = 60,
    ):
        self._region = region
        self._base = f"https://{region}.api.cognitive.microsoft.com"
        self._poll = poll_interval_s
        self._max_polls = max_polls
        self._cred = DefaultAzureCredential()

    def _token(self) -> str:
        return self._cred.get_token(_TOKEN_SCOPE).token

    def render(
        self,
        *,
        script: str,
        avatar_character: str = "lisa",
        avatar_style: str = "graceful-sitting",
        voice: str = "en-US-JennyNeural",
    ) -> bytes:
        job_id = uuid.uuid4().hex
        url = f"{self._base}/avatar/batchsyntheses/{job_id}?api-version={_API_VERSION}"
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }
        payload = {
            "synthesisConfig": {"voice": voice},
            "inputKind": "PlainText",
            "inputs": [{"content": script}],
            "avatarConfig": {
                "talkingAvatarCharacter": avatar_character,
                "talkingAvatarStyle": avatar_style,
                "videoFormat": "mp4",
                "videoCodec": "h264",
                "subtitleType": "soft_embedded",
            },
        }

        with httpx.Client(timeout=60.0) as http:
            r = http.put(url, json=payload, headers=headers)
            if r.status_code >= 400:
                raise AvatarRenderError(f"submit failed: {r.status_code} {r.text}")

            for _ in range(self._max_polls):
                s = http.get(url, headers={"Authorization": f"Bearer {self._token()}"})
                if s.status_code >= 400:
                    raise AvatarRenderError(f"poll failed: {s.status_code} {s.text}")
                data = s.json()
                status = data.get("status")
                if status == "Succeeded":
                    result_url = (data.get("outputs") or {}).get("result")
                    if not result_url:
                        raise AvatarRenderError("no result url in succeeded response")
                    mp4 = http.get(result_url)
                    if mp4.status_code >= 400:
                        raise AvatarRenderError(f"mp4 download failed: {mp4.status_code}")
                    return mp4.content
                if status == "Failed":
                    err = ((data.get("properties") or {}).get("error") or {}).get("message", data)
                    raise AvatarRenderError(f"render failed: {err}")
                time.sleep(self._poll)
            raise AvatarRenderTimeout(job_id)
```

(Adjust URL paths and payload shape per Phase 0 docs read — the exact `2024-08-01` API version and the `outputs.result` shape may vary. Test against the real Azure Speech endpoint once provisioned.)

- [ ] **Step 3: Tests pass; commit**

```
git commit -m "feat(avatar): Azure Speech batch synthesis client"
```

### Task 3: MCP tool — `avatar_render`

**Files:**
- Create: `api/server/mcp_tools/avatar_render.py`
- Test: `tests/api/server/mcp_tools/test_avatar_render.py`
- Modify: `api/server/mcp_tools/__init__.py` (registration if needed)

- [ ] **Step 1: Read `api/server/mcp_tools/ocr_extract.py`** as the pattern. Confirm the registration helper, the Pydantic result type, lazy singleton pattern, and `is_configured()` shape.

- [ ] **Step 2: Write tests**

```python
def test_avatar_render_cache_hit_returns_blob_url_without_calling_api(monkeypatch, tmp_path):
    cache = RenderCache(db_path=tmp_path / "rc.sqlite")
    cache.put(content_hash="abc", avatar_id="lisa", blob_name="abc.mp4", blob_url="https://cached")
    monkeypatch.setattr(avatar_render, "_render_cache", lambda: cache)
    monkeypatch.setattr(avatar_render, "_speech_client",
                        lambda: pytest.fail("should not call client on cache hit"))
    monkeypatch.setattr(avatar_render, "_blob_store",
                        lambda: pytest.fail("should not upload on cache hit"))
    monkeypatch.setattr(avatar_render, "_compute_hash", lambda script: "abc")

    result = avatar_render.avatar_render(script="welcome", avatar_character="lisa")
    assert result.video_url == "https://cached"
    assert result.cached is True
    assert result.result_type == "success"


def test_avatar_render_cache_miss_renders_uploads_caches(monkeypatch, tmp_path):
    """Mock SpeechAvatarClient.render to return canned mp4 bytes; mock BlobStore.put + sas_url."""
    ...


def test_avatar_render_returns_failure_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    result = avatar_render.avatar_render(script="x", avatar_character="lisa")
    assert result.result_type == "failure"
    assert "AZURE_SPEECH_REGION" in (result.error or "")
```

- [ ] **Step 3: Implement**

```python
# api/server/mcp_tools/avatar_render.py
"""Azure AI Speech avatar video render — MCP tool surface.

Cached by sha256(script + voice) keyed against avatar character. Cache hit
returns the existing Blob SAS URL. Cache miss renders via Azure Speech batch
synthesis, uploads the mp4 to Azure Blob, persists the cache entry, returns
the new SAS URL.
"""
from __future__ import annotations
import hashlib
import os

from copilot.tools import define_tool
from pydantic import BaseModel

from api.server.services.speech_avatar_client import (
    SpeechAvatarClient, AvatarRenderError, AvatarRenderTimeout,
)
from api.server.services.blob_store import BlobStore
from api.server.services.render_cache import RenderCache


class AvatarRenderResult(BaseModel):
    result_type: str       # "success" | "failure"
    video_url: str | None = None
    cached: bool = False
    error: str | None = None


_BLOB_CONTAINER = "avatar-renders"
_SAS_TTL_S = 24 * 3600
_DEFAULT_VOICE = "en-US-JennyNeural"


def is_configured() -> bool:
    return bool(os.environ.get("AZURE_SPEECH_REGION")) and bool(os.environ.get("AZURE_STORAGE_CONNECTION_STRING"))


def _compute_hash(script: str, voice: str = _DEFAULT_VOICE) -> str:
    return hashlib.sha256(f"{voice}|{script}".encode("utf-8")).hexdigest()[:16]


@define_tool(
    name="avatar_render",
    description=(
        "Render an avatar video reading the given script. Uses Azure AI Speech batch "
        "avatar synthesis. Returns a video URL the candidate portal can play. Avatars: "
        "lisa, harry, lori, max, jeff, meg. Voices: any Azure Neural voice (default "
        "en-US-JennyNeural)."
    ),
)
def avatar_render(
    script: str,
    avatar_character: str = "lisa",
    avatar_style: str = "graceful-sitting",
    voice: str = _DEFAULT_VOICE,
) -> AvatarRenderResult:
    if not is_configured():
        missing = [v for v in ("AZURE_SPEECH_REGION", "AZURE_STORAGE_CONNECTION_STRING")
                   if not os.environ.get(v)]
        return AvatarRenderResult(result_type="failure",
                                  error=f"unconfigured: {', '.join(missing)}")

    sha = _compute_hash(script, voice)
    cache = _render_cache()
    blob_name = f"{sha}-{avatar_character}.mp4"
    cached = cache.lookup(content_hash=sha, avatar_id=avatar_character)
    if cached is not None:
        return AvatarRenderResult(result_type="success",
                                  video_url=cached["blob_url"], cached=True)

    try:
        mp4 = _speech_client().render(
            script=script,
            avatar_character=avatar_character,
            avatar_style=avatar_style,
            voice=voice,
        )
    except AvatarRenderError as e:
        return AvatarRenderResult(result_type="failure", error=f"render failed: {e}")
    except AvatarRenderTimeout as e:
        return AvatarRenderResult(result_type="failure", error=f"render timeout: {e}")

    bs = _blob_store()
    bs.put(blob_name, mp4, content_type="video/mp4")
    sas = bs.sas_url(blob_name, ttl_seconds=_SAS_TTL_S)
    cache.put(content_hash=sha, avatar_id=avatar_character,
              blob_name=blob_name, blob_url=sas)
    return AvatarRenderResult(result_type="success", video_url=sas, cached=False)


# Lazy singletons — keep import-time clean so unconfigured envs don't crash.
def _speech_client():
    return SpeechAvatarClient(region=os.environ["AZURE_SPEECH_REGION"])


def _blob_store():
    return BlobStore(connection_string=os.environ["AZURE_STORAGE_CONNECTION_STRING"],
                     container=_BLOB_CONTAINER)


def _render_cache():
    return RenderCache(db_path="data/.avatar/cache.sqlite")
```

- [ ] **Step 4: Register the tool** alongside `ocr_extract` in `mcp_tools/__init__.py`.

- [ ] **Step 5: Tests pass; commit**

```
git commit -m "feat(avatar): real Azure Speech MCP tool with sha256+blob cache"
```

### Task 4: `onboarding-buddy` skill — rename tool reference

**Files:** `api/server/skills/onboarding-buddy/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md.** Find the `allowed-tools:` frontmatter line — currently lists `heygen_render` (or a similar name).

- [ ] **Step 2: Replace `heygen_render` with `avatar_render`** in:
  - `allowed-tools:` frontmatter
  - Any procedural instructions in the body

- [ ] **Step 3: Commit**

```
git commit -m "feat(skill): onboarding-buddy calls avatar_render (was heygen_render)"
```

### Task 5: Phase 10 onboarding graph stores `video_url` on workflow

**Files:** `api/functions/graphs/onboarding.py`

- [ ] **Step 1: Read the current graph.** Identify the executor that calls the avatar tool.

- [ ] **Step 2: Capture the `video_url` from the tool result and write it onto the workflow's `metadata.onboarding_video_url`** so the portal can read it via `/api/portal/status/{token}` (look at `routes/portal.py::status` to confirm where this is read from):

```python
# inside onboarding graph executor — pseudo-code
result = ctx.tools.avatar_render(
    script=welcome_script,
    avatar_character=avatar_for_role(role),
)
if result.result_type == "success":
    ctx.state.setdefault("metadata", {})["onboarding_video_url"] = result.video_url
else:
    log.warning("avatar render failed: %s", result.error)
```

- [ ] **Step 3: Tests + commit**

```
git commit -m "feat(avatar): Phase 10 persists video_url for portal display"
```

---

## Phase 2 — Demo robustness

### Task 6: Pre-render hook for demo cache warming

**Files:** New script `scripts/prewarm_avatar.py`

- [ ] **Step 1: Write a CLI** that takes `(script, avatar_character)` pairs from a fixture file (`data/synthetic/hiring/onboarding_scripts.json`) and calls `avatar_render` for each, populating the cache.

- [ ] **Step 2: Document in `docs/poc2-DEMO.md` §0 Pre-flight**

```
# Pre-render demo onboarding videos (cache warm)
uv run python scripts/prewarm_avatar.py
```

- [ ] **Step 3: Commit**

```
git commit -m "feat(avatar): pre-warm script for demo cache"
```

### Task 7: Failure surface

**Files:** `docs/poc2-DEMO.md`

- [ ] Add row to §3 Failure surfaces:

```
| Avatar render fails / times out | Real Azure Speech API issue | Set AVATAR_TRANSPORT=mock; the mocks/heygen-mcp canned mp4 plays instead. |
```

- [ ] Add `AVATAR_TRANSPORT` env-var support to the MCP tool — short-circuit `is_configured()` to fall through to the existing mock when `AVATAR_TRANSPORT=mock`.

---

## Acceptance criteria

- [ ] `is_configured()` returns true when `AZURE_SPEECH_REGION` + `AZURE_STORAGE_CONNECTION_STRING` are set
- [ ] Cache hit returns the cached blob URL without calling Azure Speech
- [ ] Cache miss renders via Azure Speech, uploads to Blob, persists cache, returns SAS URL
- [ ] `onboarding-buddy` SKILL.md references `avatar_render` (not `heygen_render`); the skill produces a real avatar mp4 URL on Phase 10 entry
- [ ] Portal `/portal?token=xxx` plays the video at Onboarding phase
- [ ] `AVATAR_TRANSPORT=mock` falls back to the existing canned mp4
- [ ] `scripts/prewarm_avatar.py` populates the cache for the demo's expected scripts

## Out of scope

- Custom avatar training (custom-trained avatars)
- Real-time avatar (interactive — the Speech service supports it, but Phase 10 only needs batch)
- Multi-language avatars (single locale `en-US` for the demo)
- Lip-sync customisation beyond defaults

## Dependencies on other streams

- **Candidate portal** owns `/portal?token=xxx` rendering of the video — needs to read `onboarding_video_url` from `/api/portal/status/{token}`. The portal stream already wires that.
- **Voice real** is independent.
- **AG-UI render** is independent.
- **Blob storage service** (`api/server/services/blob_store.py`) — Subagent A's commit `58fa9337` landed this; this stream consumes it directly.

## Azure resources needed

| Resource | Purpose | Notes |
|---|---|---|
| Azure AI Speech / Cognitive Services | Avatar batch synthesis API | Provision in same tenant; signed-in identity needs **Cognitive Services Speech User** role |
| Azure Storage account | mp4 cache | Already provisioned for portal CV uploads — same `AZURE_STORAGE_CONNECTION_STRING` |

Single env var to add: `AZURE_SPEECH_REGION` (e.g. `eastus`).
