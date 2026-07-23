// @vitest-environment jsdom
// web/client/components/feed/__tests__/cards/MilestoneCard.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MilestoneCard from "@client/components/feed/cards/MilestoneCard";
import type { MilestoneItem } from "@shared/feedItems";

afterEach(cleanup);

const item: MilestoneItem = {
  type: "milestone", id: "milestone:WF-9", timestamp: 100,
  workflowId: "WF-9", domain: "expense-claim", severity: null,
  outcome: "completed",
  workflow: {
    id: "WF-9", type: "expense-claim", status: "completed",
    currentPhase: "Audit", createdAt: 100, slaDueAt: 9999,
    jurisdiction: "UK", agency: "Z", actionLedger: [],
    tokensSpent: 0, costUSD: 0,
  },
};

describe("MilestoneCard", () => {
  it("renders the outcome verb", () => {
    render(<MemoryRouter><MilestoneCard item={item} /></MemoryRouter>);
    expect(screen.getByText(/completed/i)).toBeTruthy();
  });

  it("fires onOpenDrawer when the card is clicked", () => {
    const onOpen = vi.fn();
    render(<MemoryRouter><MilestoneCard item={item} onOpenDrawer={onOpen} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("card-WF-9"));
    expect(onOpen).toHaveBeenCalledWith("WF-9");
  });
});
