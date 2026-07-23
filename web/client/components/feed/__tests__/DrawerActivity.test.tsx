// @vitest-environment jsdom
// web/client/components/feed/__tests__/DrawerActivity.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DrawerActivity from "@client/components/feed/DrawerActivity";
import type { DrawerData } from "@client/components/feed/Drawer";

afterEach(cleanup);

const d: DrawerData = {
  workflow: {
    id: "WF-1", type: "expense-claim", status: "in_progress",
    currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [
      { workflowId: "WF-1", timestamp: 100, actorKind: "human", actorId: "u", action: "approve", revocable: true, details: {} },
    ],
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
};

describe("DrawerActivity", () => {
  it("renders the Activity heading and the 3-view toggle", () => {
    render(<MemoryRouter><DrawerActivity data={d} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Activity/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Timeline$/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Spans$/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Ledger$/i })).toBeTruthy();
  });
  it("switches view when a toggle is clicked", () => {
    render(<MemoryRouter><DrawerActivity data={d} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /^Spans$/i }));
    expect(screen.getByRole("button", { name: /^Spans$/i }).className).toMatch(/bg-blue-600/);
  });
});
