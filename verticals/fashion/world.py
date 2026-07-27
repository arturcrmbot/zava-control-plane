from __future__ import annotations

from dataclasses import asdict
from typing import Any

from api.server.world.model import SimulationCommand, SimulationEvent
from api.server.world.runtime import SimulationRuntime
from verticals.fashion.actors import (
    Brand,
    Customer,
    Delivery,
    InventoryPosition,
    Location,
    Order,
    ProcessCase,
    Promotion,
    Return,
    SKU,
    SellerOffer,
    Staff,
    Style,
    view,
)
from verticals.fashion.dynamics import (
    HERO_SALE_TICKS,
    ORDINARY_TICK_MINUTES,
    customer_number,
    should_cancel,
    should_receive_delivery,
    should_receive_return,
    store_number,
)
from verticals.fashion.process_profiles import (
    FASHION_PROCESS_PROFILES,
    FashionProcessProfile,
)
from verticals.fashion.reference_cases import FASHION_REFERENCE_CASES
from verticals.fashion.sensors import (
    DESTINATION_LOCATION,
    HERO_SKU,
    SOURCE_LOCATION,
    inventory_imbalance_crossed,
    inventory_measurements,
)
from verticals.fashion.trading_shock import TradingShockState


STORE_DATA = (
    ("STORE-UK-LON-01", "Oxford Street Flagship", "GB", "UK South"),
    ("STORE-UK-MAN-01", "Manchester", "GB", "UK North"),
    ("STORE-UK-EDI-01", "Edinburgh", "GB", "UK North"),
    ("STORE-UK-BHM-01", "Birmingham", "GB", "UK Midlands"),
    ("STORE-EU-PAR-01", "Paris Rivoli", "FR", "EU West"),
    ("STORE-EU-BER-01", "Berlin Mitte", "DE", "EU Central"),
    ("STORE-EU-AMS-01", "Amsterdam", "NL", "EU West"),
    ("STORE-EU-MIL-01", "Milan", "IT", "EU South"),
)
DC_DATA = (
    ("DC-UK-MID-01", "Midlands DC", "GB", "UK Midlands"),
    ("DC-EU-LIL-01", "Lille EU DC", "FR", "EU West"),
)
COLOUR_PAIRS = (
    ("BLK", "WHT"),
    ("RED", "NAV"),
    ("NAV", "CRM"),
    ("TAN", "BLK"),
    ("GRN", "CRM"),
    ("BLU", "WHT"),
)
SIZES = ("XS", "S", "M", "L")
STAFF_NAMES = (
    "Maya Patel",
    "Owen Hughes",
    "Aisha Khan",
    "Leo Martin",
    "Sofia Rossi",
    "Nora Weber",
    "Lotte de Vries",
    "Amelia Clarke",
)


class FashionScenario:
    reference_process_types = tuple(FASHION_PROCESS_PROFILES)

    def __init__(self, runtime: SimulationRuntime) -> None:
        self.runtime = runtime
        self.stores: dict[str, Location] = {}
        self.distribution_centres: dict[str, Location] = {}
        self.brands: dict[str, Brand] = {}
        self.styles: dict[str, Style] = {}
        self.skus: dict[str, SKU] = {}
        self.customers: dict[str, Customer] = {}
        self.staff: dict[str, Staff] = {}
        self.inventory: dict[tuple[str, str], InventoryPosition] = {}
        self.orders: dict[str, Order] = {}
        self.deliveries: dict[str, Delivery] = {}
        self.returns: dict[str, Return] = {}
        self.promotions: dict[str, Promotion] = {}
        self.seller_offers: dict[str, SellerOffer] = {}
        self.process_cases: dict[str, ProcessCase] = {}
        self.demand_history: list[dict[str, Any]] = []
        self.knowledge_relationships: list[dict[str, Any]] = []
        self.hero_sales = 0
        self._tick = 0
        self._order_seq = 0
        self._return_seq = 42
        self._delivery_seq = 42
        self._imbalance_active = False
        self._applied_command_ids: set[str] = set()
        self.trading_shock = TradingShockState(seed=runtime.seed)

    def install(self) -> None:
        self._seed_locations()
        self._seed_catalogue()
        self._seed_people()
        self._seed_inventory()
        self._seed_operations()
        self.runtime.process(self._retail_lifecycle())

    def _seed_locations(self) -> None:
        self.stores = {
            item[0]: Location(item[0], item[1], "store", item[2], item[3])
            for item in STORE_DATA
        }
        self.distribution_centres = {
            item[0]: Location(
                item[0], item[1], "distribution-centre", item[2], item[3]
            )
            for item in DC_DATA
        }

    def _seed_catalogue(self) -> None:
        relationships = ("owned",) * 4 + ("concession",) * 4 + ("marketplace",) * 4
        self.brands = {
            f"BRAND-{number:02d}": Brand(
                id=f"BRAND-{number:02d}",
                name=f"Atelier {number:02d}",
                relationship=relationships[number - 1],
            )
            for number in range(1, 13)
        }
        for number in range(1, 25):
            style_id = f"STYLE-{number:02d}"
            brand_id = f"BRAND-{((number - 1) % 12) + 1:02d}"
            self.styles[style_id] = Style(
                id=style_id,
                brand_id=brand_id,
                name=f"Seasonal style {number:02d}",
                lifecycle="current-season",
            )
            colours = COLOUR_PAIRS[(number - 1) % len(COLOUR_PAIRS)]
            for colour in colours:
                for size in SIZES:
                    sku_id = f"SKU-{style_id}-{colour}-{size}"
                    self.skus[sku_id] = SKU(
                        id=sku_id,
                        style_id=style_id,
                        colour=colour,
                        size=size,
                        retail_price_gbp=float(70 + ((number * 5) % 60)),
                    )

    def _seed_people(self) -> None:
        self.customers = {
            f"CUST-{number:04d}": Customer(
                id=f"CUST-{number:04d}",
                home_region=("UK" if number % 3 else "EU"),
                location_id="OFFSITE",
                status="offsite",
            )
            for number in range(1, 301)
        }
        for store_index, store_id in enumerate(self.stores):
            for staff_index in range(1, 4):
                staff_id = f"STAFF-{store_id.split('-')[1]}-{store_index + 1:02d}-{staff_index:02d}"
                self.staff[staff_id] = Staff(
                    id=staff_id,
                    name=STAFF_NAMES[(store_index + staff_index - 1) % len(STAFF_NAMES)],
                    role=("style-advisor" if staff_index < 3 else "store-manager"),
                    location_id=store_id,
                    status="available",
                )

    def _seed_inventory(self) -> None:
        locations = (*self.stores, *self.distribution_centres)
        for sku_index, sku in enumerate(self.skus.values()):
            brand = self.brands[self.styles[sku.style_id].brand_id]
            for location_index, location_id in enumerate(locations):
                is_dc = location_id.startswith("DC-")
                on_hand = (
                    70 + ((sku_index + location_index) % 25)
                    if is_dc
                    else 18 + ((sku_index * 3 + location_index) % 17)
                )
                safety = 20 if is_dc else 8
                position = InventoryPosition(
                    id=f"STOCK-{location_id}-{sku.id}",
                    location_id=location_id,
                    sku_id=sku.id,
                    ownership=brand.relationship,
                    on_hand=on_hand,
                    reserved=(sku_index + location_index) % 4,
                    safety_stock=safety,
                    version=1,
                    retail_price_gbp=sku.retail_price_gbp,
                )
                self.inventory[(location_id, sku.id)] = position

        source = self.inventory[(SOURCE_LOCATION, HERO_SKU)]
        source.ownership = "owned"
        source.on_hand = 90
        source.reserved = 4
        source.safety_stock = 20
        source.retail_price_gbp = 90.0
        destination = self.inventory[(DESTINATION_LOCATION, HERO_SKU)]
        destination.ownership = "owned"
        destination.on_hand = 20
        destination.reserved = 8
        destination.safety_stock = 12
        destination.retail_price_gbp = 90.0

        domestic_sku = "SKU-STYLE-02-RED-S"
        domestic_source = self.inventory[("DC-UK-MID-01", domestic_sku)]
        domestic_source.ownership = "owned"
        domestic_source.on_hand = 100
        domestic_source.reserved = 2
        domestic_source.safety_stock = 20
        domestic_destination = self.inventory[("STORE-UK-MAN-01", domestic_sku)]
        domestic_destination.ownership = "owned"
        domestic_destination.on_hand = 12
        domestic_destination.reserved = 2
        domestic_destination.safety_stock = 6

    def _seed_operations(self) -> None:
        self.demand_history = [
            {
                "day": day,
                "orders": 92 + ((day * 17) % 31),
                "returns": 8 + ((day * 3) % 7),
                "full_price_sell_through": round(0.61 + day * 0.006, 3),
            }
            for day in range(-13, 1)
        ]
        self.deliveries["DELIVERY-IN-0042"] = Delivery(
            id="DELIVERY-IN-0042",
            location_id="DC-UK-MID-01",
            supplier_id="SUPPLIER-07",
            status="delayed",
            expected_at=48.0,
        )
        self.returns["RETURN-0042"] = Return(
            id="RETURN-0042",
            order_id="ORDER-0042",
            customer_id="CUST-0042",
            sku_id="SKU-STYLE-05-GRN-M",
            location_id="STORE-UK-LON-01",
            status="received",
        )
        self.promotions["PROMO-AUTUMN-01"] = Promotion(
            id="PROMO-AUTUMN-01",
            name="Autumn city edit",
            status="at-risk",
            sku_ids=("SKU-STYLE-03-NAV-M",),
        )
        self.seller_offers["OFFER-MKT-0003"] = SellerOffer(
            id="OFFER-MKT-0003",
            seller_id="SELLER-03",
            sku_id="SKU-STYLE-09-NAV-M",
            status="active",
        )
        self.process_cases = {
            workflow_type: ProcessCase(
                id=case.id,
                workflow_type=case.workflow_type,
                subject_ids=case.subject_ids,
                status="open",
                facts=dict(case.facts),
                allowed_actions=case.allowed_actions,
            )
            for workflow_type, case in FASHION_REFERENCE_CASES.items()
        }

    def _retail_lifecycle(self):
        store_ids = tuple(self.stores)
        staff_by_store = {
            store_id: tuple(
                person.id
                for person in self.staff.values()
                if person.location_id == store_id
            )
            for store_id in store_ids
        }
        while True:
            yield self.runtime.env.timeout(ORDINARY_TICK_MINUTES)
            self._tick += 1
            customer = self.customers[
                f"CUST-{customer_number(self._tick, len(self.customers)):04d}"
            ]
            hero_tick = self._tick in HERO_SALE_TICKS
            store_id = (
                DESTINATION_LOCATION
                if hero_tick
                else store_ids[store_number(self._tick, len(store_ids)) - 1]
            )
            customer.location_id = store_id
            customer.status = "shopping"
            entered = self.runtime.emit(
                "customer.entered",
                actor_id=customer.id,
                target_id=store_id,
                trace_id=f"retail-{self._tick:04d}",
                payload={"location_id": store_id},
            )
            customer.last_event_id = entered.event_id

            staff_id = staff_by_store[store_id][self._tick % len(staff_by_store[store_id])]
            colleague = self.staff[staff_id]
            colleague.status = "serving"
            colleague.serving_customer_id = customer.id
            served = self.runtime.emit(
                "staff.served",
                actor_id=colleague.id,
                target_id=customer.id,
                cause_event_id=entered.event_id,
                trace_id=entered.trace_id,
                payload={"location_id": store_id},
            )
            colleague.last_event_id = served.event_id

            sku_id = (
                HERO_SKU
                if hero_tick
                else "SKU-STYLE-02-RED-S"
            )
            self._order_seq += 1
            order_id = f"ORDER-LIVE-{self._order_seq:05d}"
            order = Order(
                id=order_id,
                customer_id=customer.id,
                sku_id=sku_id,
                quantity=1,
                location_id=store_id,
                channel=("store" if self._tick % 3 else "click-and-collect"),
                status="confirmed",
                created_at=self.runtime.now,
            )
            self.orders[order_id] = order
            placed = self.runtime.emit(
                "order.placed",
                actor_id=order.id,
                target_id=customer.id,
                cause_event_id=served.event_id,
                trace_id=entered.trace_id,
                payload={
                    "location_id": store_id,
                    "sku_id": sku_id,
                    "quantity": 1,
                    "channel": order.channel,
                },
            )
            order.last_event_id = placed.event_id

            sale_location = (
                DESTINATION_LOCATION if sku_id == HERO_SKU else store_id
            )
            position = self.inventory[(sale_location, sku_id)]
            sold: SimulationEvent | None = None
            if position.available > 0:
                position.on_hand -= 1
                position.version += 1
                sold = self.runtime.emit(
                    "inventory.sold",
                    actor_id=position.id,
                    target_id=order.id,
                    cause_event_id=placed.event_id,
                    trace_id=entered.trace_id,
                    payload={
                        "location_id": sale_location,
                        "sku_id": sku_id,
                        "available": position.available,
                        "version": position.version,
                    },
                )
                position.last_event_id = sold.event_id
                inventory_event = sold
                if sku_id == HERO_SKU:
                    self.hero_sales += 1
                    self._evaluate_inventory_sensor(sold)
            else:
                order.status = "cancelled"
                stockout = self.runtime.emit(
                    "inventory.stockout",
                    actor_id=position.id,
                    target_id=order.id,
                    cause_event_id=placed.event_id,
                    trace_id=entered.trace_id,
                    payload={
                        "location_id": sale_location,
                        "sku_id": sku_id,
                        "available": position.available,
                        "version": position.version,
                    },
                )
                cancelled = self.runtime.emit(
                    "order.cancelled",
                    actor_id=order.id,
                    target_id=customer.id,
                    cause_event_id=stockout.event_id,
                    trace_id=entered.trace_id,
                    payload={
                        "location_id": store_id,
                        "reason": "out_of_stock",
                    },
                )
                order.last_event_id = cancelled.event_id
                inventory_event = cancelled

            if sold is not None and should_cancel(self._tick):
                order.status = "cancelled"
                cancelled = self.runtime.emit(
                    "order.cancelled",
                    actor_id=order.id,
                    target_id=customer.id,
                    cause_event_id=sold.event_id,
                    trace_id=entered.trace_id,
                    payload={"location_id": store_id, "reason": "customer_changed_mind"},
                )
                order.last_event_id = cancelled.event_id

            if sold is not None and should_receive_return(self._tick):
                self._return_seq += 1
                return_id = f"RETURN-LIVE-{self._return_seq:05d}"
                returned = Return(
                    id=return_id,
                    order_id=order.id,
                    customer_id=customer.id,
                    sku_id=sku_id,
                    location_id=store_id,
                    status="received",
                )
                self.returns[return_id] = returned
                event = self.runtime.emit(
                    "return.received",
                    actor_id=returned.id,
                    target_id=order.id,
                    cause_event_id=order.last_event_id,
                    trace_id=entered.trace_id,
                    payload={"location_id": store_id, "sku_id": sku_id},
                )
                returned.last_event_id = event.event_id

            if should_receive_delivery(self._tick):
                self._delivery_seq += 1
                delivery_id = f"DELIVERY-LIVE-{self._delivery_seq:05d}"
                delivery = Delivery(
                    id=delivery_id,
                    location_id=store_id,
                    supplier_id=f"SUPPLIER-{(self._tick % 12) + 1:02d}",
                    status="arrived",
                    expected_at=self.runtime.now,
                )
                self.deliveries[delivery_id] = delivery
                event = self.runtime.emit(
                    "delivery.arrived",
                    actor_id=delivery.id,
                    target_id=store_id,
                    cause_event_id=inventory_event.event_id,
                    trace_id=entered.trace_id,
                    payload={"location_id": store_id},
                )
                delivery.last_event_id = event.event_id

            customer.status = "departed"
            customer.location_id = "OFFSITE"
            moved = self.runtime.emit(
                "customer.moved",
                actor_id=customer.id,
                target_id="OFFSITE",
                cause_event_id=inventory_event.event_id,
                trace_id=entered.trace_id,
                payload={"location_id": "OFFSITE", "status": "departed"},
            )
            customer.last_event_id = moved.event_id
            colleague.status = "available"
            colleague.serving_customer_id = None

    def _evaluate_inventory_sensor(self, cause: SimulationEvent) -> None:
        crossed = inventory_imbalance_crossed(self)
        if not crossed or self._imbalance_active:
            return
        self._imbalance_active = True
        story_id = f"fashion-trading-shock-{self.runtime.seed}"
        baseline = self._executive_kpis()
        self.trading_shock.start(
            cause.event_id,
            story_id,
            self.runtime.now,
            baseline,
        )
        detected = self.runtime.emit(
            "retail.trading-shock.detected",
            actor_id="retail:trading-shock",
            target_id=HERO_SKU,
            cause_event_id=cause.event_id,
            trace_id=story_id,
            payload={
                "story_id": story_id,
                "baseline_kpis": baseline,
            },
        )
        self._emit_ready_story_sensors(detected)

    def _emit_ready_story_sensors(self, cause: SimulationEvent) -> None:
        story_id = self.trading_shock.trace_id
        if story_id is None:
            return
        for stage in self.trading_shock.ready_to_trigger():
            profile = FASHION_PROCESS_PROFILES[stage.workflow_type]
            case = self.process_cases[stage.workflow_type]
            payload = {
                "workflow_type": stage.workflow_type,
                "story_id": story_id,
                "case_id": case.id,
                "actor_ids": list(case.subject_ids),
                "measurements": {
                    "risk_score": float(case.facts.get("risk_score") or 0.75),
                },
            }
            target_id = case.subject_ids[0] if case.subject_ids else case.id
            if stage.workflow_type == "inventory-rebalancing":
                payload.update(
                    {
                        "measurements": inventory_measurements(self),
                        "threshold": {
                            "crossed": True,
                            "destination_available_lte": 8,
                            "source_available_gte": 60,
                            "demand_sales_gte": 4,
                        },
                        "source_location_id": SOURCE_LOCATION,
                        "destination_location_id": DESTINATION_LOCATION,
                        "ownership": "owned",
                    }
                )
                target_id = HERO_SKU
            sensor = self.runtime.emit(
                "sensor.tripped",
                actor_id=profile.sensor_id,
                target_id=target_id,
                cause_event_id=cause.event_id,
                trace_id=story_id,
                payload=payload,
            )
            self.trading_shock.mark_triggered(
                stage.workflow_type,
                sensor_event_id=sensor.event_id,
                reason="causal trading shock",
            )

    def bind_story_workflow(
        self,
        sensor_event: dict[str, Any],
        workflow_id: str,
    ) -> None:
        payload = sensor_event.get("payload")
        if not isinstance(payload, dict):
            return
        if payload.get("story_id") != self.trading_shock.trace_id:
            return
        workflow_type = payload.get("workflow_type")
        if workflow_type not in FASHION_PROCESS_PROFILES:
            return
        self.trading_shock.bind_workflow(
            workflow_type,
            workflow_id=workflow_id,
        )

    def fail_story_workflow(self, workflow_id: str, reason: str) -> None:
        for workflow_type in FASHION_PROCESS_PROFILES:
            stage = self.trading_shock.stage(workflow_type)
            if stage.workflow_id == workflow_id:
                if stage.status == "active":
                    self.trading_shock.fail(workflow_type, reason=reason)
                return

    def _complete_story_workflow(
        self,
        workflow_id: str,
        cause: SimulationEvent,
    ) -> None:
        for workflow_type in FASHION_PROCESS_PROFILES:
            stage = self.trading_shock.stage(workflow_type)
            if stage.workflow_id == workflow_id:
                self.trading_shock.complete(
                    workflow_type,
                    reason=f"world success: {cause.type}",
                )
                self.trading_shock.update_outcome(self._executive_kpis())
                self._emit_ready_story_sensors(cause)
                return

    def _executive_kpis(self) -> dict[str, float]:
        inventory = tuple(self.inventory.values())
        total_on_hand = sum(position.on_hand for position in inventory)
        available = sum(position.available for position in inventory)
        destination = self.inventory[(DESTINATION_LOCATION, HERO_SKU)]
        hero_stockouts = sum(
            event.type == "inventory.stockout"
            and event.payload.get("sku_id") == HERO_SKU
            for event in self.runtime.journal
        )
        completed_cases = sum(
            case.status == "completed" for case in self.process_cases.values()
        )
        confirmed_orders = sum(
            order.status == "confirmed" for order in self.orders.values()
        )
        active_promotion_value = sum(
            self.skus[sku_id].retail_price_gbp
            for promotion in self.promotions.values()
            if promotion.status != "ready"
            for sku_id in promotion.sku_ids
        )
        active_offer_value = sum(
            self.skus[offer.sku_id].retail_price_gbp
            for offer in self.seller_offers.values()
            if offer.status == "active"
        )
        recovered_transfer_value = sum(
            relationship["quantity"]
            * self.skus[relationship["sku_id"]].retail_price_gbp
            for relationship in self.knowledge_relationships
        )
        return {
            "availability_pct": round(100 * available / total_on_hand, 2)
            if total_on_hand
            else 0.0,
            "projected_lost_sales_gbp": round(
                (hero_stockouts + max(0, destination.safety_stock - destination.available))
                * destination.retail_price_gbp,
                2,
            ),
            "full_price_sell_through_pct": round(
                100 * self.hero_sales / (self.hero_sales + destination.available),
                2,
            )
            if self.hero_sales + destination.available
            else 0.0,
            "fulfilment_success_pct": round(
                100 * confirmed_orders / len(self.orders),
                2,
            )
            if self.orders
            else 100.0,
            "markdown_exposure_gbp": round(
                active_promotion_value + active_offer_value,
                2,
            ),
            "recovery_value_gbp": round(
                recovered_transfer_value
                + completed_cases * destination.retail_price_gbp,
                2,
            ),
        }

    def build_observation(
        self,
        sensor_event: dict[str, Any],
        *,
        now: float,
    ) -> dict[str, Any]:
        sensor_id = sensor_event.get("actor_id")
        profile = next(
            (
                candidate
                for candidate in FASHION_PROCESS_PROFILES.values()
                if candidate.sensor_id == sensor_id
            ),
            None,
        )
        if profile is None:
            raise ValueError(f"unknown Fashion sensor {sensor_id!r}")
        case = self.process_cases[profile.workflow_type]
        observation = {
            "workflow_type": profile.workflow_type,
            "case": self._case_view(case),
            "actor_ids": list(case.subject_ids),
            "event_ids": [sensor_event["event_id"]],
            "trace_id": sensor_event["trace_id"],
            "as_of_sim_time": now,
            "skills": [profile.skill],
            "mcp_tools": self._tools_for(profile),
            "authority": {
                "persona": profile.hitl_persona,
                "external_event": profile.hitl_event,
            },
            "typed_command": profile.command_type,
        }
        story_id = (sensor_event.get("payload") or {}).get("story_id")
        if story_id:
            observation["story_id"] = story_id
        if profile.workflow_type == "inventory-rebalancing":
            observation.update(
                {
                    "measurements": inventory_measurements(self),
                    "transfer_candidate": {
                        "source_location_id": SOURCE_LOCATION,
                        "destination_location_id": DESTINATION_LOCATION,
                        "sku_id": HERO_SKU,
                        "quantity": 24,
                        "ownership": "owned",
                        "expected_source_version": self.inventory[
                            (SOURCE_LOCATION, HERO_SKU)
                        ].version,
                        "expected_destination_version": self.inventory[
                            (DESTINATION_LOCATION, HERO_SKU)
                        ].version,
                        "cross_border": True,
                    },
                    "policy": {
                        "decision": "approval_required",
                        "reason": "cross-border transfer",
                        "auto_value_limit_gbp": 10_000,
                        "auto_quantity_limit": 50,
                    },
                }
            )
        return observation

    @staticmethod
    def _tools_for(profile: FashionProcessProfile) -> list[str]:
        tools = {
            "inventory-rebalancing": [
                "fashion_read_inventory",
                "fashion_prepare_inventory_transfer",
            ],
            "demand-spike-response": ["fashion_read_inventory"],
            "promotion-readiness": ["fashion_assess_promotion"],
            "markdown-governance": ["fashion_prepare_markdown_recommendation"],
            "supplier-delay-recovery": ["fashion_prepare_supplier_recovery"],
            "fulfilment-exception-resolution": [
                "fashion_prepare_fulfilment_resolution"
            ],
            "marketplace-seller-exception": [
                "fashion_prepare_seller_suppression"
            ],
            "returns-disposition": ["fashion_prepare_return_disposition"],
        }
        return tools[profile.workflow_type]

    def run_reference_process(self, workflow_type: str) -> dict[str, Any]:
        profile = FASHION_PROCESS_PROFILES.get(workflow_type)
        if profile is None:
            raise ValueError(f"unknown Fashion process {workflow_type!r}")
        case = self.process_cases[workflow_type]
        event = self.runtime.emit(
            "sensor.tripped",
            actor_id=profile.sensor_id,
            target_id=case.subject_ids[0] if case.subject_ids else case.id,
            payload={
                "workflow_type": workflow_type,
                "case_id": case.id,
                "measurements": {
                    "risk_score": float(case.facts.get("risk_score") or 0.75)
                },
                "diagnostic": True,
            },
        )
        return {
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "case_id": case.id,
        }

    def command_for_reference_process(
        self,
        workflow_type: str,
        *,
        trace_id: str,
        workflow_id: str,
        approval_decision: str | None,
    ) -> SimulationCommand:
        profile = FASHION_PROCESS_PROFILES[workflow_type]
        case = self.process_cases[workflow_type]
        return SimulationCommand(
            command_id=f"CMD-{profile.prefix.upper()}-{len(self._applied_command_ids) + 1:04d}",
            trace_id=trace_id,
            issued_by=profile.function,
            type=profile.command_type,
            payload={
                "workflow_id": workflow_id,
                "case_id": case.id,
                "subject_ids": list(case.subject_ids),
                "action": profile.command_type,
                "approval_decision": approval_decision,
                "approval_reference": (
                    f"HITL-{profile.prefix.upper()}-001"
                    if approval_decision == "approve"
                    else None
                ),
                "skill_outputs": {
                    profile.skill: {
                        "recommendation": profile.command_type,
                        "actor_ids": list(case.subject_ids),
                    }
                },
                "evidence_digest": f"sha256:{profile.prefix}-evidence",
            },
        )

    def apply_command(self, command: SimulationCommand) -> SimulationEvent:
        if command.command_id in self._applied_command_ids:
            return self.runtime.emit(
                "command.duplicate",
                actor_id=command.issued_by,
                trace_id=command.trace_id,
                payload={"command_id": command.command_id},
            )
        if command.type == "inventory.transfer":
            return self._apply_inventory_transfer(command)
        profile = next(
            (
                candidate
                for candidate in FASHION_PROCESS_PROFILES.values()
                if candidate.command_type == command.type
            ),
            None,
        )
        if profile is None:
            return self._reject(command, f"unknown command type {command.type!r}")
        return self._apply_reference_command(profile, command)

    def _apply_inventory_transfer(
        self,
        command: SimulationCommand,
    ) -> SimulationEvent:
        payload = command.payload
        required = {
            "workflow_id",
            "source_location_id",
            "destination_location_id",
            "sku_id",
            "quantity",
            "ownership",
            "expected_source_version",
            "expected_destination_version",
            "policy_decision",
            "evidence_digest",
        }
        missing = sorted(required - set(payload))
        if missing:
            return self._reject(command, f"missing transfer fields: {missing}")
        source_key = (payload["source_location_id"], payload["sku_id"])
        destination_key = (payload["destination_location_id"], payload["sku_id"])
        source = self.inventory.get(source_key)
        destination = self.inventory.get(destination_key)
        if source is None or destination is None or source_key == destination_key:
            return self._reject(command, "invalid source/destination combination")
        if payload["ownership"] != "owned" or source.ownership != "owned":
            return self._reject(
                command,
                "inventory.transfer accepts owned inventory only",
            )
        if source.version != payload["expected_source_version"]:
            return self._reject(command, "stale source version")
        if destination.version != payload["expected_destination_version"]:
            return self._reject(command, "stale destination version")
        quantity = payload["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            return self._reject(command, "quantity must be a positive integer")
        if quantity > 50 and not payload.get("approval_reference"):
            return self._reject(command, "quantity above 50 requires approval")
        if source.available - quantity < source.safety_stock:
            return self._reject(command, "transfer would breach source safety stock")
        retail_value = quantity * source.retail_price_gbp
        if retail_value > 10_000 and not payload.get("approval_reference"):
            return self._reject(command, "retail value above GBP 10000 requires approval")
        source_location = self._location(source.location_id)
        destination_location = self._location(destination.location_id)
        cross_border = source_location.country != destination_location.country
        if cross_border and not payload.get("approval_reference"):
            return self._reject(command, "cross-border transfer requires approval")

        accepted = self._accept(command, target_id=source.id)
        source.on_hand -= quantity
        source.version += 1
        destination.on_hand += quantity
        destination.version += 1
        transferred = self.runtime.emit(
            "inventory.transferred",
            actor_id=source.id,
            target_id=destination.id,
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "command_id": command.command_id,
                "workflow_id": payload["workflow_id"],
                "sku_id": source.sku_id,
                "quantity": quantity,
                "source_location_id": source.location_id,
                "destination_location_id": destination.location_id,
                "source_stock_id": source.id,
                "destination_stock_id": destination.id,
                "approval_reference": payload.get("approval_reference"),
                "measurements": {
                    "source_available": source.available,
                    "destination_available": destination.available,
                    "transfer_cost_gbp": 180.0,
                    "expected_recovered_margin_gbp": 864.0,
                    "fairness_score": 0.94,
                },
            },
        )
        source.last_event_id = transferred.event_id
        destination.last_event_id = transferred.event_id
        self.knowledge_relationships.append(
            {
                "workflow_id": payload["workflow_id"],
                "event_id": transferred.event_id,
                "source_id": source.id,
                "relationship": "TRANSFERRED_TO",
                "destination_id": destination.id,
                "sku_id": source.sku_id,
                "quantity": quantity,
            }
        )
        case = self.process_cases["inventory-rebalancing"]
        case.status = "completed"
        case.outcome = dict(self.knowledge_relationships[-1])
        if payload.get("story_id"):
            self._complete_story_workflow(payload["workflow_id"], transferred)
        return accepted

    def _apply_reference_command(
        self,
        profile: FashionProcessProfile,
        command: SimulationCommand,
    ) -> SimulationEvent:
        payload = command.payload
        case = self.process_cases.get(profile.workflow_type)
        if case is None or payload.get("case_id") != case.id:
            return self._reject(command, "unknown process case")
        if case.status != "open":
            return self._reject(command, f"case {case.id} is not open")
        if payload.get("action") != profile.command_type:
            return self._reject(command, "action is outside process contract")
        if tuple(payload.get("subject_ids") or ()) != case.subject_ids:
            return self._reject(command, "command subject IDs do not match case")
        skill_outputs = payload.get("skill_outputs")
        if not isinstance(skill_outputs, dict) or profile.skill not in skill_outputs:
            return self._reject(command, "command is missing declared skill output")
        if profile.hitl_persona and payload.get("approval_decision") != "approve":
            return self._reject(command, f"{profile.hitl_event} approval is required")

        accepted = self._accept(command, target_id=case.id)
        case.status = "completed"
        case.outcome = {
            "workflow_id": payload["workflow_id"],
            "command_type": profile.command_type,
            "subject_ids": list(case.subject_ids),
            "approval_reference": payload.get("approval_reference"),
        }
        self._mutate_reference_state(profile, case)
        success = self.runtime.emit(
            profile.success_event,
            actor_id=case.id,
            target_id=case.subject_ids[0] if case.subject_ids else None,
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={
                "workflow_id": payload["workflow_id"],
                "command_id": command.command_id,
                "case": self._case_view(case),
                "measurements": {"contract_passed": 1, "risk_remaining": 0},
            },
        )
        if payload.get("story_id"):
            self._complete_story_workflow(payload["workflow_id"], success)
        return accepted

    def _mutate_reference_state(
        self,
        profile: FashionProcessProfile,
        case: ProcessCase,
    ) -> None:
        if profile.workflow_type == "demand-spike-response":
            case.outcome["allocation_status"] = "adjusted"
        elif profile.workflow_type == "promotion-readiness":
            self.promotions["PROMO-AUTUMN-01"].status = "ready"
        elif profile.workflow_type == "markdown-governance":
            case.outcome["price_mutated"] = False
            case.outcome["recommendation_status"] = "approved"
        elif profile.workflow_type == "supplier-delay-recovery":
            self.deliveries["DELIVERY-IN-0042"].status = "recovery-planned"
        elif profile.workflow_type == "fulfilment-exception-resolution":
            case.outcome["fulfilment_status"] = "rerouted"
        elif profile.workflow_type == "marketplace-seller-exception":
            self.seller_offers["OFFER-MKT-0003"].status = "suppressed"
        elif profile.workflow_type == "returns-disposition":
            returned = self.returns["RETURN-0042"]
            returned.status = "completed"
            returned.disposition = "restock"
            stock = self.inventory[(returned.location_id, returned.sku_id)]
            stock.on_hand += 1
            stock.version += 1

    def _accept(
        self,
        command: SimulationCommand,
        *,
        target_id: str | None,
    ) -> SimulationEvent:
        self._applied_command_ids.add(command.command_id)
        return self.runtime.emit(
            "command.accepted",
            actor_id=command.issued_by,
            target_id=target_id,
            trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )

    def _reject(
        self,
        command: SimulationCommand,
        reason: str,
    ) -> SimulationEvent:
        event = self.runtime.emit(
            "command.rejected",
            actor_id=command.issued_by,
            trace_id=command.trace_id,
            payload={"command": command.to_dict(), "reason": reason},
        )
        if command.payload.get("story_id"):
            self.fail_story_workflow(str(command.payload.get("workflow_id")), reason)
        return event

    def _location(self, location_id: str) -> Location:
        location = self.stores.get(location_id) or self.distribution_centres.get(
            location_id
        )
        if location is None:
            raise ValueError(f"unknown Fashion location {location_id!r}")
        return location

    @staticmethod
    def _case_view(case: ProcessCase) -> dict[str, Any]:
        data = asdict(case)
        data["subject_ids"] = list(case.subject_ids)
        data["allowed_actions"] = list(case.allowed_actions)
        return data

    def _inventory_token_views(self) -> list[dict[str, Any]]:
        visible_skus = {HERO_SKU, "SKU-STYLE-02-RED-S"}
        tokens: list[dict[str, Any]] = []
        for (location_id, sku_id), position in self.inventory.items():
            if sku_id not in visible_skus:
                continue
            if (
                location_id not in self.stores
                and (location_id, sku_id)
                not in {
                    ("DC-UK-MID-01", "SKU-STYLE-02-RED-S"),
                    ("DC-EU-LIL-01", HERO_SKU),
                }
            ):
                continue
            token = view(position)
            token["status"] = f"{position.available} available"
            tokens.append(token)
        return tokens

    def render_state(self) -> dict[str, Any]:
        return {
            "stores": [view(item) for item in self.stores.values()],
            "distribution_centres": [
                view(item) for item in self.distribution_centres.values()
            ],
            "brands": [view(item) for item in self.brands.values()],
            "styles": [view(item) for item in self.styles.values()],
            "skus": [view(item) for item in self.skus.values()],
            "customers": [view(item) for item in self.customers.values()],
            "staff": [view(item) for item in self.staff.values()],
            "inventory": [view(item) for item in self.inventory.values()],
            "inventory_tokens": self._inventory_token_views(),
            "orders": [view(item) for item in self.orders.values()],
            "deliveries": [view(item) for item in self.deliveries.values()],
            "returns": [view(item) for item in self.returns.values()],
            "promotions": [view(item) for item in self.promotions.values()],
            "seller_offers": [view(item) for item in self.seller_offers.values()],
            "process_cases": [
                self._case_view(item) for item in self.process_cases.values()
            ],
            "demand_history": list(self.demand_history),
            "threshold_state": {
                "sensor_id": "sensor:inventory_imbalance",
                "active": self._imbalance_active,
                "measurements": inventory_measurements(self),
            },
            "knowledge_relationships": list(self.knowledge_relationships),
            "ordinary_activity_count": self._order_seq,
            "story": self.trading_shock.view(),
        }
