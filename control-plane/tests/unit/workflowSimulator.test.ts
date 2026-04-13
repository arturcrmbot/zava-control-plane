import { describe, it, expect } from "vitest";
import { pickScenario, buildSeedWorkflow } from "@server/services/workflowSimulator";

describe("pickScenario", () => {
  it("returns 'normal' most often", () => {
    const rng = () => 0.95;
    expect(pickScenario(rng)).toBe("normal");
  });
  it("returns 'duplicate-invoice' at lowest bucket", () => {
    const rng = () => 0.05;
    expect(pickScenario(rng)).toBe("duplicate-invoice");
  });
});

describe("buildSeedWorkflow", () => {
  it("creates Workflow with Intake phase and future SLA", () => {
    const w = buildSeedWorkflow("INV-001", () => 0.5);
    expect(w.currentPhase).toBe("Intake");
    expect(w.slaDueAt).toBeGreaterThan(w.createdAt);
  });
});
