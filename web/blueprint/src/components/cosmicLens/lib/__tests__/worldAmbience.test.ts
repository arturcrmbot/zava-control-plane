import { describe, it, expect } from "vitest";
import { ambientRates, ambientSamples, AMBIENCE_WINDOW_MS } from "../worldAmbience";
import type { CosmicFlash } from "../types";

function activity(fn: string | undefined, count?: number): CosmicFlash {
  return { type: "world.activity", ts: 0, function: fn, world_type: "banking.payment.settled", count };
}

describe("ambientSamples", () => {
  it("keeps only world activity that names its function", () => {
    const samples = ambientSamples(
      [activity("payments", 4), activity(undefined, 9), { type: "persona.decided", ts: 0, function: "payments" }],
      1_000,
    );
    expect(samples).toEqual([{ at: 1_000, fn: "payments", count: 4 }]);
  });

  it("counts a flash without a count as one event", () => {
    expect(ambientSamples([activity("markets")], 5)[0].count).toBe(1);
  });
});

describe("ambientRates", () => {
  it("weights each flash by the events it coalesced", () => {
    const now = 120_000;
    const samples = [
      { at: now - 30_000, fn: "payments", count: 30 },
      { at: now - 10_000, fn: "payments", count: 30 },
      { at: now - 5_000, fn: "markets", count: 3 },
    ];
    const rates = ambientRates(samples, now, 0);
    expect(rates.get("payments")).toBe(60);
    expect(rates.get("markets")).toBe(3);
  });

  it("drops samples older than the window", () => {
    const now = 200_000;
    const rates = ambientRates([{ at: now - AMBIENCE_WINDOW_MS - 1, fn: "payments", count: 50 }], now, 0);
    expect(rates.has("payments")).toBe(false);
  });

  it("does not extrapolate the first seconds into a huge rate", () => {
    const now = 1_000_000;
    // One flash two seconds after mount: normalised over the 10s floor, not 2s.
    const rates = ambientRates([{ at: now, fn: "payments", count: 5 }], now, now - 2_000);
    expect(rates.get("payments")).toBe(30);
  });

  it("reports at least one event per minute for any live function", () => {
    const now = 100_000;
    const rates = ambientRates([{ at: now, fn: "credit-risk", count: 1 }], now, 0, 600_000);
    expect(rates.get("credit-risk")).toBe(1);
  });
});
