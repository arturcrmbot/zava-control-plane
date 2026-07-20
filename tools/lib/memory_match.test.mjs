import { describe, it, expect } from "vitest";
import { workflowMemoryIdMatched } from "./memory_match.mjs";

// Regression coverage for the Fashion E2E proof's memory gate: it must
// require the domain's memory to reference the *exact* workflow id, not
// merely be non-empty for the domain. A prior version gated on
// `JSON.stringify(memoryList).includes(workflow.id)`, which is a substring
// test — it can spuriously match unrelated same-domain memory whenever one
// workflow id happens to be a substring of another (e.g. "wf-10" is a
// substring of "wf-100"), and it can never fail-closed on structure alone.

describe("workflowMemoryIdMatched", () => {
  it("matches when a memory entry references the exact workflow id", () => {
    const memoryList = [
      { id: "m1", memory: "restocked shelf", metadata: { workflow_id: "wf-10", domain: "inventory-rebalancing" } },
    ];

    expect(workflowMemoryIdMatched(memoryList, "wf-10")).toBe(true);
  });

  it("does not match unrelated same-domain memory for a different workflow", () => {
    const memoryList = [
      { id: "m1", memory: "unrelated note", metadata: { workflow_id: "wf-999", domain: "inventory-rebalancing" } },
    ];

    expect(workflowMemoryIdMatched(memoryList, "wf-10")).toBe(false);
  });

  it("does not accept an accidental substring collision (wf-100 must not match wf-10)", () => {
    // This is the exact failure mode of the old substring-based check: the
    // domain has genuine memory, just for a *different* workflow whose id
    // happens to contain the target id as a substring.
    const memoryList = [
      { id: "m1", memory: "closed out a return", metadata: { workflow_id: "wf-100", domain: "returns-disposition" } },
    ];

    expect(workflowMemoryIdMatched(memoryList, "wf-10")).toBe(false);
  });

  it("does not accept the target id appearing only inside an unrelated free-text field", () => {
    const memoryList = [
      { id: "m1", memory: "see also case referencing wf-10 in passing", metadata: { workflow_id: "wf-999" } },
    ];

    expect(workflowMemoryIdMatched(memoryList, "wf-10")).toBe(false);
  });

  it("fails closed on an empty memory list", () => {
    expect(workflowMemoryIdMatched([], "wf-10")).toBe(false);
  });

  it("matches when the exact id is nested anywhere in the entry (structured recursive match)", () => {
    const memoryList = [
      { id: "m1", metadata: { domain: "returns-disposition", links: { workflow_id: "wf-10" } } },
    ];

    expect(workflowMemoryIdMatched(memoryList, "wf-10")).toBe(true);
  });
});
