// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { loadGuidedJourney } from "../guidedJourney";

describe("loadGuidedJourney", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("replay: does not call fetch and returns six phases", async () => {
    const result = await loadGuidedJourney(true);
    expect(vi.mocked(global.fetch)).not.toHaveBeenCalled();
    expect(result.phases).toHaveLength(6);
    const phaseNames = result.phases.map((p) => p.phase);
    expect(phaseNames).toEqual([
      "overrun",
      "cfo_observe",
      "approve",
      "cfo_observe_post",
      "spawn_invoices",
      "ceo_synthesise",
    ]);
  });

  it("live: POSTs to the aurora arc endpoint and returns parsed result", async () => {
    const mockArc = {
      phases: [{ phase: "overrun", elapsed_ms: 1 }],
      total_elapsed_ms: 1,
      narrative: "test",
    };
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockArc), { status: 200 }),
    );

    const result = await loadGuidedJourney(false);
    expect(vi.mocked(global.fetch)).toHaveBeenCalledWith(
      "/api/demo/trigger/full-aurora-arc?delay_seconds=2.0&count=3",
      { method: "POST" },
    );
    expect(result.phases[0].phase).toBe("overrun");
  });

  it("live: throws with status message when response is not ok", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response("error", { status: 503 }),
    );

    await expect(loadGuidedJourney(false)).rejects.toThrow(
      "Could not start the Aurora journey (503)",
    );
  });
});
