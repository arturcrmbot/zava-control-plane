// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useReplayMode } from "../useReplayMode";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useReplayMode", () => {
  it("does not assume live while metadata is pending", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const { result } = renderHook(useReplayMode);
    expect(result.current).toMatchObject({ source: { mode: "loading" } });
  });

  it.each([
    [{ mode: "live" }, { mode: "live" }],
    [
      { mode: "replay", recorded_at: "2026-05-22T19:26:10Z" },
      { mode: "replay", recordedAt: "2026-05-22T19:26:10Z" },
    ],
    [{ mode: "replay" }, { mode: "replay" }],
  ])("uses confirmed metadata %j", async (meta, source) => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(meta)));
    const { result } = renderHook(useReplayMode);
    await waitFor(() => expect(result.current).toMatchObject({ source }));
  });

  it.each([null, {}, { mode: "unknown" }, { mode: "replay", recorded_at: "not-a-date" }])(
    "surfaces invalid metadata %j",
    async (meta) => {
      vi.stubGlobal("fetch", vi.fn(async () => Response.json(meta)));
      const { result } = renderHook(useReplayMode);
      await waitFor(() => expect(result.current).toMatchObject({
        source: { mode: "unavailable" },
      }));
    },
  );

  it("does not assume live on an HTTP failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 503 })));
    const { result } = renderHook(useReplayMode);
    await waitFor(() => expect(result.current).toMatchObject({
      source: { mode: "unavailable", error: expect.stringContaining("503") },
    }));
  });

  it("can retry a failed probe", async () => {
    const fetch = vi.fn()
      .mockRejectedValueOnce(new Error("Offline"))
      .mockResolvedValueOnce(Response.json({ mode: "live" }));
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(useReplayMode);
    await waitFor(() => expect(result.current).toMatchObject({
      source: { mode: "unavailable", error: "Offline" },
    }));

    act(() => result.current.retry());

    await waitFor(() => expect(result.current).toMatchObject({
      source: { mode: "live" },
    }));
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
