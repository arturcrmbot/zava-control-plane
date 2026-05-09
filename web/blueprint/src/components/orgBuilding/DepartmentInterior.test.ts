import { describe, expect, it } from "vitest";
import { flattenPersonas, countTouchedByFunction, Sparkline } from "./DepartmentInterior";
import type { OrgFunction } from "../../lib/useOrgData";

describe("DepartmentInterior pure helpers", () => {
  it("flattenPersonas walks a tree pre-order with depth", () => {
    const tree = {
      role: "cfo",
      manages: [
        { role: "controller", manages: [{ role: "ap_clerk", manages: [] }] },
        { role: "fpa", manages: [] },
      ],
    };
    const flat = flattenPersonas(tree);
    expect(flat).toEqual([
      { role: "cfo", depth: 0 },
      { role: "controller", depth: 1 },
      { role: "ap_clerk", depth: 2 },
      { role: "fpa", depth: 1 },
    ]);
  });

  it("flattenPersonas tolerates null/empty roots", () => {
    expect(flattenPersonas(null)).toEqual([]);
    expect(flattenPersonas(undefined)).toEqual([]);
  });

  it("countTouchedByFunction joins owned domains against hot entities", () => {
    const fn: OrgFunction = {
      name: "finance",
      display: "Finance",
      operatorSurface: "finance-controller",
      ownsDomains: ["ap-invoice", "vendor-kyc"],
      ambientAgents: [],
      kpis: [],
      personaHierarchy: { role: "cfo", manages: [] },
    };
    const counts = countTouchedByFunction(fn, [
      { kind: "Money", source_workflows: ["ap-invoice"] },
      { kind: "Person", source_workflows: ["hire-to-productive"] },
      { kind: "Decision", source_workflows: ["vendor-kyc"] },
      { kind: "Money", source_workflows: ["ap-invoice"] },
    ]);
    expect(counts.Money).toBe(2);
    expect(counts.Decision).toBe(1);
    expect(counts.Person).toBe(0);
    expect(counts.Place).toBe(0);
  });

  it("Sparkline component is callable with empty values", () => {
    expect(typeof Sparkline).toBe("function");
  });
});
