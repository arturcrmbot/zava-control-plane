import { describe, expect, it } from "vitest";
import {
  ambientSensorPosition,
  floorY,
  lobbyKindPosition,
  windowPosition,
} from "./floorLayout";

describe("floorLayout", () => {
  it("places the lobby at y=0 and the floors above it", () => {
    expect(floorY("customer-success")).toBe(1);
    expect(floorY("ceo")).toBe(10);
  });

  it("returns null for unknown floor names", () => {
    expect(floorY("unknown")).toBeNull();
    expect(windowPosition("nope", "wf-1")).toBeNull();
    expect(lobbyKindPosition("Banana")).toBeNull();
  });

  it("assigns deterministic window slots to a workflow id", () => {
    const a = windowPosition("finance", "wf-abc");
    const b = windowPosition("finance", "wf-abc");
    const c = windowPosition("finance", "wf-xyz");
    expect(a).not.toBeNull();
    expect(a).toEqual(b);
    expect(a).not.toEqual(c);
  });

  it("places lobby kind icons across the lobby front", () => {
    const person = lobbyKindPosition("Person");
    const period = lobbyKindPosition("Period");
    expect(person).not.toBeNull();
    expect(period).not.toBeNull();
    // Person is the leftmost, Period the rightmost.
    expect(person![0]).toBeLessThan(period![0]);
  });

  it("stacks ambient sensor positions on the floor's right edge", () => {
    const a = ambientSensorPosition("revenue", 0, 2);
    const b = ambientSensorPosition("revenue", 1, 2);
    expect(a).not.toBeNull();
    expect(b).not.toBeNull();
    // Two agents → vertically distinct on the same floor.
    expect(a![0]).toBeCloseTo(b![0]);
    expect(a![1]).not.toBeCloseTo(b![1]);
  });
});
