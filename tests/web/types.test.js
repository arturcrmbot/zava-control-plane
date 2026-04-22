// control-plane/tests/unit/types.test.ts
import { describe, it, expect } from "vitest";
import { nextPhase, PHASE_ORDER } from "@shared/types";
describe("nextPhase", () => {
    it("returns next phase in order", () => {
        expect(nextPhase("Intake")).toBe("Validation");
        expect(nextPhase("Approval")).toBe("Payment");
    });
    it("returns null for last phase", () => {
        expect(nextPhase("Reconciliation")).toBeNull();
    });
    it("phase order is six long", () => {
        expect(PHASE_ORDER).toHaveLength(6);
    });
});
