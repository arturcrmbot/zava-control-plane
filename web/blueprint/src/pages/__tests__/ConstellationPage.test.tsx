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
  DemoHUD: ({ enabled }: { enabled: boolean }) => (
    <div data-testid="demo-hud" data-enabled={String(enabled)} />
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
vi.mock("../../components/cosmicLens/HUD/StoryGuide", () => ({
  StoryGuide: ({ source, onFollow }: { source: ReplayModeInfo; onFollow: (journey: GuidedJourney) => void }) => (
    <div
      data-testid="story-guide"
      data-source={source.mode}
      data-replay={String(source.mode === "replay")}
      data-recorded-at={source.mode === "replay" ? source.recordedAt ?? "" : ""}
    >
      <button onClick={() => onFollow({ workflowId: "AUR-real", source: "live" })}>Follow fixture</button>
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

  it("renders StoryGuide with isReplay=false in live mode", () => {
    render(<ConstellationPage />);
    const sg = screen.getByTestId("story-guide");
    expect(sg.getAttribute("data-replay")).toBe("false");
  });

  it("passes isReplay=true to StoryGuide and DecisionTicker when replay", async () => {
    mockSource = { mode: "replay", recordedAt: "2026-07-01T00:00:00Z" };
    render(<ConstellationPage />);
    await waitFor(() => {
      const sg = screen.getByTestId("story-guide");
      expect(sg.getAttribute("data-replay")).toBe("true");
      expect(sg.getAttribute("data-recorded-at")).toBe("2026-07-01T00:00:00Z");
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
    expect(screen.getByTestId("story-guide").getAttribute("data-source")).toBe(source.mode);
    expect(screen.getByTestId("decision-ticker").getAttribute("data-enabled")).toBe("false");
    expect(screen.getByTestId("demo-hud").getAttribute("data-enabled")).toBe("false");
  });
});
