// @vitest-environment jsdom
// web/client/components/feed/__tests__/CardList.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CardList from "@client/components/feed/CardList";
import { ResolutionProvider } from "@client/hooks/useResolutionStore";
import { ToastProvider } from "@client/components/feed/Toast";
import type { FeedItem } from "@shared/feedItems";

afterEach(cleanup);

function mk(i: number): FeedItem {
  return {
    type: "hitl", id: `hitl:W-${i}`, timestamp: 1000 - i,
    workflowId: `W-${i}`, domain: "expense-claim", severity: "medium",
    workflow: {
      id: `W-${i}`, type: "expense-claim", status: "awaiting_hitl",
      currentPhase: "Intake", createdAt: 1, slaDueAt: 9999,
      jurisdiction: "UK", agency: "Z", actionLedger: [],
      tokensSpent: 0, costUSD: 0,
      claim: {
        claimId: `C-${i}`, employeeId: `E-${i}`, submittedAt: "2024-01-01",
        market: "UK", currency: "GBP", category: "meals", vendor: "Vendor",
        amount: 10, attendees: 1, emsSource: "workday",
      },
    },
  };
}

describe("CardList", () => {
  it("renders all items below the windowing threshold", () => {
    const items = Array.from({ length: 5 }, (_, i) => mk(i));
    render(
      <MemoryRouter><ToastProvider><ResolutionProvider>
        <CardList items={items} hideActions={false} onOpenDrawer={() => {}} selectMode={false} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></ToastProvider></MemoryRouter>,
    );
    expect(screen.getAllByText(/^W-/).length).toBe(5);
  });

  it("renders an empty-state hint when items is empty", () => {
    render(
      <MemoryRouter><ToastProvider><ResolutionProvider>
        <CardList items={[]} hideActions={false} onOpenDrawer={() => {}} selectMode={false} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></ToastProvider></MemoryRouter>,
    );
    expect(screen.getByText(/nothing here/i)).toBeTruthy();
  });

  it("renders a checkbox per card in selectMode", () => {
    const items = Array.from({ length: 3 }, (_, i) => mk(i));
    render(
      <MemoryRouter><ToastProvider><ResolutionProvider>
        <CardList items={items} hideActions={false} onOpenDrawer={() => {}} selectMode={true} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></ToastProvider></MemoryRouter>,
    );
    expect(screen.getAllByRole("checkbox").length).toBe(3);
  });

  it("windows to 100 items at most when list is larger", () => {
    const items = Array.from({ length: 150 }, (_, i) => mk(i));
    render(
      <MemoryRouter><ToastProvider><ResolutionProvider>
        <CardList items={items} hideActions={false} onOpenDrawer={() => {}} selectMode={false} selected={new Set()} onToggleSelect={() => {}} />
      </ResolutionProvider></ToastProvider></MemoryRouter>,
    );
    // After windowing, only first 100 cards' workflow ids render.
    expect(screen.queryByText(/^W-149$/)).toBeNull();
    expect(screen.getByText(/^W-0$/)).toBeTruthy();
  });
});
