import { describe, it, expect } from "vitest";
import { ROLE_PRESETS, getRolePreset, type RoleId } from "../roles";

describe("role presets", () => {
  it("ships exactly five roles in the expected order", () => {
    expect(ROLE_PRESETS.map((r) => r.id)).toEqual([
      "ops-reviewer",
      "finance-controller",
      "hiring-manager",
      "sre",
      "executive",
    ] as RoleId[]);
  });

  it("ops-reviewer defaults to 'needs-you' and shows actionable card types", () => {
    const r = getRolePreset("ops-reviewer");
    expect(r.defaultFilter).toBe("needs-you");
    expect(r.hideActionButtons).toBe(false);
    expect(r.visibleCardTypes).toEqual(
      expect.arrayContaining(["hitl", "exception", "external-wait", "resolved"]),
    );
    expect(r.drawerSectionOrder).toEqual(["decision", "activity", "audit"]);
  });

  it("executive is read-only with audit-first drawer order", () => {
    const r = getRolePreset("executive");
    expect(r.hideActionButtons).toBe(true);
    expect(r.drawerSectionOrder[0]).toBe("audit");
    expect(r.visibleCardTypes).not.toContain("hitl");
  });

  it("finance-controller restricts default domains to finance prefixes", () => {
    const r = getRolePreset("finance-controller");
    expect(r.defaultDomains).toEqual([
      "expense-claim",
      "ap-invoice",
      "purchase-order",
      "treasury-fx",
      "contract-renewal",
    ]);
  });

  it("getRolePreset falls back to ops-reviewer for unknown ids", () => {
    expect(getRolePreset("nope" as RoleId).id).toBe("ops-reviewer");
  });
});
