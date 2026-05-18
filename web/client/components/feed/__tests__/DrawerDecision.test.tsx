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
  it("renders the 4 action buttons", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("ops-reviewer")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByRole("button", { name: /Approve/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Request docs/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Escalate/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeTruthy();
  });
  it("hides actions for executive role", () => {
    render(<MemoryRouter><ResolutionProvider><DrawerDecision data={d} role={getRolePreset("executive")} onRefresh={() => {}} /></ResolutionProvider></MemoryRouter>);
    expect(screen.queryByRole("button", { name: /Approve/i })).toBeNull();
  });
});
