import { describe, expect, it } from "vitest";
import {
  animReducer,
  initialAnimState,
  KIND_CAPS,
  nextAnimId,
} from "./animationQueue";
import type { AnimEntry } from "./animationQueue";

function makeEntry(over: Partial<AnimEntry> = {}): AnimEntry {
  return {
    id: nextAnimId("test"),
    kind: "spark",
    from: [0, 0, 0],
    to: [1, 1, 1],
    color: "#ffffff",
    t: 0,
    lifetime: 1,
    ...over,
  };
}

describe("animReducer", () => {
  it("enqueues entries", () => {
    const s = animReducer(initialAnimState, {
      type: "enqueue",
      entry: makeEntry(),
    });
    expect(s.entries).toHaveLength(1);
  });

  it("ticks t forward and evicts at t>=1", () => {
    let s = animReducer(initialAnimState, {
      type: "enqueue",
      entry: makeEntry({ t: 0, lifetime: 1 }),
    });
    s = animReducer(s, { type: "tick", dt: 0.5 });
    expect(s.entries[0].t).toBeCloseTo(0.5);
    s = animReducer(s, { type: "tick", dt: 0.6 });
    expect(s.entries).toHaveLength(0);
  });

  it("respects per-kind caps (oldest evicted first)", () => {
    let s = initialAnimState;
    const cap = KIND_CAPS.spark;
    for (let i = 0; i < cap + 5; i += 1) {
      s = animReducer(s, {
        type: "enqueue",
        entry: makeEntry({ id: `s-${i}`, kind: "spark" }),
      });
    }
    const sparks = s.entries.filter((e) => e.kind === "spark");
    expect(sparks.length).toBe(cap);
    // The first 5 ids should be gone.
    expect(sparks.find((e) => e.id === "s-0")).toBeUndefined();
    expect(sparks.find((e) => e.id === `s-${cap + 4}`)).toBeDefined();
  });

  it("clearKind only removes the targeted kind", () => {
    let s = animReducer(initialAnimState, {
      type: "enqueue",
      entry: makeEntry({ kind: "spark" }),
    });
    s = animReducer(s, {
      type: "enqueue",
      entry: makeEntry({ kind: "mote", to: [1, 1, 1] }),
    });
    s = animReducer(s, { type: "clearKind", kind: "spark" });
    expect(s.entries).toHaveLength(1);
    expect(s.entries[0].kind).toBe("mote");
  });
});
