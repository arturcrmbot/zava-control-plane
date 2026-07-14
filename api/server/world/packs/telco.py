"""Explicit-actor telco network-incident scenario running on SimulationRuntime.

Mirrors the support scenario's shape (explicit dataclass actors, deterministic
SimPy generation, a rising-edge sensor, an idempotent typed command) for a
different corporate function: cell-network incident response.

Actors:
  * ``CellSite``    — a radio site with finite capacity and live metrics.
  * ``Subscriber``  — a customer homed on a site.
  * ``NetworkSession`` — an active voice/data/video flow drawing capacity.

The incident lifecycle is fully causal: a site fails → its sessions degrade
and neighbours take reattach congestion → the ``network.anomaly`` sensor trips
→ (via the world bridge) a Durable responder returns a typed
``reroute_sessions`` command → sessions move to real neighbour sites with spare
capacity → the failed site recovers. Same seed ⇒ identical journal.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime

SessionKind = Literal["voice", "data", "video"]
SessionStatus = Literal["active", "degraded", "dropped", "rerouted"]
SiteStatus = Literal["healthy", "failed"]

REGIONS: tuple[str, ...] = ("north", "east", "south", "west")
KINDS: tuple[SessionKind, ...] = ("voice", "data", "video")
# Nominal per-kind demand envelopes (Mbps); jittered deterministically per session.
KIND_DEMAND: dict[SessionKind, tuple[float, float]] = {
    "voice": (0.08, 0.12),
    "data": (1.5, 2.5),
    "video": (4.0, 6.0),
}


@dataclass(slots=True)
class CellSite:
    id: str
    region: str
    capacity_mbps: float
    neighbor_ids: tuple[str, ...]
    status: SiteStatus = "healthy"
    traffic_mbps: float = 0.0
    utilization: float = 0.0
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    reattach_congestion: float = 0.0
    session_ids: set[str] = field(default_factory=set)
    last_event_id: str | None = None


@dataclass(slots=True)
class Subscriber:
    id: str
    home_site_id: str
    tier: str
    session_ids: set[str] = field(default_factory=set)


@dataclass(slots=True)
class NetworkSession:
    id: str
    subscriber_id: str
    site_id: str
    kind: SessionKind
    demand_mbps: float
    origin_site_id: str
    status: SessionStatus = "active"
    last_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class SiteFailure:
    at_minute: float
    site_id: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    site_count: int = 12
    subscriber_count: int = 2_000
    session_count: int = 2_200
    site_capacity_mbps: float = 600.0
    simulation_minutes: float = 240.0
    packet_loss_trip_pct: float = 20.0


def _demand_for(rng, kind: SessionKind) -> float:
    low, high = KIND_DEMAND[kind]
    return round(rng.uniform(low, high), 3)


class NetworkScenario:
    def __init__(self, runtime: SimulationRuntime, config: NetworkConfig) -> None:
        if config.site_count < 4 or config.site_count % len(REGIONS) != 0:
            raise ValueError("site_count must be a multiple of 4 and >= 4")
        if config.subscriber_count <= 0 or config.session_count <= 0:
            raise ValueError("subscriber_count and session_count must be positive")
        self.runtime = runtime
        self.config = config
        self.sites: dict[str, CellSite] = {}
        self.subscribers: dict[str, Subscriber] = {}
        self.sessions: dict[str, NetworkSession] = {}
        self._site_ids: list[str] = []
        self._subscriber_ids: list[str] = []
        self._failed_sites_latched: set[str] = set()
        self.applied_commands: dict[str, SimulationEvent] = {}

    # -- installation ------------------------------------------------------

    def install(self) -> None:
        self.runtime.emit(
            "simulation.started",
            actor_id="scenario:network",
            payload={"seed": self.runtime.seed, "config": asdict(self.config)},
        )
        self._create_sites()
        self._create_subscribers()
        self._create_sessions()
        for site in self.sites.values():
            self._derive_metrics(site)
            self.runtime.emit(
                "site.metrics",
                actor_id=site.id,
                trace_id=f"site-{site.id}",
                payload=self._metrics_payload(site),
            )
        self.runtime.process(self._sensor_loop())

    def _create_sites(self) -> None:
        per_region = self.config.site_count // len(REGIONS)
        ordered: list[tuple[str, str]] = []
        for r_index, region in enumerate(REGIONS):
            for slot in range(per_region):
                site_id = f"SITE-{r_index * per_region + slot + 1:02d}"
                ordered.append((site_id, region))
        for index, (site_id, region) in enumerate(ordered):
            r_index = index // per_region
            slot = index % per_region
            neighbors = [
                other for other in range(r_index * per_region, (r_index + 1) * per_region)
                if other != index
            ]
            bridge = ((r_index + 1) % len(REGIONS)) * per_region + slot
            neighbor_ids = tuple(ordered[n][0] for n in (*neighbors, bridge))
            site = CellSite(
                id=site_id,
                region=region,
                capacity_mbps=self.config.site_capacity_mbps,
                neighbor_ids=neighbor_ids,
            )
            self.sites[site_id] = site
            self._site_ids.append(site_id)
            self.runtime.emit(
                "site.created",
                actor_id=site_id,
                trace_id=f"site-{site_id}",
                payload={
                    "region": region,
                    "capacity_mbps": site.capacity_mbps,
                    "neighbor_ids": list(neighbor_ids),
                },
            )

    def _create_subscribers(self) -> None:
        tiers = ("consumer", "business", "priority")
        for index in range(1, self.config.subscriber_count + 1):
            home = self._site_ids[(index - 1) % len(self._site_ids)]
            tier = self.runtime.rng.choices(tiers, weights=[75, 20, 5], k=1)[0]
            subscriber = Subscriber(id=f"SUB-{index:05d}", home_site_id=home, tier=tier)
            self.subscribers[subscriber.id] = subscriber
            self._subscriber_ids.append(subscriber.id)
            self.runtime.emit(
                "subscriber.created",
                actor_id=subscriber.id,
                target_id=home,
                trace_id=f"subscriber-{subscriber.id}",
                payload={"home_site_id": home, "tier": tier},
            )

    def _create_sessions(self) -> None:
        for index in range(1, self.config.session_count + 1):
            subscriber = self.subscribers[self._subscriber_ids[(index - 1) % len(self._subscriber_ids)]]
            kind: SessionKind = self.runtime.rng.choices(
                KINDS, weights=[45, 40, 15], k=1
            )[0]
            demand = _demand_for(self.runtime.rng, kind)
            session = NetworkSession(
                id=f"SES-{index:06d}",
                subscriber_id=subscriber.id,
                site_id=subscriber.home_site_id,
                kind=kind,
                demand_mbps=demand,
                origin_site_id=subscriber.home_site_id,
            )
            self.sessions[session.id] = session
            subscriber.session_ids.add(session.id)
            site = self.sites[subscriber.home_site_id]
            site.session_ids.add(session.id)
            site.traffic_mbps = round(site.traffic_mbps + demand, 3)
            started = self.runtime.emit(
                "session.started",
                actor_id=session.id,
                target_id=session.site_id,
                trace_id=f"session-{session.id}",
                payload={
                    "subscriber_id": subscriber.id,
                    "site_id": session.site_id,
                    "kind": kind,
                    "demand_mbps": demand,
                },
            )
            session.last_event_id = started.event_id

    # -- metrics -----------------------------------------------------------

    def _derive_metrics(self, site: CellSite) -> None:
        if site.status == "failed":
            site.utilization = 0.0
            site.packet_loss = 1.0
            site.latency_ms = 0.0
            return
        util = site.traffic_mbps / site.capacity_mbps if site.capacity_mbps else 0.0
        site.utilization = round(util, 4)
        congestion = max(0.0, util - 0.85) * 0.4
        site.packet_loss = round(min(0.5, congestion + site.reattach_congestion), 4)
        site.latency_ms = round(15.0 + util * 45.0 + site.reattach_congestion * 120.0, 2)

    def _metrics_payload(self, site: CellSite) -> dict[str, Any]:
        return {
            "status": site.status,
            "traffic_mbps": round(site.traffic_mbps, 3),
            "utilization": site.utilization,
            "packet_loss_pct": round(site.packet_loss * 100.0, 3),
            "latency_ms": site.latency_ms,
            "session_count": len(site.session_ids),
        }

    # -- perturbation ------------------------------------------------------

    def schedule_failure(self, failure: SiteFailure) -> None:
        self.runtime.process(self._failure_process(failure))

    def inject_site_failure(self, site_id: str | None = None) -> str:
        resolved = self._resolve_failure_site(site_id)
        self.schedule_failure(SiteFailure(at_minute=self.runtime.now, site_id=resolved))
        return resolved

    def _resolve_failure_site(self, site_id: str | None) -> str:
        if site_id is not None:
            site = self.sites.get(site_id)
            if site is None:
                raise ValueError(f"unknown site_id: {site_id}")
            if site.status != "healthy":
                raise ValueError(f"site {site_id} is not healthy")
            return site_id
        healthy = [s for s in self.sites.values() if s.status == "healthy"]
        if not healthy:
            raise ValueError("no healthy site to fail")
        ranked = sorted(healthy, key=lambda s: (-s.traffic_mbps, s.id))
        return ranked[0].id

    def _failure_process(self, failure: SiteFailure):
        if failure.at_minute < self.runtime.now:
            raise ValueError("failure cannot start in the past")
        yield self.runtime.env.timeout(failure.at_minute - self.runtime.now)
        site_id = failure.site_id or self._resolve_failure_site(None)
        site = self.sites.get(site_id)
        if site is None or site.status != "healthy":
            return
        self._apply_site_failure(site)

    def _apply_site_failure(self, site: CellSite) -> None:
        prior_traffic = site.traffic_mbps
        prior_util = site.utilization
        affected = sorted(
            (self.sessions[sid] for sid in list(site.session_ids)
             if self.sessions[sid].status == "active"),
            key=lambda s: s.id,
        )
        failed = self.runtime.emit(
            "site.failed",
            actor_id=site.id,
            target_id=f"region:{site.region}",
            trace_id=f"network-incident-{site.id}-{int(self.runtime.now)}",
            payload={
                "region": site.region,
                "capacity_mbps": site.capacity_mbps,
                "prior_traffic_mbps": round(prior_traffic, 3),
                "prior_utilization": prior_util,
                "affected_session_count": len(affected),
                "affected_session_ids": [s.id for s in affected[:20]],
            },
        )
        site.last_event_id = failed.event_id
        for session in affected:
            session.status = "degraded"
            site.session_ids.discard(session.id)
            site.traffic_mbps = round(max(0.0, site.traffic_mbps - session.demand_mbps), 3)
            degraded = self.runtime.emit(
                "session.degraded",
                actor_id=session.id,
                target_id=site.id,
                cause_event_id=failed.event_id,
                trace_id=failed.trace_id,
                payload={
                    "site_id": site.id,
                    "kind": session.kind,
                    "demand_mbps": session.demand_mbps,
                },
            )
            session.last_event_id = degraded.event_id
        site.status = "failed"
        self._derive_metrics(site)
        for neighbor_id in site.neighbor_ids:
            neighbor = self.sites.get(neighbor_id)
            if neighbor is None or neighbor.status != "healthy":
                continue
            neighbor.reattach_congestion = round(neighbor.reattach_congestion + 0.01, 4)
            self._derive_metrics(neighbor)
            self.runtime.emit(
                "site.metrics",
                actor_id=neighbor.id,
                cause_event_id=failed.event_id,
                trace_id=failed.trace_id,
                payload={**self._metrics_payload(neighbor), "reason": "reattach_congestion"},
            )

    # -- sensor ------------------------------------------------------------

    def _sensor_loop(self):
        while self.runtime.now < self.config.simulation_minutes:
            yield self.runtime.env.timeout(1)
            for site_id in self._site_ids:
                site = self.sites[site_id]
                if site.status != "failed" or site_id in self._failed_sites_latched:
                    continue
                self._trip_anomaly(site)
                self._failed_sites_latched.add(site_id)

    def _trip_anomaly(self, site: CellSite) -> None:
        affected = sorted(
            (s for s in self.sessions.values()
             if s.status == "degraded" and s.origin_site_id == site.id),
            key=lambda s: s.id,
        )
        neighbor_util = {
            n: self.sites[n].utilization
            for n in site.neighbor_ids
            if self.sites[n].status == "healthy"
        }
        self.runtime.emit(
            "sensor.tripped",
            actor_id="sensor:network_anomaly",
            target_id=site.id,
            cause_event_id=site.last_event_id,
            trace_id=f"network-anomaly-{site.id}-{int(self.runtime.now)}",
            payload={
                "actor_ids": [s.id for s in affected[:20]],
                "measurements": {
                    "site_id": site.id,
                    "region": site.region,
                    "packet_loss_pct": round(site.packet_loss * 100.0, 3),
                    "affected_session_count": len(affected),
                    "neighbor_utilization": neighbor_util,
                },
            },
        )

    # -- command -----------------------------------------------------------

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        existing = self.applied_commands.get(command.command_id)
        if existing is not None:
            return existing
        if command.type != "reroute_sessions":
            return self._reject_command(command, f"unsupported command type: {command.type!r}")
        reason = self._validate_reroute_sessions(command.payload)
        if reason is not None:
            return self._reject_command(command, reason)
        return self._accept_reroute_sessions(command)

    def _validate_reroute_sessions(self, payload: dict[str, Any]) -> str | None:
        incident_site_id = payload.get("incident_site_id")
        if incident_site_id not in self.sites:
            return f"unknown incident_site_id: {incident_site_id!r}"
        assignments = payload.get("assignments")
        if not isinstance(assignments, list) or not assignments:
            return "assignments must be a non-empty list"
        seen: set[str] = set()
        incoming: dict[str, float] = defaultdict(float)
        for entry in assignments:
            if not isinstance(entry, dict):
                return "each assignment must be an object"
            session_id = entry.get("session_id")
            to_site_id = entry.get("to_site_id")
            if not isinstance(session_id, str) or not isinstance(to_site_id, str):
                return "assignment session_id/to_site_id must be strings"
            if session_id in seen:
                return f"duplicate session_id: {session_id}"
            seen.add(session_id)
            session = self.sessions.get(session_id)
            if session is None:
                return f"unknown session_id: {session_id}"
            if session.status != "degraded":
                return f"session {session_id} is not degraded"
            if session.origin_site_id != incident_site_id:
                return f"session {session_id} is not affected by {incident_site_id}"
            target = self.sites.get(to_site_id)
            if target is None:
                return f"unknown to_site_id: {to_site_id}"
            if to_site_id == incident_site_id:
                return f"cannot reroute session {session_id} back onto the incident site"
            if target.status != "healthy":
                return f"target site {to_site_id} is not healthy"
            incoming[to_site_id] += session.demand_mbps
        for site_id, added in incoming.items():
            target = self.sites[site_id]
            if target.traffic_mbps + added > target.capacity_mbps + 1e-6:
                return f"insufficient capacity at {site_id}"
        return None

    def _reject_command(self, command: SimulationCommand, reason: str) -> SimulationEvent:
        rejected = self.runtime.emit(
            "command.rejected",
            actor_id=command.issued_by,
            target_id=command.payload.get("incident_site_id"),
            trace_id=command.trace_id,
            payload={"command": command.to_dict(), "reason": reason},
        )
        self.applied_commands[command.command_id] = rejected
        return rejected

    def _accept_reroute_sessions(self, command: SimulationCommand) -> SimulationEvent:
        payload = command.payload
        incident_site_id: str = payload["incident_site_id"]
        assignments: list[dict[str, str]] = list(payload["assignments"])
        accepted = self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            target_id=incident_site_id,
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
        self.applied_commands[command.command_id] = accepted

        touched: set[str] = set()
        for entry in assignments:
            session = self.sessions[entry["session_id"]]
            target = self.sites[entry["to_site_id"]]
            from_site_id = session.site_id
            session.site_id = target.id
            session.status = "rerouted"
            target.session_ids.add(session.id)
            target.traffic_mbps = round(target.traffic_mbps + session.demand_mbps, 3)
            self._derive_metrics(target)
            touched.add(target.id)
            rerouted = self.runtime.emit(
                "session.rerouted",
                actor_id=session.id,
                target_id=target.id,
                cause_event_id=accepted.event_id,
                trace_id=command.trace_id,
                payload={
                    "command_id": command.command_id,
                    "from_site_id": from_site_id,
                    "to_site_id": target.id,
                    "kind": session.kind,
                    "demand_mbps": session.demand_mbps,
                },
            )
            session.last_event_id = rerouted.event_id

        for site_id in sorted(touched):
            self.runtime.emit(
                "site.metrics",
                actor_id=site_id,
                cause_event_id=accepted.event_id,
                trace_id=command.trace_id,
                payload={**self._metrics_payload(self.sites[site_id]), "reason": "rerouted_load"},
            )

        incident = self.sites[incident_site_id]
        incident.status = "healthy"
        incident.reattach_congestion = 0.0
        self._derive_metrics(incident)
        for neighbor_id in incident.neighbor_ids:
            neighbor = self.sites.get(neighbor_id)
            if neighbor is None:
                continue
            if neighbor.reattach_congestion:
                neighbor.reattach_congestion = 0.0
                self._derive_metrics(neighbor)
        self.runtime.emit(
            "site.recovered",
            actor_id=incident_site_id,
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                **self._metrics_payload(incident),
                "rerouted_session_count": len(assignments),
            },
        )
        return accepted

    # -- views (snapshot / observation) ------------------------------------

    def _site_view(self, site: CellSite) -> dict[str, Any]:
        return {
            "id": site.id,
            "region": site.region,
            "status": site.status,
            "capacity_mbps": site.capacity_mbps,
            "traffic_mbps": round(site.traffic_mbps, 3),
            "utilization": site.utilization,
            "packet_loss_pct": round(site.packet_loss * 100.0, 3),
            "latency_ms": site.latency_ms,
            "session_count": len(site.session_ids),
            "neighbor_ids": list(site.neighbor_ids),
        }

    def _session_view(self, session: NetworkSession) -> dict[str, Any]:
        return {
            "id": session.id,
            "subscriber_id": session.subscriber_id,
            "site_id": session.site_id,
            "origin_site_id": session.origin_site_id,
            "kind": session.kind,
            "demand_mbps": session.demand_mbps,
            "status": session.status,
        }

    def _subscriber_view(self, subscriber: Subscriber) -> dict[str, Any]:
        return {
            "id": subscriber.id,
            "home_site_id": subscriber.home_site_id,
            "tier": subscriber.tier,
            "session_count": len(subscriber.session_ids),
        }

    def render_state(self) -> dict[str, Any]:
        from api.server.world.projection import project_network

        return {
            "projection": asdict(project_network(self)),
            "sites": [self._site_view(s) for s in self.sites.values()],
            "sessions": [self._session_view(s) for s in self.sessions.values()],
            "subscribers": [self._subscriber_view(s) for s in self.subscribers.values()],
        }

    def build_observation(self, sensor_event: dict[str, Any], *, now: float) -> dict[str, Any]:
        from api.server.world.projection import project_network

        payload = sensor_event.get("payload") or {}
        measurements = payload.get("measurements") or {}
        site_id = measurements.get("site_id")
        incident = self.sites.get(site_id)
        neighbor_sites: list[dict[str, Any]] = []
        if incident is not None:
            for neighbor_id in incident.neighbor_ids:
                neighbor = self.sites.get(neighbor_id)
                if neighbor is None or neighbor.status != "healthy":
                    continue
                view = self._site_view(neighbor)
                view["spare_mbps"] = round(neighbor.capacity_mbps - neighbor.traffic_mbps, 3)
                neighbor_sites.append(view)
        affected = sorted(
            (s for s in self.sessions.values()
             if s.status == "degraded" and s.origin_site_id == site_id),
            key=lambda s: s.id,
        )
        return {
            "trace_id": sensor_event.get("trace_id"),
            "sensor_event_id": sensor_event.get("event_id"),
            "incident_site": self._site_view(incident) if incident is not None else None,
            "neighbor_sites": neighbor_sites,
            "affected_sessions": [self._session_view(s) for s in affected],
            "projection": asdict(project_network(self)),
            "allowed_commands": ["reroute_sessions"],
        }


def run_network(
    *,
    seed: int,
    config: NetworkConfig,
    failures: tuple[SiteFailure, ...] = (),
) -> NetworkScenario:
    runtime = SimulationRuntime(seed)
    scenario = NetworkScenario(runtime, config)
    scenario.install()
    for failure in failures:
        scenario.schedule_failure(failure)
    runtime.run_until(config.simulation_minutes)
    return scenario
