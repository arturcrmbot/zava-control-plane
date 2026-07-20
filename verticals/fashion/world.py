from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.reference_actions import (
    PROFILE_BY_COMMAND,
    apply_reference_command,
    validate_reference_command,
)
from verticals.fashion.reference_cases import (
    FashionProcessCase,
    build_reference_case,
    process_case_view,
)


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
        self.inventory: dict[str, InventoryPosition] = {}
        self.process_cases: dict[str, FashionProcessCase] = {}
        self.workflow_state: dict[str, dict[str, Any]] = {}
        self.applied_commands: dict[str, SimulationEvent] = {}

    @classmethod
    def demo(cls, runtime: SimulationRuntime) -> "FashionScenario":
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
        channels = ("store", "ecommerce")
        sku_ids = tuple(self.skus)
        for index in range(1, 301):
            customer_id = f"CUSTOMER-{index:04d}"
            region = regions[(index - 1) % len(regions)]
            self.customers[customer_id] = Customer(customer_id, region)
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
        hero_sku = "SKU-0001"
        source = self.inventory[f"INV-DC-UK-01-{hero_sku}"]
        destination = self.inventory[f"INV-STORE-UK-01-{hero_sku}"]
        eu_excess = self.inventory[f"INV-STORE-EU-01-{hero_sku}"]
        source.on_hand = 120
        source.reserved = 5
        source.safety_stock = 20
        destination.on_hand = 2
        destination.reserved = 1
        eu_excess.on_hand = 90

    def case_evidence(
        self,
        workflow_type: str,
    ) -> tuple[tuple[str, ...], dict[str, Any]]:
        hero_sku = "SKU-0001"
        source_id = f"INV-DC-UK-01-{hero_sku}"
        destination_id = f"INV-STORE-UK-01-{hero_sku}"
        subjects = {
            "inventory-rebalancing": (source_id, destination_id, hero_sku),
            "demand-spike-response": ("STORE-UK-01", hero_sku),
            "promotion-readiness": ("PROMOTION-001", hero_sku),
            "markdown-governance": ("STYLE-002", "STORE-EU-01"),
            "supplier-delay-recovery": ("SUPPLIER-001", "STYLE-003"),
            "fulfilment-exception-resolution": ("ORDER-001", hero_sku),
            "marketplace-seller-exception": (
                "SELLER-001",
                "OFFER-001",
            ),
            "returns-disposition": ("RETURN-001", "SKU-0002"),
        }
        facts = {
            "inventory-rebalancing": {
                "demand_confidence": 0.9,
                "transfer_cost_gbp": 120.0,
                "expected_recovered_margin_gbp": 800.0,
                "fairness_score": 0.8,
                "weather_signal": "warm-campaign-spike",
                "eu_excess_position_id": f"INV-STORE-EU-01-{hero_sku}",
            },
            "demand-spike-response": {
                "regional_velocity_change": 0.45,
                "available_units": 120,
            },
            "promotion-readiness": {
                "stock_ready": True,
                "content_ready": True,
                "channels": ["store", "ecommerce"],
            },
            "markdown-governance": {
                "weeks_of_supply": 14.0,
                "recommendation_only": True,
            },
            "supplier-delay-recovery": {
                "milestone_delay_days": 6,
                "substitute_available": True,
            },
            "fulfilment-exception-resolution": {
                "allocation_failure": "local-stockout",
                "alternate_location": "DC-UK-01",
            },
            "marketplace-seller-exception": {
                "seller_verified": True,
                "sla_breach_hours": 8,
            },
            "returns-disposition": {
                "condition": "resalable",
                "ownership": "owned",
                "recovery_value_gbp": 75.0,
            },
        }
        return subjects[workflow_type], facts[workflow_type]

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
            return common
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
        if quantity > source.available_to_transfer:
            return "insufficient available stock"
        source_location = self.locations[source.location_id]
        destination_location = self.locations[destination.location_id]
        cross_border = source_location.country != destination_location.country
        style = self.styles[self.skus[source.sku_id].style_id]
        retail_value = quantity * style.unit_retail_gbp
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
        if exception and not payload.get("approval_reference"):
            return "approval reference is required for transfer exception"
        if not payload.get("workflow_id"):
            return "workflow_id is required"
        if not payload.get("reason_code") or not payload.get(
            "evidence_digest"
        ):
            return "reason code and evidence digest are required"
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
            "inventory": [
                asdict(value) for value in self.inventory.values()
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
