// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReplayModeInfo } from "../../lib/useReplayMode";
import type { GuidedJourney } from "../../components/cosmicLens/HUD/guidedJourney";

// Module mocks — must be hoisted before imports of the components under test.
vi.mock("../../components/cosmicLens/CosmicLens", () => ({
  CosmicLens: ({ embed, source, workflowToOpen }: { embed?: boolean; source: ReplayModeInfo; workflowToOpen?: string }) => (
    <div data-testid="cosmic-lens" data-embed={String(embed)} data-source={source.mode} data-workflow-request={workflowToOpen ?? ""} />
  ),
}));
vi.mock("../../components/cosmicLens/HUD/DemoHUD", () => ({
  DemoHUD: ({ enabled, onFollow }: { enabled: boolean; onFollow: (journey: GuidedJourney) => void }) => (
    <div data-testid="demo-hud" data-enabled={String(enabled)}>
      <button onClick={() => onFollow({ workflowId: "AUR-real", source: "live" })}>Follow fixture</button>
    </div>
  ),
}));
vi.mock("../../components/cosmicLens/HUD/DecisionTicker", () => ({
  DecisionTicker: ({ enabled, isReplay }: { enabled: boolean; isReplay?: boolean }) => (
    <div data-testid="decision-ticker" data-enabled={String(enabled)} data-replay={String(isReplay)} />
  ),
}));
vi.mock("../../components/cosmicLens/HUD/PolicyRipple", () => ({
  PolicyRipple: ({ enabled }: { enabled: boolean }) => (
    <div data-testid="policy-ripple" data-enabled={String(enabled)} />
  ),
}));
vi.mock("../../components/cosmicLens/HUD/Narrator", () => ({
  Narrator: ({ journey, onInspect }: { journey: GuidedJourney; onInspect: (id: string) => void }) => (
    <div data-testid="narrator" data-workflow={journey.workflowId}>
      <button onClick={() => onInspect(journey.workflowId)}>Inspect fixture</button>
    </div>
  ),
}));

let mockSource: ReplayModeInfo = { mode: "live" };
vi.mock("../../lib/useReplayMode", () => ({
  useReplayMode: () => ({ source: mockSource, retry: vi.fn() }),
}));

import { ConstellationPage } from "../ConstellationPage";

describe("ConstellationPage", () => {
  beforeEach(() => {
    mockSource = { mode: "live" };
    // Set up window.location.search for the page
    Object.defineProperty(window, "location", {
      writable: true,
      value: { search: "", protocol: "http:", hostname: "localhost", port: "" },
    });
    (global as any).EventSource = class {
      close() {}
      onmessage: any = null;
      onerror: any = null;
      constructor(_: string) {}
    };
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders CosmicLens", () => {
    render(<ConstellationPage />);
    expect(screen.getByTestId("cosmic-lens")).toBeTruthy();
  });

  it("does not mount the orientation overlay over the scene", () => {
    render(<ConstellationPage />);
    expect(screen.queryByTestId("story-guide")).toBeNull();
  });

  it("passes isReplay=true to DecisionTicker when replay", async () => {
    mockSource = { mode: "replay", recordedAt: "2026-07-01T00:00:00Z" };
    render(<ConstellationPage />);
    await waitFor(() => {
      const dt = screen.getByTestId("decision-ticker");
      expect(dt.getAttribute("data-replay")).toBe("true");
    });
  });

  it("opens the evidence panel only for an actual selected workflow", () => {
    render(<ConstellationPage />);
    expect(screen.getByTestId("policy-ripple")).toBeTruthy();
    expect(screen.queryByTestId("narrator")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Follow fixture" }));
    expect(screen.getByTestId("narrator").getAttribute("data-workflow")).toBe("AUR-real");
  });

  it("clears the guide when opening the existing workflow inspector", () => {
    render(<ConstellationPage />);
    fireEvent.click(screen.getByRole("button", { name: "Follow fixture" }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect fixture" }));
    expect(screen.queryByTestId("narrator")).toBeNull();
    expect(screen.getByTestId("cosmic-lens").getAttribute("data-workflow-request")).toBe("AUR-real");
  });

  it.each<ReplayModeInfo>([
    { mode: "loading" },
    { mode: "unavailable", error: "Offline" },
  ])("shares $mode without showing a live decision ticker", (source) => {
    mockSource = source;
    render(<ConstellationPage />);
    expect(screen.getByTestId("cosmic-lens").getAttribute("data-source")).toBe(source.mode);
    expect(screen.getByTestId("decision-ticker").getAttribute("data-enabled")).toBe("false");
    expect(screen.getByTestId("demo-hud").getAttribute("data-enabled")).toBe("false");
  });
});
