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
  timeline: [],
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
  it("passes workflow timeline evidence into the default view", () => {
    render(
      <MemoryRouter>
        <DrawerActivity
          data={{
            ...d,
            timeline: [{
              id: "workflow:WF-1",
              ts: 1,
              kind: "workflow",
              label: "workflow.started",
              status: "in_progress",
            }],
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Workflow started")).toBeTruthy();
  });

  it("passes canonical MCP evidence to timeline tool expansion", () => {
    render(
      <MemoryRouter>
        <DrawerActivity
          data={{
            ...d,
            mcpCalls: [{
              workflowId: "WF-1",
              timestamp: 2,
              tool: "screenVendor",
              url: "https://mcp.example.test/screen",
              method: "POST",
              request: { vendorId: "V-1" },
              response: { clear: true },
              statusCode: 200,
              durationMs: 25,
            }],
            timeline: [{
              id: "mcp:0:screenVendor:2",
              ts: 2,
              kind: "tool",
              label: "screenVendor",
              status: "ok",
              mcpCallIndex: 0,
              tool: "screenVendor",
              method: "POST",
              url: "https://mcp.example.test/screen",
              statusCode: 200,
              durationMs: 25,
            }],
          }}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("execution-timeline-row-mcp:0:screenVendor:2"));

    const details = screen.getByTestId("execution-timeline-details-mcp:0:screenVendor:2");
    expect(details.textContent).toContain('"vendorId": "V-1"');
    expect(details.textContent).toContain('"clear": true');
  });

  it("treats malformed timeline data as empty instead of crashing", () => {
    render(
      <MemoryRouter>
        <DrawerActivity
          data={{
            ...d,
            timeline: null as unknown as DrawerData["timeline"],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("execution-timeline").textContent)
      .toContain("No execution evidence was captured");
  });
});
