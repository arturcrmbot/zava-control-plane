// control-plane/tests/unit/events.test.ts
import { describe, it, expect } from "vitest";
import { wakesFleetManager, WAKE_TYPES } from "@shared/events";
describe("wakesFleetManager", () => {
    it("wakes on exception detected", () => {
        expect(wakesFleetManager({
            type: "workflow.exception.detected",
            workflowId: "INV-1",
            category: "duplicate-invoice",
            severity: "high"
        })).toBe(true);
    });
    it("does not wake on phase started", () => {
        expect(wakesFleetManager({
            type: "workflow.phase.started",
            workflowId: "INV-1",
            phase: "Intake"
        })).toBe(false);
    });
    it("wake set contains six entries", () => {
        expect(WAKE_TYPES.size).toBe(6);
    });
});
