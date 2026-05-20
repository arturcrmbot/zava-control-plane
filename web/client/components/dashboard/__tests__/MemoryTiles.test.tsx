// @vitest-environment jsdom
import { describe, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import MemoryTiles from "../MemoryTiles";


beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/v2/memories?domain=hiring")) {
      return new Response(JSON.stringify({ memories: [{ id: "M1" }, { id: "M2" }], count: 2 }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("MemoryTiles", () => {
  it("renders the Memories count from /api/memory/v2/memories", async () => {
    render(<MemoryTiles />);
    await waitFor(() => screen.getByText(/Memories/i));
    await waitFor(() => screen.getByText("2"));
  });
});
