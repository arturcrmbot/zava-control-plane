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
});
