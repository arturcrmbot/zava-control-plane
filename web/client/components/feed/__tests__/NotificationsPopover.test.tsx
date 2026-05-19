// @vitest-environment jsdom
// web/client/components/feed/__tests__/NotificationsPopover.test.tsx
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import NotificationsPopover from "@client/components/feed/NotificationsPopover";
import type { FeedItem } from "@shared/feedItems";

beforeEach(() => {
  if (typeof localStorage !== "undefined") localStorage.clear();
});
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
    render(<NotificationsPopover roleId="ops-reviewer" items={items} onJumpTo={() => {}} />);
    expect(screen.getByRole("button", { name: /2 unread/i })).toBeTruthy();
  });

  it("clicking an item fires onJumpTo, dismisses it, and drops the unread count", () => {
    const onJumpTo = vi.fn();
    render(<NotificationsPopover roleId="ops-reviewer" items={items} onJumpTo={onJumpTo} />);
    fireEvent.click(screen.getByRole("button", { name: /2 unread/i }));
    fireEvent.click(screen.getByText(/W-2/));
    expect(onJumpTo).toHaveBeenCalledWith("exception:E-2");
    // popover auto-closes; re-open and confirm count fell to 1
    fireEvent.click(screen.getByRole("button", { name: /1 unread/i }));
    expect(screen.queryByText(/W-2/)).toBeNull();
    expect(screen.getByText(/W-1/)).toBeTruthy();
  });

  it("'Clear all' wipes every item and shows the empty state", () => {
    render(<NotificationsPopover roleId="ops-reviewer" items={items} onJumpTo={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /2 unread/i }));
    fireEvent.click(screen.getByRole("button", { name: /Clear all/i }));
    // bell now reads "0 unread"; re-open and assert the empty state
    fireEvent.click(screen.getByRole("button", { name: /0 unread/i }));
    expect(screen.getByText(/all caught up/i)).toBeTruthy();
    expect(screen.queryByText(/W-1/)).toBeNull();
    expect(screen.queryByText(/W-2/)).toBeNull();
  });

  it("dismissal is keyed by role: switching roles re-exposes the same items", () => {
    const { rerender } = render(<NotificationsPopover roleId="ops-reviewer" items={items} onJumpTo={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /2 unread/i }));
    fireEvent.click(screen.getByRole("button", { name: /Clear all/i }));
    // ops-reviewer is now empty
    rerender(<NotificationsPopover roleId="executive" items={items} onJumpTo={() => {}} />);
    expect(screen.getByRole("button", { name: /2 unread/i })).toBeTruthy();
  });
});
