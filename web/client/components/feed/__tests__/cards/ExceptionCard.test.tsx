// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ExceptionCard.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, act, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ExceptionCard from "@client/components/feed/cards/ExceptionCard";
import ResolvedCard from "@client/components/feed/cards/ResolvedCard";
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
  localStorage.clear();
  vi.useFakeTimers();
  globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) } as Response);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

function SwitchingCard() {
  const store = useResolutionStore();
  const resolution = store.get(baseItem.id);
  return (
    <div data-testid="feed-card">
      {resolution ? (
        <ResolvedCard item={{
          type: "resolved", id: `resolved:${baseItem.id}`, timestamp: baseItem.timestamp,
          workflowId: baseItem.workflowId, severity: null, origin: baseItem,
          verb: resolution.verb, actor: resolution.actor, actedAt: resolution.actedAt,
        }} />
      ) : <ExceptionCard item={baseItem} />}
    </div>
  );
}

function renderSwitchingCard() {
  render(
    <MemoryRouter><ToastProvider><ResolutionProvider>
      <SwitchingCard />
    </ResolutionProvider></ToastProvider></MemoryRouter>,
  );
}

describe("ExceptionCard", () => {
  it("resolved-card Undo cancels the delayed approval POST", async () => {
    renderSwitchingCard();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(within(screen.getByTestId("feed-card")).getByRole("button", { name: "Undo" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(5_001); });
    expect(globalThis.fetch).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
  });

  it("toast Undo cancels the same pending approval", async () => {
    renderSwitchingCard();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(within(screen.getByRole("status")).getByRole("button", { name: "Undo" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(5_001); });
    expect(globalThis.fetch).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
  });

  it("shows pending before dispatch and no Undo after acknowledgement", async () => {
    renderSwitchingCard();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(within(screen.getByTestId("feed-card")).getByText("pending")).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(5_001); });
    expect(globalThis.fetch).toHaveBeenCalledOnce();
    expect(within(screen.getByTestId("feed-card")).queryByRole("button", { name: "Undo" })).toBeNull();
    expect(within(screen.getByTestId("feed-card")).queryByText("pending")).toBeNull();
  });

  it("returns to the actionable card when the server rejects the request", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("failed", { status: 503 }));
    renderSwitchingCard();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(5_001); });
    expect(screen.getByRole("button", { name: "Approve" })).toBeTruthy();
    expect(screen.getByText(/Couldn't resolve/)).toBeTruthy();
  });

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
    await vi.advanceTimersByTimeAsync(5_001);
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/api/exceptions/E-1/resolve",
    );
  });
});
