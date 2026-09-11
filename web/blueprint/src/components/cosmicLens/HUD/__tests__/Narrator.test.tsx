// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { JourneyDetails } from "../guidedJourney";

vi.mock("../guidedJourney", () => ({
  readJourneyDetails: vi.fn(),
  resolveJourneyDecision: vi.fn(),
}));

import { Narrator } from "../Narrator";
import { readJourneyDetails, resolveJourneyDecision } from "../guidedJourney";

const detail: JourneyDetails = {
  workflowId: "AUR-real",
  workflowType: "aurora-budget-response",
  status: "awaiting_hitl",
  currentPhase: "Executive approval",
  phases: [
    { name: "Observe budget signal", status: "completed" },
    { name: "Executive approval", status: "in_progress" },
  ],
  activeExceptionId: "exception-real",
  recommendation: "Budget commitments need review.",
  children: [],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(readJourneyDetails).mockResolvedValue(detail);
});
afterEach(cleanup);

describe("Narrator execution evidence", () => {
  it("renders observed phases and IDs instead of canned captions", async () => {
    render(<Narrator journey={{ workflowId: "AUR-real", source: "replay" }} onClose={vi.fn()} />);
    expect(await screen.findByText("Observe budget signal")).toBeTruthy();
    expect(screen.getByTestId("journey-root-id").textContent).toBe("AUR-real");
    expect(screen.getByTestId("journey-source-mode").textContent).toBe("Recorded execution");
    expect(screen.queryByText(/123 %/)).toBeNull();
    expect(screen.getByTestId("journey-evidence-link").getAttribute("href")).toBe("/api/workflows/AUR-real");
  });

  it("does not offer recorded approvals as live actions", async () => {
    render(<Narrator journey={{ workflowId: "AUR-real", source: "replay" }} onClose={vi.fn()} />);
    await screen.findByText("Executive approval");
    expect(screen.queryByRole("button", { name: /^Approve/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Reject/ })).toBeNull();
  });

  it("follows recorded state as the tape advances without enabling actions", async () => {
    vi.mocked(readJourneyDetails)
      .mockResolvedValueOnce(detail)
      .mockResolvedValue({ ...detail, status: "completed", activeExceptionId: undefined });
    render(<Narrator journey={{ workflowId: "AUR-real", source: "replay" }} onClose={vi.fn()} />);
    await screen.findByText("Executive approval");
    await waitFor(() => {
      expect(screen.getByTestId("journey-status").getAttribute("data-status")).toBe("completed");
    }, { timeout: 1800 });
    expect(screen.queryByRole("button", { name: /^Approve/ })).toBeNull();
  });

  it("does not invent evidence for a missing workflow", async () => {
    vi.mocked(readJourneyDetails).mockResolvedValue(null);
    render(<Narrator journey={{ workflowId: "AUR-real", source: "replay" }} onClose={vi.fn()} />);
    expect(await screen.findByText(/No workflow evidence is available/i)).toBeTruthy();
    expect(screen.queryByText("Executive approval")).toBeNull();
  });

  it("submits an operator decision but waits for actual workflow progression", async () => {
    vi.mocked(resolveJourneyDecision).mockResolvedValue();
    render(<Narrator journey={{ workflowId: "AUR-real", source: "live" }} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve recommendation" }));
    await waitFor(() => expect(resolveJourneyDecision).toHaveBeenCalledWith("exception-real", "approve"));
    await waitFor(() => expect(screen.getByTestId("journey-status").getAttribute("data-status")).toBe("awaiting_hitl"));
    expect(screen.queryByText("Policy applied")).toBeNull();
  });

  it("shows rejected decisions without advancing the story", async () => {
    vi.mocked(resolveJourneyDecision).mockRejectedValue(new Error("CFO role required"));
    render(<Narrator journey={{ workflowId: "AUR-real", source: "live" }} onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve recommendation" }));
    expect((await screen.findByRole("alert")).textContent).toContain("CFO role required");
    expect(screen.getByTestId("journey-status").getAttribute("data-status")).toBe("awaiting_hitl");
  });
});
