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

  it("emits a new event when currentValue changes for a policy without gitSha", async () => {
    mockPolicyApi([
      [{ id: "P1", description: "d", currentValue: 0.8 }],
      [{ id: "P1", description: "d", currentValue: 0.9 }],
    ]);
    const { result } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].currentValue).toBe(0.9);
  });

  it("caps event history at MAX_EVENTS (50)", async () => {
    // Snapshot 0 is baseline (silent). Snapshots 1..N add fresh rows so each
    // poll produces fresh events. Use 60 distinct ids across snapshots.
    const snapshots: Array<Array<Record<string, unknown>>> = [[]];
    for (let i = 0; i < 60; i++) {
      snapshots.push([{ id: `P${i}`, description: "d", currentValue: i, gitSha: `sha${i}` }]);
    }
    mockPolicyApi(snapshots);

    const { result } = renderHook(() => usePolicyEvents(1_000));
    await act(async () => { await Promise.resolve(); });
    for (let i = 0; i < 60; i++) {
      await act(async () => {
        vi.advanceTimersByTime(1_000);
        await Promise.resolve();
        await Promise.resolve();
      });
    }
    await waitFor(() => expect(result.current.length).toBe(50));
    // Newest first: snapshot 60 is the last fresh row.
    expect(result.current[0].id).toBe("P59");
  });

  it("stops polling after unmount", async () => {
    mockPolicyApi([[{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }]]);
    const { unmount } = renderHook(() => usePolicyEvents(30_000));
    await act(async () => { await Promise.resolve(); });
    const callsBefore = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    unmount();
    await act(async () => {
      vi.advanceTimersByTime(120_000);
      await Promise.resolve();
    });
    const callsAfter = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(callsAfter).toBe(callsBefore);
  });

  it("silently recovers from a transient network failure", async () => {
    let call = 0;
    globalThis.fetch = vi.fn().mockImplementation(() => {
      call += 1;
      if (call === 2) return Promise.reject(new Error("network down"));
      const body =
        call === 1
          ? [{ id: "P1", description: "d", currentValue: 0.8, gitSha: "a" }]
          : [{ id: "P1", description: "d", currentValue: 0.9, gitSha: "b", author: "alice" }];
      return Promise.resolve({ ok: true, json: async () => body } as Response);
    });
    const { result } = renderHook(() => usePolicyEvents(1_000));
    await act(async () => { await Promise.resolve(); });
    // Tick once → fetch rejects → no throw, no state change
    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current).toEqual([]);
    // Tick again → fetch resolves with a real change → one event
    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
      await Promise.resolve();
    });
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].author).toBe("alice");
  });
});
