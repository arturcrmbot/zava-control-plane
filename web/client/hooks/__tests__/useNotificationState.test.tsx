// @vitest-environment jsdom
// web/client/hooks/__tests__/useNotificationState.test.tsx
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useNotificationState } from "@client/hooks/useNotificationState";
import type { FeedItem } from "@shared/feedItems";

beforeEach(() => {
  if (typeof localStorage !== "undefined") localStorage.clear();
});
afterEach(() => {
  if (typeof localStorage !== "undefined") localStorage.clear();
});

const items: FeedItem[] = [
  { type: "hitl", id: "hitl:W-1", timestamp: 100, workflowId: "W-1" },
  { type: "hitl", id: "hitl:W-2", timestamp: 200, workflowId: "W-2" },
  { type: "exception", id: "exception:E-3", timestamp: 300, workflowId: "W-3",
    exception: { id: "E-3", workflowId: "W-3", composedBy: "fleet-manager",
      severity: "medium", category: "compliance", summary: "s",
      recommendation: "r", options: [], relatedPolicyRefs: [],
      confidence: 0.5, createdAt: 300 } },
];

describe("useNotificationState", () => {
  it("counts every item as unread on first render", () => {
    const { result } = renderHook(() => useNotificationState("ops-reviewer"));
    expect(result.current.count(items)).toBe(3);
    expect(result.current.unread(items).map((i) => i.id)).toEqual(
      ["hitl:W-1", "hitl:W-2", "exception:E-3"],
    );
  });

  it("markSeen removes a single item from the unread set", () => {
    const { result } = renderHook(() => useNotificationState("ops-reviewer"));
    act(() => result.current.markSeen("hitl:W-2"));
    expect(result.current.count(items)).toBe(2);
    expect(result.current.unread(items).map((i) => i.id)).toEqual(
      ["hitl:W-1", "exception:E-3"],
    );
  });

  it("clearAll dismisses every item with timestamp <= now", () => {
    const { result } = renderHook(() => useNotificationState("ops-reviewer"));
    act(() => result.current.clearAll());
    expect(result.current.count(items)).toBe(0);
  });

  it("newer items arriving after clearAll are unread again", () => {
    const { result } = renderHook(() => useNotificationState("ops-reviewer"));
    act(() => result.current.clearAll());
    const future: FeedItem = {
      type: "hitl",
      id: "hitl:W-99",
      timestamp: Math.floor(Date.now() / 1000) + 60,
      workflowId: "W-99",
    };
    expect(result.current.count([...items, future])).toBe(1);
    expect(result.current.unread([...items, future]).map((i) => i.id)).toEqual(["hitl:W-99"]);
  });

  it("state is keyed per role", () => {
    const r1 = renderHook(() => useNotificationState("ops-reviewer"));
    const r2 = renderHook(() => useNotificationState("executive"));
    act(() => r1.result.current.clearAll());
    expect(r1.result.current.count(items)).toBe(0);
    expect(r2.result.current.count(items)).toBe(3);
  });

  it("persists dismissed state across remounts", () => {
    const first = renderHook(() => useNotificationState("ops-reviewer"));
    act(() => first.result.current.markSeen("hitl:W-1"));
    first.unmount();
    const second = renderHook(() => useNotificationState("ops-reviewer"));
    expect(second.result.current.count(items)).toBe(2);
  });
});
