// @vitest-environment jsdom
// web/client/hooks/__tests__/useWorldSimulation.test.tsx
//
// Proves the polling contract of useWorldSimulation against the real
// /api/world/{state,events,inject/demand_surge} JSON surfaces:
//   1. initial snapshot + events load
//   2. latest_seq is used as the cursor on the next events request
//   3. duplicate seqs are de-duplicated and the ring stays bounded at 300
//   4. injectSurge POSTs the exact typed payload
//   5. unmount aborts in-flight fetches and clears both intervals
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useWorldSimulation, type WorldEvent } from "../useWorldSimulation";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

function mkEvent(seq: number, over: Partial<WorldEvent> = {}): WorldEvent {
  return {
    seq,
    event_id: `E-${seq}`,
    sim_time: seq,
    type: "ticket.queued",
    actor_id: `TCK-${seq}`,
    target_id: "queue:support",
    cause_event_id: null,
    trace_id: `trace-${seq}`,
    payload: {},
    ...over,
  };
}

const BASE_STATE = {
  enabled: true,
  scenario: "support",
  seed: 42,
  status: "running",
  sim_time: 12.5,
  latest_seq: 3,
  projection: { support_backlog: 2 },
  tickets: [{ id: "TCK-1", status: "queued" }],
  workers: [{ id: "WRK-0001", team_id: "TEAM-SUPPORT", status: "idle" }],
};

async function flush(times = 5): Promise<void> {
  for (let i = 0; i < times; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await Promise.resolve();
  }
}
async function tick(ms: number): Promise<void> {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await flush();
  });
}

describe("useWorldSimulation", () => {
  it("loads the initial snapshot and events on mount", async () => {
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      if (u.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (u.includes("/api/world/events")) {
        return jsonResponse({ enabled: true, latest_seq: 2, events: [mkEvent(1), mkEvent(2)] });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useWorldSimulation());
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.state).not.toBeNull());
    expect(result.current.state?.scenario).toBe("support");
    expect(result.current.state?.seed).toBe(42);
    await waitFor(() => expect(result.current.events).toHaveLength(2));
    expect(result.current.events.map((e) => e.seq)).toEqual([1, 2]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("uses the returned latest_seq as the cursor on the next events request", async () => {
    const eventsUrls: string[] = [];
    let eventsCall = 0;
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      if (u.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (u.includes("/api/world/events")) {
        eventsUrls.push(u);
        eventsCall += 1;
        if (eventsCall === 1) {
          return jsonResponse({ enabled: true, latest_seq: 5, events: [mkEvent(3), mkEvent(4)] });
        }
        return jsonResponse({ enabled: true, latest_seq: 8, events: [mkEvent(5)] });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });
    expect(eventsUrls[0]).toContain("after=0");

    // Events poll again at 300ms; state poll (1000ms) has not fired yet.
    await tick(300);
    expect(eventsUrls[1]).toContain("after=5");
  });

  it("de-duplicates events by seq and bounds the ring to 300", async () => {
    // Each poll returns 20 seqs stepping the base by 10 so consecutive
    // batches overlap by 10 (genuine duplicates). One poll fires on mount and
    // one per tick (41 total) spanning seqs 1..420, i.e. 420 distinct — the
    // ring must keep the newest 300.
    let call = 0;
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      if (u.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (u.includes("/api/world/events")) {
        call += 1;
        const base = (call - 1) * 10 + 1;
        const batch = Array.from({ length: 20 }, (_, i) => mkEvent(base + i));
        return jsonResponse({ enabled: true, latest_seq: base + 19, events: batch });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });
    for (let i = 0; i < 40; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      await tick(300);
    }

    const seqs = result.current.events.map((e) => e.seq);
    expect(seqs.length).toBe(300);
    expect(new Set(seqs).size).toBe(300); // no duplicates
    // Sorted ascending, newest kept.
    expect(seqs[0]).toBe(121);
    expect(seqs[seqs.length - 1]).toBe(420);
  });

  it("injectSurge POSTs the exact typed payload then refreshes", async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
      const u = String(url);
      if (u.includes("/api/world/inject/demand_surge")) return jsonResponse({ ok: true });
      if (u.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (u.includes("/api/world/events")) return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      return jsonResponse({});
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });

    await act(async () => {
      await result.current.injectSurge();
      await flush();
    });

    const call = fetchMock.mock.calls.find((c) =>
      String(c[0]).includes("/api/world/inject/demand_surge"),
    );
    expect(call).toBeTruthy();
    const opts = call?.[1] as RequestInit;
    expect(opts.method).toBe("POST");
    expect(JSON.parse(String(opts.body))).toEqual({ multiplier: 4, duration_minutes: 90 });
  });

  it("preserves the demand-surge fallback message", async () => {
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      if (u.includes("/api/world/inject/demand_surge")) throw new Error();
      if (u.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (u.includes("/api/world/events")) {
        return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });

    await act(async () => {
      await result.current.injectSurge();
    });

    expect(result.current.error).toBe("failed to inject demand surge");
  });

  it("clears both intervals and aborts in-flight fetches on unmount", async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, "abort");
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      if (u.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (u.includes("/api/world/events")) return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      return jsonResponse({});
    }) as unknown as typeof fetch;

    const { unmount } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });
    const callsBefore = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    unmount();
    expect(abortSpy).toHaveBeenCalled();

    await tick(5000);
    const callsAfter = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(callsAfter).toBe(callsBefore);
  });
});
