import { describe, expect, it } from "vitest";
import {
  buildWorkflowTypeIndex,
  computeCrossFunctionBeams,
  type HotEntity,
  type OrgFunction,
} from "./useOrgData";

const fn = (name: string, owns: string[]): OrgFunction => ({
  name,
  display: name,
  operatorSurface: name,
  ownsDomains: owns,
  ambientAgents: [],
  kpis: [],
  personaHierarchy: { role: name, manages: [] },
});

describe("buildWorkflowTypeIndex", () => {
  it("maps every owned domain back to its function", () => {
    const idx = buildWorkflowTypeIndex([
      fn("finance", ["vendor_kyc", "expense_claim"]),
      fn("hr", ["hiring"]),
    ]);
    expect(idx.get("vendor_kyc")).toBe("finance");
    expect(idx.get("hiring")).toBe("hr");
    expect(idx.size).toBe(3);
  });
});

describe("computeCrossFunctionBeams", () => {
  const idx = buildWorkflowTypeIndex([
    fn("finance", ["vendor_kyc"]),
    fn("hr", ["hiring"]),
    fn("legal", ["contract_review"]),
  ]);

  it("emits a beam when an entity is touched by 2+ functions", () => {
    const now = 1_000_000;
    const hot: HotEntity[] = [
      {
        entity_id: "ORG-1",
        kind: "Organisation",
        source_workflows: ["vendor_kyc", "hiring"],
        updated_at: now / 1000,
      },
    ];
    const beams = computeCrossFunctionBeams(hot, idx, now);
    expect(beams).toHaveLength(1);
    expect([beams[0].fromFn, beams[0].toFn].sort()).toEqual(["finance", "hr"]);
    expect(beams[0].weight).toBe(1);
  });

  it("emits no beam when an entity has only one function", () => {
    const hot: HotEntity[] = [
      {
        entity_id: "X",
        kind: "Person",
        source_workflows: ["vendor_kyc"],
        updated_at: Date.now() / 1000,
      },
    ];
    expect(computeCrossFunctionBeams(hot, idx)).toHaveLength(0);
  });

  it("aggregates weight across multiple cross-cutting entities", () => {
    const now = 1_000_000;
    const hot: HotEntity[] = [
      { entity_id: "A", kind: "Organisation", source_workflows: ["vendor_kyc", "hiring"], updated_at: now / 1000 },
      { entity_id: "B", kind: "Organisation", source_workflows: ["vendor_kyc", "hiring"], updated_at: now / 1000 },
      { entity_id: "C", kind: "Organisation", source_workflows: ["vendor_kyc", "contract_review"], updated_at: now / 1000 },
    ];
    const beams = computeCrossFunctionBeams(hot, idx, now);
    const financeHr = beams.find((b) => b.fromFn === "finance" && b.toFn === "hr");
    expect(financeHr?.weight).toBe(2);
    const financeLegal = beams.find((b) => b.fromFn === "finance" && b.toFn === "legal");
    expect(financeLegal?.weight).toBe(1);
  });

  it("drops stale entities (>30s old)", () => {
    const now = 1_000_000_000;
    const hot: HotEntity[] = [
      {
        entity_id: "STALE",
        kind: "Organisation",
        source_workflows: ["vendor_kyc", "hiring"],
        updated_at: (now - 60_000) / 1000,
      },
    ];
    expect(computeCrossFunctionBeams(hot, idx, now)).toHaveLength(0);
  });
});
