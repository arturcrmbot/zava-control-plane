// @vitest-environment jsdom
// web/client/hooks/__tests__/useNewItemsBuffer.test.ts
import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useNewItemsBuffer } from "../useNewItemsBuffer";
import type { FeedItem } from "@shared/feedItems";

const mk = (id: string, ts: number): FeedItem => ({
  type: "hitl", id, timestamp: ts, workflowId: id, domain: "expense-claim", severity: "medium",
});

describe("useNewItemsBuffer", () => {
  it("shows the initial list as visible with no pending", () => {
    const { result } = renderHook(() => useNewItemsBuffer([mk("a", 1), mk("b", 2)]));
    expect(result.current.visible.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.pendingCount).toBe(0);
  });

  it("treats new top items as pending until pulled in", () => {
    const initial = [mk("a", 1), mk("b", 2)];
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: initial },
    });
    rerender({ list: [mk("c", 3), mk("a", 1), mk("b", 2)] });
    expect(result.current.visible.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.pendingCount).toBe(1);

    act(() => result.current.pullIn());
    expect(result.current.visible.map((i) => i.id)).toEqual(["c", "a", "b"]);
    expect(result.current.pendingCount).toBe(0);
  });

  it("does not flag re-ordered or removed items as pending", () => {
    const initial = [mk("a", 1), mk("b", 2)];
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: initial },
    });
    rerender({ list: [mk("a", 1)] });
    expect(result.current.pendingCount).toBe(0);
  });

  it("uses the first non-empty items as baseline when mounted with empty list", () => {
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: [] as FeedItem[] },
    });
    expect(result.current.visible).toEqual([]);
    expect(result.current.pendingCount).toBe(0);

    rerender({ list: [mk("a", 1), mk("b", 2)] });
    expect(result.current.visible.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.pendingCount).toBe(0); // baseline, not pending

    // After baseline, a new id behaves as pending.
    rerender({ list: [mk("c", 3), mk("a", 1), mk("b", 2)] });
    expect(result.current.visible.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.pendingCount).toBe(1);
  });

  it("returns the same visible reference across renders when ids and severities are unchanged", () => {
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: [mk("a", 1), mk("b", 2)] },
    });
    const firstRef = result.current.visible;
    rerender({ list: [mk("a", 1), mk("b", 2)] });
    expect(result.current.visible).toBe(firstRef);
  });

  it("propagates severity escalations on existing items even when ids are unchanged", () => {
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: [mk("a", 1)] },
    });
    expect(result.current.visible[0].severity).toBe("medium");
    rerender({
      list: [{ ...mk("a", 1), severity: "critical" }],
    });
    expect(result.current.visible[0].severity).toBe("critical");
  });

  it("pullIn() is a no-op when pendingCount is zero", () => {
    const { result } = renderHook(() => useNewItemsBuffer([mk("a", 1), mk("b", 2)]));
    const before = result.current.visible;
    act(() => result.current.pullIn());
    expect(result.current.visible).toBe(before);
    expect(result.current.pendingCount).toBe(0);
  });

  it("accumulates pending across multiple churns before pullIn()", () => {
    const { result, rerender } = renderHook(({ list }) => useNewItemsBuffer(list), {
      initialProps: { list: [mk("a", 1)] },
    });
    rerender({ list: [mk("b", 2), mk("a", 1)] });
    expect(result.current.pendingCount).toBe(1);
    rerender({ list: [mk("c", 3), mk("b", 2), mk("a", 1)] });
    expect(result.current.pendingCount).toBe(2);
    act(() => result.current.pullIn());
    expect(result.current.visible.map((i) => i.id)).toEqual(["c", "b", "a"]);
    expect(result.current.pendingCount).toBe(0);
  });
});
