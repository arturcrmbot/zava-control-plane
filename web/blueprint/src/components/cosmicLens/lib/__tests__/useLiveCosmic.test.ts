// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useLiveCosmic } from "../useLiveCosmic";

// Matches CITIES_POLL_MS in useLiveCosmic.ts (capabilities mode).
const CITIES_POLL_MS = 30_000;

class MockEventSource {
  url: string;
  onerror: ((e: unknown) => void) | null = null;
  private listeners = new Map<string, Array<(e: unknown) => void>>();
  constructor(url: string) {
    this.url = url;
  }
  addEventListener(type: string, fn: (e: unknown) => void) {
    const arr = this.listeners.get(type) ?? [];
    arr.push(fn);
    this.listeners.set(type, arr);
  }
  close() {}
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function makeFetch(citiesResponse: () => Response | Promise<Response>) {
  return vi.fn(async (input: unknown) => {
    const url = typeof input === "string" ? input : String(input);
    if (url.includes("/api/cities")) {
      return await citiesResponse();
    }
    return jsonResponse([]);
  });
}

async function flushMicrotasks(times = 25) {
  for (let i = 0; i < times; i++) {
    await Promise.resolve();
  }
}

function citiesTimerCalls(spy: { mock: { calls: unknown[][] } }) {
  return (spy.mock.calls as unknown as Array<[unknown, number]>).filter(
    (c) => c[1] === CITIES_POLL_MS,
  );
}

describe("useLiveCosmic pollCities timer scheduling", () => {
  let setTimeoutSpy: { mock: { calls: unknown[][]; results: Array<{ value: unknown }> } };
  let clearTimeoutSpy: { mock: { calls: unknown[][] } };

  beforeEach(() => {
    vi.useFakeTimers();
    (globalThis as unknown as { EventSource: unknown }).EventSource = MockEventSource;
    setTimeoutSpy = vi.spyOn(globalThis, "setTimeout") as unknown as typeof setTimeoutSpy;
    clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout") as unknown as typeof clearTimeoutSpy;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    delete (globalThis as unknown as { EventSource?: unknown }).EventSource;
    delete (globalThis as unknown as { fetch?: unknown }).fetch;
  });

  it("schedules exactly one next-poll timer on the success path", async () => {
    (globalThis as unknown as { fetch: unknown }).fetch = makeFetch(() =>
      jsonResponse({ cities: [] }),
    );

    const { unmount } = renderHook(() => useLiveCosmic());
    await flushMicrotasks();

    expect(citiesTimerCalls(setTimeoutSpy)).toHaveLength(1);
    unmount();
  });

  it("schedules exactly one retry timer when the response is not ok", async () => {
    (globalThis as unknown as { fetch: unknown }).fetch = makeFetch(() =>
      new Response("nope", { status: 503 }),
    );

    const { unmount } = renderHook(() => useLiveCosmic());
    await flushMicrotasks();

    expect(citiesTimerCalls(setTimeoutSpy)).toHaveLength(1);
    unmount();
  });

  it("schedules exactly one retry timer when fetch rejects", async () => {
    (globalThis as unknown as { fetch: unknown }).fetch = vi.fn(
      async (input: unknown) => {
        const url = typeof input === "string" ? input : String(input);
        if (url.includes("/api/cities")) {
          throw new Error("network down");
        }
        return jsonResponse([]);
      },
    );

    const { unmount } = renderHook(() => useLiveCosmic());
    await flushMicrotasks();

    expect(citiesTimerCalls(setTimeoutSpy)).toHaveLength(1);
    unmount();
  });

  it("clears the pending pollCities timer on unmount", async () => {
    (globalThis as unknown as { fetch: unknown }).fetch = makeFetch(() =>
      jsonResponse({ cities: [] }),
    );

    const { unmount } = renderHook(() => useLiveCosmic());
    await flushMicrotasks();

    const citiesCalls = citiesTimerCalls(setTimeoutSpy);
    expect(citiesCalls).toHaveLength(1);

    const citiesHandle = (setTimeoutSpy.mock.results as Array<{ value: unknown }>)[
      (setTimeoutSpy.mock.calls as unknown as Array<[unknown, number]>).findIndex(
        (c) => c[1] === CITIES_POLL_MS,
      )
    ].value;

    unmount();

    const clearedHandles = (clearTimeoutSpy.mock.calls as unknown as Array<[unknown]>).map(
      (c) => c[0],
    );
    expect(clearedHandles).toContain(citiesHandle);
  });
});
