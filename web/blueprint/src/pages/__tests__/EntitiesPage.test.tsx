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
  it("lists all 15 kinds in the dropdown", async () => {
    render(<EntitiesPage />);
    for (const k of ["Person", "Organisation", "Asset", "Money", "Decision",
                     "Place", "Period", "Workflow", "Brand", "Campaign",
                     "Pitch", "MediaPlan", "Subsidiary", "Account", "CostCentre"]) {
      expect(await screen.findByRole("option", { name: k })).toBeTruthy();
    }
  });
});
