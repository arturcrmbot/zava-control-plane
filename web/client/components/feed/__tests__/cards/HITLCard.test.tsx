// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/HITLCard.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HITLCard from "@client/components/feed/cards/HITLCard";
import { ResolutionProvider, useResolutionStore } from "@client/hooks/useResolutionStore";
import { ToastProvider } from "@client/components/feed/Toast";
import type { HITLItem } from "@shared/feedItems";
import type { Workflow } from "@shared/types";

const baseWf: Workflow = {
  id: "WF-1", type: "expense-claim", status: "awaiting_hitl",
  currentPhase: "Intake", createdAt: 100, slaDueAt: 99999,
  jurisdiction: "UK", agency: "Z", actionLedger: [],
  tokensSpent: 0, costUSD: 0,
  claim: {
    claimId: "CL-1", employeeId: "E-1", submittedAt: "2026-05-18T10:00:00Z",
    market: "UK", currency: "GBP", category: "meals", vendor: "Pret",
    amount: 42.5, attendees: 1, emsSource: "concur",
  },
};

const baseItem: HITLItem = {
  type: "hitl", id: "hitl:WF-1", timestamp: 100,
  workflowId: "WF-1", domain: "expense-claim", severity: "high",
  workflow: baseWf,
};

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderWithProviders(item: HITLItem, opts: { hideActions?: boolean } = {}) {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <ResolutionProvider>
          <HITLCard item={item} hideActions={!!opts.hideActions} />
        </ResolutionProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("HITLCard", () => {
  it("renders the four inline action buttons by default", () => {
    renderWithProviders(baseItem);
    expect(screen.getByRole("button", { name: /Approve/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Request docs/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Escalate/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reject/i })).toBeTruthy();
  });

  it("hides actions when hideActions is true (executive role)", () => {
    renderWithProviders(baseItem, { hideActions: true });
    expect(screen.queryByRole("button", { name: /Approve/i })).toBeNull();
  });

  it("records an optimistic resolution and POSTs to /api/exceptions/{id}/resolve when there is an exception", async () => {
    const item: HITLItem = {
      ...baseItem,
      workflow: { ...baseWf, activeExceptionId: "EXC-1" },
    };
    function Probe() {
      const store = useResolutionStore();
      return <span data-testid="probe">{store.get("hitl:WF-1")?.verb ?? "none"}</span>;
    }
    render(
      <MemoryRouter>
        <ToastProvider>
          <ResolutionProvider>
            <HITLCard item={item} />
            <Probe />
          </ResolutionProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("Approved");
    });
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/exceptions/EXC-1/resolve",
    );
  });

  it("reverts the optimistic resolution if the backend call fails", async () => {
    const item: HITLItem = {
      ...baseItem,
      workflow: { ...baseWf, activeExceptionId: "EXC-1" },
    };
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, text: async () => "boom" } as Response);
    function Probe() {
      const store = useResolutionStore();
      return <span data-testid="probe">{store.get("hitl:WF-1")?.verb ?? "none"}</span>;
    }
    render(
      <MemoryRouter>
        <ToastProvider>
          <ResolutionProvider>
            <HITLCard item={item} />
            <Probe />
          </ResolutionProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => {
      expect(screen.getByTestId("probe").textContent).toBe("none");
    });
  });
});
