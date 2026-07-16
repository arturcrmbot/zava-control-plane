// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { useRuntimeManifest } from "@client/hooks/useRuntimeManifest";

const agencyManifest = {
  vertical: {
    name: "agency",
    display_name: "Agency",
    manifest_version: "1",
    fingerprint: "agency:1",
  },
  world: null,
  world_scale: null,
  capabilities: ["blueprint", "compose", "knowledge", "memory"],
  ui: {
    lenses: ["agency-operations"],
    theme: { accent: "#2563eb", label: "Agency" },
  },
} as const;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useRuntimeManifest", () => {
  it("loads the active runtime manifest", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(agencyManifest), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRuntimeManifest());

    await waitFor(() => {
      expect(result.current.manifest).toEqual(agencyManifest);
    });
    expect(result.current.error).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runtime",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("surfaces a non-success response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("", { status: 503 })),
    );

    const { result } = renderHook(() => useRuntimeManifest());

    await waitFor(() => {
      expect(result.current.error).toBe("runtime manifest HTTP 503");
    });
    expect(result.current.manifest).toBeNull();
  });
});
