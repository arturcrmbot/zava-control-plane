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

# Repo root resolved from this file's location so the entity-graph bootstrap
# fixtures load regardless of the cwd that AppState is constructed from
# (pytest from "/", uvicorn from the api/ dir, the Functions worker, etc.).
# api/server/state.py → parents[2] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


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

        # ----------------------------------------------------- entity graph plane
        # (a) Governance kernel singleton — canonical entry-point for every
        #     later actor (reflector here, ambient dispatcher in Phase 3,
        #     cadence loop in Phase 4). Set BEFORE any consumer of self.bus.
        from api.server.services.governance.kernel import kernel as _governance_kernel
        self.governance = _governance_kernel()

        # (b) Embedded property graph for the entity-graph plane. Imports
        #     are local to delay the kuzu import until AppState is actually
        #     constructed (preserves the existing module-import shape).
        from api.server.services.entity_graph import EntityGraph
        self.entities = EntityGraph(_PORTAL_DATA_DIR / "entity_graph.kuzu")

        # (c) Wire bus/audit/governance into the graph for event + audit emission.
        self.entities.attach(bus=self.bus, audit=self.audit, governance=self.governance)

        # (d) One-shot bootstrap from the existing fixtures into Person /
        #     Organisation entities. Repo-rooted so it works regardless of cwd.
        self.entities.bootstrap_from_fixtures(
            employees_path=_REPO_ROOT / "data/synthetic/employees.json",
            vendors_path=_REPO_ROOT / "api/server/fixtures/vendors.json",
            agencies_path=_REPO_ROOT / "api/server/fixtures/agencies.json",
        )

        # (e) Reflector subscribes AFTER bootstrap so the very first workflow
        #     event does not race against an unfinished bootstrap.
        from api.server.services.entity_reflector import EntityReflector
        # Trigger projection registration by importing the package.
        import api.server.services.entity_projections  # noqa: F401
        self.entity_reflector = EntityReflector(
            self.bus, self.store, self.entities,
            governance=self.governance, audit=self.audit,
        )
        self.entity_reflector.start()

        self.hub = SSEHub()

        # Phase 3 (TASK-028) — per-non-legacy-function Fleet Managers.
        # Container only; populated by ``_init_function_fms()`` below
        # AFTER the module-level ``app_state`` binding lands. The
        # mcp_tools package eagerly imports modules that themselves do
        # ``from api.server.state import app_state`` at top level, so
        # constructing function FMs here would race the binding.
        self.function_fms: dict = {}

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

    async def aclose(self) -> None:
        """Release pooled / long-lived resources owned by this AppState.

        Called from the FastAPI lifespan teardown so that under
        uvicorn --reload (or any teardown / re-construct cycle) we don't
        leak the BlobServiceClient's underlying httpx pool. MagicLinkStore
        and EmailSender open connections per-call and need no close.
        """
        if self.blob_store is not None:
            svc = getattr(self.blob_store, "_svc", None)
            if svc is not None:
                try:
                    # BlobServiceClient is sync; close() releases the pool.
                    svc.close()
                except Exception:
                    pass
        # Entity-graph plane teardown — sync calls; hasattr guards make
        # aclose idempotent and safe even if __init__ raised mid-way.
        if hasattr(self, "entity_reflector"):
            self.entity_reflector.aclose()
        if hasattr(self, "entities"):
            self.entities.close()


    def init_function_fms(self) -> None:
        """Instantiate one FunctionFleetManager per non-legacy function.

        Phase 3 (TASK-028). Called at module bottom AFTER the module-level
        ``app_state`` binding so the mcp_tools package's eager submodule
        imports (``query_reviewer_decisions``, ``query_economics`` —
        each `from api.server.state import app_state`) resolve cleanly
        without a half-built singleton.

        Each FM gets:
          - its own bound MCP tool surface (5 tools via
            ``build_function_fm_tools``);
          - its own SSE topic ``fleet-manager.<fn_name>`` registered on
            the shared SSEHub so a function-specific UI can subscribe;
          - the function-scoped SKILL prompt assembled at session-start
            (see ``FleetManagerService._build_skill_text``).

        Construction is cheap — the GHCP subprocess is not spawned until
        ``start()`` runs. Today only the fleet-wide singleton is
        ``start()``-ed by main.py; per-function start-up lands with the
        function-specific UIs.

        Idempotent: re-calling is a no-op once ``function_fms`` is
        populated.
        """
        if self.function_fms:
            return
        from api.shared.functions import FUNCTIONS
        from api.server.mcp_tools import build_function_fm_tools
        from api.server.services.fleet_manager_service import FunctionFleetManager
        for fn_name in FUNCTIONS:
            if fn_name == "legacy":
                continue
            topic = f"fleet-manager.{fn_name}"
            self.hub.register(topic)
            tools = build_function_fm_tools(
                self.store, self.audit, self.entities, fn_name
            )
            self.function_fms[fn_name] = FunctionFleetManager(
                bus=self.bus,
                store=self.store,
                audit=self.audit,
                hub=self.hub,
                function=fn_name,
                tools=tools,
                on_live=lambda ev, _t=topic: self.hub.broadcast(_t, ev),
            )


app_state = AppState()
