import { describe, it, expect } from "vitest";
import { Triage } from "@server/services/triage";
describe("Triage", () => {
    it("does not wake on phase.started", () => {
        const t = new Triage();
        expect(t.shouldWake({ type: "workflow.phase.started", workflowId: "A", phase: "Intake" })).toBe(false);
    });
    it("wakes on exception.detected", () => {
        const t = new Triage();
        expect(t.shouldWake({ type: "workflow.exception.detected", workflowId: "A", category: "duplicate-invoice", severity: "high" })).toBe(true);
    });
    it("detects fleet anomaly on 3+ duplicates in 60s", () => {
        const t = new Triage();
        const now = Date.now();
        for (let i = 0; i < 3; i++) {
            t.observe({ type: "workflow.exception.detected", workflowId: `W-${i}`, category: "duplicate-invoice", severity: "high" }, now + i);
        }
        expect(t.detectAnomaly(now + 3)).toMatchObject({ pattern: "duplicate-burst" });
    });
});
