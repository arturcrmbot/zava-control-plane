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
from api.server.services.kpi_store import KpiStore
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

        # Phase 1 sub-phase 4 + Phase 4 IP2 — the agentic-org entity plane
        # (KuzuDB graph + reflectors + KPI store) is single-writer per file.
        # In multi-process boot (FastAPI on :3001 + Azure Functions host on
        # :7071, started by scripts/boot-demo.sh / `make up`) BOTH processes
        # import this module and would race for the kuzu file lock. Gate the
        # plane behind ENTITY_PLANE_ENABLED — default "1" preserves
        # existing single-process behaviour (uvicorn standalone, every
        # test, every CI run); boot-demo.sh sets "0" for the func launch
        # so only the FastAPI worker owns the entity graph + reflector.
        # Cross-process workflow events still flow via Durable Task storage
        # (Azurite) → FastAPI's simulator/durable client → in-process bus.
        self._entity_plane_enabled = os.getenv("ENTITY_PLANE_ENABLED", "1") == "1"

        # Governance kernel singleton — canonical entry-point for every
        # later actor (reflector, ambient dispatcher, cadence loop). Cheap
        # to construct; always enabled so non-entity-plane code paths
        # (persona auto-close, MCP tool gating, etc.) keep working.
        from api.server.services.governance.kernel import kernel as _governance_kernel
        self.governance = _governance_kernel()

        if self._entity_plane_enabled:
            # Phase 4 IP2 (TASK-010) — KPI snapshot store. File lives at
            # data/portal/kpis.sqlite. Constructed early so per-function
            # FMs built later can reference it via app_state.kpi_store.
            self.kpi_store = KpiStore(_PORTAL_DATA_DIR / "kpis.sqlite")

            # ----------------------------------------------------- entity graph plane
            # (a) Embedded property graph for the entity-graph plane. Imports
            #     are local to delay the kuzu import until AppState is actually
            #     constructed (preserves the existing module-import shape).
            from api.server.services.entity_graph import EntityGraph
            self.entities = EntityGraph(_PORTAL_DATA_DIR / "entity_graph.kuzu")

            # (b) Wire bus/audit/governance into the graph for event + audit emission.
            self.entities.attach(bus=self.bus, audit=self.audit, governance=self.governance)

            # (c) One-shot bootstrap from the existing fixtures into Person /
            #     Organisation entities. Repo-rooted so it works regardless of cwd.
            self.entities.bootstrap_from_fixtures(
                employees_path=_REPO_ROOT / "data/synthetic/employees.json",
                vendors_path=_REPO_ROOT / "api/server/fixtures/vendors.json",
                agencies_path=_REPO_ROOT / "api/server/fixtures/agencies.json",
            )

            # (d) Reflector subscribes AFTER bootstrap so the very first workflow
            #     event does not race against an unfinished bootstrap.
            from api.server.services.entity_reflector import EntityReflector
            # Trigger projection registration by importing the package.
            import api.server.services.entity_projections  # noqa: F401
            self.entity_reflector = EntityReflector(
                self.bus, self.store, self.entities,
                governance=self.governance, audit=self.audit,
            )
            self.entity_reflector.start()

            # Phase 4 IP7 (TASK-033b) — meta-workflow reflector mirrors
            # workflow.sub_spawned events into the Workflow self-relation
            # so /api/workflows/{id}/tree can render meta-workflow trees.
            from api.server.services.meta_workflow_reflector import MetaWorkflowReflector
            self.meta_workflow_reflector = MetaWorkflowReflector(
                bus=self.bus, audit=self.audit, graph=self.entities,
            )
            self.meta_workflow_reflector.start()

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
        # Phase 4 IP1 — cancel cadence tasks BEFORE the ambient
        # dispatcher tears down, so no in-flight tick races teardown.
        for t in getattr(self, "_cadence_tasks", []):
            try:
                t.cancel()
            except Exception:
                pass
        # Ambient dispatcher teardown — MUST run BEFORE the entity
        # reflector so no in-flight cypher sweep tries to spawn through
        # a half-torn graph. ``aclose`` is async (cancels asyncio tasks).
        if hasattr(self, "ambient_dispatcher"):
            try:
                await self.ambient_dispatcher.aclose()
            except Exception:
                pass
        # Entity-graph plane teardown — sync calls; hasattr guards make
        # aclose idempotent and safe even if __init__ raised mid-way.
        if hasattr(self, "entity_reflector"):
            self.entity_reflector.aclose()
        if hasattr(self, "meta_workflow_reflector"):
            self.meta_workflow_reflector.aclose()
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
        populated. Skipped entirely when ENTITY_PLANE_ENABLED=0
        (Functions host process — no entity graph, no per-function FMs,
        no ambient dispatcher).
        """
        if self.function_fms:
            return
        if not getattr(self, "_entity_plane_enabled", True):
            # Functions host process: per-function FMs depend on EntityGraph
            # for tools (query_entity, find_entities, query_recent_decisions),
            # the kpi_store for query_kpi, and AmbientDispatcher (which sweeps
            # cypher patterns against the graph). All gated together; the
            # FastAPI process owns the whole agentic-org plane.
            return
        from api.shared.functions import FUNCTIONS
        from api.server.mcp_tools import build_function_fm_tools
        from api.server.mcp_tools.query_function_fm import make_query_function_fm_tool
        from api.server.services.fleet_manager_service import FunctionFleetManager
        for fn_name in FUNCTIONS:
            if fn_name == "legacy":
                continue
            topic = f"fleet-manager.{fn_name}"
            self.hub.register(topic)
            tools = build_function_fm_tools(
                self.store, self.audit, self.entities, fn_name,
                kpi_store=self.kpi_store,
            )
            # Phase 4 IP6 (TASK-030/031, DEC-OQ2) — only the CEO-FM gets
            # the query_function_fm delegation tool. The other 9 FMs
            # never delegate sideways through this surface.
            if fn_name == "ceo":
                tools = [*tools, make_query_function_fm_tool(self)]
            self.function_fms[fn_name] = FunctionFleetManager(
                bus=self.bus,
                store=self.store,
                audit=self.audit,
                hub=self.hub,
                function=fn_name,
                tools=tools,
                on_live=lambda ev, _t=topic: self.hub.broadcast(_t, ev),
            )

        # Phase 3 IP6 (TASK-030..-032) — wire the AmbientDispatcher AFTER
        # ambient_agents discovery has run (it ran at import of the package
        # above when ambient_agents.__init__ was first loaded). The
        # dispatcher snapshots AMBIENT_AGENTS at construction so importing
        # it here picks up all three concrete declarations.
        from api.server.services.ambient_dispatcher import AmbientDispatcher

        def _spawn_workflow(workflow_type: str, payload: dict):
            # Forward-declared workflow_types (variance-investigation,
            # access-review) are not yet registered DOMAINS. Until they
            # land we log + skip rather than crash the dispatcher.
            try:
                from api.shared.domains import DOMAINS
            except Exception:
                DOMAINS = {}
            if workflow_type not in DOMAINS:
                import logging
                logging.getLogger(__name__).info(
                    "ambient_dispatcher: skipping spawn of unknown workflow_type=%s",
                    workflow_type,
                )
                return None
            # Real spawn integration lands with the per-domain UIs in
            # Phase 4. For now the simulator orchestrator's spawn helper
            # is the closest concrete entry-point — wire it lazily so a
            # missing dependency at boot doesn't break the dispatcher.
            try:
                from api.server.services import simulator_orchestrator
                spawn = getattr(simulator_orchestrator, "spawn_workflow", None)
                if callable(spawn):
                    return spawn(workflow_type)
            except Exception as ex:
                import logging
                logging.getLogger(__name__).warning(
                    "ambient_dispatcher: spawn failed for %s: %s",
                    workflow_type, ex,
                )
            return None

        self.ambient_dispatcher = AmbientDispatcher(
            bus=self.bus,
            graph=self.entities,
            audit=self.audit,
            spawn_workflow=_spawn_workflow,
        )
        # ``start()`` schedules cypher sweep loops via asyncio.create_task,
        # so it requires a running event loop. Guard the call so unit
        # tests that construct AppState without a loop still work; the
        # FastAPI lifespan will re-call start() under uvicorn.
        try:
            import asyncio as _asyncio
            _asyncio.get_running_loop()
            self.ambient_dispatcher.start()
        except RuntimeError:
            pass

        # Phase 4 IP1 (TASK-004) — cadence loop. Loads cadence YAMLs
        # once at startup and starts one asyncio task per cadence. The
        # tasks only run under a live event loop; without one we leave
        # the cadences declared but unfired (smoke tests, sync ctors).
        from api.server.services.cadence_loader import load_cadences
        cadences_dir = _REPO_ROOT / "data" / "governance" / "cadences"
        try:
            self.cadences = load_cadences(cadences_dir)
        except Exception as ex:
            import logging
            logging.getLogger(__name__).warning(
                "cadence loader failed (%s); cadences disabled", ex,
            )
            self.cadences = []
        self._cadence_tasks: list = []
        try:
            import asyncio as _asyncio
            _asyncio.get_running_loop()
            for cad in self.cadences:
                self._cadence_tasks.append(
                    _asyncio.create_task(self._run_cadence(cad))
                )
        except RuntimeError:
            pass

    async def _run_cadence(self, cadence) -> None:
        """One asyncio task per cadence — sleeps until next cron tick,
        dispatches to the named ambient agent, emits ``cadence.tick``
        audit, repeats. Cancelled by ``aclose``.

        Phase 4 IP1 (TASK-004). The croniter-driven sleep keeps the loop
        body small (<60 LoC); the trigger_ctx contract matches what
        ``AmbientDispatcher.dispatch`` already accepts (P3 TASK-018b).
        """
        import asyncio as _asyncio
        import datetime as _dt
        import logging as _logging
        from croniter import croniter as _croniter

        log = _logging.getLogger(__name__)
        while True:
            try:
                now = _dt.datetime.now()
                nxt = _croniter(cadence.schedule, now).get_next(_dt.datetime)
                wait_s = max(0.0, (nxt - now).total_seconds())
                await _asyncio.sleep(wait_s)
                scheduled_for = nxt.isoformat()
                self.audit.log("cadence.tick", {
                    "cadence_name": cadence.name,
                    "scheduled_for": scheduled_for,
                    "fired_at": _dt.datetime.now().isoformat(),
                    "ambient_agent": cadence.fires_ambient_agent,
                })
                try:
                    await self.ambient_dispatcher.dispatch(
                        cadence.fires_ambient_agent,
                        trigger_ctx={
                            "kind": "cadence",
                            "cadence_name": cadence.name,
                            "scheduled_for": scheduled_for,
                        },
                    )
                except Exception as ex:
                    log.warning(
                        "cadence %s: dispatch to %s failed: %s",
                        cadence.name, cadence.fires_ambient_agent, ex,
                    )
            except _asyncio.CancelledError:
                raise
            except Exception as ex:  # pragma: no cover — defensive
                log.warning("cadence %s loop error: %s", cadence.name, ex)
                await _asyncio.sleep(1.0)


app_state = AppState()
