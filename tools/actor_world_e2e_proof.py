#!/usr/bin/env python3
"""Assertion driver for Plan 2 Task 6 — the real actor → Durable → worker proof.

This drives an ALREADY-RUNNING stack (booted by ``actor_world_e2e_proof.sh``):

  * FastAPI (:3101) hosting the live ``ActorWorldService`` (``ZAVA_WORLD=support``)
  * Azure Durable Functions host (:7071) with ``SurgeStaffingOrchestrator`` indexed

It proves the closed loop end to end against the REAL stack — no mocks:

  1. Read baseline ``/api/world/state``; record reserve/support worker IDs + seq.
  2. Inject a demand surge.
  3. Poll ``/api/world/events`` (from the baseline cursor, accumulating/deduping
     by ``seq``) until the causal journal contains a real sensor trip, a real
     Durable responder request/decision, an accepted command and at least one
     reallocated worker.
  4. Snapshot the post-command world; assert the reallocated actors were
     baseline reserve workers and are now on ``TEAM-SUPPORT``.
  5. Keep polling until a ``ticket.resolved`` lands *after* the command — proof
     the world keeps running after the intervention.
  6. Query the Durable runtime on :7071 directly; require ``Completed`` with an
     actor-level observation input and a typed ``reallocate_workers`` output
     whose worker IDs equal the journal's reallocated IDs.
  7. Validate the causal chain sensor → requested → decided → accepted →
     reallocated via ``cause_event_id``/``trace_id``.
  8. Write evidence and print one JSON summary. Exit 0 only if every assertion
     holds.

Every network read has a bounded deadline; the driver never blocks forever.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

API_BASE = os.getenv("WORLD_API_BASE", "http://127.0.0.1:3101").rstrip("/")
FUNC_BASE = os.getenv("FUNCTIONS_HOST", "http://127.0.0.1:7071").rstrip("/")
TASK_HUB = os.getenv("WORLD_TASK_HUB", "InvoiceP2PHub")
OUT_DIR = Path(os.getenv("PROOF_OUT_DIR", "tmp/actor-world-e2e-proof"))

SURGE_MULTIPLIER = float(os.getenv("PROOF_SURGE_MULTIPLIER", "4"))
SURGE_DURATION = float(os.getenv("PROOF_SURGE_DURATION", "90"))

# Bounded deadlines (wall seconds). The live sim runs ~480 sim-min at
# 10 min/s ≈ 48 wall-s, so these are generous but finite.
CHAIN_DEADLINE = float(os.getenv("PROOF_CHAIN_DEADLINE", "90"))
RESOLVE_DEADLINE = float(os.getenv("PROOF_RESOLVE_DEADLINE", "45"))
DURABLE_DEADLINE = float(os.getenv("PROOF_DURABLE_DEADLINE", "30"))
POLL_INTERVAL = float(os.getenv("PROOF_POLL_INTERVAL", "0.4"))

REQUIRED_TYPES = {
    "sensor.tripped",
    "responder.requested",
    "responder.decided",
    "command.accepted",
    "worker.reallocated",
}


class ProofError(AssertionError):
    """Raised when a proof assertion fails; carries a human-readable reason."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def _as_obj(value: Any) -> Any:
    """Durable status fields (input/output) arrive as an object or a JSON string."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _write(name: str, data: Any) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _reserve_ids(snapshot: dict) -> set[str]:
    return {w["id"] for w in snapshot["workers"] if w["team_id"] == "TEAM-RESERVE"}


def _support_ids(snapshot: dict) -> set[str]:
    return {w["id"] for w in snapshot["workers"] if w["team_id"] == "TEAM-SUPPORT"}


class Proof:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        # seq -> event, deduped/accumulated across every poll.
        self.events: dict[int, dict[str, Any]] = {}
        self.cursor = 0

    # -- HTTP helpers --------------------------------------------------------

    def get_state(self) -> dict:
        resp = self.client.get(f"{API_BASE}/api/world/state", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def inject_surge(self) -> dict:
        resp = self.client.post(
            f"{API_BASE}/api/world/inject/demand_surge",
            json={"multiplier": SURGE_MULTIPLIER, "duration_minutes": SURGE_DURATION},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def drain_events(self) -> None:
        """Fetch every journal event after the moving cursor into ``self.events``."""
        resp = self.client.get(
            f"{API_BASE}/api/world/events", params={"after": self.cursor}, timeout=10
        )
        resp.raise_for_status()
        body = resp.json()
        _require(bool(body.get("enabled")), "actor-world /events reported disabled")
        for event in body.get("events", []):
            self.events[int(event["seq"])] = event
        if self.events:
            self.cursor = max(self.cursor, max(self.events))

    def seen_types(self) -> set[str]:
        return {event["type"] for event in self.events.values()}

    def by_type(self, event_type: str, *, trace: str | None = None) -> list[dict]:
        out = [
            event
            for event in self.events.values()
            if event["type"] == event_type
            and (trace is None or event["trace_id"] == trace)
        ]
        out.sort(key=lambda event: event["seq"])
        return out

    # -- phases --------------------------------------------------------------

    def poll_for_required_chain(self) -> None:
        deadline = time.monotonic() + CHAIN_DEADLINE
        while True:
            self.drain_events()
            missing = REQUIRED_TYPES - self.seen_types()
            if not missing:
                return
            if time.monotonic() >= deadline:
                raise ProofError(
                    "timed out waiting for causal chain; still missing "
                    f"{sorted(missing)} after {CHAIN_DEADLINE:.0f}s "
                    f"(saw {sorted(self.seen_types())})"
                )
            time.sleep(POLL_INTERVAL)

    def wait_for_last_response(self) -> dict:
        deadline = time.monotonic() + DURABLE_DEADLINE
        while True:
            snapshot = self.get_state()
            last = snapshot.get("last_response")
            if isinstance(last, dict) and last.get("instance_id"):
                return snapshot
            if time.monotonic() >= deadline:
                raise ProofError(
                    "world state never exposed a Durable last_response.instance_id"
                )
            time.sleep(POLL_INTERVAL)

    def poll_for_trace(self, trace: str) -> None:
        """Ensure every required event for the anchored trace is present."""
        deadline = time.monotonic() + DURABLE_DEADLINE
        while True:
            self.drain_events()
            have = {event["type"] for event in self.events.values() if event["trace_id"] == trace}
            if REQUIRED_TYPES <= have:
                return
            if time.monotonic() >= deadline:
                raise ProofError(
                    f"trace {trace!r} incomplete: missing {sorted(REQUIRED_TYPES - have)}"
                )
            time.sleep(POLL_INTERVAL)

    def poll_for_resolved_after(self, command_seq: int) -> dict:
        deadline = time.monotonic() + RESOLVE_DEADLINE
        while True:
            self.drain_events()
            later = [
                event
                for event in self.by_type("ticket.resolved")
                if event["seq"] > command_seq
            ]
            if later:
                return later[0]
            if time.monotonic() >= deadline:
                raise ProofError(
                    "no ticket.resolved observed after command.accepted seq "
                    f"{command_seq} within {RESOLVE_DEADLINE:.0f}s"
                )
            time.sleep(POLL_INTERVAL)

    def fetch_durable(self, instance_id: str) -> dict:
        url = f"{FUNC_BASE}/runtime/webhooks/durabletask/instances/{instance_id}"
        params = {"taskHub": TASK_HUB, "connection": "Storage", "showHistory": "true"}
        deadline = time.monotonic() + DURABLE_DEADLINE
        last_status = None
        while True:
            resp = self.client.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                last_status = data.get("runtimeStatus")
                if last_status == "Completed":
                    return data
                if last_status in {"Failed", "Terminated", "Canceled"}:
                    raise ProofError(
                        f"Durable instance {instance_id} ended {last_status}: "
                        f"{data.get('output')}"
                    )
            if time.monotonic() >= deadline:
                raise ProofError(
                    f"Durable instance {instance_id} not Completed within "
                    f"{DURABLE_DEADLINE:.0f}s (last status={last_status}, "
                    f"http={resp.status_code})"
                )
            time.sleep(POLL_INTERVAL)


def run() -> dict:
    started = time.monotonic()
    timeline: list[dict[str, Any]] = []

    def mark(label: str, **extra: Any) -> None:
        timeline.append({"t": round(time.monotonic() - started, 3), "step": label, **extra})

    with httpx.Client() as client:
        proof = Proof(client)

        # 1. Baseline ------------------------------------------------------
        baseline = proof.get_state()
        _require(baseline.get("enabled") is True, "world not enabled at baseline")
        _require(baseline.get("scenario") == "support", "baseline scenario is not 'support'")
        baseline_reserve = _reserve_ids(baseline)
        baseline_support = _support_ids(baseline)
        baseline_seq = int(baseline["latest_seq"])
        _require(bool(baseline_reserve), "baseline has no TEAM-RESERVE workers")
        proof.cursor = baseline_seq
        _write("baseline.json", baseline)
        mark(
            "baseline",
            latest_seq=baseline_seq,
            reserve=sorted(baseline_reserve),
            support_count=len(baseline_support),
        )

        # 2. Inject surge --------------------------------------------------
        injected = proof.inject_surge()
        mark("inject_demand_surge", sim_time=injected.get("sim_time"))

        # 3. Poll journal until the full chain exists ----------------------
        proof.poll_for_required_chain()
        mark("chain_present", seen=sorted(proof.seen_types() & REQUIRED_TYPES))

        # 4. Anchor on the Durable response and snapshot the post-command world
        final = proof.wait_for_last_response()
        last_response = final["last_response"]
        instance_id = str(last_response["instance_id"])
        command_data = last_response.get("command") or {}
        anchor_trace = str(command_data.get("trace_id"))
        _require(bool(anchor_trace), "last_response command carried no trace_id")
        proof.poll_for_trace(anchor_trace)

        sensor = proof.by_type("sensor.tripped", trace=anchor_trace)
        requested = proof.by_type("responder.requested", trace=anchor_trace)
        decided = proof.by_type("responder.decided", trace=anchor_trace)
        accepted = proof.by_type("command.accepted", trace=anchor_trace)
        reallocated = proof.by_type("worker.reallocated", trace=anchor_trace)
        _require(bool(sensor), f"no sensor.tripped for trace {anchor_trace!r}")
        _require(bool(requested), f"no responder.requested for trace {anchor_trace!r}")
        _require(bool(decided), f"no responder.decided for trace {anchor_trace!r}")
        _require(bool(accepted), f"no command.accepted for trace {anchor_trace!r}")
        _require(bool(reallocated), f"no worker.reallocated for trace {anchor_trace!r}")

        command_accepted_seq = accepted[0]["seq"]
        reallocated_ids = [event["actor_id"] for event in reallocated]

        _write("final.json", final)
        final_support = _support_ids(final)
        _require(
            set(reallocated_ids) <= baseline_reserve,
            f"reallocated {reallocated_ids} were not all baseline reserve "
            f"{sorted(baseline_reserve)}",
        )
        _require(
            set(reallocated_ids) <= final_support,
            f"reallocated {reallocated_ids} are not all on TEAM-SUPPORT after the "
            f"command (support now {sorted(final_support)})",
        )
        mark(
            "command_applied",
            trace=anchor_trace,
            instance_id=instance_id,
            command_accepted_seq=command_accepted_seq,
            reallocated=reallocated_ids,
        )

        # 5. World continues: a ticket resolves after the command ----------
        resolved = proof.poll_for_resolved_after(command_accepted_seq)
        mark("ticket_resolved_after_command", seq=resolved["seq"], ticket=resolved["actor_id"])

        # 6. Verify the real Durable instance ------------------------------
        durable = proof.fetch_durable(instance_id)
        _write("durable-instance.json", durable)
        _require(
            durable["runtimeStatus"] == "Completed",
            f"Durable runtimeStatus={durable.get('runtimeStatus')!r}, expected Completed",
        )
        durable_input = _as_obj(durable.get("input")) or {}
        observation = (durable_input or {}).get("observation") or {}
        _require(
            isinstance(observation.get("queued_tickets"), list)
            and bool(observation["queued_tickets"]),
            "Durable input observation has no queued_tickets (not actor-level)",
        )
        _require(
            isinstance(observation.get("reserve_workers"), list)
            and bool(observation["reserve_workers"]),
            "Durable input observation has no reserve_workers (not actor-level)",
        )
        _require(
            str(durable_input.get("trace_id")) == anchor_trace,
            f"Durable input trace_id={durable_input.get('trace_id')!r} != {anchor_trace!r}",
        )
        durable_output = _as_obj(durable.get("output")) or {}
        out_command = (durable_output or {}).get("command") or {}
        _require(
            out_command.get("type") == "reallocate_workers",
            f"Durable output command type={out_command.get('type')!r}",
        )
        out_worker_ids = (out_command.get("payload") or {}).get("worker_ids")
        _require(
            out_worker_ids == reallocated_ids,
            f"Durable output worker_ids {out_worker_ids} != journal reallocated "
            f"{reallocated_ids}",
        )
        mark("durable_verified", runtime_status=durable["runtimeStatus"])

        # 7. Causal chain: sensor → requested → decided → accepted → reallocated
        chain_ok, chain = _validate_chain(sensor[0], requested[0], decided[0], accepted[0], reallocated)
        _require(chain_ok, f"causal chain broken: {chain}")
        mark("causal_chain_ok")

        # 8. Evidence + summary -------------------------------------------
        events_sorted = [proof.events[seq] for seq in sorted(proof.events)]
        _write("events.json", events_sorted)
        summary = {
            "result": "PASS",
            "api_base": API_BASE,
            "func_base": FUNC_BASE,
            "task_hub": TASK_HUB,
            "trace_id": anchor_trace,
            "baseline_seq": baseline_seq,
            "baseline_reserve_ids": sorted(baseline_reserve),
            "reallocated_worker_ids": reallocated_ids,
            "reallocated_now_support": sorted(set(reallocated_ids) & final_support),
            "command_accepted_seq": command_accepted_seq,
            "ticket_resolved_after_command": {
                "seq": resolved["seq"],
                "ticket_id": resolved["actor_id"],
            },
            "durable": {
                "instance_id": instance_id,
                "runtime_status": durable["runtimeStatus"],
                "command_type": out_command.get("type"),
                "worker_ids": out_worker_ids,
                "reasoning": durable_output.get("reasoning"),
            },
            "causal_chain": chain,
            "events_captured": len(events_sorted),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "timeline": timeline,
            "evidence_dir": str(OUT_DIR),
        }
        _write("summary.json", summary)
        return summary


def _validate_chain(
    sensor: dict, requested: dict, decided: dict, accepted: dict, reallocated: list[dict]
) -> tuple[bool, dict]:
    """Confirm each hop links to its cause; the accepted→reallocated hop is by
    ``cause_event_id`` and the sensor→…→accepted hops by ``cause_event_id`` with
    a shared ``trace_id`` tying ``command.accepted`` into the episode."""
    trace = sensor["trace_id"]
    chain = {
        "trace_id": trace,
        "sensor": sensor["event_id"],
        "responder_requested": requested["event_id"],
        "responder_decided": decided["event_id"],
        "command_accepted": accepted["event_id"],
        "worker_reallocated": [event["event_id"] for event in reallocated],
    }
    ok = (
        requested["cause_event_id"] == sensor["event_id"]
        and decided["cause_event_id"] == requested["event_id"]
        and accepted["trace_id"] == trace
        and all(event["cause_event_id"] == accepted["event_id"] for event in reallocated)
        and all(
            event["trace_id"] == trace
            for event in (requested, decided, accepted, *reallocated)
        )
    )
    return ok, chain


def main() -> int:
    try:
        summary = run()
    except ProofError as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc)}, indent=2))
        return 1
    except httpx.HTTPError as exc:
        print(json.dumps({"result": "FAIL", "reason": f"HTTP error: {exc}"}, indent=2))
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
