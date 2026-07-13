# src/server/services/simulator_orchestrator.py
"""
Spawns synthetic workflows by scheduling Durable Functions orchestration instances.

Week 2 pivot: ExpenseClaim is the active orchestrator; the legacy invoice
spawn_workflow is preserved for backward compatibility but no longer invoked
by the ramp loop.
"""
from __future__ import annotations
import asyncio
import json
import os
import random
from importlib import import_module
from pathlib import Path
from typing import Awaitable, Callable

from api.server.state import app_state
from api.server.services.synthetic_data import (
    build_workflow, build_expense_workflow, build_hiring_workflow,
    build_fleet_travel_preapproval_workflow,
    build_fleet_vendor_kyc_workflow,
    build_fleet_employee_onboarding_workflow,
    build_fleet_it_access_request_workflow,
    build_fleet_contract_renewal_workflow,
    build_fleet_perf_review_workflow,
    build_fleet_ap_invoice_workflow,
    build_fleet_purchase_order_workflow,
    build_fleet_contract_review_workflow,
    build_fleet_privacy_dpia_workflow,
    build_fleet_treasury_fx_workflow,
    build_creative_campaign_workflow,
)
from api.server.services.durable_client import (
    schedule_new_orchestration, raise_orchestration_event,
)
from api.shared.expense_taxonomy import ReceiptFlavour
from api.shared import domains as _registry
from api.shared.domains import Domain, live_domains, DOMAINS
from api.server.services.time_compression import business_now

# Cache resolved spawners so we import the module + look up the attr once
# per process, not once per ramp cycle.
_SPAWNER_CACHE: dict[str, Callable[..., Awaitable[str]]] = {}


def _resolve_spawner(domain: Domain) -> Callable[..., Awaitable[str]]:
    """Import the spawner callable named in ``domain.spawn_fn`` and cache it.

    Raises a clear RuntimeError if the domain has no ``spawn_fn`` set or
    if the dotted path doesn't resolve, so missing wiring fails loudly at
    the first spawn attempt rather than silently dropping the domain.
    """
    if not domain.spawn_fn:
        raise RuntimeError(
            f"domain {domain.workflow_type!r} has no spawn_fn declared in "
            f"api/shared/domains.py — cannot spawn"
        )
    cached = _SPAWNER_CACHE.get(domain.spawn_fn)
    if cached is not None:
        return cached
    module_name, _, attr = domain.spawn_fn.rpartition(".")
    if not module_name:
        raise RuntimeError(
            f"domain {domain.workflow_type!r} spawn_fn={domain.spawn_fn!r} "
            f"is not a dotted path"
        )
    module = import_module(module_name)
    try:
        fn = getattr(module, attr)
    except AttributeError as ex:
        raise RuntimeError(
            f"domain {domain.workflow_type!r} spawn_fn={domain.spawn_fn!r} "
            f"not found in {module_name}"
        ) from ex
    _SPAWNER_CACHE[domain.spawn_fn] = fn
    return fn


def _effective_interval(domain: Domain) -> float:
    """Compute the per-domain spawn interval in seconds.

    effective = realistic_interval_seconds / DEMO_TIME_WARP_FACTOR

    Falls back to the legacy SIMULATOR_RAMP_AVG_INTERVAL_SECONDS env var
    when the domain doesn't declare a realistic_interval_seconds (e.g.
    test fixtures, partially-migrated domains).
    """
    if domain.realistic_interval_seconds is not None:
        warp = float(os.getenv("DEMO_TIME_WARP_FACTOR", "60"))
        if warp <= 0:
            warp = 1.0
        interval = domain.realistic_interval_seconds / warp
        # pitch-c5: slow-burn domains (contract renewals, perf cycles,
        # M&A, annual budgets, …) fire 5x less often than their
        # nominal cadence so the activity stream isn't drowned in
        # quarter-long workflows during a demo.
        if getattr(domain, "slow_burn", False):
            interval *= 5
        return interval
    return float(os.getenv("SIMULATOR_RAMP_AVG_INTERVAL_SECONDS", "90"))


def _apply_business_time_to_workflow(workflow_type: str, workflow_id: str) -> None:
    """For slow-burn domains, advance the workflow's ``created_at`` to
    business-time so dashboards/age-buckets show realistic ageing during
    a fast-forward demo. No-op for fast (wall-clock) domains.
    """
    domain = DOMAINS.get(workflow_type)
    if not domain or not getattr(domain, "slow_burn", False):
        return
    w = app_state.store.get_workflow(workflow_id)
    if w is None:
        return
    try:
        w.created_at = business_now().timestamp()
        app_state.store.upsert_workflow(w)
    except Exception as ex:  # pragma: no cover - defensive
        print(f"[orchestrator] slow-burn created_at update failed for {workflow_id}: {ex}")

_seq = 0
_exp_seq = 0
_hire_seq = 0
_travel_seq = 0

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

# Maps a Day 7 simulator scenario to the receipt_mismatch_flavour stamped on
# the claim by the receipt PNG generator. spawn_expense_workflow picks a
# deterministic claim from the synthetic corpus matching the scenario's
# flavour so the Phase 3 receipt validator has known content to classify.
_SCENARIO_TO_FLAVOUR: dict[str, ReceiptFlavour] = {
    "receipt-mismatch-correct": "correct",
    "receipt-mismatch-amount": "wrong-amount",
    "receipt-mismatch-date": "wrong-date",
    "receipt-mismatch-vendor": "wrong-vendor",
    "receipt-missing-line": "missing-line-item",
    "receipt-missing": "missing-receipt",
}

# Module-level RNG keyed off the synthetic-data seed so picks are deterministic
# within a process and reproducible across restarts.
_scenario_rng = random.Random(20260427)


# Lazy-loaded indices over the synthetic claim corpus. The corpus is
# immutable at runtime (300 files committed to git); reading + parsing them
# on every spawn was costing ~300 file reads per ramp call.
_corpus_by_employee: dict[str, list[str]] | None = None
_corpus_by_flavour: dict[str, list[str]] | None = None


def _build_corpus_indices() -> None:
    """Walk the claim corpus once and populate both indices."""
    global _corpus_by_employee, _corpus_by_flavour
    by_employee: dict[str, list[str]] = {}
    by_flavour: dict[str, list[str]] = {}
    for path in sorted(_CLAIMS_DIR.glob("CLM-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        cid = record["claim_id"]
        emp = record.get("employee_id")
        flav = record.get("receipt_mismatch_flavour")
        if emp:
            by_employee.setdefault(emp, []).append(cid)
        if flav:
            by_flavour.setdefault(flav, []).append(cid)
    _corpus_by_employee = by_employee
    _corpus_by_flavour = by_flavour


def reset_corpus_cache() -> None:
    """Invalidate the lazy indices — call after regenerating synthetic data."""
    global _corpus_by_employee, _corpus_by_flavour
    _corpus_by_employee = None
    _corpus_by_flavour = None


def _claims_for_employee(employee_id: str) -> list[str]:
    """Return all claim_ids for a given employee, sorted by claim_id (which is
    chronological by construction). Used by the repeat-offender ramp."""
    if _corpus_by_employee is None:
        _build_corpus_indices()
    assert _corpus_by_employee is not None
    return list(_corpus_by_employee.get(employee_id, []))


def _pick_claim_for_flavour(flavour: str) -> str:
    """Pick a deterministic claim_id whose receipt_mismatch_flavour matches.
    Raises if no claim has the requested flavour."""
    if _corpus_by_flavour is None:
        _build_corpus_indices()
    assert _corpus_by_flavour is not None
    candidates = _corpus_by_flavour.get(flavour, [])
    if not candidates:
        raise ValueError(
            f"no claim with receipt_mismatch_flavour={flavour!r} in {_CLAIMS_DIR}"
        )
    return _scenario_rng.choice(candidates)


# --------------------------------------------------------------------------
# Per-domain seed-corpus loader (Phase 5 of feature-fleet-domain-substrate-1).
#
# Each fleet-* domain has a seed JSON under
# data/synthetic/<workflow_type>/<filename>.json carrying ≥40 records with
# `id`, semantic fields, and a `scenario` tag. These supply spawner inputs
# in place of the previously-hardcoded inline arrays.
# --------------------------------------------------------------------------

_CORPUS_ROOT = Path(__file__).resolve().parents[3] / "data" / "synthetic"

_CORPUS_FILE: dict[str, str] = {
    "travel-preapproval": "travel-preapproval/trips.json",
    "vendor-kyc":         "vendor-kyc/vendors.json",
    "employee-onboarding": "employee-onboarding/joiners.json",
    "it-access-request":  "it-access-request/requests.json",
    "contract-renewal":   "contract-renewal/contracts.json",
    "perf-review":        "perf-review/reviewees.json",
    "ap-invoice":         "ap-invoice/invoices.json",
    "purchase-order":     "purchase-order/pos.json",
    "contract-review":    "contract-review/contracts.json",
    "privacy-dpia":       "privacy-dpia/dpias.json",
    "creative-campaign":  "creative-campaign/briefs.json",
    "treasury-fx":        "treasury-fx/ops.json",
}

# Per-(workflow_type) lazy cache. Each value is a list of record dicts.
_corpus_cache: dict[str, list[dict]] = {}
# Round-robin position per (workflow_type, scenario|None) so successive
# spawns walk the corpus deterministically.
_corpus_cursor: dict[tuple[str, str | None], int] = {}


def _load_corpus(workflow_type: str) -> list[dict]:
    """Read the per-domain seed JSON, cached. Returns [] if the file
    doesn't exist yet (graceful: spawner falls back to inline synthesis)."""
    cached = _corpus_cache.get(workflow_type)
    if cached is not None:
        return cached
    rel = _CORPUS_FILE.get(workflow_type)
    if not rel:
        _corpus_cache[workflow_type] = []
        return []
    path = _CORPUS_ROOT / rel
    if not path.exists():
        _corpus_cache[workflow_type] = []
        return []
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            print(f"[corpus] {path} is not a list; ignoring")
            records = []
    except Exception as ex:
        print(f"[corpus] failed to load {path}: {ex}")
        records = []
    _corpus_cache[workflow_type] = records
    return records


def _pick_record(workflow_type: str, scenario: str | None = None) -> dict | None:
    """Round-robin pick the next record from the per-domain corpus,
    optionally filtered to records with a matching `scenario`. Returns
    None if the corpus is empty (caller falls back to inline synthesis)."""
    records = _load_corpus(workflow_type)
    if not records:
        return None
    if scenario:
        records = [r for r in records if r.get("scenario") == scenario]
        if not records:
            return None
    key = (workflow_type, scenario)
    idx = _corpus_cursor.get(key, 0) % len(records)
    _corpus_cursor[key] = idx + 1
    return records[idx]


def reset_seed_corpus_cache() -> None:
    """Test helper: invalidate the per-domain corpus cache + cursors."""
    _corpus_cache.clear()
    _corpus_cursor.clear()


async def spawn_workflow(scenario: str | None = None) -> str:
    """Legacy: create an invoice workflow and start an InvoiceP2POrchestrator instance.

    Retained for any code/test still exercising the invoice path. The Week 2
    ramp loop spawns expense claims instead — see ``spawn_expense_workflow``.
    """
    global _seq
    _seq += 1
    wid = f"INV-{_seq:04d}"
    w = build_workflow(wid)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": w.id,
        "vendor": w.vendor.model_dump() if w.vendor else None,
        "invoice": w.invoice.model_dump() if w.invoice else None,
        "agency": w.agency,
        "jurisdiction": w.jurisdiction,
        "type": "invoice-p2p",
    }
    if scenario == "demo-fail":
        payload["force_gl_fail"] = True
    elif scenario == "demo-hitl":
        payload["force_hitl"] = True
        if payload.get("invoice"):
            payload["invoice"]["amount"] = 12500.00
    try:
        result = await schedule_new_orchestration(payload, function_name="InvoiceP2POrchestrator")
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


async def spawn_expense_workflow(
    scenario: str | None = None,
    claim_id: str | None = None,
) -> str:
    """Create an expense-claim workflow and start an ExpenseClaimOrchestrator instance.

    ``scenario`` is forwarded as a tag on the orchestration payload so downstream
    activities (Day 7+ receipt validator, Day 11 mismatch flavours) can override
    behaviour deterministically.

    ``claim_id`` deterministically picks a claim from the synthetic corpus
    (used by repeat-offender / breach-justification ramps).
    """
    global _exp_seq
    _exp_seq += 1
    wid = f"EXP-{_exp_seq:04d}"

    # Day 7 receipt-mismatch scenarios: pick a claim whose flavour matches.
    # Explicit claim_id arg wins (used by repeat-offender ramps, Day 9).
    if claim_id is None and scenario in _SCENARIO_TO_FLAVOUR:
        claim_id = _pick_claim_for_flavour(_SCENARIO_TO_FLAVOUR[scenario])

    w = build_expense_workflow(wid, claim_id=claim_id)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": w.id,
        "claim": w.claim.model_dump() if w.claim else None,
        "claim_id": w.claim.claim_id if w.claim else None,
        "ems_source": w.claim.ems_source if w.claim else None,
        "agency": w.agency,
        "jurisdiction": w.jurisdiction,
        "type": "expense-claim",
    }
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="ExpenseClaimOrchestrator"
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


async def spawn_hiring_workflow(
    candidate_id: str | None = None,
    scenario: str | None = None,
) -> str:
    """Create a hiring workflow and start a HiringOrchestrator instance.

    POC2 simulator entry point — analogue of `spawn_expense_workflow`. Picks
    a synthetic CV, builds the Workflow record, and schedules a Durable
    `HiringOrchestrator` run. `scenario` is forwarded as a tag so per-track
    work can override behaviour deterministically (e.g.
    "rtw-unknown" forces the `right_to_work_unverified` block at Phase 8).
    """
    global _hire_seq
    _hire_seq += 1
    wid = f"HIRE-{_hire_seq:04d}"
    w = build_hiring_workflow(wid, candidate_id=candidate_id)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": w.id,
        "type": "hiring",
        "candidate_id": w.metadata.get("candidate_id"),
        "candidate_name": w.metadata.get("candidate_name"),
        "role_family": w.metadata.get("role_family"),
        "level_target": w.metadata.get("level_target"),
        "jurisdiction": w.metadata.get("jurisdiction"),
        "agency": w.agency,
    }
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="HiringOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


async def spawn_travel_preapproval_workflow(
    employee_id: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn a travel pre-approval workflow. Picks a record from
    data/synthetic/travel-preapproval/trips.json (filtered by `scenario`
    when set); falls back to inline synthesis when the corpus is missing.
    Upserts a Workflow record so the FM's `query_fleet` can see it.
    """
    global _travel_seq
    _travel_seq += 1
    wid = f"TRV-{_travel_seq:04d}"
    record = _pick_record("travel-preapproval", scenario=scenario) or {}
    if employee_id:
        record = {**record, "employee_id": employee_id}
    w = build_fleet_travel_preapproval_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "travel-preapproval",
        "trip": w.payload.get("trip"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetTravelPreapprovalOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


async def simulate_justification(
    workflow_id: str,
    text: str = "Client dinner with VP-level stakeholder; named attendees on the receipt; business reason annotated post-hoc.",
    submitted_by: str | None = None,
) -> None:
    """Day 10 round-trip: fire a `justification` external event into a Red
    workflow that's currently suspended at the Phase 5 HITL wait. The
    orchestrator resumes and proceeds to Phase 6 (Arbitrate, Week 3).

    Also emits a `justification.received` FleetEvent so the Control Plane
    surfaces the round-trip in real time.
    """
    w = app_state.store.get_workflow(workflow_id)
    if not w:
        raise KeyError(f"workflow {workflow_id!r} not found in store")
    if not w.orchestration_instance_id:
        raise ValueError(f"workflow {workflow_id!r} has no orchestration_instance_id")
    submitter = submitted_by or (
        w.claim.employee_id if getattr(w, "claim", None) else "operator"
    )
    payload = {
        "claim_id": getattr(w.claim, "claim_id", workflow_id) if getattr(w, "claim", None) else workflow_id,
        "text": text,
        "submitted_by": submitter,
        "submitted_at": _utcnow_iso(),
    }
    await raise_orchestration_event(w.orchestration_instance_id, "justification", payload)
    try:
        from api.shared.events import FleetEvent
        app_state.bus.emit(FleetEvent(
            type="justification.received",
            workflow_id=workflow_id,
            claim_id=payload["claim_id"],
            submitted_by=submitter,
        ))
    except Exception:
        pass


def _utcnow_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def spawn_repeat_offender_ramp(
    employee_id: str = "EMP-0001",
    count: int = 3,
    delay_seconds: float = 1.0,
) -> list[str]:
    """Day 9 ramp demo: spawn `count` consecutive claims from the same employee
    so the escalation_advisor's tier visibly ramps warning -> escalation ->
    major-violation across the three workflows.

    The seeded synthetic data has at least three employees (EMP-0001 et al.)
    with prior breach histories of length 2+, so the third claim should land
    in major-violation when the same-category override applies.
    """
    claim_ids = _claims_for_employee(employee_id)
    if len(claim_ids) < count:
        raise ValueError(
            f"employee {employee_id!r} has only {len(claim_ids)} claims in the corpus "
            f"(need {count}); seed more in data/synthetic/employees.json"
        )
    spawned: list[str] = []
    for cid in claim_ids[:count]:
        wid = await spawn_expense_workflow(
            scenario="repeat-offender", claim_id=cid,
        )
        spawned.append(wid)
        await asyncio.sleep(delay_seconds)
    return spawned


async def simulate_region_failure(stop_seconds: int = 10) -> dict:
    """Demo-only: emit a `region.failure.simulated` event marking the
    wall-clock window during which the operator stops the Functions host.

    Durable Functions handles checkpoint/replay natively against Azurite;
    this helper does not stop or restart anything itself — it only marks
    the audit trail and returns a snapshot of in-flight workflows so the
    UI can show before/after counts.
    """
    from api.shared.events import FleetEvent

    workflows = app_state.store.list_workflows()
    in_flight = len(workflows)
    paused = sum(1 for w in workflows if w.status == "awaiting_hitl")

    app_state.bus.emit(FleetEvent(
        type="region.failure.simulated",
        workflow_id="*",
        stop_seconds=stop_seconds,
        in_flight_count=in_flight,
        paused_at_hitl=paused,
    ))
    await asyncio.sleep(stop_seconds)
    return {
        "in_flight": in_flight,
        "paused_at_hitl": paused,
        "stop_seconds": stop_seconds,
    }


async def _wait_for_functions_host(timeout_seconds: float = 120.0) -> bool:
    """Block until the Azure Functions host on :7071 answers, or the
    timeout elapses.

    Without this guard the ramp loop fires its first spawn ~immediately
    after FastAPI starts, while the Functions host is still loading
    extension bundles. The first spawn then fails with "All connection
    attempts failed", the workflow is upserted into StateStore but never
    scheduled on Durable, and the operator sees a workflow stuck at
    Intake forever.

    Returns True if the host is reachable, False on timeout. The caller
    starts ramping either way \u2014 a missing Functions host is the
    operator's call to debug, not a reason to silently wedge the ramp.
    """
    import httpx
    base = os.getenv("FUNCTIONS_HOST", "http://localhost:7071").rstrip("/")
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    interval = 1.0
    print(f"[ramp] waiting for Functions host at {base} ...")
    async with httpx.AsyncClient(timeout=2.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(f"{base}/")
                if r.status_code < 500:
                    print(f"[ramp] Functions host ready ({r.status_code})")
                    return True
            except Exception:
                pass
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, 5.0)
    print(
        f"[ramp] WARNING: Functions host did not bind within {timeout_seconds}s; "
        "ramping anyway. Early spawns may fail."
    )
    return False


async def ramp_loop() -> None:
    """Domain-aware steady-state ramp loop.

    Default: enabled, spawning each live domain at ~90s intervals jittered
    \u00b130%. With 4 domains that's roughly one new workflow every 22s
    org-wide \u2014 enough to keep the observatory full, light enough to not
    fork-bomb the GHCP SDK on a laptop.

    Each domain runs in its own coroutine so a failure in one (e.g.
    Functions host down for hiring) does not stall the others.

    Env vars
    --------
    SIMULATOR_RAMP_ENABLED              "1" (default) | "0" to disable.
    SIMULATOR_RAMP_AVG_INTERVAL_SECONDS Seconds between spawns per domain
                                        (default 90). Real interval is
                                        uniform [0.7\u00d7, 1.3\u00d7] of this.
    SIMULATOR_RAMP_DOMAINS              CSV of domain names to spawn.
                                        Default = all known domains
                                        (expense-claim, hiring,
                                        travel-preapproval). Set to a
                                        subset to focus a demo, e.g.
                                        "travel-preapproval" for a demo
                                        that only needs travel.

    Deprecated
    ----------
    SIMULATOR_TARGET_WORKFLOWS, SIMULATOR_STEADY_STATE,
    SIMULATOR_STEADY_INTERVAL_SECONDS \u2014 the old expense-only ramp.
    Logged as deprecated if set; values are ignored.
    """
    enabled = os.getenv("SIMULATOR_RAMP_ENABLED", "1") == "1"
    if not enabled:
        print("[ramp] disabled (SIMULATOR_RAMP_ENABLED=0); use POST /api/simulator/{inject,hire,travel} to fire workflows by hand")
        return

    # Boot-race guard: the FastAPI lifespan kicks the ramp loop a few
    # seconds before the Functions host finishes binding port 7071. Any
    # spawn fired in that window fails with "All connection attempts
    # failed" and leaves an orphan workflow stuck at Intake — confusing
    # during a demo. Probe the host until it answers or we hit the cap.
    await _wait_for_functions_host(timeout_seconds=120.0)

    # Deprecation warning for any operator still on the old vars.
    deprecated_set = [
        v for v in (
            "SIMULATOR_TARGET_WORKFLOWS",
            "SIMULATOR_STEADY_STATE",
            "SIMULATOR_STEADY_INTERVAL_SECONDS",
        ) if os.getenv(v) not in (None, "", "0")
    ]
    if deprecated_set:
        print(
            f"[ramp] WARNING: {deprecated_set} are deprecated and ignored. "
            "Use SIMULATOR_RAMP_ENABLED / SIMULATOR_RAMP_AVG_INTERVAL_SECONDS "
            "/ SIMULATOR_RAMP_DOMAINS instead."
        )

    # Build the spawn map from the live domain registry. Adding a new
    # domain is now a single edit in api/shared/domains.py — no second
    # registry to maintain here.
    by_type: dict[str, Domain] = {d.workflow_type: d for d in live_domains()}

    domains_csv = os.getenv("SIMULATOR_RAMP_DOMAINS", "").strip()
    if domains_csv:
        wanted = [d.strip() for d in domains_csv.split(",") if d.strip()]
    else:
        wanted = list(by_type.keys())

    avg_interval = float(os.getenv("SIMULATOR_RAMP_AVG_INTERVAL_SECONDS", "90"))

    valid_domains: list[Domain] = []
    for d in wanted:
        if d not in by_type:
            print(f"[ramp] WARNING: unknown domain {d!r}; skipping")
            continue
        valid_domains.append(by_type[d])

    if not valid_domains:
        print("[ramp] no valid domains in SIMULATOR_RAMP_DOMAINS; nothing to spawn")
        return

    initial_stagger = avg_interval / max(len(valid_domains), 1)

    print(
        f"[ramp] starting steady-state for domains={[d.workflow_type for d in valid_domains]}, "
        f"avg_interval={avg_interval}s \u00b130%, initial_stagger={initial_stagger:.1f}s/domain"
    )

    tasks = []
    for i, domain in enumerate(valid_domains):
        spawn_fn = _resolve_spawner(domain)
        per_domain_interval = _effective_interval(domain)
        scenarios = _scenarios_for(domain.workflow_type)
        # Stagger initial spawns across the first global cycle so we don't
        # fire all 14 domains at t=0 (cold-cache subprocess pile-up).
        tasks.append(asyncio.create_task(
            _per_domain_ramp(domain.workflow_type, spawn_fn, per_domain_interval,
                             initial_delay=i * initial_stagger,
                             scenario_rotation=scenarios)
        ))

    # Block forever; the loop is supervised by the FastAPI lifespan which
    # cancels the parent task on shutdown.
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        raise


def _scenarios_for(domain: str) -> list[str] | None:
    """Return the scenario rotation for a domain. Interleaves scenarios
    in proportion to their corpus frequency so the operator sees variety
    inside the first 4-5 spawns instead of 24 cleans before any
    interesting scenario fires.

    Example for vendor-kyc (24 clean / 6 each of 3 risky):
      ['clean', 'sanctions-hit-entity', 'clean', 'sanctions-hit-ubo',
       'clean', 'adverse-media', 'clean', 'sanctions-hit-entity', ...]

    None for POC1/POC2 (no per-domain seed file declared in _CORPUS_FILE).
    """
    if domain not in _CORPUS_FILE:
        return None
    records = _load_corpus(domain)
    if not records:
        return None
    counts: dict[str, int] = {}
    for r in records:
        scen = r.get("scenario")
        if scen:
            counts[scen] = counts.get(scen, 0) + 1
    if not counts:
        return None
    # Round-robin over scenario buckets, drawing in proportion to count.
    # Sort scenarios alphabetically for determinism (apart from majority).
    majority = max(counts.items(), key=lambda kv: kv[1])[0]
    others = sorted(s for s in counts if s != majority)
    rotation: list[str] = []
    # Interleave: alternate majority with the next "other" scenario.
    # Total length matches the corpus; majority shows ~half the rotation,
    # others share the rest.
    other_cursor = 0
    for i in range(sum(counts.values())):
        if i % 2 == 0 or not others:
            rotation.append(majority)
        else:
            rotation.append(others[other_cursor % len(others)])
            other_cursor += 1
    return rotation


async def _per_domain_ramp(
    domain: str,
    spawn_fn,
    avg_interval: float,
    initial_delay: float = 0.0,
    scenario_rotation: list[str] | None = None,
) -> None:
    """One domain's spawn loop. Survives individual spawn failures so a
    single domain outage doesn't stall the rest. When `scenario_rotation`
    is set, every spawn picks the next scenario in the list (cycling)."""
    if initial_delay > 0:
        await asyncio.sleep(initial_delay)
    cursor = 0
    while True:
        scenario = None
        if scenario_rotation:
            scenario = scenario_rotation[cursor % len(scenario_rotation)]
            cursor += 1
        try:
            if scenario:
                wid = await spawn_fn(scenario=scenario)
            else:
                wid = await spawn_fn()
            print(f"[ramp][{domain}] spawned {wid}"
                  + (f" scenario={scenario}" if scenario else ""))
        except Exception as ex:
            print(f"[ramp][{domain}] spawn failed: {ex}")
        # \u00b130% jitter so the cadence isn't robotic.
        jittered = avg_interval * (0.7 + random.random() * 0.6)
        await asyncio.sleep(jittered)



# === BEGIN compose-domain fleet-employee-onboarding ===
_onb_seq = 0


async def spawn_fleet_employee_onboarding_workflow(
    employee_id: str | None = None,
    department: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn an Employee onboarding workflow from the seed corpus."""
    global _onb_seq
    _onb_seq += 1
    wid = f"ONB-{_onb_seq:04d}"
    record = _pick_record("employee-onboarding", scenario=scenario) or {}
    if employee_id:
        record = {**record, "employee_id": employee_id}
    if department:
        record = {**record, "department": department}
    w = build_fleet_employee_onboarding_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "employee-onboarding",
        "joiner": w.payload.get("joiner"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetEmployeeOnboardingOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END compose-domain fleet-employee-onboarding ===


# === BEGIN compose-domain fleet-vendor-kyc ===
_fvk_seq = 0


async def spawn_fleet_vendor_kyc_workflow(
    vendor_name: str | None = None,
    country: str | None = None,
    proposing_agency: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn a Vendor KYC workflow from the seed corpus."""
    global _fvk_seq
    _fvk_seq += 1
    wid = f"VKY-{_fvk_seq:04d}"
    record = _pick_record("vendor-kyc", scenario=scenario) or {}
    if vendor_name:
        record = {**record, "vendor_name": vendor_name}
    if country:
        record = {**record, "country_of_incorporation": country}
    if proposing_agency:
        record = {**record, "proposing_agency": proposing_agency}
    w = build_fleet_vendor_kyc_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "vendor-kyc",
        "vendor": w.payload.get("vendor"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetVendorKycOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END compose-domain fleet-vendor-kyc ===


# === BEGIN compose-domain fleet-it-access-request ===
_itar_seq = 0


async def spawn_fleet_it_access_request_workflow(
    employee_id: str | None = None,
    department: str | None = None,
    requested_role_templates: list[str] | None = None,
    business_justification: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn an IT access request workflow from the seed corpus."""
    global _itar_seq
    _itar_seq += 1
    wid = f"ITAR-{_itar_seq:04d}"
    record = _pick_record("it-access-request", scenario=scenario) or {}
    overrides = {}
    if employee_id:
        overrides["employee_id"] = employee_id
    if department:
        overrides["department"] = department
    if requested_role_templates:
        overrides["requested_role_templates"] = requested_role_templates
    if business_justification:
        overrides["business_justification"] = business_justification
    record = {**record, **overrides}
    w = build_fleet_it_access_request_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "it-access-request",
        "request": w.payload.get("request"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetItAccessRequestOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END compose-domain fleet-it-access-request ===


# === BEGIN compose-domain fleet-contract-renewal ===
_crn_seq = 0


async def spawn_fleet_contract_renewal_workflow(
    contract_id: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn a Contract renewal workflow from the seed corpus."""
    global _crn_seq
    _crn_seq += 1
    wid = f"CRN-{_crn_seq:04d}"
    record = _pick_record("contract-renewal", scenario=scenario) or {}
    if contract_id:
        record = {**record, "contract_id": contract_id}
    w = build_fleet_contract_renewal_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "contract-renewal",
        "contract": w.payload.get("contract"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetContractRenewalOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    _apply_business_time_to_workflow("contract-renewal", wid)
    return wid
# === END compose-domain fleet-contract-renewal ===


# === BEGIN compose-domain fleet-perf-review ===
_prr_seq = 0


async def spawn_fleet_perf_review_workflow(
    employee_id: str | None = None,
    cycle: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn a Performance review workflow from the seed corpus."""
    global _prr_seq
    _prr_seq += 1
    wid = f"PRR-{_prr_seq:04d}"
    record = _pick_record("perf-review", scenario=scenario) or {}
    if employee_id:
        record = {**record, "employee_id": employee_id}
    if cycle:
        record = {**record, "cycle": cycle}
    w = build_fleet_perf_review_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "perf-review",
        "review": w.payload.get("review"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetPerfReviewOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    _apply_business_time_to_workflow("perf-review", wid)
    return wid
# === END compose-domain fleet-perf-review ===


# === BEGIN hand-graduated fleet-ap-invoice ===
_api_seq = 0


async def spawn_fleet_ap_invoice_workflow(
    invoice_id: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn an AP-invoice workflow from the seed corpus."""
    global _api_seq
    _api_seq += 1
    wid = f"API-{_api_seq:04d}"
    record = _pick_record("ap-invoice", scenario=scenario) or {}
    if invoice_id:
        record = {**record, "invoice_id": invoice_id}
    w = build_fleet_ap_invoice_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "ap-invoice",
        "invoice": w.payload.get("invoice"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetApInvoiceOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END hand-graduated fleet-ap-invoice ===


# === BEGIN hand-graduated wave 2: fleet-purchase-order ===
_po_seq = 0


async def spawn_fleet_purchase_order_workflow(
    po_id: str | None = None,
    scenario: str | None = None,
) -> str:
    global _po_seq
    _po_seq += 1
    wid = f"POW-{_po_seq:04d}"
    record = _pick_record("purchase-order", scenario=scenario) or {}
    if po_id:
        record = {**record, "po_id": po_id}
    w = build_fleet_purchase_order_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "purchase-order",
        "purchase_order": w.payload.get("purchase_order"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetPurchaseOrderOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END hand-graduated wave 2: fleet-purchase-order ===


# === BEGIN hand-graduated wave 2: fleet-contract-review ===
_cr_seq = 0


async def spawn_fleet_contract_review_workflow(
    contract_id: str | None = None,
    scenario: str | None = None,
) -> str:
    global _cr_seq
    _cr_seq += 1
    wid = f"CRW-{_cr_seq:04d}"
    record = _pick_record("contract-review", scenario=scenario) or {}
    if contract_id:
        record = {**record, "contract_id": contract_id}
    w = build_fleet_contract_review_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "contract-review",
        "contract_review": w.payload.get("contract_review"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetContractReviewOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    _apply_business_time_to_workflow("contract-review", wid)
    return wid
# === END hand-graduated wave 2: fleet-contract-review ===


# === BEGIN hand-graduated wave 2: fleet-privacy-dpia ===
_dpi_seq = 0


async def spawn_fleet_privacy_dpia_workflow(
    dpia_id: str | None = None,
    scenario: str | None = None,
) -> str:
    global _dpi_seq
    _dpi_seq += 1
    wid = f"DPI-{_dpi_seq:04d}"
    record = _pick_record("privacy-dpia", scenario=scenario) or {}
    if dpia_id:
        record = {**record, "dpia_id": dpia_id}
    w = build_fleet_privacy_dpia_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "privacy-dpia",
        "dpia": w.payload.get("dpia"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetPrivacyDpiaOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END hand-graduated wave 2: fleet-privacy-dpia ===


# === BEGIN hand-graduated wave 2: fleet-treasury-fx ===
_tfx_seq = 0


async def spawn_fleet_treasury_fx_workflow(
    op_id: str | None = None,
    scenario: str | None = None,
) -> str:
    global _tfx_seq
    _tfx_seq += 1
    wid = f"TFX-{_tfx_seq:04d}"
    record = _pick_record("treasury-fx", scenario=scenario) or {}
    if op_id:
        record = {**record, "op_id": op_id}
    w = build_fleet_treasury_fx_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "treasury-fx",
        "treasury_op": w.payload.get("treasury_op"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetTreasuryFxOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END hand-graduated wave 2: fleet-treasury-fx ===


# === BEGIN POC3: creative-campaign ===
_cmp_seq = 0


async def spawn_creative_campaign_workflow(
    brief_id: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn a creative-campaign workflow. Picks a record from
    data/synthetic/creative-campaign/briefs.json (filtered by `scenario`
    when set); falls back to inline synthesis when the corpus is missing.
    Upserts a Workflow record so the FM's `query_fleet` can see it.
    """
    global _cmp_seq
    _cmp_seq += 1
    wid = f"CMP-{_cmp_seq:04d}"
    record = _pick_record("creative-campaign", scenario=scenario) or {}
    if brief_id:
        record = {**record, "id": brief_id}
    w = build_creative_campaign_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "creative-campaign",
        "brief": w.payload.get("brief"),
        "brief_id": (w.payload.get("brief") or {}).get("id"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="CreativeCampaignOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END POC3: creative-campaign ===


# === BEGIN pitch-c1: generic strategic-domain spawners ===
# These five domains were previously stub=True placeholders; pitch-c1
# graduates them to live workflows with deterministic phases. The
# orchestrators in function_app.py are minimal pass-through stubs — the
# domains exist to populate the entity graph and exercise the substrate.
from api.shared.types import Workflow as _Workflow  # noqa: E402


def _build_strategic_workflow(
    workflow_id: str,
    workflow_type: str,
    payload_key: str,
    payload_data: dict,
    *,
    initial_phase: str = "Intake",
) -> _Workflow:
    """Generic Workflow factory for pitch-c1/c2/c3 strategic domains.

    Strategic / meta / agency-specific domains don't need bespoke
    synthetic-data factories — they share a tiny payload shape.
    """
    import time as _time
    now = _time.time()
    return _Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase=initial_phase,
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava",
        payload={payload_key: dict(payload_data), "scenario": payload_data.get("scenario")},
    )


_h2p_seq = 0


async def spawn_hire_to_productive_workflow(scenario: str | None = None) -> str:
    """Spawn a hire-to-productive (H2P) workflow."""
    global _h2p_seq
    _h2p_seq += 1
    wid = f"H2P-{_h2p_seq:04d}"
    data = {
        "joiner_id": f"EMP-{1000 + _h2p_seq:04d}",
        "role_family": "engineering",
        "scenario": scenario,
    }
    w = _build_strategic_workflow(wid, "hire-to-productive", "joiner", data)
    app_state.store.upsert_workflow(w)
    payload = {"workflow_id": wid, "type": "hire-to-productive", "joiner": data}
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="HireToProductiveOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


_vrp_seq = 0


async def spawn_vendor_risk_to_pay_workflow(scenario: str | None = None) -> str:
    """Spawn a vendor-risk-to-pay (VRP) workflow."""
    global _vrp_seq
    _vrp_seq += 1
    wid = f"VRP-{_vrp_seq:04d}"
    data = {
        "vendor_name": f"Vendor-{_vrp_seq:03d}",
        "amount_gbp": 12000.0,
        "scenario": scenario,
    }
    w = _build_strategic_workflow(wid, "vendor-risk-to-pay", "vendor_payment", data)
    app_state.store.upsert_workflow(w)
    payload = {"workflow_id": wid, "type": "vendor-risk-to-pay", "vendor_payment": data}
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="VendorRiskToPayOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


_l2c_seq = 0


async def spawn_lead_to_cash_workflow(scenario: str | None = None) -> str:
    """Spawn a lead-to-cash (L2C) workflow."""
    global _l2c_seq
    _l2c_seq += 1
    wid = f"L2C-{_l2c_seq:04d}"
    data = {
        "client_name": f"Client-{_l2c_seq:03d}",
        "deal_value_gbp": 75000.0,
        "scenario": scenario,
    }
    w = _build_strategic_workflow(wid, "lead-to-cash", "deal", data)
    app_state.store.upsert_workflow(w)
    payload = {"workflow_id": wid, "type": "lead-to-cash", "deal": data}
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="LeadToCashOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


_fyc_seq = 0


async def spawn_fy_close_workflow(scenario: str | None = None) -> str:
    """Spawn a fy-close (FYC) workflow."""
    global _fyc_seq
    _fyc_seq += 1
    wid = f"FYC-{_fyc_seq:04d}"
    data = {
        "fiscal_year": "FY2026",
        "entity": "Zava-Group",
        "scenario": scenario,
    }
    w = _build_strategic_workflow(wid, "fy-close", "close", data)
    app_state.store.upsert_workflow(w)
    payload = {"workflow_id": wid, "type": "fy-close", "close": data}
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FyCloseOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


_brd_seq = 0


async def spawn_board_prep_workflow(scenario: str | None = None) -> str:
    """Spawn a board-prep (BRD) workflow."""
    global _brd_seq
    _brd_seq += 1
    wid = f"BRD-{_brd_seq:04d}"
    data = {
        "meeting_date": "2026-Q2",
        "agenda": "quarterly-review",
        "scenario": scenario,
    }
    w = _build_strategic_workflow(wid, "board-prep", "board_pack", data)
    app_state.store.upsert_workflow(w)
    payload = {"workflow_id": wid, "type": "board-prep", "board_pack": data}
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="BoardPrepOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END pitch-c1: generic strategic-domain spawners ===


# === BEGIN pitch-c2: cross-domain meta-workflow spawners ===
# Each meta-workflow synchronously emits 2-4 ``workflow.sub_spawned`` bus
# events. The MetaWorkflowReflector listens and links the children via
# SUB_WORKFLOW_OF in the entity graph. The meta orchestrator itself is a
# minimal pass-through stub in function_app.py.


def _emit_sub_spawned(parent_id: str, parent_type: str, child_type: str, child_id: str) -> None:
    """Emit a ``workflow.sub_spawned`` FleetEvent for the meta-workflow reflector."""
    try:
        from api.shared.events import FleetEvent
        app_state.bus.emit(FleetEvent(
            type="workflow.sub_spawned",
            workflow_id=parent_id,
            parent_workflow_id=parent_id,
            parent_workflow_type=parent_type,
            child_workflow_id=child_id,
            child_workflow_type=child_type,
        ))
    except Exception as ex:
        print(f"[orchestrator] failed to emit sub_spawned for {parent_id}->{child_id}: {ex}")


async def _spawn_meta_workflow(
    *,
    workflow_type: str,
    prefix: str,
    seq: int,
    orchestrator_name: str,
    children: tuple[tuple[str, str], ...],
    payload_extras: dict | None = None,
) -> str:
    """Generic meta-workflow spawner: upserts a parent Workflow record,
    schedules a stub orchestration, and emits one workflow.sub_spawned
    event per (child_type, child_id) tuple.
    """
    wid = f"{prefix}-{seq:04d}"
    data = {"meta_kind": workflow_type, **(payload_extras or {})}
    w = _build_strategic_workflow(wid, workflow_type, "meta", data)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": workflow_type,
        "meta": data,
        "children": [{"type": c_type, "id": c_id} for c_type, c_id in children],
    }
    try:
        result = await schedule_new_orchestration(
            payload, function_name=orchestrator_name,
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    for child_type, child_id in children:
        _emit_sub_spawned(wid, workflow_type, child_type, child_id)
    _apply_business_time_to_workflow(workflow_type, wid)
    return wid


_mpw_seq = 0


async def spawn_media_pitch_to_win_workflow(scenario: str | None = None) -> str:
    """Spawn a media-pitch-to-win meta-workflow.

    Children: creative-campaign, contract-review, privacy-dpia.
    """
    global _mpw_seq
    _mpw_seq += 1
    children = (
        ("creative-campaign", f"CMP-mpw-{_mpw_seq:04d}"),
        ("contract-review", f"CRW-mpw-{_mpw_seq:04d}"),
        ("privacy-dpia", f"DPI-mpw-{_mpw_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="media-pitch-to-win",
        prefix="MPW",
        seq=_mpw_seq,
        orchestrator_name="MediaPitchToWinOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )


_aob_seq = 0


async def spawn_account_onboarding_workflow(scenario: str | None = None) -> str:
    """Spawn an account-onboarding meta-workflow.

    Children: contract-review, privacy-dpia, it-access-request, employee-onboarding.
    """
    global _aob_seq
    _aob_seq += 1
    children = (
        ("contract-review", f"CRW-aob-{_aob_seq:04d}"),
        ("privacy-dpia", f"DPI-aob-{_aob_seq:04d}"),
        ("it-access-request", f"ITAR-aob-{_aob_seq:04d}"),
        ("employee-onboarding", f"ONB-aob-{_aob_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="account-onboarding",
        prefix="AOB",
        seq=_aob_seq,
        orchestrator_name="AccountOnboardingOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )


_icr_seq = 0


async def spawn_intercompany_recharge_workflow(scenario: str | None = None) -> str:
    """Spawn an intercompany-recharge meta-workflow.

    Children: ap-invoice, treasury-fx.
    """
    global _icr_seq
    _icr_seq += 1
    children = (
        ("ap-invoice", f"API-icr-{_icr_seq:04d}"),
        ("treasury-fx", f"TFX-icr-{_icr_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="intercompany-recharge",
        prefix="ICR",
        seq=_icr_seq,
        orchestrator_name="IntercompanyRechargeOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )


_tlr_seq = 0


async def spawn_talent_redeployment_workflow(scenario: str | None = None) -> str:
    """Spawn a talent-redeployment meta-workflow.

    Children: hire-to-productive, perf-review, it-access-request.
    """
    global _tlr_seq
    _tlr_seq += 1
    children = (
        ("hire-to-productive", f"H2P-tlr-{_tlr_seq:04d}"),
        ("perf-review", f"PRR-tlr-{_tlr_seq:04d}"),
        ("it-access-request", f"ITAR-tlr-{_tlr_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="talent-redeployment",
        prefix="TLR",
        seq=_tlr_seq,
        orchestrator_name="TalentRedeploymentOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )


_anr_seq = 0


async def spawn_agency_network_roll_up_workflow(scenario: str | None = None) -> str:
    """Spawn an agency-network-roll-up meta-workflow.

    Children: fy-close, board-prep.
    """
    global _anr_seq
    _anr_seq += 1
    children = (
        ("fy-close", f"FYC-anr-{_anr_seq:04d}"),
        ("board-prep", f"BRD-anr-{_anr_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="agency-network-roll-up",
        prefix="ANR",
        seq=_anr_seq,
        orchestrator_name="AgencyNetworkRollUpOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )


_mai_seq = 0


async def spawn_m_and_a_integration_workflow(scenario: str | None = None) -> str:
    """Spawn an m-and-a-integration meta-workflow.

    Children: contract-review, vendor-kyc, employee-onboarding, it-access-request.
    """
    global _mai_seq
    _mai_seq += 1
    children = (
        ("contract-review", f"CRW-mai-{_mai_seq:04d}"),
        ("vendor-kyc", f"VKY-mai-{_mai_seq:04d}"),
        ("employee-onboarding", f"ONB-mai-{_mai_seq:04d}"),
        ("it-access-request", f"ITAR-mai-{_mai_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="m-and-a-integration",
        prefix="MAI",
        seq=_mai_seq,
        orchestrator_name="MAndAIntegrationOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )


_crs_seq = 0


async def spawn_crisis_response_workflow(scenario: str | None = None) -> str:
    """Spawn a crisis-response meta-workflow.

    Children: privacy-dpia, contract-review.
    """
    global _crs_seq
    _crs_seq += 1
    children = (
        ("privacy-dpia", f"DPI-crs-{_crs_seq:04d}"),
        ("contract-review", f"CRW-crs-{_crs_seq:04d}"),
    )
    return await _spawn_meta_workflow(
        workflow_type="crisis-response",
        prefix="CRS",
        seq=_crs_seq,
        orchestrator_name="CrisisResponseOrchestrator",
        children=children,
        payload_extras={"scenario": scenario} if scenario else None,
    )
# === END pitch-c2: cross-domain meta-workflow spawners ===


# === BEGIN telco: network-incident spawner ===
# Secondary trigger only. The authoritative live trigger is the actor-world
# ``network.anomaly`` sensor bridged to NetworkIncidentOrchestrator (see
# api/server/services/world_bridge.py). This lets the simulator ramp loop
# schedule the same orchestrator with a synthetic single-site observation;
# with no affected sessions supplied the decision activity defers, so a
# ramp-spawned instance never mutates the live world.
_nir_seq = 0


async def spawn_network_incident_workflow(scenario: str | None = None) -> str:
    """Spawn a network-incident workflow (simulator secondary trigger)."""
    global _nir_seq
    _nir_seq += 1
    wid = f"NIR-{_nir_seq:04d}"
    # Raw observation, passed as-is for payload_key "incident" — the same
    # single-nesting shape every other strategic spawner uses (see
    # spawn_hire_to_productive_workflow etc). No extra wrapping here; the
    # projection reads workflow.payload["incident"]["incident_site"] directly.
    observation = {
        "incident_site": {"id": "SITE-01", "status": "failed"},
        "neighbor_sites": [],
        "affected_sessions": [],
        "scenario": scenario,
    }
    w = _build_strategic_workflow(wid, "network-incident", "incident", observation)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "network-incident",
        "trace_id": wid,
        "observation": observation,
    }
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="NetworkIncidentOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    _apply_business_time_to_workflow("network-incident", wid)
    return wid
# === END telco: network-incident spawner ===


# === BEGIN pitch-c3: agency-specific domain spawners ===
# Ten domains scoped to agency operations. Each shares the
# _build_strategic_workflow factory and is a thin spawn wrapper.


async def _spawn_agency_workflow(
    *,
    workflow_type: str,
    prefix: str,
    seq: int,
    payload_key: str,
    payload_data: dict,
    orchestrator_name: str,
    scenario: str | None = None,
) -> str:
    wid = f"{prefix}-{seq:04d}"
    if scenario:
        payload_data = {**payload_data, "scenario": scenario}
    w = _build_strategic_workflow(wid, workflow_type, payload_key, payload_data)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": workflow_type,
        payload_key: payload_data,
    }
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name=orchestrator_name,
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    _apply_business_time_to_workflow(workflow_type, wid)
    return wid


_cas_seq = 0


async def spawn_creative_awards_submission_workflow(scenario: str | None = None) -> str:
    global _cas_seq
    _cas_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="creative-awards-submission", prefix="CAS", seq=_cas_seq,
        payload_key="submission",
        payload_data={"award": "Cannes-Lions", "campaign": f"Campaign-{_cas_seq:03d}"},
        orchestrator_name="CreativeAwardsSubmissionOrchestrator", scenario=scenario,
    )


_clr_seq = 0


async def spawn_client_renewal_workflow(scenario: str | None = None) -> str:
    global _clr_seq
    _clr_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="client-renewal", prefix="CLR", seq=_clr_seq,
        payload_key="renewal",
        payload_data={"client_name": f"Client-{_clr_seq:03d}", "annual_value_gbp": 250000.0,
                      "brand_name": f"Brand-{_clr_seq:03d}"},
        orchestrator_name="ClientRenewalOrchestrator", scenario=scenario,
    )


_fob_seq = 0


async def spawn_freelancer_onboarding_workflow(scenario: str | None = None) -> str:
    global _fob_seq
    _fob_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="freelancer-onboarding", prefix="FOB", seq=_fob_seq,
        payload_key="freelancer",
        payload_data={"freelancer_id": f"FRL-{_fob_seq:04d}", "discipline": "creative"},
        orchestrator_name="FreelancerOnboardingOrchestrator", scenario=scenario,
    )


_dcr_seq = 0


async def spawn_data_clean_room_setup_workflow(scenario: str | None = None) -> str:
    global _dcr_seq
    _dcr_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="data-clean-room-setup", prefix="DCR", seq=_dcr_seq,
        payload_key="clean_room",
        payload_data={"partner_org": f"Partner-{_dcr_seq:03d}", "data_classes": ["audience", "spend"]},
        orchestrator_name="DataCleanRoomSetupOrchestrator", scenario=scenario,
    )


_wpr_seq = 0


async def spawn_weekly_pitch_review_workflow(scenario: str | None = None) -> str:
    global _wpr_seq
    _wpr_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="weekly-pitch-review", prefix="WPR", seq=_wpr_seq,
        payload_key="review",
        payload_data={"week_label": f"W{_wpr_seq:02d}", "pitch_count": 7},
        orchestrator_name="WeeklyPitchReviewOrchestrator", scenario=scenario,
    )


_mcp_seq = 0


async def spawn_monthly_client_pnl_workflow(scenario: str | None = None) -> str:
    global _mcp_seq
    _mcp_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="monthly-client-pnl", prefix="MCP", seq=_mcp_seq,
        payload_key="pnl",
        payload_data={"client_name": f"Client-{_mcp_seq:03d}", "month": "2026-04",
                      "revenue_gbp": 120000.0},
        orchestrator_name="MonthlyClientPnlOrchestrator", scenario=scenario,
    )


_qca_seq = 0


async def spawn_quarterly_creative_awards_workflow(scenario: str | None = None) -> str:
    global _qca_seq
    _qca_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="quarterly-creative-awards", prefix="QCA", seq=_qca_seq,
        payload_key="quarterly_awards",
        payload_data={"quarter": f"2026-Q{(_qca_seq % 4) + 1}", "shortlist_size": 12},
        orchestrator_name="QuarterlyCreativeAwardsOrchestrator", scenario=scenario,
    )


_abs_seq = 0


async def spawn_annual_budget_setting_workflow(scenario: str | None = None) -> str:
    global _abs_seq
    _abs_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="annual-budget-setting", prefix="ABS", seq=_abs_seq,
        payload_key="budget",
        payload_data={"fiscal_year": "FY2027", "total_gbp": 12000000.0},
        orchestrator_name="AnnualBudgetSettingOrchestrator", scenario=scenario,
    )


_nbp_seq = 0


async def spawn_new_business_pipeline_scrub_workflow(scenario: str | None = None) -> str:
    global _nbp_seq
    _nbp_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="new-business-pipeline-scrub", prefix="NBP", seq=_nbp_seq,
        payload_key="scrub",
        payload_data={"week_label": f"W{_nbp_seq:02d}", "pipeline_count": 24},
        orchestrator_name="NewBusinessPipelineScrubOrchestrator", scenario=scenario,
    )


_itt_seq = 0


async def spawn_intercompany_talent_transfer_workflow(scenario: str | None = None) -> str:
    global _itt_seq
    _itt_seq += 1
    return await _spawn_agency_workflow(
        workflow_type="intercompany-talent-transfer", prefix="ITT", seq=_itt_seq,
        payload_key="transfer",
        payload_data={"employee_id": f"EMP-{2000 + _itt_seq:04d}",
                      "from_subsidiary": "Zava-UK", "to_subsidiary": "Zava-DE"},
        orchestrator_name="IntercompanyTalentTransferOrchestrator", scenario=scenario,
    )
# === END pitch-c3: agency-specific domain spawners ===


# === BEGIN compose-domain fleet-employee-transfer ===
_fet_seq = 0


async def spawn_fleet_employee_transfer_workflow(
    employee_id: str | None = None,
    source_org_id: str | None = None,
    target_org_id: str | None = None,
    effective_date: str | None = None,
    target_role: str | None = None,
    business_reason: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn an Employee transfer between organisations workflow.

    Mirrors the v3 fleet-* spawn helpers: builds a Workflow via the
    synthetic-data factory, upserts it into app_state.store (so it shows
    up in /api/workflows/* + the Feed UI), schedules the Durable
    orchestration, and back-fills the instance id on completion.
    """
    from api.server.services.synthetic_data import build_fleet_employee_transfer_workflow

    global _fet_seq
    _fet_seq += 1
    wid = f"EXF-{_fet_seq:04d}"
    _emp_ids = ["EMP-1001", "EMP-1042", "EMP-1107", "EMP-1284", "EMP-1396"]
    _source_orgs = ["ORG-HELIOS-UK", "ORG-NORTHWIND-DE", "ORG-MERIDIAN-FR"]
    _target_orgs = ["ORG-NORTHWIND-DE", "ORG-AURORA-US", "ORG-HELIOS-UK"]
    _dates = ["2026-07-01", "2026-08-01", "2026-09-01"]
    _roles = ["Senior Planner", "Account Director", "Strategy Lead"]
    transfer_seed = {
        "employee_id": employee_id or _emp_ids[(_fet_seq * 7) % len(_emp_ids)],
        "source_org_id": source_org_id or _source_orgs[(_fet_seq * 5) % len(_source_orgs)],
        "target_org_id": target_org_id or _target_orgs[(_fet_seq * 3) % len(_target_orgs)],
        "effective_date": effective_date or _dates[(_fet_seq * 2) % len(_dates)],
        "target_role": target_role or _roles[(_fet_seq * 11) % len(_roles)],
        "business_reason": business_reason or "Regional rebalance",
    }
    record = {"transfer": transfer_seed}
    if scenario:
        record["scenario"] = scenario
    w = build_fleet_employee_transfer_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "employee-transfer",
        "transfer": w.payload.get("transfer"),
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetEmployeeTransferOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END compose-domain fleet-employee-transfer ===


# === BEGIN compose-domain fleet-training-request ===
_ftr_seq = 0


async def spawn_fleet_training_request_workflow(
    employee_id: str | None = None,
    topic: str | None = None,
    requested_course: str | None = None,
    estimated_cost_gbp: float | None = None,
    target_start_date: str | None = None,
    department: str | None = None,
    scenario: str | None = None,
) -> str:
    """Spawn a Training request workflow.

    Mirrors the v3 fleet-* spawn helpers: builds a Workflow via the
    synthetic-data factory, upserts it into app_state.store (so it shows
    up in /api/workflows/* + the Feed UI + AuthorityCard + HITL routing),
    schedules the Durable orchestration, and back-fills the instance id
    on completion. (KR-1 hand-patch applied.)
    """
    from api.server.services.synthetic_data import build_fleet_training_request_workflow

    global _ftr_seq
    _ftr_seq += 1
    wid = f"TRQ-{_ftr_seq:04d}"
    _emp_ids = ["EMP-1001", "EMP-1042", "EMP-1107", "EMP-1284", "EMP-1396"]
    _topics = ["leadership", "data", "creative", "engineering", "compliance"]
    _titles = [
        "Influencing Without Authority",
        "Advanced Data Storytelling",
        "Creative Direction Fundamentals",
        "Modern Engineering Practices",
        "GDPR Refresher for People Managers",
    ]
    _depts = ["Strategy", "Data Science", "Creative", "Engineering", "Compliance"]
    _dates = ["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"]
    _costs = [350.0, 720.0, 1100.0, 1800.0]
    request_seed = {
        "employee_id": employee_id or _emp_ids[(_ftr_seq * 7) % len(_emp_ids)],
        "topic": topic or _topics[(_ftr_seq * 5) % len(_topics)],
        "requested_course": requested_course or _titles[(_ftr_seq * 3) % len(_titles)],
        "estimated_cost_gbp": (
            estimated_cost_gbp if estimated_cost_gbp is not None
            else _costs[(_ftr_seq * 11) % len(_costs)]
        ),
        "target_start_date": target_start_date or _dates[(_ftr_seq * 2) % len(_dates)],
        "department": department or _depts[(_ftr_seq * 13) % len(_depts)],
    }
    record: dict = {"request": request_seed}
    if scenario:
        record["scenario"] = scenario
    w = build_fleet_training_request_workflow(wid, record=record)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": wid,
        "type": "training-request",
        **{k: v for k, v in w.payload.items() if k != "scenario"},
    }
    if scenario or w.payload.get("scenario"):
        payload["scenario"] = scenario or w.payload.get("scenario")
    try:
        result = await schedule_new_orchestration(
            payload, function_name="FleetTrainingRequestOrchestrator",
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid
# === END compose-domain fleet-training-request ===
