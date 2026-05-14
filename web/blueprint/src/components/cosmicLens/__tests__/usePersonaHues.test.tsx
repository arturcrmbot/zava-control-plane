// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { usePersonaHues } from "../usePersonaHues";

describe("usePersonaHues", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    // Each test installs its own fetch mock.
  });
  afterEach(() => {
    global.fetch = realFetch;
    vi.restoreAllMocks();
  });

  it("fetches /api/personas/colors and exposes the role→hue map", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ cfo: "#4f9bff", cpo: "#ff7e9b", neutral: null }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => usePersonaHues());
    await waitFor(() => expect(result.current.cfo).toBe("#4f9bff"));
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/colors");
    expect(result.current).toEqual({ cfo: "#4f9bff", cpo: "#ff7e9b" });
  });

  it("returns an empty map when the fetch fails", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down")) as unknown as typeof fetch;
    const { result } = renderHook(() => usePersonaHues());
    // Give the rejected promise a tick to settle.
    await new Promise((r) => setTimeout(r, 0));
    expect(result.current).toEqual({});
  });

  it("returns an empty map when the response is not ok", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({}),
    }) as unknown as typeof fetch;
    const { result } = renderHook(() => usePersonaHues());
    await new Promise((r) => setTimeout(r, 0));
    expect(result.current).toEqual({});
  });
});
