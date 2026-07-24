// @vitest-environment jsdom
// web/client/components/feed/__tests__/DrawerAudit.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DrawerAudit from "@client/components/feed/DrawerAudit";
import type { DrawerData } from "@client/components/feed/Drawer";

afterEach(cleanup);

const d: DrawerData = {
  workflow: {
    id: "WF-1", type: "expense-claim", status: "in_progress",
    currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
  },
  phases: [], spans: [], amplifications: [],
  activeException: null, mcpCalls: [],
  economics: {
    modelCostUsd: 0, inputTokens: 0, outputTokens: 0, pricingSource: "test",
    perModel: [], computeCostUsd: 0, modelCalls: 0, toolCalls: 0,
    daysElapsed: 0, slaToken: "green",
  },
  narrative: null,
  timeline: [],
};

describe("DrawerAudit", () => {
  it("renders the section heading", () => {
    render(<MemoryRouter><DrawerAudit data={d} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Audit/i })).toBeTruthy();
  });
  it("renders the three collapsed accordions by name", () => {
    render(<MemoryRouter><DrawerAudit data={d} /></MemoryRouter>);
    expect(screen.getByText(/Evidence/i)).toBeTruthy();
    expect(screen.getByText(/Audit trail/i)).toBeTruthy();
    expect(screen.getByText(/Fleet assignment/i)).toBeTruthy();
    // Economics + Skill amplification were removed — Economics lives on
    // /economics and Skill amplification is an advanced surface.
    expect(screen.queryByText(/Economics/i)).toBeNull();
    expect(screen.queryByText(/Skill amplification/i)).toBeNull();
  });
});
