import { describe, it, expect } from "vitest";
import { visibleKinds } from "../EntitiesPage";

describe("visibleKinds", () => {
  it("shows the core kinds and hides another pack's empty vocabulary", () => {
    const kinds = visibleKinds({ Person: 3, Account: 12, Brand: 0, Campaign: 0 });
    expect(kinds).toContain("Person");
    expect(kinds).toContain("Period");
    expect(kinds).toContain("Account");
    expect(kinds).not.toContain("Brand");
    expect(kinds).not.toContain("Campaign");
  });

  it("keeps the selected kind visible even when it has no rows", () => {
    expect(visibleKinds({}, "MediaPlan")).toContain("MediaPlan");
  });
});
