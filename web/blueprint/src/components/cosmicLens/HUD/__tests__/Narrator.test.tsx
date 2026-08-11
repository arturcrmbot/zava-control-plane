// @vitest-environment jsdom
import { afterEach, describe, it, expect } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { Narrator, triggerNarrator, type ArcResult } from "../Narrator";

const SAMPLE_ARC: ArcResult = {
  phases: [
    { phase: "overrun", elapsed_ms: 1, summary: { brand: "BRAND-aurora" } },
    {
      phase: "cfo_observe",
      elapsed_ms: 7,
      headline: "Aurora at 123% of FY budget — recommend freeze",
    },
    { phase: "approve", elapsed_ms: 5, policy_workflow_id: "WF-123" },
    {
      phase: "cfo_observe_post",
      elapsed_ms: 8,
      headline: "Aurora dropped from proposals",
      freezes_remaining: 2,
    },
    {
      phase: "spawn_invoices",
      elapsed_ms: 26,
      cascades: [{ id: 1 }, { id: 2 }, { id: 3 }],
    },
    {
      phase: "ceo_synthesise",
      elapsed_ms: 2,
      headline: "Org-wide spend posture: 1 freeze active across 3 brands",
    },
  ],
  total_elapsed_ms: 51,
  narrative: "Aurora overrun → CFO observed → freeze approved → cascade",
};

describe("Narrator", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders nothing by default", () => {
    const { container } = render(<Narrator />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the first bubble after triggerNarrator is called", async () => {
    render(<Narrator />);
    act(() => {
      triggerNarrator(SAMPLE_ARC);
    });
    await waitFor(() => {
      expect(screen.getByText(/A budget overrun arrived on Aurora\./i)).toBeTruthy();
    });
    expect(screen.getByText(/1 \/ 6/i)).toBeTruthy();
  });

  it("renders the cfo_observe phase with its headline as secondary text", async () => {
    render(<Narrator />);
    act(() => {
      triggerNarrator({
        ...SAMPLE_ARC,
        phases: [SAMPLE_ARC.phases[1]], // start directly with cfo_observe
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/CFO agent observes within delegated authority\./i)).toBeTruthy();
    });
    expect(
      screen.getByText(/Aurora at 123% of FY budget — recommend freeze/i),
    ).toBeTruthy();
    expect(screen.getByText(/1 \/ 1/i)).toBeTruthy();
  });
});
