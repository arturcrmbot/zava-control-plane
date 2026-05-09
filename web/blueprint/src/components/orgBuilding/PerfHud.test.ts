import { describe, expect, it } from "vitest";
import { summarise } from "./PerfHud";

describe("PerfHud.summarise", () => {
  it("returns zeros for empty samples", () => {
    expect(summarise([])).toEqual({ fpsAvg: 0, fpsMin: 0, fpsLast: 0 });
  });

  it("computes avg / min / last fps from frame deltas in ms", () => {
    // 16.67ms ≈ 60fps, 33.33ms ≈ 30fps.
    const s = summarise([16.67, 16.67, 33.33, 16.67]);
    // Avg dt = 20.835ms → 48fps
    expect(Math.round(s.fpsAvg)).toBe(48);
    // Min fps comes from worst (longest) frame.
    expect(Math.round(s.fpsMin)).toBe(30);
    // Last frame was a fast one.
    expect(Math.round(s.fpsLast)).toBe(60);
  });

  it("handles single-sample windows", () => {
    const s = summarise([16.67]);
    expect(Math.round(s.fpsAvg)).toBe(60);
    expect(Math.round(s.fpsMin)).toBe(60);
    expect(Math.round(s.fpsLast)).toBe(60);
  });
});
