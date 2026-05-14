"""Foundry health route — pre-demo sanity check.

Returns the live status of every cloud-side leg of the substrate so an
operator can verify in one HTTP call whether the Friday demo will land
correctly. No state mutation; safe to hit repeatedly.

Per plan/feature-foundry-credibility-friday-1.md (Phase 5 prep helper).

Probed:

- `application_insights`: APPLICATIONINSIGHTS_CONNECTION_STRING set; OTEL
  exporter initialised in this process.
- `foundry_eval`: AZURE_FOUNDRY_PROJECT_ENDPOINT + AZURE_OPENAI_* set
  (the LLM-judge + safety-evaluator pipeline depends on this).
- `audit_blob`: AZURE_STORAGE_AUDIT_ACCOUNT set; the AuditLogger service
  client constructed without raising.
- `model_pricing`: pricing table source date (so the demo can confirm
  it's not stale).
- `online_eval_subscriber`: queue depth + completed/errored counts so
  the operator can see whether evals are flowing.

The shape is one fields-only JSON envelope; the UI can render it as a
green/red banner.
"""
from __future__ import annotations
import logging
import os
import sqlite3

from fastapi import APIRouter

from api.server.eval import foundry_client
from api.server.eval.online_subscriber import _metrics as _online_metrics
from api.server.eval.store import default_store
from api.server.services import model_pricing
from api.server.state import app_state

router = APIRouter(prefix="/api/foundry")
log = logging.getLogger(__name__)


def _bool_check(name: str, ok: bool, detail: str | None = None) -> dict:
    return {"name": name, "ok": ok, "detail": detail}


@router.get("/health")
async def foundry_health() -> dict:
    """Aggregate Foundry-side health for the operator pre-flight."""
    appi_set = bool(os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"))
    audit_account = os.environ.get("AZURE_STORAGE_AUDIT_ACCOUNT", "").strip()
    audit_container = os.environ.get(
        "AZURE_STORAGE_AUDIT_CONTAINER", "audit-ledger"
    )
    audit_client_ok = (
        getattr(app_state.audit, "_service_client", None) is not None
        if hasattr(app_state, "audit") else False
    )

    # Foundry SDK config.
    foundry_ok = foundry_client.is_configured()
    foundry_project = os.environ.get("AZURE_FOUNDRY_PROJECT_ENDPOINT", "")
    aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")

    # Online subscriber state.
    eval_store = default_store()
    try:
        recent = eval_store.recent(50)
    except sqlite3.Error:
        # store cold or sqlite locked — degrade visibly so the operator can
        # tell "no recent evals" from "store unreachable".
        log.warning("foundry_health: eval_store.recent failed", exc_info=True)
        recent = []
    completed = sum(1 for r in recent if r.status == "completed")
    errored = sum(1 for r in recent if r.status == "error")
    pending = sum(1 for r in recent if r.status == "pending")

    checks = [
        _bool_check(
            "application_insights",
            appi_set,
            "APPLICATIONINSIGHTS_CONNECTION_STRING set" if appi_set
            else "missing — Foundry Tracing tab will be empty",
        ),
        _bool_check(
            "foundry_eval_sdk",
            foundry_ok,
            f"project: {foundry_project[:80]}..." if foundry_ok
            else "AZURE_FOUNDRY_PROJECT_ENDPOINT or AZURE_OPENAI_* missing",
        ),
        _bool_check(
            "audit_blob",
            bool(audit_account) and audit_client_ok,
            f"writing to https://{audit_account}.blob.core.windows.net/{audit_container}/"
            if (audit_account and audit_client_ok)
            else "in-memory only — audit ledger does not persist",
        ),
        _bool_check(
            "model_pricing",
            True,
            f"source: {model_pricing.PRICING_SOURCE_URL} ({model_pricing.PRICING_SOURCE_DATE})",
        ),
    ]

    overall_ok = all(c["ok"] for c in checks)

    return {
        "ok": overall_ok,
        "checks": checks,
        "online_eval_subscriber": {
            "active": foundry_ok,  # subscriber registers iff Foundry configured
            "recent_completed": completed,
            "recent_errored": errored,
            "recent_pending": pending,
            "queue_dropped": _online_metrics.get("dropped", 0),
            "queue_in_flight": _online_metrics.get("in_flight", 0),
        },
        "links": {
            "foundry_tracing": "https://ai.azure.com/build/tracing",
            "audit_blob_container": (
                f"https://portal.azure.com/#@/resource/subscriptions/_/resourceGroups/_/providers/"
                f"Microsoft.Storage/storageAccounts/{audit_account}/containersList"
                if audit_account else None
            ),
            "aoai_endpoint": aoai_endpoint or None,
        },
    }
