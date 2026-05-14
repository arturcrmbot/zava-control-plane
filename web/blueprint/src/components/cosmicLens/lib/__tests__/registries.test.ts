import { describe, it, expect } from "vitest";
import {
  CityRegistry,
  FunctionRegistry,
  MoonRegistry,
  RocketRegistry,
  TrailRegistry,
} from "../registries";

describe("FunctionRegistry slotFor", () => {
  it("returns evenly-spaced angles around 2π", () => {
    const r = new FunctionRegistry();
    r.set("a", { key: "a", label: "A" });
    r.set("b", { key: "b", label: "B" });
    r.set("c", { key: "c", label: "C" });
    r.set("d", { key: "d", label: "D" });
    const angles = ["a", "b", "c", "d"].map((k) => r.slotFor(k).angle).sort((x, y) => x - y);
    // 4 functions → angles 0, π/2, π, 3π/2
    expect(angles[0]).toBeCloseTo(0);
    expect(angles[1]).toBeCloseTo(Math.PI / 2);
    expect(angles[2]).toBeCloseTo(Math.PI);
    expect(angles[3]).toBeCloseTo((3 * Math.PI) / 2);
  });
  it("falls back gracefully for unknown function", () => {
    const r = new FunctionRegistry();
    expect(r.slotFor("missing").angle).toBe(0);
    expect(r.slotFor("missing").radius).toBeGreaterThan(0);
  });
});

describe("MoonRegistry offsetFor", () => {
  it("is deterministic per workflow id", () => {
    const m = new MoonRegistry();
    expect(m.offsetFor("VKY-0001")).toBe(m.offsetFor("VKY-0001"));
  });
  it("differs across workflow ids", () => {
    const m = new MoonRegistry();
    const a = m.offsetFor("VKY-0001");
    const b = m.offsetFor("VKY-0002");
    expect(a).not.toBe(b);
  });
  it("returns values in [0, 1)", () => {
    const m = new MoonRegistry();
    for (const id of ["a", "b", "c", "d", "VKY-0042", "INV-9999"]) {
      const v = m.offsetFor(id);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe("CityRegistry positions", () => {
  it("stores and retrieves positions", () => {
    const c = new CityRegistry();
    c.set("city1", { id: "city1", kind: "mcp", label: "stripe.charge" });
    const positions = new Map<string, [number, number, number]>();
    positions.set("city1", [1, 0, 2]);
    c.setPositions(positions);
    expect(c.positionOf("city1")).toEqual([1, 0, 2]);
  });
  it("returns undefined for unknown id", () => {
    const c = new CityRegistry();
    expect(c.positionOf("nope")).toBeUndefined();
  });
});

describe("RocketRegistry (per-workflow)", () => {
  function newRocket(workflow_id: string, overrides: Partial<import("../types").Rocket> = {}): import("../types").Rocket {
    return {
      id: workflow_id,
      workflow_id,
      origin_workflow_id: workflow_id,
      phase: "idle",
      color: "#facc15",
      current_city_id: null,
      target_city_id: null,
      current_pos: [0, 0, 0],
      travel_from: null,
      travel_to: null,
      phase_started_at: 0,
      spawned_at: 0,
      is_wounded: false,
      ...overrides,
    };
  }

  it("upsertForWorkflow keeps a single entry per workflow_id", () => {
    const r = new RocketRegistry();
    r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1"));
    r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1"));
    expect(r.size()).toBe(1);
  });

  it("upsertForWorkflow returns the existing rocket on a second call", () => {
    const r = new RocketRegistry();
    const first = r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1", { color: "#aabbcc" }));
    const second = r.upsertForWorkflow("VKY-1", () => newRocket("VKY-1", { color: "#ddeeff" }));
    expect(second).toBe(first);
    expect(second.color).toBe("#aabbcc");
  });

  it("forWorkflow returns the same instance set by upsert", () => {
    const r = new RocketRegistry();
    const x = r.upsertForWorkflow("VKY-7", () => newRocket("VKY-7"));
    expect(r.forWorkflow("VKY-7")).toBe(x);
    expect(r.forWorkflow("missing")).toBeUndefined();
  });

  it("atCity filters rockets that are idle at that city", () => {
    const r = new RocketRegistry();
    r.upsertForWorkflow("a", () => newRocket("a", { phase: "idle", current_city_id: "city1" }));
    r.upsertForWorkflow("b", () => newRocket("b", { phase: "travelling", current_city_id: "city1" }));
    r.upsertForWorkflow("c", () => newRocket("c", { phase: "idle", current_city_id: "city2" }));
    expect(r.atCity("city1").map((x) => x.id).sort()).toEqual(["a"]);
  });

  it("pruneCompleted removes rockets whose phase is done", () => {
    const r = new RocketRegistry();
    r.upsertForWorkflow("d1", () => newRocket("d1", { phase: "done" }));
    r.upsertForWorkflow("d2", () => newRocket("d2", { phase: "burst" }));
    r.pruneCompleted();
    expect(r.has("d1")).toBe(false);
    expect(r.has("d2")).toBe(true);
  });

  it("recordVisit dedups consecutive identical city ids", () => {
    const r = new RocketRegistry();
    r.recordVisit("wf", "city_a", 1);
    r.recordVisit("wf", "city_a", 2);
    r.recordVisit("wf", "city_b", 3);
    expect(r.historyFor("wf").map((h) => h.city_id)).toEqual(["city_a", "city_b"]);
  });
});

describe("TrailRegistry", () => {
  it("decays samples over time", () => {
    const t = new TrailRegistry();
    t.push({ from: [0, 0, 0], to: [1, 0, 0], emitted_at: 0, color: "#fff" });
    expect(t.visible(30_000).length).toBe(1);
    expect(t.visible(60_000).length).toBe(0);
  });
  it("respects cap", () => {
    const t = new TrailRegistry(2);
    t.push({ from: [0, 0, 0], to: [1, 0, 0], emitted_at: 0, color: "#fff" });
    t.push({ from: [0, 0, 0], to: [2, 0, 0], emitted_at: 0, color: "#fff" });
    t.push({ from: [0, 0, 0], to: [3, 0, 0], emitted_at: 0, color: "#fff" });
    expect(t.size()).toBe(2);
  });
  it("computes alpha = 1 - age/decay", () => {
    const t = new TrailRegistry();
    t.push({ from: [0, 0, 0], to: [1, 0, 0], emitted_at: 0, color: "#fff" });
    const v = t.visible(30_000, 60_000);
    expect(v[0].alpha).toBeCloseTo(0.5);
  });
});
