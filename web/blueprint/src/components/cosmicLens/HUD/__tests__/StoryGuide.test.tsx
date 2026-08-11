// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// Mock modules before importing component
vi.mock("../guidedJourney", () => ({
  loadGuidedJourney: vi.fn(),
}));
vi.mock("../Narrator", () => ({
  triggerNarrator: vi.fn(),
}));

import { StoryGuide } from "../StoryGuide";
import { loadGuidedJourney } from "../guidedJourney";
import { triggerNarrator } from "../Narrator";

const SAMPLE_ARC = {
  phases: [{ phase: "overrun", elapsed_ms: 1 }],
  total_elapsed_ms: 1,
  narrative: "test",
};

describe("StoryGuide", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders orientation substance", () => {
    render(<StoryGuide isReplay={false} />);
    expect(
      screen.getByText(/You are watching a working agentic organisation\./i),
    ).toBeTruthy();
    expect(screen.getByText(/agents, people, durable workflows, policy/i)).toBeTruthy();
    expect(screen.getByText(/one shared control plane/i)).toBeTruthy();
  });

  it("shows 'Recorded telemetry' label with date when isReplay and recordedAt provided", () => {
    render(<StoryGuide isReplay={true} recordedAt="2026-07-01T00:00:00Z" />);
    const status = screen.getByTestId("story-guide-status");
    expect(status.textContent).toMatch(/Recorded telemetry/i);
    expect(status.textContent).toMatch(/2026|Jul/i);
  });

  it("shows 'Recorded telemetry' without date when isReplay but no recordedAt", () => {
    render(<StoryGuide isReplay={true} />);
    const status = screen.getByTestId("story-guide-status");
    expect(status.textContent).toBe("Recorded telemetry");
  });

  it("shows 'Live runtime' label when not replay", () => {
    render(<StoryGuide isReplay={false} />);
    const status = screen.getByTestId("story-guide-status");
    expect(status.textContent).toBe("Live runtime");
  });

  it("renders 'Follow one decision' button", () => {
    render(<StoryGuide isReplay={false} />);
    expect(screen.getByTestId("story-guide-journey-btn")).toBeTruthy();
    expect(screen.getByText(/Follow one decision/i)).toBeTruthy();
  });

  it("starts guided journey and triggers narrator on success", async () => {
    vi.mocked(loadGuidedJourney).mockResolvedValueOnce(SAMPLE_ARC as any);
    render(<StoryGuide isReplay={false} />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("story-guide-journey-btn"));
    });

    await waitFor(() => {
      expect(loadGuidedJourney).toHaveBeenCalledWith(false);
      expect(triggerNarrator).toHaveBeenCalledWith(SAMPLE_ARC);
    });
  });

  it("passes isReplay=true to loadGuidedJourney when replay", async () => {
    vi.mocked(loadGuidedJourney).mockResolvedValueOnce(SAMPLE_ARC as any);
    render(<StoryGuide isReplay={true} />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("story-guide-journey-btn"));
    });

    await waitFor(() => {
      expect(loadGuidedJourney).toHaveBeenCalledWith(true);
    });
  });

  it("surfaces error in role=alert when journey fails", async () => {
    vi.mocked(loadGuidedJourney).mockRejectedValueOnce(
      new Error("Could not start the Aurora journey (503)"),
    );
    render(<StoryGuide isReplay={false} />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("story-guide-journey-btn"));
    });

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toBeTruthy();
      expect(alert.textContent).toMatch(/Could not start the Aurora journey/i);
    });
  });

  it("disables button while busy", async () => {
    let resolve!: (v: any) => void;
    vi.mocked(loadGuidedJourney).mockReturnValueOnce(
      new Promise((r) => { resolve = r; }),
    );
    render(<StoryGuide isReplay={false} />);

    act(() => {
      fireEvent.click(screen.getByTestId("story-guide-journey-btn"));
    });

    // While pending the button must be disabled
    await waitFor(() => {
      const btn = screen.getByTestId("story-guide-journey-btn") as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
    });

    // Resolve and clean up
    await act(async () => {
      resolve(SAMPLE_ARC);
    });
  });

  it("contains details section with three connection boundaries", () => {
    render(<StoryGuide isReplay={false} />);
    // Click to open boundaries
    fireEvent.click(screen.getByText(/Where your systems connect/i));
    const details = screen.getByTestId("story-guide-boundaries");
    expect(details).toBeTruthy();
    expect(screen.getAllByText(/Real/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Synthetic/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Connect/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Durable workflows, agent sessions, governance, audit/i)).toBeTruthy();
    expect(screen.getByText(/Organisational records, personae and external systems/i)).toBeTruthy();
    expect(screen.getByText(/Your existing systems, skills and MCPs/i)).toBeTruthy();
  });
});
