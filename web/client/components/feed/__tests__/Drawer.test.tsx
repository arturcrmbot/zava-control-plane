// @vitest-environment jsdom
// web/client/components/feed/__tests__/Drawer.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Drawer from "@client/components/feed/Drawer";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { getRolePreset } from "@shared/roles";

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      workflow: {
        id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
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
    }),
  } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Drawer", () => {
  it("renders 3 section headings in the order dictated by the role", async () => {
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Drawer
            workflowId="WF-1"
            role={getRolePreset("ops-reviewer")}
            onClose={() => {}}
          />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Decision/i)).toBeTruthy();
    });
    const headings = screen.getAllByRole("heading");
    const text = headings.map((h) => h.textContent ?? "");
    expect(text.findIndex((t) => /Decision/i.test(t)))
      .toBeLessThan(text.findIndex((t) => /Activity/i.test(t)));
    expect(text.findIndex((t) => /Activity/i.test(t)))
      .toBeLessThan(text.findIndex((t) => /Audit/i.test(t)));
  });

  it("Executive role flips section order to Audit · Activity · Decision", async () => {
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Drawer
            workflowId="WF-1"
            role={getRolePreset("executive")}
            onClose={() => {}}
          />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /^Audit$/i })).toBeTruthy();
    });
    const headings = screen.getAllByRole("heading");
    const text = headings.map((h) => h.textContent ?? "");
    const auditIdx = text.findIndex((t) => /Audit/i.test(t));
    const activityIdx = text.findIndex((t) => /Activity/i.test(t));
    const decisionIdx = text.findIndex((t) => /Decision/i.test(t));
    expect(auditIdx).toBeLessThan(activityIdx);
    expect(activityIdx).toBeLessThan(decisionIdx);
  });

  it("Esc fires onClose", async () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <ResolutionProvider>
          <Drawer
            workflowId="WF-1"
            role={getRolePreset("ops-reviewer")}
            onClose={onClose}
          />
        </ResolutionProvider>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/Decision/i));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
