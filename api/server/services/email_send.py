"""ACS Email REST sender for candidate-portal magic-link delivery.

Real-network branch: HMAC-sign the request, POST against the ACS Email
endpoint extracted from the connection string, return the server message id.

Fallback branch (connection_string is None): write the HTML body to
outbox_dir/{message_id}.html, return f"local-{uuid}".

Both branches always persist the HTML body to outbox_dir/{message_id}.html so
the demo can inspect what was sent.

Reference:
- https://learn.microsoft.com/en-us/rest/api/communication/email/email/send
- https://learn.microsoft.com/en-us/azure/communication-services/tutorials/hmac-header-tutorial
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class EmailSendError(Exception):
    """Raised when the real-network ACS Email send fails (4xx/5xx)."""


_ACS_API_VERSION = "2023-03-31"


def _parse_connection_string(conn: str) -> tuple[str, str]:
    """Parse an ACS connection string into (endpoint, access_key).

    Connection strings look like:
        endpoint=https://x.communication.azure.com/;accesskey=AAAA
    """
    parts: dict[str, str] = {}
    for segment in conn.split(";"):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        key, _, value = segment.partition("=")
        parts[key.strip().lower()] = value.strip()
    endpoint = parts.get("endpoint")
    access_key = parts.get("accesskey")
    if not endpoint or not access_key:
        raise ValueError(
            "ACS connection string missing endpoint= or accesskey="
        )
    return endpoint.rstrip("/"), access_key


def _format_rfc1123(dt: datetime) -> str:
    """Format a UTC datetime in RFC1123 form independent of locale."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    utc = dt.utctimetuple()
    return (
        f"{days[utc.tm_wday]}, {utc.tm_mday:02d} {months[utc.tm_mon - 1]}"
        f" {utc.tm_year:04d} {utc.tm_hour:02d}:{utc.tm_min:02d}:"
        f"{utc.tm_sec:02d} GMT"
    )


def _content_hash(body: bytes) -> str:
    return base64.b64encode(hashlib.sha256(body).digest()).decode("utf-8")


def _sign(string_to_sign: str, secret_b64: str) -> str:
    decoded = base64.b64decode(secret_b64)
    digest = hmac.new(
        decoded, string_to_sign.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


class EmailSender:
    """Send transactional email via ACS Email REST.

    When `connection_string` is None we run in offline mode: we never make a
    network call, we mint a `local-<uuid>` message id, and we always persist
    the HTML body to `outbox_dir/{message_id}.html`.
    """

    def __init__(
        self,
        *,
        connection_string: str | None,
        sender_address: str | None,
        outbox_dir: str | Path,
    ) -> None:
        self.connection_string = connection_string
        self.sender_address = sender_address
        self.outbox_dir = Path(outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def send(self, *, to: str, subject: str, html_body: str) -> str:
        if self.connection_string is None:
            message_id = f"local-{uuid.uuid4().hex}"
            self._write_outbox(message_id, html_body)
            return message_id

        endpoint, access_key = _parse_connection_string(self.connection_string)
        path_and_query = f"/emails:send?api-version={_ACS_API_VERSION}"
        url = f"{endpoint}{path_and_query}"

        body: dict[str, Any] = {
            "senderAddress": self.sender_address,
            "content": {"subject": subject, "html": html_body},
            "recipients": {"to": [{"address": to}]},
        }
        body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")

        host = urlparse(endpoint).netloc
        date = _format_rfc1123(datetime.now(timezone.utc))
        chash = _content_hash(body_bytes)
        string_to_sign = f"POST\n{path_and_query}\n{date};{host};{chash}"
        signature = _sign(string_to_sign, access_key)
        authorization = (
            "HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256"
            f"&Signature={signature}"
        )

        headers = {
            "Content-Type": "application/json",
            "x-ms-date": date,
            "x-ms-content-sha256": chash,
            "Authorization": authorization,
            "repeatability-request-id": str(uuid.uuid4()),
            "repeatability-first-sent": date,
        }

        try:
            resp = httpx.post(
                url, content=body_bytes, headers=headers, timeout=30.0
            )
        except httpx.HTTPError as exc:
            raise EmailSendError(f"ACS Email transport error: {exc}") from exc

        if resp.status_code >= 400:
            raise EmailSendError(
                f"ACS Email returned {resp.status_code}: {resp.text}"
            )

        try:
            payload = resp.json()
        except Exception as exc:  # pragma: no cover — defensive
            raise EmailSendError(f"ACS Email non-JSON response: {resp.text}") from exc

        message_id = payload.get("id") or f"local-{uuid.uuid4().hex}"
        self._write_outbox(message_id, html_body)
        return message_id

    def _write_outbox(self, message_id: str, html_body: str) -> None:
        path = self.outbox_dir / f"{message_id}.html"
        path.write_text(html_body, encoding="utf-8")
