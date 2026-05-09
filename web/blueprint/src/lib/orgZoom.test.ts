import { describe, expect, it } from "vitest";
import {
  DEPARTMENT_FRAMING,
  ORG_FRAMING,
  WORKFLOW_FRAMING,
  framingFor,
  levelForKind,
  wingFraming,
} from "./orgZoom";

describe("orgZoom level numbering", () => {
  it("maps kinds to spec-level numbers", () => {
    expect(levelForKind("org")).toBe(3);
    expect(levelForKind("wing")).toBe(2);
    expect(levelForKind("department")).toBe(1);
    expect(levelForKind("workflow")).toBe(0);
  });

  it("framingFor returns the kind-appropriate framing", () => {
    expect(framingFor({ kind: "org" })).toEqual(ORG_FRAMING);
    expect(framingFor({ kind: "department" })).toEqual(DEPARTMENT_FRAMING);
    expect(framingFor({ kind: "workflow" })).toEqual(WORKFLOW_FRAMING);
  });

  it("wingFraming Y-targets the mean floor Y of the wing", () => {
    const money = wingFraming("Money");
    // Money = finance + revenue (two adjacent floors); framing should
    // sit somewhere in the middle of the building, not at the org default.
    expect(money.lookAt[1]).toBeGreaterThan(0);
    expect(money.fov).toBe(38);
  });

  it("wingFraming falls back to ORG_FRAMING for unknown wings", () => {
    expect(wingFraming("not-a-wing")).toEqual(ORG_FRAMING);
  });
});
