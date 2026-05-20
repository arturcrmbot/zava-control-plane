// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import {
  useActiveLessons,
  useDreamPassesRecent,
  useMemories,
  useWorkingNotes,
} from "../useMemoryQueries";

beforeEach(() => {
  (globalThis as any).EventSource = class {
    onmessage: ((ev: MessageEvent) => void) | null = null;
    addEventListener() {}
    close() {}
  };
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/lessons/active")) {
      return new Response(JSON.stringify({ items: [{ id: "L1", body: "x" }] }), { status: 200 });
    }
    if (u.includes("/api/memory/dream-passes/recent")) {
      return new Response(JSON.stringify({ items: [{ id: "D1", domain: "hiring" }] }), { status: 200 });
    }
    if (u.includes("/api/memory/v2/memories")) {
      return new Response(JSON.stringify({ memories: [{ id: "M1", memory: "Remember screening rubric" }], count: 1 }), { status: 200 });
    }
    if (u.includes("/api/memory/working-notes")) {
      return new Response(JSON.stringify({ items: [{ id: "N1" }] }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("useMemoryQueries", () => {
  it("loads active lessons", async () => {
    const { result } = renderHook(() => useActiveLessons("hiring"));
    await waitFor(() => expect(result.current.length).toBe(1));
    expect(result.current[0].id).toBe("L1");
  });

  it("loads recent dream passes", async () => {
    const { result } = renderHook(() => useDreamPassesRecent(10));
    await waitFor(() => expect(result.current.length).toBe(1));
    expect(result.current[0].id).toBe("D1");
  });

  it("loads working notes", async () => {
    const { result } = renderHook(() => useWorkingNotes(50));
    await waitFor(() => expect(result.current.length).toBe(1));
    expect(result.current[0].id).toBe("N1");
  });

  it("loads memories from the v2 endpoint", async () => {
    const { result } = renderHook(() => useMemories("hiring"));
    await waitFor(() => expect(result.current.count).toBe(1));
    expect(result.current.memories[0].id).toBe("M1");
  });

  it("encodes a domain filter when active lessons are requested for one domain", async () => {
    renderHook(() => useActiveLessons("vendor_kyc"));
    await waitFor(() => {
      const fm = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
      expect(fm.mock.calls.some(([u]) => String(u).includes("domain=vendor_kyc"))).toBe(true);
    });
  });

  it("encodes a domain filter when memories are requested for one domain", async () => {
    renderHook(() => useMemories("vendor_kyc"));
    await waitFor(() => {
      const fm = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
      expect(fm.mock.calls.some(([u]) => String(u).includes("/api/memory/v2/memories?domain=vendor_kyc"))).toBe(true);
    });
  });
});
