// @vitest-environment jsdom
// web/client/components/feed/__tests__/DrawerDecision.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import DrawerDecision from "@client/components/feed/DrawerDecision";
import { getRolePreset } from "@shared/roles";
import type { DrawerData } from "@client/components/feed/Drawer";

afterEach(cleanup);

const d: DrawerData = {
  workflow: {
    id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
    currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
    claim: {
      claimId: "CL-1", employeeId: "E-1",
      submittedAt: "2026-05-18T10:00:00Z",
      market: "UK", currency: "GBP", category: "meals",
      vendor: "Pret", amount: 42, attendees: 1, emsSource: "concur",
    },
  },
  phases: [], spans: [], amplifications: [],
  activeException: null, mcpCalls: [],
  economics: { activeWorkflowCount: 1, totalWorkflowCount: 1, autoApprovedCount: 0, escalationCount: 0, averageCostPerWorkflow: 0 },
  narrative: null,
};

describe("DrawerDecision", () => {
  it("renders the section heading", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Decision/i })).toBeTruthy();
  });
  it("renders the receipt panel for expense claims", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByText(/CL-1/)).toBeTruthy();
  });
  it("renders primary actions inline and overflow actions in a kebab menu", async () => {
    const { waitFor, fireEvent } = await import("@testing-library/react");
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    // Primary inline buttons.
    expect(screen.getByRole("button", { name: /^Approve$/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Reject$/ })).toBeTruthy();
    // Overflow actions are hidden until the kebab is opened.
    expect(screen.queryByRole("menuitem", { name: /Request docs/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /More actions/i }));
    await waitFor(() => {
      expect(screen.getByRole("menuitem", { name: /Request docs/i })).toBeTruthy();
    });
    expect(screen.getByRole("menuitem", { name: /Escalate/i })).toBeTruthy();
  });
  it("hides actions for executive role", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("executive")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.queryByRole("button", { name: /Approve/i })).toBeNull();
  });
});
