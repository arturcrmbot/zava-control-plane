// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("react-force-graph-2d", () => ({
  default: () => <div data-testid="knowledge-force-graph" />,
}));

import Knowledge from "../Knowledge";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Knowledge", () => {
  it("visibly filters an exact changed relationship from the real graph payload", async () => {
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      disconnect() {}
    });
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL) => {
      const url = String(input);
      if (url.startsWith("/api/entities/_graph")) {
        return new Response(JSON.stringify({
          nodes: [
            { id: "BKG-4", kind: "Asset" },
            { id: "FLT-ZV205", kind: "Asset" },
          ],
          edges: [{ src: "BKG-4", dst: "FLT-ZV205", rel: "RELATED_ASSET" }],
        }), { status: 200 });
      }
      if (url === "/api/entities/_kinds") {
        return new Response(JSON.stringify({ kinds: [] }), { status: 200 });
      }
      throw new Error(`unexpected fetch ${url}`);
    }));

    render(<MemoryRouter><Knowledge /></MemoryRouter>);

    const search = await screen.findByRole("textbox", { name: "Relationship search" });
    fireEvent.change(search, { target: { value: "BKG-4" } });

    expect((await screen.findByTestId(
      "knowledge-edge-BKG-4-RELATED_ASSET-FLT-ZV205",
    )).textContent).toContain("BKG-4 RELATED_ASSET FLT-ZV205");
  });
});
