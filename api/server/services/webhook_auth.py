"""Shared HMAC-SHA256 signature verification for inbound webhooks (§4.6).

Used by the ServiceNow IT-Ops and Finance-BP Adaptive-Card webhooks. Each
provider has its own shared-secret env var; the body bytes are HMAC'd with
SHA-256 and compared in constant time against the provider-supplied header.

Production wires the secrets through Key Vault; locally they're plain env vars
listed in `.env.example`.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import HTTPException


def verify_hmac_signature(
    *,
    secret_env: str,
    signature: str | None,
    body: bytes,
) -> None:
    """Verify *signature* is a hex HMAC-SHA256 of *body* under env *secret_env*.

    Raises ``HTTPException(401)`` if the secret env var is unset, the header is
    missing, or the digest does not match. Comparison uses
    :func:`hmac.compare_digest` for constant-time equality.

    A leading ``"sha256="`` prefix on the supplied signature is tolerated to
    match the convention used by GitHub-style webhooks.
    """
    secret = os.getenv(secret_env)
    if not secret:
        raise HTTPException(status_code=401, detail="webhook_secret_not_configured")
    if not signature:
        raise HTTPException(status_code=401, detail="missing_signature")

    provided = signature[len("sha256="):] if signature.startswith("sha256=") else signature
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="invalid_signature")
