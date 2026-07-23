// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/ResolvedCard.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import ResolvedCard from "@client/components/feed/cards/ResolvedCard";
import { ResolutionProvider, useResolutionStore } from "@client/hooks/useResolutionStore";
import type { ResolvedItem, HITLItem } from "@shared/feedItems";

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });

const origin: HITLItem = {
  type: "hitl", id: "hitl:WF-1", timestamp: 100,
  workflowId: "WF-1", domain: "expense-claim", severity: "high",
};

const item: ResolvedItem = {
  type: "resolved", id: "resolved:hitl:WF-1", timestamp: 100,
  workflowId: "WF-1", domain: "expense-claim", severity: null,
  origin, verb: "Approved", actor: "you", actedAt: Math.floor(Date.now() / 1000),
};

describe("ResolvedCard", () => {
  it("renders 'Approved by you' with relative time", () => {
    render(<MemoryRouter><ResolutionProvider><ResolvedCard item={item} /></ResolutionProvider></MemoryRouter>);
    expect(screen.getByText(/Approved by you/i)).toBeTruthy();
  });

  it("undo calls store.revert when undoable", async () => {
    function Bootstrap() {
      const store = useResolutionStore();
      useEffect(() => {
        if (!store.get("hitl:WF-1")) {
          store.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 });
        }
      }, [store]);
      return <ResolvedCard item={item} />;
    }
    render(<MemoryRouter><ResolutionProvider><Bootstrap /></ResolutionProvider></MemoryRouter>);
    const undo = await screen.findByRole("button", { name: /undo/i });
    fireEvent.click(undo);
    // After click, the button is gone (state was reverted)
    expect(screen.queryByRole("button", { name: /undo/i })).toBeNull();
  });
});
