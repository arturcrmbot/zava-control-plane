// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import SpatialWorld, {
  type WorldSceneContract,
} from "@client/components/world/SpatialWorld";
import type {
  WorldEvent,
  WorldState,
} from "@client/hooks/useWorldSimulation";


const scene: WorldSceneContract = {
  enabled: true,
  schema_version: 1,
  title: "Fashion Retail Live Operations",
  subtitle: "UK/EU stores, customers, colleagues and stock",
  locations: [
    {
      id: "STORE-EU-PAR-01",
      label: "Paris Rivoli",
      kind: "flagship store",
      x: 5,
      y: 10,
      width: 35,
      height: 35,
    },
    {
      id: "STORE-UK-LON-01",
      label: "Oxford Street",
      kind: "flagship store",
      x: 55,
      y: 10,
      width: 35,
      height: 35,
    },
  ],
  layers: [
    {
      state_key: "customers",
      kind: "customer",
      label: "Customers",
      id_field: "id",
      location_field: "location_id",
      status_field: "status",
      colour: "#f43f5e",
    },
    {
      state_key: "inventory_tokens",
      kind: "stock",
      label: "Stock",
      id_field: "id",
      location_field: "location_id",
      status_field: "status",
      colour: "#10b981",
    },
  ],
  event_mappings: [
    {
      event_type: "customer.moved",
      layer: "customers",
      animation: "move",
    },
    {
      event_type: "inventory.transferred",
      layer: "inventory_tokens",
      animation: "move",
    },
  ],
  process_event_types: [
    "sensor.tripped",
    "responder.decided",
    "inventory.transferred",
  ],
  knowledge_relationship_label: "Stock moved from Paris to Oxford Street",
  knowledge_actor_ids: [
    "SKU-STYLE-01-BLK-M",
    "STORE-EU-PAR-01",
    "STORE-UK-LON-01",
  ],
};

const baseline: WorldState = {
  enabled: true,
  scenario: "fashion",
  seed: 42,
  status: "running",
  sim_time: 30,
  customers: [
    {
      id: "CUST-0042",
      location_id: "STORE-EU-PAR-01",
      status: "shopping",
    },
  ],
  inventory_tokens: [
    {
      id: "STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M",
      location_id: "STORE-EU-PAR-01",
      status: "62 available",
      sku_id: "SKU-STYLE-01-BLK-M",
    },
  ],
  threshold_state: {
    sensor_id: "sensor:inventory_imbalance",
    active: false,
    measurements: {
      destination_available: 10,
      source_available: 86,
    },
  },
  knowledge_relationships: [],
};

const sensor: WorldEvent = {
  seq: 1,
  event_id: "evt-00000142",
  sim_time: 36,
  type: "sensor.tripped",
  actor_id: "sensor:inventory_imbalance",
  target_id: "SKU-STYLE-01-BLK-M",
  cause_event_id: "evt-00000141",
  trace_id: "trace-fashion-42",
  payload: {
    workflow_type: "inventory-rebalancing",
    threshold: { crossed: true },
    measurements: {
      destination_available: 8,
      source_available: 86,
    },
  },
};

afterEach(cleanup);

function renderWorld(
  state: WorldState = baseline,
  events: WorldEvent[] = [],
) {
  return render(
    <MemoryRouter>
      <SpatialWorld
        scene={scene}
        state={state}
        events={events}
        error={null}
        onReset={async () => {}}
      />
    </MemoryRouter>,
  );
}

describe("SpatialWorld", () => {
  it("makes the industry and real actor IDs recognisable without narration", () => {
    renderWorld();

    expect(screen.getByText("Fashion Retail Live Operations")).toBeTruthy();
    expect(screen.getByText(/UK\/EU stores, customers/)).toBeTruthy();
    expect(screen.getByText("Paris Rivoli")).toBeTruthy();
    expect(screen.getByText("Oxford Street")).toBeTruthy();
    expect(screen.getByTestId("actor-CUST-0042")).toBeTruthy();
    expect(
      screen.getByTestId(
        "actor-STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /run process/i })).toBeNull();
  });

  it("moves a real actor only when snapshot and journal evidence change", () => {
    const { rerender } = renderWorld();
    const before = screen.getByTestId("actor-CUST-0042").style.left;
    const movedState: WorldState = {
      ...baseline,
      sim_time: 39,
      customers: [
        {
          id: "CUST-0042",
          location_id: "STORE-UK-LON-01",
          status: "shopping",
        },
      ],
    };
    const movement: WorldEvent = {
      ...sensor,
      seq: 2,
      event_id: "evt-00000143",
      sim_time: 39,
      type: "customer.moved",
      actor_id: "CUST-0042",
      target_id: "STORE-UK-LON-01",
      payload: { location_id: "STORE-UK-LON-01" },
    };

    rerender(
      <MemoryRouter>
        <SpatialWorld
          scene={scene}
          state={movedState}
          events={[movement]}
          error={null}
          onReset={async () => {}}
        />
      </MemoryRouter>,
    );

    const after = screen.getByTestId("actor-CUST-0042");
    expect(after.style.left).not.toBe(before);
    expect(after.dataset.eventId).toBe("evt-00000143");
  });

  it("renders journal-backed stock quantity changes as visible token state", () => {
    const { rerender } = renderWorld();
    const stockId = "STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M";
    expect(screen.getByTestId(`actor-${stockId}`).textContent).toContain(
      "62 available",
    );
    const changed: WorldState = {
      ...baseline,
      inventory_tokens: [
        {
          id: stockId,
          location_id: "STORE-EU-PAR-01",
          status: "38 available",
          sku_id: "SKU-STYLE-01-BLK-M",
        },
      ],
    };
    const event: WorldEvent = {
      ...sensor,
      seq: 2,
      event_id: "evt-stock-change",
      type: "inventory.transferred",
      actor_id: stockId,
      target_id: "STOCK-STORE-UK-LON-01-SKU-STYLE-01-BLK-M",
    };

    rerender(
      <MemoryRouter>
        <SpatialWorld
          scene={scene}
          state={changed}
          events={[event]}
          error={null}
          onReset={async () => {}}
        />
      </MemoryRouter>,
    );

    const token = screen.getByTestId(`actor-${stockId}`);
    expect(token.textContent).toContain("38 available");
    expect(token.dataset.eventId).toBe("evt-stock-change");
  });

  it("filters causal journal by the selected actor", () => {
    const unrelated: WorldEvent = {
      ...sensor,
      seq: 2,
      event_id: "evt-unrelated",
      type: "promotion.ready",
      actor_id: "PROMO-AUTUMN-01",
      target_id: null,
      trace_id: "trace-other",
    };
    renderWorld(baseline, [
      {
        ...sensor,
        type: "customer.moved",
        actor_id: "CUST-0042",
        target_id: "STORE-EU-PAR-01",
      },
      unrelated,
    ]);

    fireEvent.click(screen.getByTestId("actor-CUST-0042"));

    expect(screen.getByText(/filtering CUST-0042/)).toBeTruthy();
    expect(screen.getByText("evt-00000142")).toBeTruthy();
    expect(screen.queryByText("evt-unrelated")).toBeNull();
  });

  it("links the automatic process to its exact workflow and trigger evidence", () => {
    const decided: WorldEvent = {
      ...sensor,
      seq: 2,
      event_id: "evt-00000150",
      type: "responder.decided",
      actor_id: "merchandising-planning",
      target_id: "SKU-STYLE-01-BLK-M",
      payload: {
        workflow_id: "rebalance-evt-00000142",
        workflow_type: "inventory-rebalancing",
        command: { type: "inventory.transfer" },
        reasoning: "Demand exceeded destination availability.",
      },
    };

    renderWorld(baseline, [sensor, decided]);

    expect(screen.getByText("inventory-rebalancing")).toBeTruthy();
    expect(screen.getByText(/destination_available 8/)).toBeTruthy();
    const link = screen.getByRole("link", {
      name: /inspect workflow rebalance-evt-00000142/i,
    });
    expect(link.getAttribute("href")).toBe(
      "/workflows/rebalance-evt-00000142",
    );
  });

  it("shows the same changed relationship and links to Knowledge", () => {
    const completed: WorldState = {
      ...baseline,
      knowledge_relationships: [
        {
          workflow_id: "rebalance-evt-00000142",
          source_id: "STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M",
          relationship: "TRANSFERRED_TO",
          destination_id: "STOCK-STORE-UK-LON-01-SKU-STYLE-01-BLK-M",
        },
      ],
    };

    renderWorld(completed, []);

    expect(screen.getByText("rebalance-evt-00000142")).toBeTruthy();
    expect(screen.getByText(/TRANSFERRED_TO/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /open knowledge/i }).getAttribute("href"))
      .toBe("/knowledge");
  });
});
