// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

const { mockRuntime, mockWorld, mockScene } = vi.hoisted(() => ({
  mockRuntime: vi.fn(),
  mockWorld: vi.fn(),
  mockScene: vi.fn(),
}));

vi.mock("@client/hooks/useRuntimeManifest", () => ({
  useRuntimeManifest: mockRuntime,
}));
vi.mock("@client/hooks/useWorldSimulation", () => ({
  useWorldSimulation: mockWorld,
}));
vi.mock("@client/hooks/useWorldScene", () => ({
  useWorldScene: mockScene,
}));
vi.mock("@client/routes/TelcoWorld", () => ({
  default: () => <div data-testid="telco-world-route" />,
}));
vi.mock("@client/components/world/SpatialWorld", () => ({
  default: () => <div data-testid="spatial-world-route" />,
}));

import World from "../World";

beforeEach(() => {
  mockScene.mockReturnValue({
    scene: null,
    loading: false,
    error: null,
  });
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

  it("keeps a legacy world usable when the optional scene request fails", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { display_name: "Telco" },
        world: "telco",
        ui: { lenses: ["telco-network"], world_scene: false },
      },
    });
    mockScene.mockReturnValue({
      scene: null,
      loading: false,
      error: "world scene HTTP 500",
    });

    render(<World />);

    expect(screen.getByTestId("telco-world-route")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
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

  it("uses a pack-owned spatial scene without exposing a run-process path", async () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { name: "fashion", display_name: "Fashion Retail" },
        world: "fashion",
        ui: {
          lenses: ["process-library", "order", "customer-impact", "control"],
          world_scene: true,
        },
      },
    });
    mockScene.mockReturnValue({
      scene: {
        enabled: true,
        schema_version: 1,
        title: "Fashion Retail Live Operations",
        locations: [],
        layers: [],
        event_mappings: [],
      },
      loading: false,
      error: null,
    });
    mockWorld.mockReturnValue({
      state: {
        enabled: true,
        scenario: "fashion",
        seed: 42,
        status: "running",
        sim_time: 12,
        objectives: [],
      },
      events: [],
      loading: false,
      error: null,
      injectSurge: vi.fn(),
      injectSiteFailure: vi.fn(),
      runScenario: vi.fn(),
    });

    render(<World />);

    expect(screen.getByTestId("spatial-world-route")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /run process/i })).toBeNull();
  });

  it("fails closed when a required spatial scene is unavailable", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        vertical: { name: "scene-demo", display_name: "Scene demo" },
        world: "scene-demo",
        ui: { lenses: [], world_scene: true },
      },
    });
    mockScene.mockReturnValue({
      scene: null,
      loading: false,
      error: "world scene HTTP 500",
    });

    render(<World />);

    expect(screen.getByRole("alert").textContent).toContain(
      "world scene HTTP 500",
    );
    expect(screen.queryByTestId("world-route")).toBeNull();
  });
});
