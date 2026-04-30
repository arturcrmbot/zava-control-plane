from __future__ import annotations

import os
from pathlib import Path

# Both FastAPI and the Azure Functions worker import this module and read env
# vars at AppState construction. FastAPI's main.py already loads .env before
# this import, but the Functions worker only sees `local.settings.json` + the
# system env — without an explicit load here it would miss .env-only vars
# (ACS_EMAIL_CONNECTION_STRING, AZURE_STORAGE_CONNECTION_STRING, etc.) and
# the Phase 6 send_screen_email_activity would silently fall through to the
# offline outbox even when ACS Email is configured.
from dotenv import load_dotenv

load_dotenv()

from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.audit_logger import AuditLogger
from api.server.services.sse_hub import SSEHub
from api.server.services.magic_link import MagicLinkStore
from api.server.services.email_send import EmailSender


# Local artefact roots — magic-link sqlite, email outbox, blob fallback dir.
# All under ./data/portal/ so the demo can `ls` the artefacts in one place.
_PORTAL_DATA_DIR = Path(os.getenv("PORTAL_DATA_DIR", "data/portal"))
_PORTAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _build_blob_store():
    """Lazy: only construct BlobStore if a connection string is configured.

    The candidate-portal /apply route requires it, but most non-portal
    demos run without Azurite. Returning None is fine — /apply will surface
    a 503 if the dependency is missing.
    """
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        return None
    try:
        from api.server.services.blob_store import BlobStore
        return BlobStore(
            connection_string=conn,
            container=os.getenv("PORTAL_CV_CONTAINER", "portal-cvs"),
        )
    except Exception as exc:  # pragma: no cover — surfaces in startup logs
        print(f"[state] BlobStore init failed: {exc}")
        return None


class AppState:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.store = StateStore()
        self.audit = AuditLogger()
        self.hub = SSEHub()
        self.orchestration_history: dict[str, list[dict]] = {}
        # ----------------------------------------------------- candidate portal
        # MagicLinkStore: sqlite-backed, single-use offer tokens + repeatable
        # status tokens. File lives at data/portal/magic_links.sqlite.
        self.magic_links = MagicLinkStore(
            db_path=_PORTAL_DATA_DIR / "magic_links.sqlite",
        )
        # EmailSender: ACS Email REST when configured, outbox-only fallback
        # otherwise. Always writes the HTML body to the outbox so the demo
        # can inspect what was sent.
        self.email_sender = EmailSender(
            connection_string=os.getenv("ACS_EMAIL_CONNECTION_STRING"),
            sender_address=os.getenv("ACS_EMAIL_SENDER_ADDRESS"),
            outbox_dir=_PORTAL_DATA_DIR / "email_outbox",
        )
        # BlobStore: optional — only present when AZURE_STORAGE_CONNECTION_STRING
        # is set (Azurite locally, real Storage in cloud).
        self.blob_store = _build_blob_store()


app_state = AppState()
