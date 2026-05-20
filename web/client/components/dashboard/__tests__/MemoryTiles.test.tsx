// @vitest-environment jsdom
import { describe, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import MemoryTiles from "../MemoryTiles";


beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes("/api/memory/lessons/active")) {
      return new Response(JSON.stringify({ items: [{ id: "L1" }, { id: "L2" }] }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }) as unknown as typeof fetch;
});


describe("MemoryTiles", () => {
  it("renders the Lessons active count from /api/memory/lessons/active", async () => {
    render(<MemoryTiles />);
    await waitFor(() => screen.getByText(/Lessons active/i));
    await waitFor(() => screen.getByText("2"));
  });
});
