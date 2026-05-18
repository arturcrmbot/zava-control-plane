// @vitest-environment jsdom
// web/client/components/feed/__tests__/integration.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FleetControlShell from "@client/components/feed/FleetControlShell";

beforeEach(() => {
  (globalThis as any).EventSource = class { onmessage = null; addEventListener() {} close() {} };
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.startsWith("/api/workflows/")) {
      return Promise.resolve({ ok: true, json: async () => ({
        workflow: { id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
          currentPhase: "Intake", createdAt: 1, slaDueAt: 9999, jurisdiction: "UK",
          agency: "Z", actionLedger: [], tokensSpent: 0, costUSD: 0 },
        phases: [], spans: [], amplifications: [], activeException: null,
        mcpCalls: [], economics: { activeWorkflowCount: 0, totalWorkflowCount: 0, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
        narrative: null,
      }) } as Response);
    }
    if (url.startsWith("/api/workflows")) {
      return Promise.resolve({ ok: true, json: async () => [
        { id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
          currentPhase: "Intake", createdAt: 100, slaDueAt: 9999,
          jurisdiction: "UK", agency: "Z", actionLedger: [],
          tokensSpent: 0, costUSD: 0 },
      ] } as Response);
    }
    return Promise.resolve({ ok: true, json: async () => [] } as Response);
  });
  localStorage.clear();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

describe("FleetControlShell — integration", () => {
  it("lands on feed showing the HITL card and the header", async () => {
    render(<MemoryRouter initialEntries={["/"]}><FleetControlShell /></MemoryRouter>);
    await waitFor(() => expect(screen.getAllByText("WF-1").length).toBeGreaterThan(0));
    expect(screen.getByText(/Apex/)).toBeTruthy();
  });

  it("deep-link /workflows/:id opens the drawer over the feed on cold land", async () => {
    render(<MemoryRouter initialEntries={["/workflows/WF-1"]}><FleetControlShell /></MemoryRouter>);
    await waitFor(() => expect(screen.getByLabelText(/Workflow detail drawer/i)).toBeTruthy());
  });

  it("switching role via header re-mounts the feed with new defaults", async () => {
    render(<MemoryRouter initialEntries={["/"]}><FleetControlShell /></MemoryRouter>);
    await waitFor(() => screen.getByText(/Ops Reviewer/));
    fireEvent.click(screen.getByRole("button", { name: /Ops Reviewer/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Executive/i }));
    await waitFor(() => expect(screen.getByText(/Executive/)).toBeTruthy());
    expect(localStorage.getItem("fleetctl.role")).toBe(JSON.stringify("executive"));
    expect(
      screen.getByRole("button", { name: /All activity/i }).className,
    ).toMatch(/bg-blue-600/);
  });
});
