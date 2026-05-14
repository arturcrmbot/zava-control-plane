import { describe, it, expect } from "vitest";
import {
  keyAttrFor, verdictColor, extractEntityIdRefs, formatRelative, parseTimestamp,
} from "../entityRender";

describe("keyAttrFor", () => {
  it("Person picks name then role", () => {
    expect(keyAttrFor("Person", { name: "Aisha" })).toBe("Aisha");
    expect(keyAttrFor("Person", { role: "Engineer" })).toBe("Engineer");
    expect(keyAttrFor("Person", {})).toBe("(unnamed)");
  });
  it("Organisation appends risk_band when set", () => {
    expect(keyAttrFor("Organisation", { name: "Globex", risk_band: "amber" })).toBe("Globex · amber");
    expect(keyAttrFor("Organisation", { name: "Globex" })).toBe("Globex");
  });
  it("Money formats amount + currency + kind", () => {
    expect(keyAttrFor("Money", { amount: 1450, currency: "GBP", kind: "invoice" })).toBe("GBP 1450 · invoice");
  });
  it("Decision combines verdict and truncated reason", () => {
    const long = "x".repeat(80);
    const out = keyAttrFor("Decision", { verdict: "approve", reason: long });
    expect(out.startsWith("approve: ")).toBe(true);
    expect(out.length).toBeLessThanOrEqual(70);
  });
});

describe("verdictColor", () => {
  it("maps known verdicts", () => {
    expect(verdictColor("approve")).toBe("#4ade80");
    expect(verdictColor("reject")).toBe("#ef4444");
    expect(verdictColor("escalate")).toBe("#fbbf24");
    expect(verdictColor(undefined)).toBe("#94a3b8");
  });
});

describe("extractEntityIdRefs", () => {
  it("matches PREFIX-suffix patterns", () => {
    expect(extractEntityIdRefs("MONEY-INV-API-0001")).toEqual(["MONEY-INV-API-0001"]);
    expect(extractEntityIdRefs("ORG-vendor-globex")).toEqual(["ORG-vendor-globex"]);
  });
  it("rejects plain text", () => {
    expect(extractEntityIdRefs("hello world")).toEqual([]);
    expect(extractEntityIdRefs(42)).toEqual([]);
  });
});

describe("formatRelative", () => {
  it("formats seconds/minutes/hours/days", () => {
    const now = 10_000_000;
    expect(formatRelative(now - 5_000, now)).toBe("5s ago");
    expect(formatRelative(now - 120_000, now)).toBe("2m ago");
    expect(formatRelative(now - 7200_000, now)).toBe("2h ago");
    expect(formatRelative(now - 2 * 86400_000, now)).toBe("2d ago");
  });
});

describe("parseTimestamp", () => {
  it("handles ISO strings and unix seconds and ms", () => {
    expect(parseTimestamp("2026-05-10T18:00:00Z")).toBe(Date.parse("2026-05-10T18:00:00Z"));
    expect(parseTimestamp(1778000000)).toBe(1778000000 * 1000);
    expect(parseTimestamp(1778000000000)).toBe(1778000000000);
    expect(parseTimestamp(null)).toBe(null);
  });
});
