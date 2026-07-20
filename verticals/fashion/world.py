from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.fashion import signals
from verticals.fashion.authority import FASHION_AUTHORITY
from verticals.fashion.entities import (
    DemandSignal,
    Delivery,
    MarkdownRecommendation,
    Order,
    Promotion,
    Reservation,
    Return,
    SellerOffer,
)
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.reference_actions import (
    PROFILE_BY_COMMAND,
    apply_reference_command,
    resolve_case_entity,
    validate_reference_command,
)
from verticals.fashion.reference_cases import (
    DEFAULT_ACTIONS,
    FashionProcessCase,
    build_reference_case,
    process_case_view,
)

DEMO_SEED: int = 42

HERO_SKU: str = "SKU-0001"
HERO_STYLE: str = "STYLE-001"
HERO_REGION_PREFIX: str = "UK"
MARKDOWN_STYLE: str = "STYLE-004"
MARKDOWN_ELIGIBLE_LIFECYCLES: frozenset[str] = frozenset({"sale", "clearance"})


@dataclass(slots=True)
class Location:
    id: str
    kind: str
    country: str
    region: str


@dataclass(slots=True)
class Brand:
    id: str
    relationship: str


@dataclass(slots=True)
class Style:
    id: str
    brand_id: str
    season: str
    lifecycle: str
    unit_retail_gbp: float


@dataclass(slots=True)
class Sku:
    id: str
    style_id: str
    colour: str
    size: str


@dataclass(slots=True)
class Customer:
    id: str
    region: str
    cohort: str


@dataclass(slots=True)
class DemandRecord:
    id: str
    customer_id: str
    sku_id: str
    day: int
    channel: str
    quantity: int


@dataclass(slots=True)
class InventoryPosition:
    id: str
    location_id: str
    sku_id: str
    ownership: str
    on_hand: int
    reserved: int
    presentation_minimum: int
    safety_stock: int
    version: int = 1

    @property
    def available_to_transfer(self) -> int:
        return max(
            0,
            self.on_hand
            - self.reserved
            - self.presentation_minimum
            - self.safety_stock,
        )

    @property
    def physically_available(self) -> int:
        """Units that can physically leave without breaching committed stock
        (customer reservations and the presentation minimum). Consuming into
        this band beyond ``available_to_transfer`` dips into the protected
        safety-stock buffer; consuming beyond it entirely is impossible."""
        return max(0, self.on_hand - self.reserved - self.presentation_minimum)


class FashionScenario:
    def __init__(self, runtime: SimulationRuntime) -> None:
        self.runtime = runtime
        self.stores: dict[str, Location] = {}
        self.distribution_centres: dict[str, Location] = {}
        self.brands: dict[str, Brand] = {}
        self.styles: dict[str, Style] = {}
        self.skus: dict[str, Sku] = {}
        self.customers: dict[str, Customer] = {}
        self.demand_history: list[DemandRecord] = []
        self.demand_signals: dict[str, DemandSignal] = {}
        self.inventory: dict[str, InventoryPosition] = {}
        self.orders: dict[str, Order] = {}
        self.reservations: dict[str, Reservation] = {}
        self.promotions: dict[str, Promotion] = {}
        self.deliveries: dict[str, Delivery] = {}
        self.returns: dict[str, Return] = {}
        self.seller_offers: dict[str, SellerOffer] = {}
        self.markdown_recommendations: dict[str, MarkdownRecommendation] = {}
        self.process_cases: dict[str, FashionProcessCase] = {}
        self.workflow_state: dict[str, dict[str, Any]] = {}
        self.applied_commands: dict[str, SimulationEvent] = {}

    @classmethod
    def demo(cls, runtime: SimulationRuntime | None = None) -> "FashionScenario":
        if runtime is None:
            runtime = SimulationRuntime(DEMO_SEED)
        return cls(runtime)

    @property
    def locations(self) -> dict[str, Location]:
        return {**self.stores, **self.distribution_centres}

    def install(self) -> None:
        if self.stores:
            raise ValueError("Fashion scenario is already installed")
        self.runtime.emit(
            "simulation.started",
            actor_id="scenario:fashion",
            payload={"seed": self.runtime.seed, "scale": "demo"},
        )
        self._create_locations()
        self._create_catalogue()
        self._create_customers_and_demand()
        self._create_inventory()
        self._create_entities()

    @property
    def hero_style_sku_ids(self) -> tuple[str, ...]:
        return tuple(
            sku.id
            for sku in self.skus.values()
            if sku.style_id == HERO_STYLE
        )

    @property
    def markdown_style_id(self) -> str:
        return MARKDOWN_STYLE

    def _create_locations(self) -> None:
        store_specs = (
            ("STORE-UK-01", "UK", "London"),
            ("STORE-UK-02", "UK", "Manchester"),
            ("STORE-UK-03", "UK", "Edinburgh"),
            ("STORE-UK-04", "UK", "Birmingham"),
            ("STORE-EU-01", "FR", "Paris"),
            ("STORE-EU-02", "DE", "Berlin"),
            ("STORE-EU-03", "NL", "Amsterdam"),
            ("STORE-EU-04", "ES", "Madrid"),
        )
        for location_id, country, region in store_specs:
            self.stores[location_id] = Location(
                location_id, "store", country, region
            )
        self.distribution_centres = {
            "DC-UK-01": Location("DC-UK-01", "dc", "UK", "Midlands"),
            "DC-EU-01": Location("DC-EU-01", "dc", "NL", "Benelux"),
        }

    def _create_catalogue(self) -> None:
        relationships = (
            "owned",
            "owned",
            "owned",
            "owned",
            "concession",
            "concession",
            "concession",
            "concession",
            "marketplace",
            "marketplace",
            "marketplace",
            "marketplace",
        )
        seasons = ("spring-summer", "autumn-winter")
        lifecycles = ("new-arrival", "full-price", "sale", "clearance")
        colours = ("black", "navy")
        sizes = ("S", "M", "L", "XL")
        sku_index = 1
        for brand_index, relationship in enumerate(relationships, start=1):
            brand_id = f"BRAND-{brand_index:02d}"
            self.brands[brand_id] = Brand(brand_id, relationship)
            for style_slot in range(2):
                style_id = f"STYLE-{(brand_index - 1) * 2 + style_slot + 1:03d}"
                self.styles[style_id] = Style(
                    id=style_id,
                    brand_id=brand_id,
                    season=seasons[style_slot],
                    lifecycle=lifecycles[
                        ((brand_index - 1) * 2 + style_slot) % len(lifecycles)
                    ],
                    unit_retail_gbp=float(80 + brand_index * 5 + style_slot * 10),
                )
                for colour in colours:
                    for size in sizes:
                        sku_id = f"SKU-{sku_index:04d}"
                        self.skus[sku_id] = Sku(
                            id=sku_id,
                            style_id=style_id,
                            colour=colour,
                            size=size,
                        )
                        sku_index += 1

    def _create_customers_and_demand(self) -> None:
        regions = ("UK-North", "UK-South", "EU-North", "EU-South")
        cohorts = ("premium", "mainstream", "value", "occasional")
        channels = ("store", "ecommerce")
        sku_ids = tuple(self.skus)
        for index in range(1, 301):
            customer_id = f"CUSTOMER-{index:04d}"
            region = regions[(index - 1) % len(regions)]
            cohort = cohorts[(index - 1) % len(cohorts)]
            self.customers[customer_id] = Customer(customer_id, region, cohort)
            self.demand_history.append(
                DemandRecord(
                    id=f"DEMAND-{index:05d}",
                    customer_id=customer_id,
                    sku_id=sku_ids[
                        self.runtime.rng.randrange(len(sku_ids))
                    ],
                    day=((index - 1) % 14) + 1,
                    channel=channels[index % 2],
                    quantity=1 + self.runtime.rng.randrange(2),
                )
            )
        self._seed_hero_demand_series(channels)

    def _seed_hero_demand_series(
        self,
        channels: tuple[str, ...],
    ) -> None:
        """Lay down a deterministic 14-day demand series for the hero style in
        the UK region, with a weather/campaign uplift concentrated in the
        recent (days 8-14) window. Quantities stay at their unit base so the
        cohort weighting is applied live at signal-derivation time."""
        hero_skus = self.hero_style_sku_ids
        uk_customers = [
            customer_id
            for customer_id, customer in self.customers.items()
            if customer.region.startswith(HERO_REGION_PREFIX)
        ]
        base_per_day = 3
        recent_uplift_per_day = 3
        serial = 0
        recent_uplift_units = 0
        for day in range(1, 15):
            uplift = recent_uplift_per_day if day >= 8 else 0
            for slot in range(base_per_day + uplift):
                serial += 1
                customer_id = uk_customers[
                    (day * 7 + slot) % len(uk_customers)
                ]
                self.demand_history.append(
                    DemandRecord(
                        id=f"HERO-DEMAND-{serial:05d}",
                        customer_id=customer_id,
                        sku_id=hero_skus[slot % len(hero_skus)],
                        day=day,
                        channel=channels[slot % len(channels)],
                        quantity=1,
                    )
                )
                if day >= 8 and slot >= base_per_day:
                    recent_uplift_units += 1
        self.demand_signals[f"{HERO_STYLE}@{HERO_REGION_PREFIX}"] = DemandSignal(
            id=f"SIGNAL-{HERO_STYLE}-{HERO_REGION_PREFIX}",
            sku_ids=hero_skus,
            region=HERO_REGION_PREFIX,
            channel=None,
            kind="weather-campaign",
            active=True,
            recent_uplift_units=recent_uplift_units,
        )

    def _create_inventory(self) -> None:
        for location_index, location in enumerate(self.locations.values()):
            for sku_index, sku in enumerate(self.skus.values()):
                style = self.styles[sku.style_id]
                ownership = self.brands[style.brand_id].relationship
                position_id = f"INV-{location.id}-{sku.id}"
                self.inventory[position_id] = InventoryPosition(
                    id=position_id,
                    location_id=location.id,
                    sku_id=sku.id,
                    ownership=ownership,
                    on_hand=10 + ((location_index + sku_index) % 30),
                    reserved=(location_index + sku_index) % 3,
                    presentation_minimum=2 if location.kind == "store" else 0,
                    safety_stock=3 if location.kind == "store" else 5,
                )
        hero_sku = HERO_SKU
        source = self.inventory[f"INV-DC-UK-01-{hero_sku}"]
        destination = self.inventory[f"INV-STORE-UK-01-{hero_sku}"]
        eu_excess = self.inventory[f"INV-STORE-EU-01-{hero_sku}"]
        source.on_hand = 120
        source.reserved = 5
        source.safety_stock = 20
        destination.on_hand = 2
        destination.reserved = 1
        eu_excess.on_hand = 90

    def _create_entities(self) -> None:
        """Seed the concrete world entities the supporting workflows read and
        mutate. Every record is versioned so a mutation is observable."""
        self.reservations["RES-STORE-UK-01-" + HERO_SKU] = Reservation(
            id="RES-STORE-UK-01-" + HERO_SKU,
            location_id="STORE-UK-01",
            sku_id=HERO_SKU,
            reserved_units=4,
            status="baseline",
        )
        self.promotions["PROMOTION-001"] = Promotion(
            id="PROMOTION-001",
            sku_id=HERO_SKU,
            stock_ready=False,
            content_ready=False,
            channels_ready=(),
            status="draft",
        )
        markdown_rec_id = f"MREC-{MARKDOWN_STYLE}-STORE-EU-01"
        self.markdown_recommendations[markdown_rec_id] = MarkdownRecommendation(
            id=markdown_rec_id,
            style_id=MARKDOWN_STYLE,
            location_id="STORE-EU-01",
            recommendation=None,
            status="pending",
        )
        self.deliveries["DEL-SUPPLIER-001-STYLE-003"] = Delivery(
            id="DEL-SUPPLIER-001-STYLE-003",
            supplier_id="SUPPLIER-001",
            style_id="STYLE-003",
            delay_days=6,
            recovery_plan=None,
            status="delayed",
        )
        self.orders["ORDER-001"] = Order(
            id="ORDER-001",
            sku_id=HERO_SKU,
            location_id="STORE-UK-01",
            quantity=3,
            status="infeasible",
            allocation_location_id=None,
        )
        self.seller_offers["OFFER-001"] = SellerOffer(
            id="OFFER-001",
            seller_id="SELLER-001",
            sku_id="SKU-0002",
            sla_breach_hours=8,
            suppressed=False,
            escalated=False,
            status="breaching",
        )
        self.returns["RETURN-001"] = Return(
            id="RETURN-001",
            sku_id="SKU-0002",
            condition="resalable",
            disposition=None,
            recovery_value_gbp=75.0,
            status="inspected",
        )

    def demand_metrics(
        self,
        sku_ids: tuple[str, ...],
        region_prefix: str,
        *,
        channel: str | None = None,
    ) -> tuple[signals.DemandMetrics, bool]:
        """Derive the cohort-weighted demand series and its aggregates for a
        SKU set / region, plus whether a corroborating signal is active."""
        series = signals.daily_series(
            self.demand_history,
            self.customers,
            sku_ids=sku_ids,
            region_prefix=region_prefix,
            channel=channel,
        )
        sku_set = set(sku_ids)
        signal_active = any(
            signal.active
            and sku_set & set(signal.sku_ids)
            and (
                signal.region.startswith(region_prefix)
                or region_prefix.startswith(signal.region)
            )
            for signal in self.demand_signals.values()
        )
        metrics = signals.DemandMetrics(
            series=tuple(series),
            velocity_change=signals.velocity_change(series),
            confidence=signals.demand_confidence(
                series, signal_active=signal_active
            ),
            weekly_demand=signals.weekly_demand(series),
        )
        return metrics, signal_active

    def _demand_signal_view(
        self,
        series: list[int],
        signal_active: bool,
    ) -> dict[str, Any]:
        signal = self.demand_signals.get(f"{HERO_STYLE}@{HERO_REGION_PREFIX}")
        uplift = signal.recent_uplift_units if signal else 0
        return {
            "kind": signal.kind if signal else "none",
            "active": signal_active,
            "recent_uplift_units": uplift if signal_active else 0,
            "recent_share": (
                signals.signal_recent_share(series, uplift)
                if signal_active
                else 0.0
            ),
        }

    def _markdown_eligible(self, style_id: str) -> bool:
        style = self.styles.get(style_id)
        return bool(
            style and style.lifecycle in MARKDOWN_ELIGIBLE_LIFECYCLES
        )

    def recommended_action(
        self,
        workflow_type: str,
        subjects: tuple[str, ...],
    ) -> str:
        if workflow_type == "markdown-governance":
            if self._markdown_eligible(subjects[0]):
                return "recommend-markdown"
            return "hold-full-price"
        return DEFAULT_ACTIONS[workflow_type]

    def case_evidence(
        self,
        workflow_type: str,
    ) -> tuple[tuple[str, ...], dict[str, Any]]:
        hero_sku = HERO_SKU
        source_id = f"INV-DC-UK-01-{hero_sku}"
        destination_id = f"INV-STORE-UK-01-{hero_sku}"
        subjects = {
            "inventory-rebalancing": (source_id, destination_id, hero_sku),
            "demand-spike-response": ("STORE-UK-01", hero_sku),
            "promotion-readiness": ("PROMOTION-001", hero_sku),
            "markdown-governance": (MARKDOWN_STYLE, "STORE-EU-01"),
            "supplier-delay-recovery": ("SUPPLIER-001", "STYLE-003"),
            "fulfilment-exception-resolution": ("ORDER-001", hero_sku),
            "marketplace-seller-exception": (
                "SELLER-001",
                "OFFER-001",
            ),
            "returns-disposition": ("RETURN-001", "SKU-0002"),
        }
        return subjects[workflow_type], self._derive_facts(
            workflow_type, subjects[workflow_type]
        )

    def _derive_facts(
        self,
        workflow_type: str,
        subjects: tuple[str, ...],
    ) -> dict[str, Any]:
        hero_skus = self.hero_style_sku_ids
        if workflow_type == "inventory-rebalancing":
            metrics, active = self.demand_metrics(hero_skus, HERO_REGION_PREFIX)
            destination = self.inventory[subjects[1]]
            recovered_units = 20
            style = self.styles[self.skus[HERO_SKU].style_id]
            unit_margin = round(style.unit_retail_gbp * 0.4, 2)
            transfer_cost = 6.0 * recovered_units
            return {
                "demand_confidence": metrics.confidence,
                "regional_velocity_change": metrics.velocity_change,
                "transfer_cost_gbp": transfer_cost,
                "expected_recovered_margin_gbp": round(
                    recovered_units * unit_margin, 2
                ),
                "fairness_score": 0.8,
                "weeks_of_supply": signals.weeks_of_supply(
                    destination.on_hand, list(metrics.series)
                ),
                "demand_signal": self._demand_signal_view(
                    list(metrics.series), active
                ),
                "eu_excess_position_id": f"INV-STORE-EU-01-{HERO_SKU}",
            }
        if workflow_type == "demand-spike-response":
            metrics, active = self.demand_metrics(hero_skus, HERO_REGION_PREFIX)
            store = self.inventory[f"INV-STORE-UK-01-{HERO_SKU}"]
            dc_source = self.inventory[f"INV-DC-UK-01-{HERO_SKU}"]
            return {
                "regional_velocity_change": metrics.velocity_change,
                "demand_confidence": metrics.confidence,
                "weeks_of_supply": signals.weeks_of_supply(
                    store.on_hand, list(metrics.series)
                ),
                "available_units": dc_source.physically_available,
                "demand_signal": self._demand_signal_view(
                    list(metrics.series), active
                ),
            }
        if workflow_type == "promotion-readiness":
            promotion = self.promotions.get(subjects[0])
            metrics, _ = self.demand_metrics(hero_skus, HERO_REGION_PREFIX)
            return {
                "stock_ready": bool(promotion and promotion.stock_ready),
                "content_ready": bool(promotion and promotion.content_ready),
                "regional_velocity_change": metrics.velocity_change,
                "channels": ["store", "ecommerce"],
            }
        if workflow_type == "markdown-governance":
            style_id, location_id = subjects
            style = self.styles[style_id]
            style_skus = tuple(
                sku.id
                for sku in self.skus.values()
                if sku.style_id == style_id
            )
            on_hand = sum(
                position.on_hand
                for position in self.inventory.values()
                if position.sku_id in set(style_skus)
                and position.location_id == location_id
            )
            metrics, _ = self.demand_metrics(
                style_skus, "EU", channel=None
            )
            return {
                "lifecycle": style.lifecycle,
                "markdown_eligible": self._markdown_eligible(style_id),
                "weeks_of_supply": signals.weeks_of_supply(
                    on_hand, list(metrics.series)
                ),
                "recommendation_only": True,
            }
        if workflow_type == "supplier-delay-recovery":
            delivery = self.deliveries.get("DEL-SUPPLIER-001-STYLE-003")
            return {
                "milestone_delay_days": delivery.delay_days if delivery else 0,
                "substitute_available": True,
            }
        if workflow_type == "fulfilment-exception-resolution":
            order = self.orders.get(subjects[0])
            return {
                "allocation_failure": (
                    order.status if order else "unknown"
                ),
                "alternate_location": "DC-UK-01",
            }
        if workflow_type == "marketplace-seller-exception":
            offer = self.seller_offers.get(subjects[1])
            return {
                "seller_verified": True,
                "sla_breach_hours": offer.sla_breach_hours if offer else 0,
            }
        if workflow_type == "returns-disposition":
            returned = self.returns.get(subjects[0])
            return {
                "condition": returned.condition if returned else "unknown",
                "ownership": "owned",
                "recovery_value_gbp": (
                    returned.recovery_value_gbp if returned else 0.0
                ),
            }
        raise ValueError(f"unknown Fashion process: {workflow_type!r}")

    @property
    def reference_process_types(self) -> frozenset[str]:
        """Reference-process types this world can run — one per pack domain.

        Consumed by the vertical-agnostic world route so the proof (and any
        operator) can drive every Fashion workflow through the same
        ``POST /api/world/processes/{workflow_type}/run`` surface telco uses.
        """
        return frozenset(FASHION_PROCESS_PROFILES)

    def run_reference_process(self, workflow_type: str) -> dict[str, str]:
        """Adapter matching the ActorWorldService reference-process contract.

        Telco names this ``run_reference_process``; the Fashion world's native
        entry point is ``run_case``. Exposing both keeps the shared world
        service and route free of any per-vertical branching."""
        return self.run_case(workflow_type)

    def run_case(self, workflow_type: str) -> dict[str, str]:
        profile = FASHION_PROCESS_PROFILES.get(workflow_type)
        if profile is None:
            raise ValueError(f"unknown Fashion process: {workflow_type!r}")
        case_id = profile.case_id
        if case_id in self.process_cases:
            count = 2
            while f"{case_id}-{count}" in self.process_cases:
                count += 1
            case_id = f"{case_id}-{count}"
        case = build_reference_case(self, profile, case_id)
        self.process_cases[case.id] = case
        trace_id = f"fashion-{workflow_type}-{case.id}"
        opened = self.runtime.emit(
            "process_case.opened",
            actor_id=case.id,
            target_id=case.subject_ids[0],
            trace_id=trace_id,
            payload=process_case_view(case),
        )
        sensor = self.runtime.emit(
            "sensor.tripped",
            actor_id=profile.sensor_id,
            target_id=case.id,
            cause_event_id=opened.event_id,
            trace_id=trace_id,
            payload={
                "case_id": case.id,
                "workflow_type": workflow_type,
                "measurements": dict(case.facts),
            },
        )
        return {
            "case_id": case.id,
            "root_event_id": opened.event_id,
            "sensor_event_id": sensor.event_id,
            "trace_id": trace_id,
        }

    def command_payload(self, case_id: str) -> dict[str, Any]:
        case = self.process_cases[case_id]
        profile = FASHION_PROCESS_PROFILES[case.workflow_type]
        evidence_digest = hashlib.sha256(
            repr(sorted(case.facts.items())).encode("utf-8")
        ).hexdigest()
        common = {
            "case_id": case.id,
            "workflow_id": f"WF-{case.id}",
            "subject_ids": list(case.subject_ids),
            "action": case.recommended_action,
            "skill_outputs": {
                skill: {"reasoning": "deterministic Fashion evidence"}
                for skill in profile.skills
            },
            "approval_decision": "approve",
            "reason_code": f"{case.workflow_type}.reference",
            "evidence_digest": evidence_digest,
        }
        if case.workflow_type != "inventory-rebalancing":
            return {
                **common,
                **{
                    key: value
                    for key, value in case.facts.items()
                    if key not in common
                },
            }
        source = self.inventory[case.subject_ids[0]]
        destination = self.inventory[case.subject_ids[1]]
        sku = self.skus[source.sku_id]
        style = self.styles[sku.style_id]
        return {
            **common,
            "source_position_id": source.id,
            "destination_position_id": destination.id,
            "source_location_id": source.location_id,
            "destination_location_id": destination.location_id,
            "sku_id": source.sku_id,
            "quantity": 20,
            "inventory_ownership": source.ownership,
            "ownership": source.ownership,
            "expected_source_version": source.version,
            "expected_destination_version": destination.version,
            "retail_value_gbp": round(style.unit_retail_gbp * 20, 2),
            "policy_decision": "auto_approved",
            "approval_reference": None,
            "demand_confidence": case.facts["demand_confidence"],
            "transfer_cost_gbp": case.facts["transfer_cost_gbp"],
            "expected_recovered_margin_gbp": case.facts[
                "expected_recovered_margin_gbp"
            ],
            "fairness_score": case.facts["fairness_score"],
        }

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        existing = self.applied_commands.get(command.command_id)
        if existing is not None:
            return existing
        if command.type == "inventory.transfer":
            if command.payload.get("action") == "no-action":
                reason = self._validate_no_action(command)
                if reason is not None:
                    return self._reject_command(command, reason)
                return self._apply_no_action(command)
            reason = self._validate_inventory_transfer(command)
            if reason is not None:
                return self._reject_command(command, reason)
            return self._apply_inventory_transfer(command)
        if command.type in PROFILE_BY_COMMAND:
            reason = validate_reference_command(self, command)
            if reason is not None:
                return self._reject_command(command, reason)
            return apply_reference_command(self, command)
        return self._reject_command(
            command,
            f"unsupported command type: {command.type!r}",
        )

    def _validate_no_action(
        self,
        command: SimulationCommand,
    ) -> str | None:
        payload = command.payload
        case = self.process_cases.get(payload.get("case_id"))
        if case is None or case.workflow_type != "inventory-rebalancing":
            return "unknown inventory-rebalancing case"
        if case.status != "open":
            return f"case {case.id} is not open"
        if not payload.get("workflow_id"):
            return "workflow_id is required"
        candidates = payload.get("evaluated_candidates")
        if not isinstance(candidates, list) or not candidates:
            return "no-action requires evaluated candidates"
        constraints = payload.get("binding_constraints")
        if not isinstance(constraints, list) or not constraints:
            return "no-action requires binding constraints"
        comparison = payload.get("kpi_comparison")
        if not isinstance(comparison, dict) or not {
            "expected_recovered_margin_gbp",
            "transfer_cost_gbp",
        } <= set(comparison):
            return "no-action requires a KPI comparison"
        if not payload.get("reason_code") or not payload.get(
            "evidence_digest"
        ):
            return "reason code and evidence digest are required"
        return None

    def _apply_no_action(
        self,
        command: SimulationCommand,
    ) -> SimulationEvent:
        payload = command.payload
        case = self.process_cases[payload["case_id"]]
        accepted = self._record_command_accepted(
            command,
            target_id=case.id,
        )
        no_action = self.runtime.emit(
            "inventory.rebalance.no_action",
            actor_id=case.id,
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "evaluated_candidates": payload["evaluated_candidates"],
                "binding_constraints": payload["binding_constraints"],
                "kpi_comparison": payload["kpi_comparison"],
            },
        )
        evaluation = {
            "status": "pass",
            "kpi_comparison": payload["kpi_comparison"],
        }
        case.status = "completed"
        case.outcome = {
            "action": "no-action",
            "command_type": "inventory.transfer",
            "mutation_family": "inventory",
            "evaluated_candidates": payload["evaluated_candidates"],
            "binding_constraints": payload["binding_constraints"],
            "evaluation": evaluation,
        }
        self.workflow_state[case.workflow_type] = {
            "status": "completed",
            "case_id": case.id,
            "action": "no-action",
        }
        profile = FASHION_PROCESS_PROFILES[case.workflow_type]
        self.runtime.emit(
            profile.success_event,
            actor_id=case.id,
            cause_event_id=no_action.event_id,
            trace_id=command.trace_id,
            payload={
                "case": process_case_view(case),
                "command_id": command.command_id,
                "evaluation": evaluation,
            },
        )
        self.runtime.emit(
            "evaluation.completed",
            actor_id=case.id,
            cause_event_id=no_action.event_id,
            trace_id=command.trace_id,
            payload={
                "workflow_type": case.workflow_type,
                **evaluation,
            },
        )
        return accepted

    def _validate_inventory_transfer(
        self,
        command: SimulationCommand,
    ) -> str | None:
        payload = command.payload
        case = self.process_cases.get(payload.get("case_id"))
        if case is None or case.workflow_type != "inventory-rebalancing":
            return "unknown inventory-rebalancing case"
        if case.status != "open":
            return f"case {case.id} is not open"
        source = self.inventory.get(payload.get("source_position_id"))
        destination = self.inventory.get(
            payload.get("destination_position_id")
        )
        if source is None or destination is None:
            return "unknown source or destination inventory position"
        if source.id == destination.id or source.sku_id != destination.sku_id:
            return "invalid source/destination combination"
        if payload.get("expected_source_version") != source.version:
            return "stale source version"
        if payload.get("expected_destination_version") != destination.version:
            return "stale destination version"
        if (
            payload.get("ownership") != "owned"
            or payload.get("inventory_ownership") != "owned"
            or source.ownership != "owned"
            or destination.ownership != "owned"
        ):
            return "ineligible ownership for inventory transfer"
        quantity = payload.get("quantity")
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            return "quantity must be a positive integer"
        if quantity > source.physically_available:
            # Non-negative physically-available invariant: a transfer may never
            # drive on_hand below committed reservations and the presentation
            # minimum, no matter what approval accompanies it.
            return "insufficient physically available stock"
        source_location = self.locations[source.location_id]
        destination_location = self.locations[destination.location_id]
        cross_border = source_location.country != destination_location.country
        style = self.styles[self.skus[source.sku_id].style_id]
        retail_value = quantity * style.unit_retail_gbp
        breaches_safety_stock = quantity > source.available_to_transfer
        if breaches_safety_stock:
            # A safety-stock breach is a conditional HITL path, not a hard
            # reject: it can only execute with a valid, non-stale approval
            # from an authorised persona.
            reason = self._validate_governed_transfer_approval(
                source,
                payload,
                retail_value,
                command.issued_by,
                context="safety-stock breach",
                missing_message="safety-stock breach requires approval",
            )
            if reason is not None:
                return reason
        exception = any(
            (
                retail_value > 10_000.0,
                quantity > 50,
                cross_border,
                float(payload.get("demand_confidence", 0.0)) < 0.7,
                float(payload.get("expected_recovered_margin_gbp", 0.0))
                <= float(payload.get("transfer_cost_gbp", 0.0)),
                float(payload.get("fairness_score", 0.0)) < 0.5,
                payload.get("policy_decision") == "approval_required",
            )
        )
        if exception:
            # Every conditional transfer exception — not just a safety-stock
            # breach — is gated behind the same fully authenticated
            # approval: a free-form or unauthorised approval_reference must
            # not be able to execute a high-value, cross-border, low-
            # confidence, negative-margin, low-fairness, or policy-flagged
            # transfer.
            reason = self._validate_governed_transfer_approval(
                source,
                payload,
                retail_value,
                command.issued_by,
                context="transfer exception",
                missing_message=(
                    "approval reference is required for transfer exception"
                ),
            )
            if reason is not None:
                return reason
        if not payload.get("workflow_id"):
            return "workflow_id is required"
        if not payload.get("reason_code") or not payload.get(
            "evidence_digest"
        ):
            return "reason code and evidence digest are required"
        return None

    def _validate_governed_transfer_approval(
        self,
        source: InventoryPosition,
        payload: dict[str, Any],
        retail_value: float,
        issued_by: str = "",
        *,
        context: str,
        missing_message: str,
    ) -> str | None:
        """Gate ANY conditional inventory-transfer exception — a protected
        safety-stock consumption or a general high-value/cross-border/low-
        confidence/negative-margin/low-fairness/policy-flagged exception —
        behind the authorised persona's approval. Returns a rejection
        reason, or ``None`` to allow.

        This is the single generic authority validator: both call sites in
        ``_validate_inventory_transfer`` route through it so no conditional
        transfer exception can execute on a free-form, unknown, self, stale,
        or over-limit approval — only the safety-stock-specific wording
        differs (via ``context``/``missing_message``), the authority checks
        are identical.

        Rules (as supported by the pack authority model):
          * an approval reference must be present — otherwise the exception
            is routed to approval_required and blocked;
          * the approving role must be an authorised persona whose approval
            actions cover the inventory-rebalancing HITL decision and whose
            spend limit covers the transfer value;
          * the command issuer may not serve as their own approver — the
            recommendation generator and the approval authority must be
            distinct entities;
          * the approval must be bound to the current source version — an
            approval granted against a superseded version is stale.
        """
        if not payload.get("approval_reference"):
            return missing_message
        role = payload.get("approval_role")
        row = FASHION_AUTHORITY.get(role) if role else None
        action = FASHION_PROCESS_PROFILES["inventory-rebalancing"].hitl_event
        if row is None or action not in row.approval_actions:
            return f"{context} requires an authorized persona approval"
        if issued_by and issued_by == role:
            return f"command issuer cannot self-approve a {context}"
        if retail_value > row.spend_limit_gbp:
            return f"{context} approval exceeds persona spend limit"
        if payload.get("approved_source_version") != source.version:
            return f"stale {context} approval"
        return None

    def _apply_inventory_transfer(
        self,
        command: SimulationCommand,
    ) -> SimulationEvent:
        payload = command.payload
        case = self.process_cases[payload["case_id"]]
        source = self.inventory[payload["source_position_id"]]
        destination = self.inventory[payload["destination_position_id"]]
        quantity = int(payload["quantity"])
        source_before = source.on_hand
        destination_before = destination.on_hand
        accepted = self._record_command_accepted(
            command,
            target_id=destination.id,
        )
        source.on_hand -= quantity
        destination.on_hand += quantity
        source.version += 1
        destination.version += 1
        transfer = self.runtime.emit(
            "inventory.transferred",
            actor_id=source.id,
            target_id=destination.id,
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "sku_id": source.sku_id,
                "quantity": quantity,
                "source_before": source_before,
                "source_after": source.on_hand,
                "destination_before": destination_before,
                "destination_after": destination.on_hand,
                "command_id": command.command_id,
            },
        )
        evaluation = {
            "status": "pass",
            "full_price_demand_served_delta": quantity,
            "projected_lost_sales_delta": -quantity,
            "source_available_after": source.available_to_transfer,
            "transfer_cost_gbp": payload["transfer_cost_gbp"],
            "fairness_score": payload["fairness_score"],
        }
        case.status = "completed"
        case.outcome = {
            "action": "inventory.transfer",
            "command_type": "inventory.transfer",
            "mutation_family": "inventory",
            "source_position_id": source.id,
            "destination_position_id": destination.id,
            "governance": {
                "policy_decision": payload["policy_decision"],
                "approval_reference": payload.get("approval_reference"),
            },
            "evaluation": evaluation,
        }
        self.workflow_state[case.workflow_type] = {
            "status": "completed",
            "case_id": case.id,
            "action": "inventory.transfer",
        }
        profile = FASHION_PROCESS_PROFILES[case.workflow_type]
        self.runtime.emit(
            profile.success_event,
            actor_id=case.id,
            target_id=destination.id,
            cause_event_id=transfer.event_id,
            trace_id=command.trace_id,
            payload={
                "case": process_case_view(case),
                "command_id": command.command_id,
                "evaluation": evaluation,
            },
        )
        self.runtime.emit(
            "evaluation.completed",
            actor_id=case.id,
            cause_event_id=transfer.event_id,
            trace_id=command.trace_id,
            payload={
                "workflow_type": case.workflow_type,
                **evaluation,
            },
        )
        return accepted

    def _record_command_accepted(
        self,
        command: SimulationCommand,
        *,
        target_id: str | None,
    ) -> SimulationEvent:
        accepted = self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            target_id=target_id,
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
        self.applied_commands[command.command_id] = accepted
        return accepted

    def _reject_command(
        self,
        command: SimulationCommand,
        reason: str,
    ) -> SimulationEvent:
        rejected = self.runtime.emit(
            "command.rejected",
            actor_id=command.issued_by,
            trace_id=command.trace_id,
            payload={"command": command.to_dict(), "reason": reason},
        )
        self.applied_commands[command.command_id] = rejected
        return rejected

    def process_case_view(self, case: FashionProcessCase) -> dict[str, Any]:
        return process_case_view(case)

    def entity_snapshot(
        self,
        workflow_type: str,
        case: FashionProcessCase,
    ) -> dict[str, Any] | None:
        """Serialisable view of the concrete entity a supporting workflow
        reads and mutates, resolved from the case subjects."""
        entity = resolve_case_entity(self, workflow_type, case.subject_ids)
        return asdict(entity) if entity is not None else None

    def render_state(self) -> dict[str, Any]:
        return {
            "stores": [asdict(value) for value in self.stores.values()],
            "distribution_centres": [
                asdict(value)
                for value in self.distribution_centres.values()
            ],
            "brands": [asdict(value) for value in self.brands.values()],
            "styles": [asdict(value) for value in self.styles.values()],
            "skus": [asdict(value) for value in self.skus.values()],
            "customers": [asdict(value) for value in self.customers.values()],
            "demand_history": [
                asdict(value) for value in self.demand_history
            ],
            "demand_signals": [
                asdict(value) for value in self.demand_signals.values()
            ],
            "inventory": [
                asdict(value) for value in self.inventory.values()
            ],
            "orders": [asdict(value) for value in self.orders.values()],
            "reservations": [
                asdict(value) for value in self.reservations.values()
            ],
            "promotions": [
                asdict(value) for value in self.promotions.values()
            ],
            "deliveries": [
                asdict(value) for value in self.deliveries.values()
            ],
            "returns": [asdict(value) for value in self.returns.values()],
            "seller_offers": [
                asdict(value) for value in self.seller_offers.values()
            ],
            "markdown_recommendations": [
                asdict(value)
                for value in self.markdown_recommendations.values()
            ],
            "process_cases": [
                process_case_view(value)
                for value in self.process_cases.values()
            ],
            "workflow_state": dict(self.workflow_state),
        }

    def build_observation(
        self,
        sensor_event: dict[str, Any],
        *,
        now: float,
    ) -> dict[str, Any]:
        payload = sensor_event.get("payload") or {}
        case = self.process_cases[payload["case_id"]]
        profile = FASHION_PROCESS_PROFILES[case.workflow_type]
        return {
            "trace_id": sensor_event.get("trace_id"),
            "sensor_event_id": sensor_event.get("event_id"),
            "event_ids": [sensor_event.get("event_id")],
            "as_of_sim_time": now,
            "case": process_case_view(case),
            "command_payload": self.command_payload(case.id),
            "skills": list(profile.skills),
            "allowed_commands": [profile.command_type],
            "subject_actors": [
                {"id": subject_id} for subject_id in case.subject_ids
            ],
        }
