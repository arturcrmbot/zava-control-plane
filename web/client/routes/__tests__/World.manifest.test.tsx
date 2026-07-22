// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const { mockRuntime, mockWorld } = vi.hoisted(() => ({
  mockRuntime: vi.fn(),
  mockWorld: vi.fn(),
}));

vi.mock("@client/hooks/useRuntimeManifest", () => ({
  useRuntimeManifest: mockRuntime,
}));
vi.mock("@client/hooks/useWorldSimulation", () => ({
  useWorldSimulation: mockWorld,
}));
vi.mock("@client/routes/TelcoWorld", () => ({
  default: () => <div data-testid="telco-world-route" />,
}));

import World from "../World";

beforeEach(() => {
  mockWorld.mockReturnValue({
    state: {
      enabled: true,
      scenario: "support",
      tickets: [],
      workers: [],
      objectives: [],
    },
    events: [],
    loading: false,
    error: null,
    injectSurge: vi.fn(),
    injectSiteFailure: vi.fn(),
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("World runtime manifest routing", () => {
  it("does not poll world state when the active pack has no world", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { display_name: "Agency" },
        world: null,
        ui: { lenses: ["agency-operations"] },
      },
    });

    render(<World />);

    expect(screen.getByText(/No actor world is active for Agency/)).toBeTruthy();
    expect(mockWorld).not.toHaveBeenCalled();
  });

  it("uses the configured Telco lens instead of snapshot inference", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { display_name: "Telco" },
        world: "telco",
        ui: { lenses: ["telco-network"] },
      },
    });

    render(<World />);

    expect(screen.getByTestId("telco-world-route")).toBeTruthy();
  });

  it("waits for the first world snapshot before rendering Telco", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { display_name: "Telco" },
        world: "telco",
        ui: { lenses: ["telco-network"] },
      },
    });
    mockWorld.mockReturnValue({
      state: null,
      events: [],
      loading: true,
      error: null,
      injectSurge: vi.fn(),
      injectSiteFailure: vi.fn(),
    });

    render(<World />);

    expect(screen.getByRole("status").textContent).toContain("Loading world");
    expect(screen.queryByTestId("telco-world-route")).toBeNull();
  });

  it("renders Fashion actors and runs the eight Fashion processes", async () => {
    const runReferenceProcess = vi.fn(async () => {});
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { name: "fashion", display_name: "Fashion Retail" },
        world: "fashion",
        ui: { lenses: ["process-library", "order", "customer-impact", "control"] },
      },
    });
    mockWorld.mockReturnValue({
      state: {
        enabled: true,
        scenario: "fashion",
        seed: 42,
        status: "running",
        sim_time: 12,
        stores: Array.from({ length: 8 }, (_, i) => ({ id: `STORE-${i + 1}` })),
        distribution_centres: [
          { id: "DC-UK-01" },
          { id: "DC-EU-01" },
        ],
        brands: Array.from({ length: 12 }, (_, i) => ({ id: `BRAND-${i + 1}` })),
        styles: Array.from({ length: 24 }, (_, i) => ({ id: `STYLE-${i + 1}` })),
        skus: Array.from({ length: 192 }, (_, i) => ({ id: `SKU-${i + 1}` })),
        customers: Array.from({ length: 300 }, (_, i) => ({ id: `CUST-${i + 1}` })),
        inventory: Array.from({ length: 192 }, (_, i) => ({
          location_id: "DC-UK-01",
          sku_id: `SKU-${i + 1}`,
          on_hand: 10,
        })),
        process_cases: [
          {
            id: "fashion-inventory-rebalance-auto",
            workflow_type: "inventory-rebalancing",
            subject_ids: ["SKU-0001"],
            status: "open",
            facts: {},
            allowed_actions: ["inventory.transfer"],
            recommended_action: "inventory.transfer",
            outcome: null,
          },
        ],
        objectives: [],
      },
      events: [],
      loading: false,
      error: null,
      injectSurge: vi.fn(),
      injectSiteFailure: vi.fn(),
      runScenario: vi.fn(),
      runReferenceProcess,
    });

    render(<World />);

    expect(screen.getByTestId("fashion-world-route")).toBeTruthy();
    expect(screen.getByText("8 stores")).toBeTruthy();
    expect(screen.getByText("2 distribution centres")).toBeTruthy();
    expect(screen.getByText("192 SKUs")).toBeTruthy();
    expect(screen.getByText("192 inventory positions")).toBeTruthy();
    expect(screen.getByText("inventory-rebalancing")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Run 8 Fashion processes/i }));

    await waitFor(() => expect(runReferenceProcess).toHaveBeenCalledTimes(8));
    expect(runReferenceProcess.mock.calls.map(([workflowType]) => workflowType)).toEqual([
      "inventory-rebalancing",
      "demand-spike-response",
      "promotion-readiness",
      "markdown-governance",
      "supplier-delay-recovery",
      "fulfilment-exception-resolution",
      "marketplace-seller-exception",
      "returns-disposition",
    ]);
  });
});
