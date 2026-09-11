// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VitalSignsBar } from "../VitalSignsBar";
import type { ReplayModeInfo } from "../../../../lib/useReplayMode";

afterEach(cleanup);

const props = {
  inFlight: [],
  personas: [],
  status: "watching",
  mode: "capabilities" as const,
  setMode: vi.fn(),
  onBurst: vi.fn(),
  recentEvents: 0,
};

describe("VitalSignsBar source mode", () => {
  it.each<ReplayModeInfo>([
    { mode: "loading" },
    { mode: "unavailable", error: "Offline" },
    { mode: "replay", recordedAt: "2026-05-22T19:26:10Z" },
  ])("does not expose live actions for $mode", (source) => {
    render(<VitalSignsBar {...props} source={source} />);
    expect(screen.queryByRole("button", { name: /spawn/i })).toBeNull();
    expect(screen.queryByText("Live")).toBeNull();
  });

  it("exposes live actions only after live mode is confirmed", () => {
    render(<VitalSignsBar {...props} source={{ mode: "live" }} />);
    expect(screen.getByRole("button", { name: /spawn/i })).toBeTruthy();
    expect(screen.getByText("Live")).toBeTruthy();
  });
});
