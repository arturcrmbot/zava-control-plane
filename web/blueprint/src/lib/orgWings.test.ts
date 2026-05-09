import { describe, expect, it } from "vitest";
import { FLOOR_ORDER_TOP_DOWN } from "./floorLayout";
import { FLOOR_TO_WING, WINGS, WING_ORDER, wingForFloor } from "./orgWings";

describe("orgWings", () => {
  it("covers every floor in FLOOR_ORDER_TOP_DOWN exactly once", () => {
    const all = Object.values(WINGS).flat().sort();
    const expected = [...FLOOR_ORDER_TOP_DOWN].sort();
    expect(all).toEqual(expected);
  });

  it("FLOOR_TO_WING is a faithful inverse of WINGS", () => {
    for (const [wing, floors] of Object.entries(WINGS)) {
      for (const fn of floors) {
        expect(FLOOR_TO_WING[fn]).toBe(wing);
      }
    }
  });

  it("wingForFloor returns null for unknown floors", () => {
    expect(wingForFloor("not-a-floor")).toBeNull();
    expect(wingForFloor("finance")).toBe("Money");
  });

  it("WING_ORDER lists every wing exactly once", () => {
    expect(WING_ORDER.sort()).toEqual(Object.keys(WINGS).sort());
  });
});
