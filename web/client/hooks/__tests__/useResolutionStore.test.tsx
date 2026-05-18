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

  it("throws with a clear message when called outside <ResolutionProvider>", () => {
    // Suppress React's error-boundary console output for this expected throw.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useResolutionStore())).toThrow(
      /useResolutionStore must be used inside <ResolutionProvider>/,
    );
    spy.mockRestore();
  });

  it("revert() cancels the pending TTL so no flip fires afterwards", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => result.current.revert("hitl:WF-1"));
    // Advance past TTL — the entry was already removed; if the timer were
    // still alive and unguarded it would attempt to setMap a "undoable=false"
    // entry into nothingness, which is harmless but indicates a leaked timer.
    act(() => { vi.advanceTimersByTime(60_000); });
    expect(result.current.get("hitl:WF-1")).toBeUndefined();
  });

  it("record() called twice on the same id resets the TTL window", () => {
    const { result } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => { vi.advanceTimersByTime(20_000); });
    // Re-record at t=20s with a fresh actor; this should restart the TTL.
    act(() => result.current.record("hitl:WF-1", { verb: "Rejected", actor: "you", actedAt: 120 }));
    // Advance another 20s — total since FIRST record is 40s (> 30s TTL),
    // but only 20s since the second record, so still undoable.
    act(() => { vi.advanceTimersByTime(20_000); });
    expect(result.current.get("hitl:WF-1")?.undoable).toBe(true);
    // Advance past the second record's TTL (30s total since reset).
    act(() => { vi.advanceTimersByTime(11_000); });
    expect(result.current.get("hitl:WF-1")?.undoable).toBe(false);
  });

  it("honours a custom undoTtlMs (not just the default)", () => {
    const shortWrapper = ({ children }: { children: import("react").ReactNode }) => (
      <ResolutionProvider undoTtlMs={5_000}>{children}</ResolutionProvider>
    );
    const { result } = renderHook(() => useResolutionStore(), { wrapper: shortWrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    act(() => { vi.advanceTimersByTime(4_999); });
    expect(result.current.get("hitl:WF-1")?.undoable).toBe(true);
    act(() => { vi.advanceTimersByTime(2); });
    expect(result.current.get("hitl:WF-1")?.undoable).toBe(false);
  });

  it("unmounting the Provider cancels pending timers without warning", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result, unmount } = renderHook(() => useResolutionStore(), { wrapper });
    act(() => result.current.record("hitl:WF-1", { verb: "Approved", actor: "you", actedAt: 100 }));
    unmount();
    // Advance past TTL — without the mountedRef guard, this would attempt to
    // setMap on an unmounted tree and React would log a warning.
    act(() => { vi.advanceTimersByTime(60_000); });
    // Filter to React's specific unmounted-state-update warning (other warnings
    // may legitimately appear).
    const unmountedWarnings = spy.mock.calls.filter((args) =>
      args.some((a) => typeof a === "string" && a.includes("unmounted")),
    );
    expect(unmountedWarnings).toEqual([]);
    spy.mockRestore();
  });
});
