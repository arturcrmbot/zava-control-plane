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
  it("uses compact state and bounded journal endpoints", async () => {
    const urls: string[] = [];
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const value = String(url);
      urls.push(value);
      if (value.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (value.includes("/api/world/events")) {
        return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });

    expect(urls).toContain("/api/world/state?compact=true");
    expect(urls).toContain("/api/world/events?after=0&limit=300");
  });

  it("polls the journal no more than once per second", async () => {
    let eventCalls = 0;
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const value = String(url);
      if (value.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (value.includes("/api/world/events")) {
        eventCalls += 1;
        return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });
    expect(eventCalls).toBe(1);

    await tick(999);
    expect(eventCalls).toBe(1);
    await tick(1);
    expect(eventCalls).toBe(2);
  });

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

    await tick(1000);
    expect(eventsUrls[1]).toContain("after=5");
  });

  it("replays from zero when the backend journal sequence regresses", async () => {
    const eventsUrls: string[] = [];
    let eventsCall = 0;
    globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
      const value = String(url);
      if (value.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (value.includes("/api/world/events")) {
        eventsUrls.push(value);
        eventsCall += 1;
        if (eventsCall === 1) {
          return jsonResponse({ enabled: true, latest_seq: 10, events: [mkEvent(10)] });
        }
        if (eventsCall === 2) {
          return jsonResponse({ enabled: true, latest_seq: 3, events: [] });
        }
        return jsonResponse({
          enabled: true,
          latest_seq: 3,
          events: [mkEvent(1), mkEvent(2), mkEvent(3)],
        });
      }
      return jsonResponse({});
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });
    expect(result.current.events.map((event) => event.seq)).toEqual([10]);

    await tick(1000);

    expect(eventsUrls).toEqual([
      "/api/world/events?after=0&limit=300",
      "/api/world/events?after=10&limit=300",
      "/api/world/events?after=0&limit=300",
    ]);
    expect(result.current.events.map((event) => event.seq)).toEqual([1, 2, 3]);
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
      await tick(1000);
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

  it("runs a standard Telco process then refreshes world state", async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
      const value = String(url);
      if (value.includes("/api/world/processes/revenue-assurance/run")) {
        return jsonResponse({ ok: true, case_id: "CASE-BSS09-0001" });
      }
      if (value.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (value.includes("/api/world/events")) {
        return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      }
      return jsonResponse({});
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });

    await act(async () => {
      await result.current.runReferenceProcess("revenue-assurance");
      await flush();
    });

    const call = fetchMock.mock.calls.find((entry) =>
      String(entry[0]).includes("/api/world/processes/revenue-assurance/run")
    );
    expect(call?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
  });

  it("resets the active world and restarts the journal cursor", async () => {
    const eventUrls: string[] = [];
    const fetchMock = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
      const value = String(url);
      if (value.includes("/api/world/reset")) {
        return jsonResponse({ ok: true, seed: 42, sim_time: 0 });
      }
      if (value.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (value.includes("/api/world/events")) {
        eventUrls.push(value);
        return jsonResponse({
          enabled: true,
          latest_seq: eventUrls.length === 1 ? 4 : 0,
          events: eventUrls.length === 1 ? [mkEvent(4)] : [],
        });
      }
      return jsonResponse({});
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });
    expect(result.current.events).toHaveLength(1);

    await act(async () => {
      await result.current.resetWorld();
      await flush();
    });

    const resetCall = fetchMock.mock.calls.find((entry) =>
      String(entry[0]).includes("/api/world/reset")
    );
    expect(resetCall?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(eventUrls.at(-1)).toContain("after=0");
    expect(result.current.events).toEqual([]);
  });

  it("discards event responses that started before a reset", async () => {
    let resolveOldEvents: ((response: Response) => void) | undefined;
    const eventUrls: string[] = [];
    const fetchMock = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
      const value = String(url);
      if (value.includes("/api/world/reset")) {
        return jsonResponse({ ok: true, seed: 42, sim_time: 0 });
      }
      if (value.includes("/api/world/state")) return jsonResponse(BASE_STATE);
      if (value.includes("/api/world/events")) {
        eventUrls.push(value);
        if (eventUrls.length === 1) {
          return new Promise<Response>((resolve) => {
            resolveOldEvents = resolve;
          });
        }
        return jsonResponse({ enabled: true, latest_seq: 0, events: [] });
      }
      return jsonResponse({});
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const { result } = renderHook(() => useWorldSimulation());
    await act(async () => { await flush(); });

    await act(async () => {
      await result.current.resetWorld();
      resolveOldEvents?.(jsonResponse({
        enabled: true,
        latest_seq: 999,
        events: [mkEvent(999)],
      }));
      await flush();
    });
    await tick(1000);

    expect(result.current.events).toEqual([]);
    expect(eventUrls.at(-1)).toContain("after=0");
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
