// @vitest-environment jsdom
// web/client/hooks/__tests__/useResolutionStore.test.tsx
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { useResolutionStore, ResolutionProvider } from "../useResolutionStore";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ResolutionProvider undoTtlMs={30_000}>{children}</ResolutionProvider>
);

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useResolutionStore", () => {
  it("records a resolution and reads it back", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    expect(result.current.get("hitl:WF-1")).toEqual(
      expect.objectContaining({ verb: "Approved", actor: "you", undoable: true }),
    );
  });

  it("flips undoable=false after the TTL elapses", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => { vi.advanceTimersByTime(30_001); });
    expect(result.current.get("hitl:WF-1")?.undoable).toBe(false);
  });

  it("revert() removes the optimistic record", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => result.current.revert("hitl:WF-1"));
    expect(result.current.get("hitl:WF-1")).toBeUndefined();
  });
});
