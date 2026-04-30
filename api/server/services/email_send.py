"""ACS Email REST sender for candidate portal magic-link delivery.

Skeleton — implemented by Stream 1 candidate-portal subagent (see
docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 2).

Real-network branch: HMAC-sign the request, POST against the ACS Email
endpoint extracted from the connection string, return the server message id.

Fallback branch (connection_string is None): write the HTML body to
outbox_dir/{message_id}.html, return f"local-{uuid}".
"""
from __future__ import annotations
from pathlib import Path


class EmailSendError(Exception):
    """Raised when the real-network ACS Email send fails (4xx/5xx)."""


class EmailSender:
    """Skeleton — see plan Task 2 for the implementation contract.

    Methods to implement:
        __init__(*, connection_string, sender_address, outbox_dir)
        send(*, to, subject, html_body) -> str    # returns message_id
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
        raise NotImplementedError("Stream 1 subagent: implement per plan Task 2")
