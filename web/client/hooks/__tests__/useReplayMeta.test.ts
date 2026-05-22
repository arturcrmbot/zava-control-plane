// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useReplayMeta } from "@client/hooks/useReplayMeta";

beforeEach(() => {
  globalThis.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("useReplayMeta", () => {
  it("fetches replay meta on mount", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ mode: "live" }),
    } as Response);

    const { result } = renderHook(() => useReplayMeta());

    await waitFor(() => expect(result.current).toEqual({ mode: "live" }));
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/replay/meta");
  });

  it("polls every 30 seconds", async () => {
    vi.useFakeTimers();
    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ mode: "live" }),
    } as Response);

    renderHook(() => useReplayMeta());

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2));
  });

  it("keeps the previous meta when a poll fails", async () => {
    vi.useFakeTimers();
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ mode: "replay", recorded_at: "2026-05-22T12:00:00.000Z" }),
      } as Response)
      .mockRejectedValueOnce(new Error("network down"));

    const { result } = renderHook(() => useReplayMeta());

    await waitFor(() => expect(result.current).toEqual({
      mode: "replay",
      recorded_at: "2026-05-22T12:00:00.000Z",
    }));

    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2));
    expect(result.current).toEqual({
      mode: "replay",
      recorded_at: "2026-05-22T12:00:00.000Z",
    });
  });
});
