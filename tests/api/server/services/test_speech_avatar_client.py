"""Tests for the Azure Speech batch avatar synthesis client."""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from api.server.services.speech_avatar_client import (
    AvatarRenderError,
    AvatarRenderTimeout,
    SpeechAvatarClient,
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
    statuses = iter(
        [
            httpx.Response(200, json={"id": "job-1", "status": "Running"}),
            httpx.Response(200, json={"id": "job-1", "status": "Running"}),
            httpx.Response(
                200,
                json={
                    "id": "job-1",
                    "status": "Succeeded",
                    "outputs": {"result": "https://blob.example/out.mp4?sig=xyz"},
                },
            ),
        ]
    )
    respx.get(url__regex=rf"{_BASE}/avatar/batchsyntheses/.+").mock(
        side_effect=lambda req: next(statuses),
    )
    # The mp4 download
    respx.get(url__startswith="https://blob.example/").mock(
        return_value=httpx.Response(200, content=b"\x00\x00\x00\x18ftypisom"),
    )

    with patch.object(SpeechAvatarClient, "_token", lambda self: "fake-token"):
        client = SpeechAvatarClient(region=_REGION, poll_interval_s=0.0, max_polls=10)
        mp4 = client.render(
            script="welcome", avatar_character="lisa", voice="en-US-JennyNeural"
        )

    assert mp4.startswith(b"\x00\x00\x00\x18ftyp")


@respx.mock
def test_render_raises_on_failed_status():
    respx.put(url__regex=rf"{_BASE}/avatar/.+").mock(
        return_value=httpx.Response(201, json={"id": "j", "status": "NotStarted"}),
    )
    respx.get(url__regex=rf"{_BASE}/avatar/.+").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "j",
                "status": "Failed",
                "properties": {
                    "error": {"code": "BadRequest", "message": "voice not available"}
                },
            },
        ),
    )
    with patch.object(SpeechAvatarClient, "_token", lambda self: "x"):
        with pytest.raises(AvatarRenderError):
            SpeechAvatarClient(region=_REGION, poll_interval_s=0.0).render(
                script="x", avatar_character="lisa", voice="en-US-JennyNeural"
            )


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
            SpeechAvatarClient(
                region=_REGION, poll_interval_s=0.0, max_polls=2
            ).render(
                script="x", avatar_character="lisa", voice="en-US-JennyNeural"
            )
