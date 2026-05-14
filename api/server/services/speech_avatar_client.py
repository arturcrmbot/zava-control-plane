"""Azure AI Speech batch avatar synthesis client.

Submit a script + avatar character + voice. Poll until Succeeded. Download
the resulting mp4. Auth via DefaultAzureCredential (Entra ID) — tenant policy
disables key-auth on Cognitive Services, so we follow the same pattern as
ocr_extract.py.

Reference (verified against learn.microsoft.com 2024-08-01 API):
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/text-to-speech-avatar/batch-synthesis-avatar

Endpoint shape:
    PUT  https://{region}.api.cognitive.microsoft.com/avatar/batchsyntheses/{job_id}?api-version=2024-08-01
    GET  https://{region}.api.cognitive.microsoft.com/avatar/batchsyntheses/{job_id}?api-version=2024-08-01
Statuses: NotStarted | Running | Succeeded | Failed
On Succeeded the result mp4 URL lands at `outputs.result`.
"""
from __future__ import annotations

import time
import uuid

import httpx
from azure.identity import DefaultAzureCredential


_API_VERSION = "2024-08-01"
_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


class AvatarRenderError(Exception):
    """Submit/poll/download failed, or the job ended in status=Failed."""


class AvatarRenderTimeout(Exception):
    """Polled `max_polls` times without reaching Succeeded/Failed."""


class SpeechAvatarClient:
    def __init__(
        self,
        *,
        region: str | None = None,
        endpoint: str | None = None,
        poll_interval_s: float = 10.0,
        max_polls: int = 60,
    ):
        # Token auth (DefaultAzureCredential) requires the Speech resource's
        # custom-subdomain endpoint, NOT the regional /api.cognitive.microsoft.com
        # form — Azure rejects bearer tokens on the regional endpoint with
        # "Please provide a custom subdomain for token authentication".
        # Prefer AZURE_SPEECH_ENDPOINT (https://<resource>.cognitiveservices.azure.com)
        # over the region; fall back to regional only if endpoint is unset.
        if endpoint:
            self._base = endpoint.rstrip("/")
        elif region:
            self._base = f"https://{region}.api.cognitive.microsoft.com"
        else:
            raise ValueError("SpeechAvatarClient needs endpoint or region")
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
        # Synthesis ID must be 3-64 chars, alphanumeric/-/_, start+end with
        # letter/number — uuid4 hex satisfies this.
        job_id = uuid.uuid4().hex
        url = (
            f"{self._base}/avatar/batchsyntheses/{job_id}"
            f"?api-version={_API_VERSION}"
        )
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
                "videoFormat": "Mp4",
                "videoCodec": "h264",
                "subtitleType": "soft_embedded",
            },
        }

        with httpx.Client(timeout=60.0) as http:
            r = http.put(url, json=payload, headers=headers)
            if r.status_code >= 400:
                raise AvatarRenderError(
                    f"submit failed: {r.status_code} {r.text}"
                )

            for _ in range(self._max_polls):
                s = http.get(
                    url, headers={"Authorization": f"Bearer {self._token()}"}
                )
                if s.status_code >= 400:
                    raise AvatarRenderError(
                        f"poll failed: {s.status_code} {s.text}"
                    )
                data = s.json()
                status = data.get("status")
                if status == "Succeeded":
                    result_url = (data.get("outputs") or {}).get("result")
                    if not result_url:
                        raise AvatarRenderError(
                            "no result url in succeeded response"
                        )
                    # Result URL is a pre-signed Blob SAS — DO NOT pass our
                    # Bearer token (Blob rejects it as 403 InvalidAuthentication).
                    mp4 = http.get(result_url, headers={})
                    if mp4.status_code >= 400:
                        raise AvatarRenderError(
                            f"mp4 download failed: {mp4.status_code} {mp4.text[:200]}"
                        )
                    return mp4.content
                if status == "Failed":
                    err = (
                        ((data.get("properties") or {}).get("error") or {})
                        .get("message", data)
                    )
                    raise AvatarRenderError(f"render failed: {err}")
                time.sleep(self._poll)
            raise AvatarRenderTimeout(job_id)
