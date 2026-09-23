// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { EntitiesPage } from "../EntitiesPage";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    counts: { Person: 100, Brand: 8, Campaign: 14, Pitch: 5, MediaPlan: 3, Subsidiary: 5, Workflow: 200 },
    hot: [], recentLinks: [],
  }), { status: 200, headers: { "Content-Type": "application/json" } })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("EntitiesPage", () => {
  it("lists the core kinds and every kind the graph holds", async () => {
    render(<EntitiesPage />);
    for (const k of ["Person", "Organisation", "Asset", "Money", "Decision",
                     "Place", "Period", "Workflow", "Brand", "Campaign",
                     "Pitch", "MediaPlan", "Subsidiary"]) {
      expect(await screen.findByRole("option", { name: k })).toBeTruthy();
    }
  });

  it("hides a kind this graph holds none of", async () => {
    render(<EntitiesPage />);
    await screen.findByRole("option", { name: "Brand" });
    expect(screen.queryByRole("option", { name: "Account" })).toBeNull();
    expect(screen.queryByRole("option", { name: "CostCentre" })).toBeNull();
  });
});
