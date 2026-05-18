// @vitest-environment jsdom
// web/client/hooks/__tests__/usePolicyEvents.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { usePolicyEvents } from "../usePolicyEvents";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function mockPolicyApi(snapshots: Array<Array<Record<string, unknown>>>) {
  let call = 0;
  globalThis.fetch = vi.fn().mockImplementation(() => {
    const body = snapshots[Math.min(call, snapshots.length - 1)];
    call += 1;
    return Promise.resolve({ ok: true, json: async () => body } as Response);
  });
}

describe("usePolicyEvents", () => {
  it("emits no events on first snapshot (baseline only)", async () => {
    mockPolicyApi([[{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }]]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    expect(result.current).toEqual([]);
  });

  it("emits one event when a policy's gitSha changes between polls", async () => {
    mockPolicyApi([
      [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }],
      [{ id: "P1", description: "d", currentValue: 0.9, gitSha: "b", author: "alice" }],
    ]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(result.current).toHaveLength(1);
    });
    expect(result.current[0].id).toBe("P1");
    expect(result.current[0].currentValue).toBe(0.9);
    expect(result.current[0].author).toBe("alice");
  });

  it("does not emit when polled response is unchanged", async () => {
    mockPolicyApi([
      [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }],
      [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }],
    ]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
    });
    expect(result.current).toEqual([]);
  });
});
