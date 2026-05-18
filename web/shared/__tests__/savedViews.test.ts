import { describe, it, expect } from "vitest";
import type { SavedView } from "../roles";
import type { FeedItem } from "../feedItems";
import { matchesView } from "../savedViews";

const item: FeedItem = {
  type: "hitl",
  id: "hitl:WF-1",
  timestamp: 100,
  workflowId: "WF-1",
  domain: "expense-claim",
  severity: "high",
};

describe("matchesView", () => {
  it("matches when domains is empty (means: all)", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: [] };
    expect(matchesView(item, v)).toBe(true);
  });
  it("matches when item domain is in domains list", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: ["expense-claim"] };
    expect(matchesView(item, v)).toBe(true);
  });
  it("rejects when item domain is not in domains list", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: ["hiring"] };
    expect(matchesView(item, v)).toBe(false);
  });
  it("applies severity filter", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: [], severity: "critical" };
    expect(matchesView(item, v)).toBe(false);
  });
  it("applies search filter against workflowId", () => {
    const v: SavedView = { id: "v", label: "v", filter: "needs-you", domains: [], search: "wf-1" };
    expect(matchesView(item, v)).toBe(true);
    expect(matchesView(item, { ...v, search: "WF-99" })).toBe(false);
  });
});
