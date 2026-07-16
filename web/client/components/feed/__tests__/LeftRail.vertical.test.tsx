// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LeftRail from "@client/components/feed/LeftRail";
import { getRolePreset } from "@shared/roles";

const { mockRuntime } = vi.hoisted(() => ({
  mockRuntime: vi.fn(),
}));

vi.mock("@client/hooks/useRuntimeManifest", () => ({
  useRuntimeManifest: mockRuntime,
}));

const base = {
  world_scale: null,
};

function renderRail() {
  return render(
    <MemoryRouter>
      <LeftRail
        role={getRolePreset("ops-reviewer")}
        userViews={[]}
        onSelectView={() => {}}
        onSaveCurrent={() => {}}
      />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LeftRail vertical capabilities", () => {
  it("shows Telco routes and hides Agency-only Compose", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        ...base,
        vertical: {
          name: "telco",
          display_name: "Telco",
          manifest_version: "1",
          fingerprint: "telco:1",
        },
        world: "telco",
        capabilities: ["blueprint", "world", "memory", "knowledge"],
        ui: { lenses: ["telco-network"], theme: {} },
      },
    });

    renderRail();

    expect(screen.getByText(/Saved views · Telco/)).toBeTruthy();
    expect(screen.getByText("World")).toBeTruthy();
    expect(screen.getByText("Memory")).toBeTruthy();
    expect(screen.getByText("Knowledge")).toBeTruthy();
    expect(screen.getByText(/Constellation/)).toBeTruthy();
    expect(screen.queryByText("Compose")).toBeNull();
  });

  it("shows Agency Compose and hides World when no world is active", () => {
    mockRuntime.mockReturnValue({
      loading: false,
      error: null,
      manifest: {
        ...base,
        vertical: {
          name: "agency",
          display_name: "Agency",
          manifest_version: "1",
          fingerprint: "agency:1",
        },
        world: null,
        capabilities: ["blueprint", "compose", "memory", "knowledge"],
        ui: { lenses: ["agency-operations"], theme: {} },
      },
    });

    renderRail();

    expect(screen.getByText(/Saved views · Agency/)).toBeTruthy();
    expect(screen.getByText("Compose")).toBeTruthy();
    expect(screen.queryByText("World")).toBeNull();
  });
});
