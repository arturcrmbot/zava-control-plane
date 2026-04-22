import { describe, it, expect, beforeEach } from "vitest";
import { StateStore } from "@server/services/stateStore";
const mkWorkflow = (id, overrides = {}) => ({
    id, type: "invoice-p2p", status: "in_progress", currentPhase: "Intake",
    createdAt: Date.now(), slaDueAt: Date.now() + 3_600_000,
    vendor: { id: "V-001", name: "Acme", country: "US" },
    invoice: { number: "INV-001", amount: 1000, currency: "USD", lineItems: [], poRef: "PO-10001" },
    jurisdiction: "US-CA", agency: "Ogilvy-US",
    actionLedger: [], tokensSpent: 0, costUSD: 0,
    ...overrides
});
describe("StateStore", () => {
    let store;
    beforeEach(() => { store = new StateStore(); });
    it("stores and retrieves workflows", () => {
        store.upsertWorkflow(mkWorkflow("A"));
        expect(store.getWorkflow("A")?.id).toBe("A");
    });
    it("lists workflows with filters", () => {
        store.upsertWorkflow(mkWorkflow("A", { status: "awaiting_hitl" }));
        store.upsertWorkflow(mkWorkflow("B", { status: "completed" }));
        const awaiting = store.listWorkflows({ status: "awaiting_hitl" });
        expect(awaiting).toHaveLength(1);
        expect(awaiting[0].id).toBe("A");
    });
    it("appends action ledger entries", () => {
        store.upsertWorkflow(mkWorkflow("A"));
        store.appendLedger("A", {
            workflowId: "A", timestamp: 1, actorKind: "agent", actorId: "finance-agent",
            action: "intake.started", revocable: true, details: {}
        });
        expect(store.getWorkflow("A")?.actionLedger).toHaveLength(1);
    });
});
