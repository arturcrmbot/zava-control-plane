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
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class EmailSendError(Exception):
    """Raised when the real-network ACS Email send fails (4xx/5xx)."""


_ACS_API_VERSION = "2023-03-31"

# Two ACS Email failure modes were tripping up the demo:
#   1. Duplicate emails on replay. Sync bus handlers re-fire the shortlist /
#      offer / application-received emails for the same (candidate, scope)
#      whenever a workflow event re-emits (durable replay, ramp restart,
#      operator re-triggers). ACS sees the burst as identical sends back-to-
#      back and rate-limits us with 429.
#   2. Bursts when many workflows enter the same phase together (e.g.
#      Constellation Mode flips PERSONA_AUTO_CLOSE on and 5+ HIRE workflows
#      auto-resolve to the offer phase within ms of each other). One 429
#      previously was fatal because there was no retry path.
#
# DEDUPE_TTL_SECONDS guards (1): if the same candidate gets the same subject
# within the window, the second call no-ops and returns the original
# message_id. ACS_RETRY_BACKOFF_SECONDS guards (2): on 429 we sleep and try
# again; only after the final retry do we raise.
DEDUPE_TTL_SECONDS = 60.0
ACS_RETRY_BACKOFF_SECONDS = (2.0, 5.0)


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
        # Idempotency cache: (candidate_id, subject) -> (last_message_id, ts).
        # Cleared opportunistically on every send by walking entries older
        # than DEDUPE_TTL_SECONDS. Lock guards the dict because FastAPI runs
        # sync bus handlers in a threadpool and bus subscribers can fire
        # concurrently.
        self._dedupe: dict[tuple[str, str], tuple[str, float]] = {}
        self._dedupe_lock = threading.Lock()

    def _dedupe_key(self, *, to: str, subject: str, candidate_id: str | None) -> tuple[str, str]:
        # Prefer candidate_id when present (stable identity); fall back to
        # the recipient address so non-candidate sends still dedupe.
        ident = candidate_id or to
        return (ident, subject)

    def _check_dedupe(
        self, *, to: str, subject: str, candidate_id: str | None
    ) -> str | None:
        """Return a previously-sent message_id if the same logical email
        was sent within DEDUPE_TTL_SECONDS, else None."""
        now = time.time()
        key = self._dedupe_key(to=to, subject=subject, candidate_id=candidate_id)
        with self._dedupe_lock:
            # Cheap cleanup of expired entries.
            stale = [k for k, (_mid, ts) in self._dedupe.items() if now - ts > DEDUPE_TTL_SECONDS]
            for k in stale:
                self._dedupe.pop(k, None)
            entry = self._dedupe.get(key)
            if entry is None:
                return None
            mid, ts = entry
            if now - ts > DEDUPE_TTL_SECONDS:
                self._dedupe.pop(key, None)
                return None
            return mid

    def _record_dedupe(
        self, *, to: str, subject: str, candidate_id: str | None, message_id: str
    ) -> None:
        key = self._dedupe_key(to=to, subject=subject, candidate_id=candidate_id)
        with self._dedupe_lock:
            self._dedupe[key] = (message_id, time.time())

    def send(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        candidate_id: str | None = None,
    ) -> str:
        # Idempotency guard. If the same logical email was sent within the
        # window, no-op and return the original id. This is the primary fix
        # for the ACS 429 storms we hit on replay/restart.
        cached_id = self._check_dedupe(to=to, subject=subject, candidate_id=candidate_id)
        if cached_id is not None:
            print(f"[email] dedupe hit: skip send to={to!r} subject={subject!r} "
                  f"candidate={candidate_id!r} → {cached_id}")
            return cached_id

        if self.connection_string is None:
            message_id = f"local-{uuid.uuid4().hex}"
            self._write_outbox(message_id, html_body)
            self._write_meta(message_id, to=to, subject=subject, candidate_id=candidate_id)
            self._record_dedupe(to=to, subject=subject, candidate_id=candidate_id, message_id=message_id)
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

        # Retry-with-backoff loop. Only retries on 429 (rate limit) and
        # transient httpx transport errors; any other 4xx/5xx fails fast.
        # Headers (date, signature, repeatability id) are recomputed on each
        # attempt so the HMAC signature stays valid past the first try.
        backoffs = list(ACS_RETRY_BACKOFF_SECONDS) + [None]  # final attempt has no sleep after
        last_error: str | None = None
        for attempt_idx, backoff in enumerate(backoffs):
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
                last_error = f"transport error: {exc}"
                if backoff is not None:
                    print(f"[email] attempt {attempt_idx + 1} transport error → sleep {backoff}s and retry")
                    time.sleep(backoff)
                    continue
                raise EmailSendError(f"ACS Email transport error after retries: {exc}") from exc

            if resp.status_code == 429:
                last_error = f"429 throttled: {resp.text[:200]}"
                if backoff is not None:
                    print(f"[email] attempt {attempt_idx + 1} got 429 → sleep {backoff}s and retry")
                    time.sleep(backoff)
                    continue
                raise EmailSendError(
                    f"ACS Email throttled (429) after {len(backoffs)} attempts: {resp.text[:200]}"
                )

            if resp.status_code >= 400:
                # Non-retriable client/server error — fail fast.
                raise EmailSendError(
                    f"ACS Email returned {resp.status_code}: {resp.text}"
                )

            # Success path.
            try:
                payload = resp.json()
            except Exception as exc:  # pragma: no cover — defensive
                raise EmailSendError(f"ACS Email non-JSON response: {resp.text}") from exc

            message_id = payload.get("id") or f"local-{uuid.uuid4().hex}"
            self._write_outbox(message_id, html_body)
            self._write_meta(message_id, to=to, subject=subject, candidate_id=candidate_id)
            self._record_dedupe(to=to, subject=subject, candidate_id=candidate_id, message_id=message_id)
            return message_id

        # Defensive — the loop above always returns or raises.
        raise EmailSendError(f"ACS Email exhausted retries: {last_error or 'unknown'}")

    def _write_outbox(self, message_id: str, html_body: str) -> None:
        path = self.outbox_dir / f"{message_id}.html"
        path.write_text(html_body, encoding="utf-8")

    def _write_meta(
        self,
        message_id: str,
        *,
        to: str,
        subject: str,
        candidate_id: str | None,
    ) -> None:
        # Sidecar JSON so the recruiter UI can list emails sent per candidate
        # without parsing HTML. Best-effort — never raises.
        try:
            path = self.outbox_dir / f"{message_id}.json"
            path.write_text(
                json.dumps({
                    "id": message_id,
                    "to": to,
                    "subject": subject,
                    "candidate_id": candidate_id,
                    "sent_at": time.time(),
                }),
                encoding="utf-8",
            )
        except Exception:  # pragma: no cover
            pass

    def list_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Return metadata + html_body for every email persisted for this
        candidate, newest-first. Skips legacy files without a sidecar JSON.
        """
        rows: list[dict[str, Any]] = []
        if not self.outbox_dir.exists():
            return rows
        for meta_path in self.outbox_dir.glob("*.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if meta.get("candidate_id") != candidate_id:
                continue
            html_path = self.outbox_dir / f"{meta['id']}.html"
            html_body = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
            rows.append({
                "id": meta["id"],
                "to": meta.get("to", ""),
                "subject": meta.get("subject", ""),
                "sent_at": meta.get("sent_at", 0),
                "html_body": html_body,
            })
        rows.sort(key=lambda r: r.get("sent_at", 0), reverse=True)
        return rows
