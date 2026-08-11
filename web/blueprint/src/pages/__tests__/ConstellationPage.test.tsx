// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

// Module mocks — must be hoisted before imports of the components under test.
vi.mock("../../components/cosmicLens/CosmicLens", () => ({
  CosmicLens: ({ embed }: { embed?: boolean }) => (
    <div data-testid="cosmic-lens" data-embed={String(embed)} />
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
  Narrator: () => <div data-testid="narrator" />,
  triggerNarrator: vi.fn(),
}));
vi.mock("../../components/cosmicLens/HUD/StoryGuide", () => ({
  StoryGuide: ({ isReplay, recordedAt }: { isReplay: boolean; recordedAt?: string }) => (
    <div data-testid="story-guide" data-replay={String(isReplay)} data-recorded-at={recordedAt ?? ""} />
  ),
}));

let mockIsReplay = false;
let mockRecordedAt: string | undefined;
vi.mock("../../lib/useReplayMode", () => ({
  useReplayMode: () => ({ isReplay: mockIsReplay, recordedAt: mockRecordedAt }),
}));

import { ConstellationPage } from "../ConstellationPage";

describe("ConstellationPage", () => {
  beforeEach(() => {
    mockIsReplay = false;
    mockRecordedAt = undefined;
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
    mockIsReplay = true;
    mockRecordedAt = "2026-07-01T00:00:00Z";
    render(<ConstellationPage />);
    await waitFor(() => {
      const sg = screen.getByTestId("story-guide");
      expect(sg.getAttribute("data-replay")).toBe("true");
      expect(sg.getAttribute("data-recorded-at")).toBe("2026-07-01T00:00:00Z");
      const dt = screen.getByTestId("decision-ticker");
      expect(dt.getAttribute("data-replay")).toBe("true");
    });
  });

  it("renders PolicyRipple and Narrator", () => {
    render(<ConstellationPage />);
    expect(screen.getByTestId("policy-ripple")).toBeTruthy();
    expect(screen.getByTestId("narrator")).toBeTruthy();
  });
});
