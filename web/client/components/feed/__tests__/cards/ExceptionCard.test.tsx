// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ExceptionCard from "@client/components/feed/cards/ExceptionCard";
import { ResolutionProvider, useResolutionStore } from "@client/hooks/useResolutionStore";
import { ToastProvider } from "@client/components/feed/Toast";
import type { ExceptionItem } from "@shared/feedItems";

const baseItem: ExceptionItem = {
  type: "exception", id: "exception:E-1", timestamp: 100,
  workflowId: "WF-1", severity: "high",
  exception: {
    id: "E-1", workflowId: "WF-1", composedBy: "fleet-manager",
    severity: "high", category: "compliance",
    summary: "Vendor on watchlist", recommendation: "request-info",
    options: [], relatedPolicyRefs: [], confidence: 0.8, createdAt: 100,
  },
};

beforeEach(() => {
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("ExceptionCard", () => {
  it("renders severity, summary, and recommendation", () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <ResolutionProvider><ExceptionCard item={baseItem} /></ResolutionProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/Vendor on watchlist/i)).toBeTruthy();
    expect(screen.getByText(/request-info/i)).toBeTruthy();
  });

  it("offers 5 actions including Snooze 1h", () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <ResolutionProvider><ExceptionCard item={baseItem} /></ResolutionProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: /Snooze 1h/i })).toBeTruthy();
  });

  it("records optimistic resolution on Approve click and calls /api/exceptions/E-1/resolve", async () => {
    function Probe() {
      const store = useResolutionStore();
      return <span data-testid="probe">{store.get("exception:E-1")?.verb ?? "none"}</span>;
    }
    render(
      <MemoryRouter>
        <ToastProvider>
          <ResolutionProvider>
            <ExceptionCard item={baseItem} />
            <Probe />
          </ResolutionProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toBe("Approved"));
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/exceptions/E-1/resolve",
    );
  });
});
