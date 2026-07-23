// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, renderHook, waitFor } from "@testing-library/react";

import { useWorldScene } from "@client/hooks/useWorldScene";


afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("loads the pack-owned scene only for an active world", async () => {
  const scene = {
    enabled: true,
    schema_version: 1,
    title: "Demo world",
    locations: [],
    layers: [],
    event_mappings: [],
  };
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(scene), { status: 200 }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const { result } = renderHook(() => useWorldScene(true));

  await waitFor(() => expect(result.current.scene).toEqual(scene));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/world/scene",
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  );
});


it("does not fetch a scene when no actor world is active", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  const { result } = renderHook(() => useWorldScene(false));

  expect(result.current.scene).toBeNull();
  expect(result.current.loading).toBe(false);
  expect(fetchMock).not.toHaveBeenCalled();
});

