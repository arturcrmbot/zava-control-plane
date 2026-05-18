import { describe, it, expect } from "vitest";
import type { Workflow, Exception } from "@shared/types";
import {
  buildHITLCards,
  buildExceptionCards,
  buildExternalWaitCards,
  buildMilestoneCards,
  type FeedItem,
} from "../feedItems";

const baseWorkflow: Workflow = {
  id: "WF-1", type: "expense-claim",
  status: "in_progress",
  currentPhase: "Intake",
  createdAt: 1_000, slaDueAt: 9_999,
  jurisdiction: "UK", agency: "Zava",
  actionLedger: [], tokensSpent: 0, costUSD: 0,
};

describe("buildHITLCards", () => {
  it("emits one HITL item per awaiting_hitl workflow", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-1", status: "awaiting_hitl" },
      { ...baseWorkflow, id: "WF-2", status: "in_progress" },
      { ...baseWorkflow, id: "WF-3", status: "awaiting_hitl" },
    ];
    const cards = buildHITLCards(wfs);
    expect(cards.map((c) => c.id)).toEqual(["hitl:WF-1", "hitl:WF-3"]);
    expect(cards.every((c) => c.type === "hitl")).toBe(true);
  });

  it("derives timestamp from workflow.createdAt for ordering", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-A", status: "awaiting_hitl", createdAt: 500 },
    ];
    expect(buildHITLCards(wfs)[0].timestamp).toBe(500);
  });
});

describe("buildExceptionCards", () => {
  it("skips resolved exceptions", () => {
    const items: Exception[] = [
      { id: "E1", workflowId: "W1", composedBy: "fleet-manager", severity: "high",
        category: "compliance", summary: "x", recommendation: "y", options: [],
        relatedPolicyRefs: [], confidence: 0.5, createdAt: 1 },
      { id: "E2", workflowId: "W2", composedBy: "fleet-manager", severity: "critical",
        category: "compliance", summary: "x", recommendation: "y", options: [],
        relatedPolicyRefs: [], confidence: 0.5, createdAt: 2, resolvedAt: 5 },
    ];
    expect(buildExceptionCards(items).map((c) => c.id)).toEqual(["exception:E1"]);
  });
});

describe("buildExternalWaitCards", () => {
  it("matches workflows with metadata.wait_kind = external_party", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-7",
        metadata: { wait_kind: "external_party", awaiting_reason: "candidate-reply" } },
      { ...baseWorkflow, id: "WF-8",
        metadata: { wait_kind: "operator_review" } },
      { ...baseWorkflow, id: "WF-9" },
    ];
    expect(buildExternalWaitCards(wfs).map((c) => c.id)).toEqual(["external-wait:WF-7"]);
  });
});

describe("buildMilestoneCards", () => {
  it("emits one milestone per completed or failed workflow", () => {
    const wfs: Workflow[] = [
      { ...baseWorkflow, id: "WF-C", status: "completed" },
      { ...baseWorkflow, id: "WF-F", status: "failed" },
      { ...baseWorkflow, id: "WF-I", status: "in_progress" },
    ];
    const cards = buildMilestoneCards(wfs);
    expect(cards.map((c) => c.id).sort()).toEqual(["milestone:WF-C", "milestone:WF-F"]);
  });
});

describe("ordering helper", () => {
  it("FeedItem type discriminant works", () => {
    const it: FeedItem = {
      type: "hitl", id: "x", timestamp: 1,
      workflowId: "W", domain: "expense-claim", severity: "medium",
    };
    expect(it.type).toBe("hitl");
  });
});
