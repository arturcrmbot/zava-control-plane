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

import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.telco.commercial import (
    CreditAdjustment,
    CustomerAccount,
    Notification,
    ServiceOrder,
    ServiceSubscription,
)
from verticals.telco.operations import (
    CareTicket,
    ExperienceEpisode,
    NetworkAsset,
    RetentionOffer,
    SpareStock,
    Technician,
    WeatherEvent,
    WorkOrder,
)

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

# -- operational asset dynamics ---------------------------------------------

ASSET_KINDS: tuple[str, ...] = ("radio-unit", "power", "cooling", "backhaul")
TECHNICIANS_PER_REGION = 5
# Deterministic hero constraints (see verticals/telco/operations.py actors):
# one technician is unavailable from the start and one region's spare stock
# for one part kind is already exhausted, forcing later maintenance/field
# workflows to route around them instead of hitting a trivially-happy path.
HERO_UNAVAILABLE_TECHNICIAN_ID = "TECH-WEST-05"
HERO_SPARE_SHORTAGE_REGION = "west"
HERO_SPARE_SHORTAGE_PART_KIND = "radio-unit"

# Nominal operating temperature (°C) per asset kind at zero load/health-loss.
BASE_TEMP_C: dict[str, float] = {
    "radio-unit": 42.0,
    "power": 32.0,
    "cooling": 24.0,
    "backhaul": 28.0,
}
# Headroom above baseline before temperature starts contributing risk.
SAFE_MARGIN_C = 15.0
# How strongly site load drives each asset kind's per-tick load figure.
LOAD_MULTIPLIER: dict[str, float] = {
    "radio-unit": 1.0,
    "power": 0.7,
    "cooling": 0.6,
    "backhaul": 0.9,
}
# Baseline health decay per simulated minute, before load/weather amplify it.
BASE_DECAY_PER_MINUTE: dict[str, float] = {
    "radio-unit": 0.00006,
    "power": 0.00004,
    "cooling": 0.00005,
    "backhaul": 0.00003,
}
RISK_BANDS: tuple[str, ...] = ("healthy", "elevated", "high", "critical")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _risk_band(failure_probability: float) -> str:
    if failure_probability >= 0.5:
        return "critical"
    if failure_probability >= 0.2:
        return "high"
    if failure_probability >= 0.05:
        return "elevated"
    return "healthy"


def _require_finite_positive(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if value <= 0:
        raise ValueError(f"{label} must be positive")
    return float(value)


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
    account_id: str
    subscription_id: str
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
        self.accounts: dict[str, CustomerAccount] = {}
        self.subscriptions: dict[str, ServiceSubscription] = {}
        self.orders: dict[str, ServiceOrder] = {}
        self.notifications: dict[str, Notification] = {}
        self.credits: dict[str, CreditAdjustment] = {}
        self.assets: dict[str, NetworkAsset] = {}
        self.weather_events: dict[str, WeatherEvent] = {}
        self.work_orders: dict[str, WorkOrder] = {}
        self.technicians: dict[str, Technician] = {}
        self.spare_stocks: dict[str, SpareStock] = {}
        self.tickets: dict[str, CareTicket] = {}
        self.experience_episodes: dict[str, ExperienceEpisode] = {}
        self.retention_offers: dict[str, RetentionOffer] = {}
        self._site_ids: list[str] = []
        self._subscriber_ids: list[str] = []
        self._asset_ids: list[str] = []
        self._spare_stock_by_key: dict[tuple[str, str], str] = {}
        self._failed_sites_latched: set[str] = set()
        self._impacted_account_ids_by_trace: dict[str, tuple[str, ...]] = {}
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
        self._create_commercial_state()
        self._create_sessions()
        for site in self.sites.values():
            self._derive_metrics(site)
            self.runtime.emit(
                "site.metrics",
                actor_id=site.id,
                trace_id=f"site-{site.id}",
                payload=self._metrics_payload(site),
            )
        self._create_assets()
        self._create_technicians()
        self._create_spare_stocks()
        self.runtime.process(self._sensor_loop())
        self.runtime.process(self._operations_loop())

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
            subscriber = Subscriber(
                id=f"SUB-{index:05d}",
                home_site_id=home,
                tier=tier,
                account_id=f"ACC-{index:05d}",
                subscription_id=f"SUBS-{index:05d}",
            )
            self.subscribers[subscriber.id] = subscriber
            self._subscriber_ids.append(subscriber.id)
            self.runtime.emit(
                "subscriber.created",
                actor_id=subscriber.id,
                target_id=home,
                trace_id=f"subscriber-{subscriber.id}",
                payload={"home_site_id": home, "tier": tier},
            )

    def _create_commercial_state(self) -> None:
        for index, subscriber_id in enumerate(self._subscriber_ids, start=1):
            subscriber = self.subscribers[subscriber_id]
            if index == 1:
                segment = "priority_business"
            elif subscriber.tier == "business":
                segment = "business"
            else:
                segment = "consumer"
            account = CustomerAccount(
                id=subscriber.account_id,
                subscriber_id=subscriber.id,
                segment=segment,
                vulnerable=index == 2,
                approval_required=index == 3,
            )
            subscription = ServiceSubscription(
                id=subscriber.subscription_id,
                account_id=account.id,
                subscriber_id=subscriber.id,
                site_id=subscriber.home_site_id,
                product="business-premium" if index == 1 else "mobile-connect",
            )
            self.accounts[account.id] = account
            self.subscriptions[subscription.id] = subscription

        self.orders["ORD-00001"] = ServiceOrder(
            id="ORD-00001",
            account_id="ACC-00003",
            product="business-premium",
            requested_site_id="SITE-01",
            status="infeasible",
            reason="hero order requires exception approval",
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

    def _create_assets(self) -> None:
        for site_id in self._site_ids:
            site = self.sites[site_id]
            for kind in ASSET_KINDS:
                asset_id = f"AST-{site_id}-{kind.upper()}"
                asset = NetworkAsset(
                    id=asset_id,
                    site_id=site_id,
                    kind=kind,
                    health=1.0,
                    temperature_c=0.0,
                    load=round(site.utilization * LOAD_MULTIPLIER[kind], 4),
                )
                self._derive_asset_metrics(asset)
                self.assets[asset_id] = asset
                self._asset_ids.append(asset_id)
                self.runtime.emit(
                    "asset.created",
                    actor_id=asset_id,
                    target_id=site_id,
                    trace_id=f"asset-{asset_id}",
                    payload=asdict(asset),
                )

    def _create_technicians(self) -> None:
        for region in REGIONS:
            for slot in range(1, TECHNICIANS_PER_REGION + 1):
                tech_id = f"TECH-{region.upper()}-{slot:02d}"
                skills = (
                    ASSET_KINDS[(slot - 1) % len(ASSET_KINDS)],
                    ASSET_KINDS[slot % len(ASSET_KINDS)],
                )
                status = (
                    "unavailable" if tech_id == HERO_UNAVAILABLE_TECHNICIAN_ID
                    else "available"
                )
                technician = Technician(
                    id=tech_id, region=region, skills=skills, status=status
                )
                self.technicians[tech_id] = technician
                self.runtime.emit(
                    "technician.created",
                    actor_id=tech_id,
                    target_id=f"region:{region}",
                    trace_id=f"technician-{tech_id}",
                    payload=self._technician_view(technician),
                )

    def _create_spare_stocks(self) -> None:
        for region in REGIONS:
            for kind in ASSET_KINDS:
                stock_id = f"SPARE-{region.upper()}-{kind.upper()}"
                hero_zero = (
                    region == HERO_SPARE_SHORTAGE_REGION
                    and kind == HERO_SPARE_SHORTAGE_PART_KIND
                )
                stock = SpareStock(
                    id=stock_id,
                    region=region,
                    part_kind=kind,
                    quantity=0 if hero_zero else 15,
                    reorder_point=5,
                )
                self.spare_stocks[stock_id] = stock
                self._spare_stock_by_key[(region, kind)] = stock_id
                self.runtime.emit(
                    "spare_stock.created",
                    actor_id=stock_id,
                    target_id=f"region:{region}",
                    trace_id=f"spare-stock-{stock_id}",
                    payload=asdict(stock),
                )

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

    # -- operational asset dynamics -----------------------------------------

    def _active_weather_for_region(self, region: str) -> WeatherEvent | None:
        now = self.runtime.now
        active = [
            weather
            for weather in self.weather_events.values()
            if weather.region == region and weather.starts_at <= now < weather.ends_at
        ]
        if not active:
            return None
        return WeatherEvent(
            id="+".join(sorted(weather.id for weather in active)),
            region=region,
            severity=max(weather.severity for weather in active),
            power_risk=max(weather.power_risk for weather in active),
            cooling_risk=max(weather.cooling_risk for weather in active),
            starts_at=min(weather.starts_at for weather in active),
            ends_at=max(weather.ends_at for weather in active),
        )

    def _derive_asset_metrics(self, asset: NetworkAsset) -> None:
        """Recompute temperature/failure_probability/status band from the
        asset's current health/load and any active regional weather. Pure
        function of current state — deterministic and idempotent."""
        weather = self._active_weather_for_region(self.sites[asset.site_id].region)
        power_risk = weather.power_risk if weather else 0.0
        cooling_risk = weather.cooling_risk if weather else 0.0
        if asset.kind == "power":
            weather_term = power_risk
        elif asset.kind == "cooling":
            weather_term = cooling_risk
        else:
            weather_term = (power_risk + cooling_risk) / 2.0
        base_temp = BASE_TEMP_C[asset.kind]
        temperature = (
            base_temp
            + asset.load * 20.0
            + weather_term * 20.0
            + (1.0 - asset.health) * 10.0
        )
        asset.temperature_c = round(temperature, 2)
        temp_excess = max(0.0, asset.temperature_c - (base_temp + SAFE_MARGIN_C))
        failure_probability = (
            0.01 + (1.0 - asset.health) * 0.9 + (temp_excess / 25.0) * 0.2
        )
        asset.failure_probability = round(
            _clamp(failure_probability, 0.0, 1.0), 4
        )
        asset.status = _risk_band(asset.failure_probability)

    def _decay_asset_health(self, asset: NetworkAsset) -> None:
        site = self.sites[asset.site_id]
        asset.load = round(site.utilization * LOAD_MULTIPLIER[asset.kind], 4)
        weather = self._active_weather_for_region(site.region)
        weather_component = (
            (weather.power_risk + weather.cooling_risk) if weather else 0.0
        )
        decay = (
            BASE_DECAY_PER_MINUTE[asset.kind]
            * (1.0 + asset.load)
            * (1.0 + weather_component)
        )
        asset.health = round(_clamp(asset.health - decay, 0.0, 1.0), 6)
        self._derive_asset_metrics(asset)

    def _operations_loop(self):
        while self.runtime.now < self.config.simulation_minutes:
            yield self.runtime.env.timeout(1)
            for asset_id in self._asset_ids:
                asset = self.assets[asset_id]
                prior_status = asset.status
                self._decay_asset_health(asset)
                if asset.status == prior_status:
                    continue
                self.runtime.emit(
                    "asset.metrics",
                    actor_id=asset.id,
                    target_id=asset.site_id,
                    trace_id=f"asset-{asset.id}",
                    payload={**asdict(asset), "prior_status": prior_status},
                )

    # -- perturbation ------------------------------------------------------

    def schedule_failure(self, failure: SiteFailure) -> None:
        self.runtime.process(self._failure_process(failure))

    def inject_site_failure(self, site_id: str | None = None) -> str:
        resolved = self._resolve_failure_site(site_id)
        self.schedule_failure(SiteFailure(at_minute=self.runtime.now, site_id=resolved))
        return resolved

    def inject_capacity_pressure(
        self, site_id: str, *, utilization: float = 0.95
    ) -> str:
        target = float(utilization)
        if not 0.9 <= target <= 1.0:
            raise ValueError("utilization must be between 0.9 and 1.0")
        site = self.sites.get(site_id)
        if site is None:
            raise ValueError(f"unknown site_id: {site_id}")
        if site.status != "healthy":
            raise ValueError(f"site {site_id} is not healthy")
        if site.traffic_mbps <= 0:
            raise ValueError(f"site {site_id} has no traffic to constrain")
        prior_capacity = site.capacity_mbps
        site.capacity_mbps = round(site.traffic_mbps / target, 3)
        self._derive_metrics(site)
        constrained = self.runtime.emit(
            "site.capacity_constrained",
            actor_id=site.id,
            trace_id=f"capacity-pressure-{site.id}-{int(self.runtime.now)}",
            payload={
                "prior_capacity_mbps": prior_capacity,
                "capacity_mbps": site.capacity_mbps,
                "utilization": site.utilization,
            },
        )
        self.runtime.emit(
            "site.metrics",
            actor_id=site.id,
            cause_event_id=constrained.event_id,
            trace_id=constrained.trace_id,
            payload={**self._metrics_payload(site), "reason": "capacity_pressure"},
        )
        return site.id

    def inject_weather_risk(
        self, region: str, severity: float, duration_minutes: float
    ) -> str:
        if region not in REGIONS:
            raise ValueError(f"unknown region: {region!r}")
        severity = _require_finite_positive(severity, label="severity")
        duration_minutes = _require_finite_positive(
            duration_minutes, label="duration_minutes"
        )
        starts_at = self.runtime.now
        ends_at = starts_at + duration_minutes
        event_id = f"WEATHER-{len(self.weather_events) + 1:04d}"
        weather = WeatherEvent(
            id=event_id,
            region=region,
            severity=round(severity, 4),
            power_risk=round(_clamp(severity * 0.6, 0.0, 1.0), 4),
            cooling_risk=round(_clamp(severity * 0.9, 0.0, 1.0), 4),
            starts_at=starts_at,
            ends_at=ends_at,
        )
        self.weather_events[event_id] = weather
        self.runtime.emit(
            "weather.risk_injected",
            actor_id=event_id,
            target_id=f"region:{region}",
            trace_id=f"weather-{event_id}",
            payload=asdict(weather),
        )
        return event_id

    def inject_spare_shortage(self, region: str, part_kind: str) -> str:
        if region not in REGIONS:
            raise ValueError(f"unknown region: {region!r}")
        if part_kind not in ASSET_KINDS:
            raise ValueError(f"unknown part_kind: {part_kind!r}")
        stock_id = self._spare_stock_by_key.get((region, part_kind))
        if stock_id is None:
            raise ValueError(
                f"no spare stock for region={region!r} part_kind={part_kind!r}"
            )
        stock = self.spare_stocks[stock_id]
        if stock.quantity <= 0:
            raise ValueError(f"spare stock {stock_id} is already at zero")
        prior_quantity = stock.quantity
        stock.quantity = 0
        self.runtime.emit(
            "spare_stock.shortage",
            actor_id=stock_id,
            target_id=f"region:{region}",
            trace_id=f"spare-shortage-{stock_id}-{int(self.runtime.now)}",
            payload={
                "region": region,
                "part_kind": part_kind,
                "prior_quantity": prior_quantity,
                "quantity": 0,
                "reorder_point": stock.reorder_point,
            },
        )
        return stock_id

    def inject_technician_unavailable(self, technician_id: str) -> str:
        technician = self.technicians.get(technician_id)
        if technician is None:
            raise ValueError(f"unknown technician_id: {technician_id!r}")
        if technician.status != "available":
            raise ValueError(f"technician {technician_id} is not available")
        technician.status = "unavailable"
        self.runtime.emit(
            "technician.unavailable",
            actor_id=technician_id,
            target_id=f"region:{technician.region}",
            trace_id=f"technician-unavailable-{technician_id}-{int(self.runtime.now)}",
            payload={"region": technician.region, "status": technician.status},
        )
        return technician_id

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
        self._emit_customer_impact(failed, affected)
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

    def _emit_customer_impact(
        self, failed: SimulationEvent, affected: list[NetworkSession]
    ) -> None:
        account_ids = tuple(
            sorted(
                {
                    self.subscribers[session.subscriber_id].account_id
                    for session in affected
                }
            )
        )
        subscription_ids = tuple(
            sorted(
                {
                    self.subscribers[session.subscriber_id].subscription_id
                    for session in affected
                }
            )
        )
        self._impacted_account_ids_by_trace[failed.trace_id] = account_ids
        self.runtime.emit(
            "sensor.tripped",
            actor_id="sensor:customer_impact",
            target_id=failed.actor_id,
            cause_event_id=failed.event_id,
            trace_id=failed.trace_id,
            payload={
                "account_ids": list(account_ids[:50]),
                "subscription_ids": list(subscription_ids[:50]),
                "measurements": {
                    "site_id": failed.actor_id,
                    "affected_account_count": len(account_ids),
                    "affected_subscription_count": len(subscription_ids),
                },
            },
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
            trace_id=next(
                (
                    event.trace_id
                    for event in reversed(self.runtime.journal)
                    if event.event_id == site.last_event_id
                ),
                f"network-incident-{site.id}-{int(self.runtime.now)}",
            ),
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

    def submit_service_order(
        self, *, account_id: str, product: str, requested_site_id: str
    ) -> str:
        if account_id not in self.accounts:
            raise ValueError(f"unknown account_id: {account_id!r}")
        if requested_site_id not in self.sites:
            raise ValueError(f"unknown requested_site_id: {requested_site_id!r}")
        order_id = f"ORD-{len(self.orders) + 1:05d}"
        order = ServiceOrder(
            id=order_id,
            account_id=account_id,
            product=product,
            requested_site_id=requested_site_id,
            status="pending",
        )
        self.orders[order_id] = order
        trace_id = f"service-order-{order_id}"
        created = self.runtime.emit(
            "order.created",
            actor_id=order_id,
            target_id=account_id,
            trace_id=trace_id,
            payload=asdict(order),
        )
        self.runtime.emit(
            "sensor.tripped",
            actor_id="sensor:service_order",
            target_id=order_id,
            cause_event_id=created.event_id,
            trace_id=trace_id,
            payload={"order_id": order_id},
        )
        return order_id

    # -- command -----------------------------------------------------------

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        existing = self.applied_commands.get(command.command_id)
        if existing is not None:
            return existing
        if command.type == "reroute_sessions":
            reason = self._validate_reroute_sessions(command.payload)
            if reason is not None:
                return self._reject_command(command, reason)
            return self._accept_reroute_sessions(command)
        if command.type == "apply_customer_remediation":
            reason = self._validate_customer_remediation(command)
            if reason is not None:
                return self._reject_command(command, reason)
            return self._accept_customer_remediation(command)
        if command.type == "activate_service_order":
            reason = self._validate_service_order_activation(command)
            if reason is not None:
                return self._reject_command(command, reason)
            return self._accept_service_order_activation(command)
        return self._reject_command(command, f"unsupported command type: {command.type!r}")

    def _validate_service_order_activation(
        self, command: SimulationCommand
    ) -> str | None:
        order = self.orders.get(command.payload.get("order_id"))
        if order is None:
            return f"unknown order_id: {command.payload.get('order_id')!r}"
        if order.status != "pending":
            return f"order {order.id} is not pending"
        site = self.sites[order.requested_site_id]
        if site.status != "healthy":
            return f"requested site {site.id} is not healthy"
        if site.utilization >= 0.9 and command.payload.get("capacity_approved") is not True:
            return f"insufficient capacity at {site.id}"
        return None

    def _accept_service_order_activation(
        self, command: SimulationCommand
    ) -> SimulationEvent:
        order = self.orders[command.payload["order_id"]]
        accepted = self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            target_id=order.id,
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
        self.applied_commands[command.command_id] = accepted
        account = self.accounts[order.account_id]
        subscription_id = f"SUBS-{len(self.subscriptions) + 1:05d}"
        subscription = ServiceSubscription(
            id=subscription_id,
            account_id=account.id,
            subscriber_id=account.subscriber_id,
            site_id=order.requested_site_id,
            product=order.product,
            status="active",
        )
        self.subscriptions[subscription.id] = subscription
        order.status = "activated"
        order.reason = None
        self.runtime.emit(
            "order.activated",
            actor_id=order.id,
            target_id=subscription.id,
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "order": asdict(order),
                "subscription": asdict(subscription),
            },
        )
        return accepted

    def _validate_customer_remediation(
        self, command: SimulationCommand
    ) -> str | None:
        actions = command.payload.get("actions")
        if not isinstance(actions, list) or not actions:
            return "actions must be a non-empty list"
        impacted = set(self._impacted_account_ids_by_trace.get(command.trace_id, ()))
        seen: set[str] = set()
        for action in actions:
            if not isinstance(action, dict):
                return "each remediation action must be an object"
            account_id = action.get("account_id")
            if not isinstance(account_id, str) or account_id not in impacted:
                return f"account {account_id!r} is not affected on this trace"
            if account_id in seen:
                return f"duplicate account_id: {account_id}"
            seen.add(account_id)
            if action.get("channel") not in {"sms", "email"}:
                return f"unsupported channel: {action.get('channel')!r}"
            if not isinstance(action.get("message"), str) or not action["message"].strip():
                return "message must be a non-empty string"
            amount = action.get("credit_amount")
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                return "credit_amount must be numeric"
            account = self.accounts[account_id]
            expected_amount = (
                50.0
                if account.approval_required
                else 20.0
                if account.vulnerable
                else 10.0
                if account.segment == "priority_business"
                else 5.0
            )
            if float(amount) != expected_amount:
                return (
                    f"credit_amount for {account_id} does not match policy "
                    f"entitlement {expected_amount:.2f}"
                )
            if (
                account.approval_required
                and command.payload.get("approval_decision") != "approve"
            ):
                return f"approved cs_manager decision required for {account_id}"
        return None

    def _accept_customer_remediation(
        self, command: SimulationCommand
    ) -> SimulationEvent:
        accepted = self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
        self.applied_commands[command.command_id] = accepted
        actions = list(command.payload["actions"])
        for action in actions:
            account = self.accounts[action["account_id"]]
            notification = Notification(
                id=f"NOT-{len(self.notifications) + 1:06d}",
                account_id=account.id,
                channel=action["channel"],
                message=action["message"],
                trace_id=command.trace_id,
            )
            self.notifications[notification.id] = notification
            account.notification_ids.append(notification.id)
            self.runtime.emit(
                "notification.sent",
                actor_id=notification.id,
                target_id=account.id,
                cause_event_id=accepted.event_id,
                trace_id=command.trace_id,
                payload=asdict(notification),
            )
            amount = float(action["credit_amount"])
            if amount > 0:
                credit = CreditAdjustment(
                    id=f"CRD-{len(self.credits) + 1:06d}",
                    account_id=account.id,
                    amount=amount,
                    trace_id=command.trace_id,
                    authority_approved=True,
                )
                self.credits[credit.id] = credit
                account.credit_ids.append(credit.id)
                account.total_credits = round(account.total_credits + amount, 2)
                self.runtime.emit(
                    "credit.applied",
                    actor_id=credit.id,
                    target_id=account.id,
                    cause_event_id=accepted.event_id,
                    trace_id=command.trace_id,
                    payload=asdict(credit),
                )
        self.runtime.emit(
            "care.completed",
            actor_id="customer_care",
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "account_ids": [action["account_id"] for action in actions],
                "notification_count": len(actions),
                "credit_total": round(
                    sum(float(action["credit_amount"]) for action in actions), 2
                ),
            },
        )
        return accepted

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
            "account_id": subscriber.account_id,
            "subscription_id": subscriber.subscription_id,
            "session_count": len(subscriber.session_ids),
        }

    def _account_view(self, account: CustomerAccount) -> dict[str, Any]:
        return asdict(account)

    def _asset_view(self, asset: NetworkAsset) -> dict[str, Any]:
        return asdict(asset)

    def _weather_view(self, weather: WeatherEvent) -> dict[str, Any]:
        return asdict(weather)

    def _technician_view(self, technician: Technician) -> dict[str, Any]:
        data = asdict(technician)
        data["skills"] = list(technician.skills)
        return data

    def _customer_impact_view(self) -> dict[str, Any]:
        impacted = {
            account_id
            for account_ids in self._impacted_account_ids_by_trace.values()
            for account_id in account_ids
        }
        return {
            "affected_account_count": len(impacted),
            "notified_account_count": sum(
                bool(self.accounts[account_id].notification_ids)
                for account_id in impacted
            ),
            "credited_account_count": sum(
                bool(self.accounts[account_id].credit_ids)
                for account_id in impacted
            ),
            "account_ids": sorted(impacted),
        }

    def render_state(self) -> dict[str, Any]:
        from api.server.world.projection import project_network

        return {
            "projection": asdict(project_network(self)),
            "sites": [self._site_view(s) for s in self.sites.values()],
            "sessions": [self._session_view(s) for s in self.sessions.values()],
            "subscribers": [self._subscriber_view(s) for s in self.subscribers.values()],
            "accounts": [self._account_view(a) for a in self.accounts.values()],
            "subscriptions": [asdict(s) for s in self.subscriptions.values()],
            "orders": [asdict(order) for order in self.orders.values()],
            "notifications": [asdict(item) for item in self.notifications.values()],
            "credits": [asdict(item) for item in self.credits.values()],
            "customer_impact": self._customer_impact_view(),
            "assets": [self._asset_view(a) for a in self.assets.values()],
            "weather_events": [self._weather_view(w) for w in self.weather_events.values()],
            "work_orders": [asdict(w) for w in self.work_orders.values()],
            "technicians": [self._technician_view(t) for t in self.technicians.values()],
            "spare_stocks": [asdict(s) for s in self.spare_stocks.values()],
            "tickets": [asdict(t) for t in self.tickets.values()],
            "experience_episodes": [
                asdict(e) for e in self.experience_episodes.values()
            ],
            "retention_offers": [asdict(o) for o in self.retention_offers.values()],
        }

    def build_observation(self, sensor_event: dict[str, Any], *, now: float) -> dict[str, Any]:
        from api.server.world.projection import project_network

        payload = sensor_event.get("payload") or {}
        if sensor_event.get("actor_id") == "sensor:service_order":
            order = self.orders[payload["order_id"]]
            return {
                "trace_id": sensor_event.get("trace_id"),
                "sensor_event_id": sensor_event.get("event_id"),
                "order": asdict(order),
                "account": self._account_view(self.accounts[order.account_id]),
                "requested_site": self._site_view(
                    self.sites[order.requested_site_id]
                ),
                "allowed_commands": ["activate_service_order"],
            }
        if sensor_event.get("actor_id") == "sensor:customer_impact":
            account_ids = self._impacted_account_ids_by_trace.get(
                sensor_event.get("trace_id"), ()
            )
            return {
                "trace_id": sensor_event.get("trace_id"),
                "sensor_event_id": sensor_event.get("event_id"),
                "incident_site_id": (payload.get("measurements") or {}).get("site_id"),
                "impacted_accounts": [
                    self._account_view(self.accounts[account_id])
                    for account_id in account_ids
                ],
                "subscriptions": [
                    asdict(self.subscriptions[self.subscribers[
                        self.accounts[account_id].subscriber_id
                    ].subscription_id])
                    for account_id in account_ids
                ],
                "allowed_commands": ["apply_customer_remediation"],
            }
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
