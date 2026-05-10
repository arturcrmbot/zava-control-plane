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

describe("RocketRegistry", () => {
  it("filters parked rockets at a city", () => {
    const r = new RocketRegistry();
    r.set("r1", {
      id: "r1",
      workflow_id: "VKY-1",
      city_id: "ap_clerk",
      label: "x",
      origin_workflow_id: "VKY-1",
      phase: "parked",
      dispatched_at: 0,
    });
    r.set("r2", {
      id: "r2",
      workflow_id: "VKY-2",
      city_id: "ap_clerk",
      label: "y",
      origin_workflow_id: "VKY-2",
      phase: "outbound",
      dispatched_at: 0,
    });
    expect(r.atCity("ap_clerk").map((x) => x.id)).toEqual(["r1"]);
  });
  it("prunes done rockets older than maxAgeMs", () => {
    const r = new RocketRegistry();
    r.set("r-old", {
      id: "r-old",
      workflow_id: "X",
      city_id: "c",
      label: "",
      origin_workflow_id: "X",
      phase: "done",
      dispatched_at: 0,
      returned_at: 0,
    });
    r.set("r-new", {
      id: "r-new",
      workflow_id: "Y",
      city_id: "c",
      label: "",
      origin_workflow_id: "Y",
      phase: "done",
      dispatched_at: 0,
      returned_at: 1000,
    });
    r.pruneCompleted(1100, 200);
    expect(r.has("r-old")).toBe(false);
    expect(r.has("r-new")).toBe(true);
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
