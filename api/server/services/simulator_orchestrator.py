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
from pathlib import Path

from api.server.state import app_state
from api.server.services.synthetic_data import (
    build_workflow, build_expense_workflow, build_hiring_workflow,
    build_fleet_travel_preapproval_workflow,
    build_fleet_vendor_kyc_workflow,
    build_fleet_employee_onboarding_workflow,
    build_fleet_it_access_request_workflow,
    build_fleet_contract_renewal_workflow,
    build_fleet_perf_review_workflow,
)
from api.server.services.durable_client import (
    schedule_new_orchestration, raise_orchestration_event,
)
from api.shared.expense_taxonomy import ReceiptFlavour
from api.shared import domains as _registry

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

    spawners = {
        "expense-claim": spawn_expense_workflow,
        "hiring": spawn_hiring_workflow,
        "travel-preapproval": spawn_travel_preapproval_workflow,
        "employee-onboarding": spawn_fleet_employee_onboarding_workflow,
        "vendor-kyc": spawn_fleet_vendor_kyc_workflow,
        "it-access-request": spawn_fleet_it_access_request_workflow,
        "contract-renewal": spawn_fleet_contract_renewal_workflow,
        "perf-review": spawn_fleet_perf_review_workflow,
    }

    domains_csv = os.getenv("SIMULATOR_RAMP_DOMAINS", "").strip()
    if domains_csv:
        wanted = [d.strip() for d in domains_csv.split(",") if d.strip()]
    else:
        wanted = list(spawners.keys())

    avg_interval = float(os.getenv("SIMULATOR_RAMP_AVG_INTERVAL_SECONDS", "90"))

    # Initial-stagger the per-domain coroutines so we don't spawn every
    # domain at t=0 (which would queue 3+ GHCP SDK subprocesses
    # simultaneously on cold cache).
    valid_domains = []
    for d in wanted:
        if d not in spawners:
            print(f"[ramp] WARNING: unknown domain {d!r}; skipping")
            continue
        valid_domains.append(d)

    if not valid_domains:
        print("[ramp] no valid domains in SIMULATOR_RAMP_DOMAINS; nothing to spawn")
        return

    initial_stagger = avg_interval / max(len(valid_domains), 1)

    print(
        f"[ramp] starting steady-state for domains={valid_domains}, "
        f"avg_interval={avg_interval}s \u00b130%, initial_stagger={initial_stagger:.1f}s/domain"
    )

    tasks = []
    for i, domain in enumerate(valid_domains):
        spawn_fn = spawners[domain]
        # Domain-specific scenario rotation: walk every distinct `scenario`
        # tag in the seed corpus in order. None means "let the spawner
        # round-robin records without filtering" (POC1/POC2 behaviour).
        scenarios = _scenarios_for(domain)
        tasks.append(asyncio.create_task(
            _per_domain_ramp(domain, spawn_fn, avg_interval,
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
    return wid
# === END compose-domain fleet-perf-review ===
