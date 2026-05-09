import { describe, expect, it } from "vitest";
import { isCrossFunction } from "./WorkflowZoom";

describe("WorkflowZoom helpers", () => {
  const idx = new Map([
    ["ap-invoice", "finance"],
    ["vendor-kyc", "finance"],
    ["hire-to-productive", "hr"],
    ["it-access-request", "tech"],
  ]);

  it("flags cross-function when entity also touches another function's workflow", () => {
    const e = {
      id: "ent-1",
      kind: "Money",
      source_workflows: ["ap-invoice", "hire-to-productive"],
    };
    expect(isCrossFunction(e, "ap-invoice", idx)).toBe(true);
  });

  it("returns false when all source workflows belong to the same function", () => {
    const e = {
      id: "ent-2",
      kind: "Money",
      source_workflows: ["ap-invoice", "vendor-kyc"],
    };
    expect(isCrossFunction(e, "ap-invoice", idx)).toBe(false);
  });

  it("returns false when this workflow type isn't indexed", () => {
    const e = {
      id: "ent-3",
      kind: "Person",
      source_workflows: ["hire-to-productive"],
    };
    expect(isCrossFunction(e, "unknown-type", idx)).toBe(false);
  });

  it("handles missing source_workflows", () => {
    expect(isCrossFunction({ id: "ent-4" }, "ap-invoice", idx)).toBe(false);
  });
});
