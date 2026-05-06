"""Tests for the image_gen MCP tool (POC3, Foundry gpt-image-2).

Mirrors the shape of test_avatar_render.py:
- cache hit returns blob URL without calling Foundry
- cache miss generates, uploads, returns SAS URL
- unconfigured env returns structured failure
- content-safety rejection surfaces the right error_code
- CREATIVE_REAL_FOUNDRY=0 short-circuits is_configured
"""
from __future__ import annotations

import base64

import httpx
import pytest
from openai import BadRequestError, RateLimitError

from api.server.mcp_tools import image_gen


# ------------------------------------------------------------------ helpers


def _bad_request(message: str, *, code: str | None = None) -> BadRequestError:
    """Build a BadRequestError with a real httpx Response so str(e) and
    e.body work the same way they do against live Foundry."""
    req = httpx.Request("POST", "https://example.com/v1/images/generations")
    resp = httpx.Response(400, request=req)
    body: dict = {"error": {"message": message}}
    if code:
        body["error"]["code"] = code
    return BadRequestError(message=message, response=resp, body=body)


def _rate_limit(retry_after: int = 30) -> RateLimitError:
    """Build a RateLimitError with a real httpx Response carrying
    Retry-After. Mirrors what gpt-image-2 returns when over quota."""
    req = httpx.Request("POST", "https://example.com/v1/images/generations")
    resp = httpx.Response(429, headers={"retry-after": str(retry_after)}, request=req)
    body: dict = {"error": {"code": "RateLimitReached", "message": "throttled"}}
    return RateLimitError(message="rate limited", response=resp, body=body)


# ------------------------------------------------------------------ helpers


def _set_real_env(monkeypatch):
    """Flip the env flags so is_configured() returns True."""
    monkeypatch.setenv("CREATIVE_REAL_FOUNDRY", "1")
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT", "https://example.cognitiveservices.azure.com"
    )
    monkeypatch.setenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=Zm9v;"
        "EndpointSuffix=core.windows.net",
    )


class _FakeBlob:
    """Stand-in for BlobStore. `existing` controls cache-hit semantics."""

    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = set(existing or ())
        self.calls: list[tuple] = []

    def exists(self, name: str) -> bool:
        self.calls.append(("exists", name))
        return name in self.existing

    def put(self, name: str, data: bytes, *, content_type: str) -> str:
        self.calls.append(("put", name, len(data), content_type))
        self.existing.add(name)
        return f"https://blob.example/{name}"

    def sas_url(self, name: str, *, ttl_seconds: int) -> str:
        self.calls.append(("sas_url", name, ttl_seconds))
        return f"https://blob.example/{name}?sas=signed"


# ------------------------------------------------------------------ tests


def test_image_gen_unconfigured_when_flag_not_set(monkeypatch):
    """Default state is canned-fixture; the MCP returns a structured failure
    that the caller (agent_creative_stub) reads to fall back."""
    monkeypatch.delenv("CREATIVE_REAL_FOUNDRY", raising=False)
    result = image_gen.image_gen(prompt="anything")
    assert result.result_type == "failure"
    assert result.error_code == "unconfigured"


def test_image_gen_unconfigured_when_env_missing(monkeypatch):
    """Flag set but Foundry / Storage env not — surface which one is missing."""
    monkeypatch.setenv("CREATIVE_REAL_FOUNDRY", "1")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    result = image_gen.image_gen(prompt="x")
    assert result.result_type == "failure"
    assert result.error_code == "unconfigured"
    assert "AZURE_OPENAI_ENDPOINT" in (result.error or "")


def test_image_gen_cache_hit_skips_foundry(monkeypatch):
    """Blob existence is the cache. Hit ⇒ no openai client instantiation."""
    _set_real_env(monkeypatch)
    monkeypatch.setattr(
        image_gen, "_compute_hash", lambda prompt, size, model, quality: "abc123"
    )
    fake = _FakeBlob(existing={"abc123.png"})
    monkeypatch.setattr(image_gen, "_blob_store", lambda: fake)
    monkeypatch.setattr(
        image_gen,
        "_openai_client",
        lambda: pytest.fail("should not call Foundry on cache hit"),
    )

    result = image_gen.image_gen(prompt="a luxe fragrance bottle on marble")
    assert result.result_type == "success"
    assert result.cached is True
    assert result.cost_usd == 0.0
    assert result.image_url == "https://blob.example/abc123.png?sas=signed"
    assert result.prompt_hash == "abc123"


def test_image_gen_cache_miss_calls_foundry_uploads_returns_sas(monkeypatch):
    _set_real_env(monkeypatch)
    monkeypatch.setattr(
        image_gen, "_compute_hash", lambda prompt, size, model, quality: "fresh1"
    )
    fake = _FakeBlob(existing=set())
    monkeypatch.setattr(image_gen, "_blob_store", lambda: fake)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 64

    class _FakeImage:
        b64_json = base64.b64encode(png_bytes).decode("ascii")
        revised_prompt = "a luxe fragrance bottle on marble (rewritten for safety)"

    class _FakeResp:
        data = [_FakeImage()]

    generate_calls: list[dict] = []

    class _FakeImages:
        def generate(self, **kw):
            generate_calls.append(kw)
            return _FakeResp()

    class _FakeClient:
        images = _FakeImages()

    monkeypatch.setattr(image_gen, "_openai_client", lambda: _FakeClient())

    result = image_gen.image_gen(
        prompt="a luxe fragrance bottle on marble",
        size="1024x1024",
        quality="medium",
    )

    assert result.result_type == "success"
    assert result.cached is False
    assert result.image_url == "https://blob.example/fresh1.png?sas=signed"
    assert result.prompt_hash == "fresh1"
    assert result.cost_usd == pytest.approx(0.042)
    assert "rewritten" in (result.revised_prompt or "")

    # Foundry was called once with the right shape
    assert len(generate_calls) == 1
    assert generate_calls[0]["model"] == "gpt-image-2"
    assert generate_calls[0]["prompt"].startswith("a luxe fragrance")
    assert generate_calls[0]["size"] == "1024x1024"
    assert generate_calls[0]["quality"] == "medium"
    assert generate_calls[0]["n"] == 1

    # Blob received put then sas_url; raw bytes (not base64) were uploaded
    put_call = next(c for c in fake.calls if c[0] == "put")
    assert put_call[1] == "fresh1.png"
    assert put_call[2] == len(png_bytes)
    assert put_call[3] == "image/png"


def test_image_gen_content_safety_rejection_surfaces_error_code(monkeypatch):
    """gpt-image-2 RAI rejection ⇒ result_type=failure, error_code=
    content_safety_rejection so the orchestrator can raise the
    `creative.content_safety.rejected` workflow exception (TASK-018)."""
    _set_real_env(monkeypatch)
    monkeypatch.setattr(
        image_gen, "_compute_hash", lambda prompt, size, model, quality: "rai1"
    )
    monkeypatch.setattr(image_gen, "_blob_store", lambda: _FakeBlob())

    class _FakeImages:
        def generate(self, **kw):
            # Mimic the actual Azure OpenAI BadRequestError shape; the
            # message contains 'content_filter' which is what we sniff for.
            raise _bad_request(
                "Your prompt was flagged by content_filter policy.",
                code="content_filter",
            )

    class _FakeClient:
        images = _FakeImages()

    monkeypatch.setattr(image_gen, "_openai_client", lambda: _FakeClient())

    result = image_gen.image_gen(prompt="something disallowed")
    assert result.result_type == "failure"
    assert result.error_code == "content_safety_rejection"
    assert result.prompt_hash == "rai1"


def test_image_gen_generic_api_error_surfaces_api_error_code(monkeypatch):
    """Non-RAI BadRequestError still fails but with a different code so
    the orchestrator routes it differently (retry vs. exception)."""
    _set_real_env(monkeypatch)
    monkeypatch.setattr(
        image_gen, "_compute_hash", lambda prompt, size, model, quality: "err1"
    )
    monkeypatch.setattr(image_gen, "_blob_store", lambda: _FakeBlob())

    class _FakeImages:
        def generate(self, **kw):
            raise _bad_request("invalid size param", code="invalid_request_error")

    class _FakeClient:
        images = _FakeImages()

    monkeypatch.setattr(image_gen, "_openai_client", lambda: _FakeClient())

    result = image_gen.image_gen(prompt="ok prompt", size="999x999")
    assert result.result_type == "failure"
    assert result.error_code == "api_error"


def test_image_gen_cost_table_returns_known_rates():
    """The price table must cover the three sizes × three quality tiers we
    actually use; medium 1024 is the concept-tile default."""
    assert image_gen._cost_for("1024x1024", "low") == pytest.approx(0.011)
    assert image_gen._cost_for("1024x1024", "medium") == pytest.approx(0.042)
    assert image_gen._cost_for("1024x1024", "high") == pytest.approx(0.167)
    # Unlisted combination falls back to medium 1024 — keeps the cost
    # ledger sane rather than logging $0 for a real render.
    assert image_gen._cost_for("nonexistent", "weird") == pytest.approx(0.042)


def test_compute_hash_is_deterministic_and_input_sensitive():
    """Same inputs ⇒ same hash; any input change ⇒ different hash. This is
    what makes blob existence a safe cache."""
    h1 = image_gen._compute_hash("luxe bottle", "1024x1024", "gpt-image-2", "medium")
    h2 = image_gen._compute_hash("luxe bottle", "1024x1024", "gpt-image-2", "medium")
    assert h1 == h2
    # Each input field changes the hash
    assert h1 != image_gen._compute_hash("luxe bottle ", "1024x1024", "gpt-image-2", "medium")
    assert h1 != image_gen._compute_hash("luxe bottle", "1024x1536", "gpt-image-2", "medium")
    assert h1 != image_gen._compute_hash("luxe bottle", "1024x1024", "gpt-image-1", "medium")
    assert h1 != image_gen._compute_hash("luxe bottle", "1024x1024", "gpt-image-2", "high")


# ------------------------------------------------------------------ conn-string


def test_augment_azurite_conn_string_adds_missing_endpoints():
    """Azurite-shaped conn string with only BlobEndpoint gets queue/table
    endpoints derived (10000 -> 10001/10002)."""
    cs = (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=KEY==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )
    out = image_gen._augment_azurite_conn_string(cs)
    assert "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1" in out
    assert "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1" in out
    # Original parts preserved
    assert "AccountName=devstoreaccount1" in out
    assert "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1" in out


def test_augment_azurite_conn_string_noop_when_complete():
    """Already-complete Azurite conn string passes through unchanged."""
    cs = (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=KEY==;"
        "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
        "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;"
        "TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
    )
    assert image_gen._augment_azurite_conn_string(cs) == cs


def test_augment_azurite_conn_string_noop_for_real_azure():
    """Real Azure storage uses EndpointSuffix; never augment those — we
    don't want to derive non-Azurite endpoints from a real BlobEndpoint."""
    cs = (
        "DefaultEndpointsProtocol=https;AccountName=apexdemo;"
        "AccountKey=REAL==;EndpointSuffix=core.windows.net;"
    )
    assert image_gen._augment_azurite_conn_string(cs) == cs


# ------------------------------------------------------------------ rate limit


def test_image_gen_429_then_success_succeeds(monkeypatch):
    """One 429 then a 200 ⇒ retry path catches the 429, sleeps the
    retry-after, retries, returns success. The activity caller should
    never see the 429 in this case."""
    _set_real_env(monkeypatch)
    monkeypatch.setenv("AZURE_OPENAI_IMAGE_RETRY_BUDGET_S", "5")
    monkeypatch.setattr(
        image_gen, "_compute_hash", lambda prompt, size, model, quality: "rl1"
    )
    fake = _FakeBlob(existing=set())
    monkeypatch.setattr(image_gen, "_blob_store", lambda: fake)

    # Sleep is mocked so the test runs in microseconds, not 30s.
    sleeps: list[float] = []
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: sleeps.append(s))

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"y" * 32

    class _FakeImage:
        b64_json = base64.b64encode(png_bytes).decode("ascii")
        revised_prompt = None

    class _FakeResp:
        data = [_FakeImage()]

    call_log: list[str] = []

    class _FakeImages:
        def generate(self, **kw):
            call_log.append("call")
            if len(call_log) == 1:
                raise _rate_limit(retry_after=2)
            return _FakeResp()

    class _FakeClient:
        images = _FakeImages()

    monkeypatch.setattr(image_gen, "_openai_client", lambda: _FakeClient())

    result = image_gen.image_gen(prompt="anything", quality="low")
    assert result.result_type == "success"
    assert result.cached is False
    assert len(call_log) == 2  # one 429, one success
    assert sleeps == [2]  # honoured retry-after


def test_image_gen_429_persistent_exceeds_budget_returns_rate_limited(monkeypatch):
    """Persistent 429s past the retry budget ⇒ structured rate_limited
    error so the caller falls back to fixture rather than hanging."""
    _set_real_env(monkeypatch)
    monkeypatch.setenv("AZURE_OPENAI_IMAGE_RETRY_BUDGET_S", "5")
    monkeypatch.setattr(
        image_gen, "_compute_hash", lambda prompt, size, model, quality: "rl2"
    )
    monkeypatch.setattr(image_gen, "_blob_store", lambda: _FakeBlob())

    import time as _time
    sleeps: list[float] = []
    monkeypatch.setattr(_time, "sleep", lambda s: sleeps.append(s))

    class _FakeImages:
        def generate(self, **kw):
            # Each call asks us to wait 60s — fits one retry then we're
            # out of the 5s budget on the second 429.
            raise _rate_limit(retry_after=60)

    class _FakeClient:
        images = _FakeImages()

    monkeypatch.setattr(image_gen, "_openai_client", lambda: _FakeClient())

    result = image_gen.image_gen(prompt="anything", quality="low")
    assert result.result_type == "failure"
    assert result.error_code == "rate_limited"
    assert result.prompt_hash == "rl2"
    # No sleeps — first 429's retry-after (60s) already exceeds the
    # 5s budget, so we bail without sleeping.
    assert sleeps == []
