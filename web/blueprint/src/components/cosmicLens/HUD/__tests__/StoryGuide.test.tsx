// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// Mock modules before importing component
vi.mock("../guidedJourney", () => ({
  loadGuidedJourney: vi.fn(),
}));
import { StoryGuide } from "../StoryGuide";
import { loadGuidedJourney, type GuidedJourney } from "../guidedJourney";

const SAMPLE_JOURNEY: GuidedJourney = { workflowId: "AUR-real", source: "live" };
const onFollow = vi.fn();

describe("StoryGuide", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });
  afterEach(() => {
    cleanup();
  });

  it("does not start work while source mode is unknown", () => {
    render(<StoryGuide source={{ mode: "loading" }} onFollow={onFollow} />);
    const button = screen.getByTestId("story-guide-journey-btn");
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(screen.getByTestId("story-guide-status").textContent).toMatch(/checking/i);
    fireEvent.click(button);
    expect(loadGuidedJourney).not.toHaveBeenCalled();
  });

  it("shows source failure and offers a retry without claiming live", () => {
    const retry = vi.fn();
    render(<StoryGuide source={{ mode: "unavailable", error: "Offline" }} onRetry={retry} onFollow={onFollow} />);
    expect(screen.getByRole("alert").textContent).toContain("Offline");
    expect(screen.getByTestId("story-guide-journey-btn").hasAttribute("disabled")).toBe(true);
    expect(screen.queryByText("Live runtime")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("renders orientation substance", () => {
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);
    expect(
      screen.getByText(/You are watching a working agentic organisation\./i),
    ).toBeTruthy();
    expect(screen.getByText(/agents, people, durable workflows, policy/i)).toBeTruthy();
    expect(screen.getByText(/one shared control plane/i)).toBeTruthy();
  });

  it("shows 'Recorded telemetry' label with date when isReplay and recordedAt provided", () => {
    render(<StoryGuide source={{ mode: "replay", recordedAt: "2026-07-01T00:00:00Z" }} onFollow={onFollow} />);
    const status = screen.getByTestId("story-guide-status");
    expect(status.textContent).toMatch(/Recorded telemetry/i);
    expect(status.textContent).toMatch(/2026|Jul/i);
  });

  it("shows 'Recorded telemetry' without date when isReplay but no recordedAt", () => {
    render(<StoryGuide source={{ mode: "replay" }} onFollow={onFollow} />);
    const status = screen.getByTestId("story-guide-status");
    expect(status.textContent).toBe("Recorded telemetry");
  });

  it("shows 'Live runtime' label when not replay", () => {
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);
    const status = screen.getByTestId("story-guide-status");
    expect(status.textContent).toBe("Live runtime");
  });

  it("renders 'Follow one decision' button", () => {
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);
    expect(screen.getByTestId("story-guide-journey-btn")).toBeTruthy();
    expect(screen.getByText(/Follow one decision/i)).toBeTruthy();
  });

  it("opens actual workflow evidence on success", async () => {
    vi.mocked(loadGuidedJourney).mockResolvedValueOnce(SAMPLE_JOURNEY);
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("story-guide-journey-btn"));
    });

    await waitFor(() => {
      expect(loadGuidedJourney).toHaveBeenCalledWith(false, expect.any(String));
      expect(onFollow).toHaveBeenCalledWith(SAMPLE_JOURNEY);
    });
  });

  it("passes isReplay=true to loadGuidedJourney when replay", async () => {
    vi.mocked(loadGuidedJourney).mockResolvedValueOnce({ ...SAMPLE_JOURNEY, source: "replay" });
    render(<StoryGuide source={{ mode: "replay" }} onFollow={onFollow} />);

    await act(async () => {
      fireEvent.click(screen.getByTestId("story-guide-journey-btn"));
    });

    await waitFor(() => {
      expect(loadGuidedJourney).toHaveBeenCalledWith(true, undefined);
    });
  });

  it("surfaces error in role=alert when journey fails", async () => {
    vi.mocked(loadGuidedJourney).mockRejectedValueOnce(
      new Error("Could not start the Aurora journey (503)"),
    );
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);

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
    let resolve!: (v: GuidedJourney) => void;
    vi.mocked(loadGuidedJourney).mockReturnValueOnce(
      new Promise((r) => { resolve = r; }),
    );
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);

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
      resolve(SAMPLE_JOURNEY);
    });
  });

  it("contains details section with three connection boundaries", () => {
    render(<StoryGuide source={{ mode: "live" }} onFollow={onFollow} />);
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
