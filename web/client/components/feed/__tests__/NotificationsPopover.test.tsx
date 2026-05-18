// @vitest-environment jsdom
// web/client/components/feed/__tests__/NotificationsPopover.test.tsx
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import NotificationsPopover from "@client/components/feed/NotificationsPopover";
import type { FeedItem } from "@shared/feedItems";

afterEach(cleanup);

const items: FeedItem[] = [
  { type: "hitl", id: "hitl:W-1", timestamp: 100, workflowId: "W-1", domain: "expense-claim", severity: "critical" },
  { type: "exception", id: "exception:E-2", timestamp: 90, workflowId: "W-2", severity: "high",
    exception: { id: "E-2", workflowId: "W-2", composedBy: "fleet-manager", severity: "high",
      category: "compliance", summary: "S", recommendation: "R", options: [],
      relatedPolicyRefs: [], confidence: 0.5, createdAt: 90 } },
];

describe("NotificationsPopover", () => {
  it("renders a bell button with the unread count", () => {
    render(<NotificationsPopover items={items} onJumpTo={() => {}} />);
    expect(screen.getByRole("button", { name: /2 unread/i })).toBeTruthy();
  });
  it("opens and lists items; clicking one fires onJumpTo with the item id", () => {
    const onJumpTo = vi.fn();
    render(<NotificationsPopover items={items} onJumpTo={onJumpTo} />);
    fireEvent.click(screen.getByRole("button", { name: /2 unread/i }));
    fireEvent.click(screen.getByText(/W-2/));
    expect(onJumpTo).toHaveBeenCalledWith("exception:E-2");
  });
});
