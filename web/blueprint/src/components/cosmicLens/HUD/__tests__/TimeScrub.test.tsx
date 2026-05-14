// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TimeScrub } from "../TimeScrub";

const SNAPSHOT = {
  at: 1_700_000_000,
  entities: [{ id: "vendor:acme", kind: "vendor", workflow_id: "wf1" }],
  in_flight_workflows: [],
  recent_events: [],
  kpis_at: [{ label: "entities", value: 1, unit: "" }],
};

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchSpy = vi.fn(async () => new Response(JSON.stringify(SNAPSHOT), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TimeScrub", () => {
  it("renders in LIVE mode by default and does not fetch", () => {
    render(<TimeScrub />);
    expect(screen.getByTestId("time-scrub")).toBeTruthy();
    expect(screen.getByTestId("time-scrub-at").textContent).toBe("now");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("dragging the slider updates the displayed offset", () => {
    render(<TimeScrub />);
    const slider = screen.getByTestId("time-scrub-slider") as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "120" } });
    expect(slider.value).toBe("120");
    expect(screen.getByTestId("time-scrub-at").textContent).toContain("ago");
  });

  it("fetches /api/replay/snapshot when scrubAt < now-5s", async () => {
    const onSnapshot = vi.fn();
    render(<TimeScrub onSnapshot={onSnapshot} />);
    const slider = screen.getByTestId("time-scrub-slider") as HTMLInputElement;
    // Drag back 60s — well past the 5s replay threshold.
    fireEvent.change(slider, { target: { value: "60" } });
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled();
    });
    const url = String(fetchSpy.mock.calls[0][0]);
    expect(url).toMatch(/^\/api\/replay\/snapshot\?at=\d+/);
    await waitFor(() => {
      expect(onSnapshot).toHaveBeenCalledWith(SNAPSHOT);
    });
  });

  it("Exit replay button returns to LIVE and clears snapshot", async () => {
    const onSnapshot = vi.fn();
    render(<TimeScrub onSnapshot={onSnapshot} />);
    const slider = screen.getByTestId("time-scrub-slider") as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "60" } });
    await waitFor(() => expect(screen.getByTestId("time-scrub-exit")).toBeTruthy());
    fireEvent.click(screen.getByTestId("time-scrub-exit"));
    expect(screen.getByTestId("time-scrub-at").textContent).toBe("now");
    // Last call to onSnapshot should be null (live mode).
    expect(onSnapshot).toHaveBeenLastCalledWith(null);
  });
});
