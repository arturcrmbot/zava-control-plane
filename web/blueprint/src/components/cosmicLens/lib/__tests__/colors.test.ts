import { describe, it, expect } from "vitest";
import { colorForKind, colorForFunction, familyForFunction, colorForEntityType } from "../colors";

describe("colorForKind", () => {
  it("maps machine kinds to cool colors", () => {
    expect(colorForKind("mcp")).toMatch(/^#[0-9a-f]{6}$/i);
    expect(colorForKind("skill")).not.toBe(colorForKind("mcp"));
    expect(colorForKind("python")).not.toBe(colorForKind("skill"));
  });
  it("maps persona kind to a warm color (distinct from machines)", () => {
    const persona = colorForKind("persona");
    const mcp = colorForKind("mcp");
    expect(persona).not.toBe(mcp);
  });
  it("falls back to unknown for missing kind", () => {
    expect(colorForKind(undefined)).toMatch(/^#[0-9a-f]{6}$/i);
    expect(colorForKind("nonsense")).toMatch(/^#[0-9a-f]{6}$/i);
  });
  it("is case insensitive", () => {
    expect(colorForKind("MCP")).toBe(colorForKind("mcp"));
  });
});

describe("familyForFunction", () => {
  it("classifies finance variants", () => {
    expect(familyForFunction("vendor-kyc")).toBe("finance");
    expect(familyForFunction("ap-invoice")).toBe("finance");
    expect(familyForFunction("treasury-fx")).toBe("finance");
  });
  it("classifies HR variants", () => {
    expect(familyForFunction("hiring")).toBe("hr");
    expect(familyForFunction("perf-review")).toBe("hr");
  });
  it("classifies legal/creative", () => {
    expect(familyForFunction("legal-contracts")).toBe("legal");
    expect(familyForFunction("creative-campaign")).toBe("creative");
  });
  it("falls back to ops for unknown", () => {
    expect(familyForFunction("totally-made-up")).toBe("ops");
  });
});

describe("colorForFunction", () => {
  it("returns a hex color", () => {
    expect(colorForFunction("vendor-kyc")).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

describe("colorForEntityType", () => {
  it("returns distinct colors for known kinds", () => {
    expect(colorForEntityType("Person")).not.toBe(colorForEntityType("Money"));
  });
  it("falls back for unknown entity kinds", () => {
    expect(colorForEntityType("RandomKind")).toMatch(/^#[0-9a-f]{6}$/i);
  });
});
