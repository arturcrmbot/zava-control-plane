// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

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
});
