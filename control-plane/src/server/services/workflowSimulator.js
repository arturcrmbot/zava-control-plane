// src/server/services/workflowSimulator.ts
import { createRequire } from "module";
import { nanoid } from "nanoid";
import { PHASE_ORDER, nextPhase } from "@shared/types";
import { callMcp } from "./mcpClient";
const require = createRequire(import.meta.url);
const vendorsFixture = require("../fixtures/vendors.json");
const poFixture = require("../fixtures/purchase-orders.json");
const agenciesFixture = require("../fixtures/agencies.json");
const SCENARIO_DISTRIBUTION = [
    { p: 0.10, s: "duplicate-invoice" },
    { p: 0.15, s: "po-mismatch" },
    { p: 0.08, s: "threshold-exceeded" },
    { p: 0.05, s: "sanctions-flag" },
    { p: 0.02, s: "payment-timeout" },
    { p: 0.01, s: "compliance" },
    // remainder is normal (~0.59)
];
export function pickScenario(rng = Math.random) {
    const r = rng();
    let acc = 0;
    for (const { p, s } of SCENARIO_DISTRIBUTION) {
        acc += p;
        if (r < acc)
            return s;
    }
    return "normal";
}
export function buildSeedWorkflow(id, rng = Math.random) {
    const vendor = vendorsFixture[Math.floor(rng() * vendorsFixture.length)];
    const po = poFixture[Math.floor(rng() * poFixture.length)];
    const agency = agenciesFixture[Math.floor(rng() * agenciesFixture.length)];
    const now = Date.now();
    return {
        id, type: "invoice-p2p", status: "in_progress", currentPhase: "Intake",
        createdAt: now, slaDueAt: now + (1 + rng() * 4) * 3_600_000,
        vendor: { id: vendor.id, name: vendor.name, country: vendor.country },
        invoice: {
            number: `INV-${nanoid(6).toUpperCase()}`,
            amount: Math.round(po.amount * (0.98 + rng() * 0.05) * 100) / 100,
            currency: po.currency,
            lineItems: Array.from({ length: po.lineCount }, (_, i) => ({
                description: `Line ${i + 1}`, qty: 1, unitPrice: po.amount / po.lineCount
            })),
            poRef: po.id
        },
        jurisdiction: `${vendor.country}-CA`,
        agency: agency.id,
        actionLedger: [], tokensSpent: 0, costUSD: 0
    };
}
function mkSpan(workflowId, phase, name, startMs, endMs, attrs = {}) {
    return {
        traceId: workflowId,
        spanId: nanoid(12),
        name, startMs, endMs,
        attributes: { "workflow.id": workflowId, "workflow.phase": phase, ...attrs },
        status: "ok"
    };
}
export class WorkflowSimulator {
    deps;
    seq = 0;
    paymentTimeoutDone = new Set();
    constructor(deps) {
        this.deps = deps;
    }
    async spawn(forcedScenario) {
        this.seq++;
        const id = `INV-${String(this.seq).padStart(4, "0")}`;
        const w = buildSeedWorkflow(id);
        this.deps.store.upsertWorkflow(w);
        this.deps.bus.emit({ type: "workflow.started", workflowId: id });
        void this.runLifecycle(id, forcedScenario ?? pickScenario());
        return id;
    }
    sleep(min, max) {
        return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
    }
    async runLifecycle(workflowId, scenario) {
        for (const phase of PHASE_ORDER) {
            await this.runPhase(workflowId, phase, scenario);
            const w = this.deps.store.getWorkflow(workflowId);
            if (!w || w.status === "failed" || w.status === "awaiting_hitl")
                return;
            const next = nextPhase(phase);
            if (next) {
                w.currentPhase = next;
                this.deps.store.upsertWorkflow(w);
            }
        }
        const w = this.deps.store.getWorkflow(workflowId);
        if (w) {
            w.status = "completed";
            this.deps.store.upsertWorkflow(w);
            this.deps.bus.emit({ type: "workflow.resolved", workflowId, resolution: "completed" });
        }
    }
    async runPhase(workflowId, phase, scenario) {
        const start = Date.now();
        this.deps.store.appendPhase(workflowId, {
            workflowId, name: phase, status: "in_progress",
            startedAt: start, agentId: "finance-agent", toolCalls: [], spanIds: []
        });
        this.deps.bus.emit({ type: "workflow.phase.started", workflowId, phase });
        try {
            switch (phase) {
                case "Intake":
                    await this.doIntake(workflowId);
                    break;
                case "Validation":
                    await this.doValidation(workflowId, scenario);
                    break;
                case "Routing":
                    await this.doRouting(workflowId, scenario);
                    break;
                case "Approval":
                    await this.doApproval(workflowId, scenario);
                    break;
                case "Payment":
                    await this.doPayment(workflowId, scenario);
                    break;
                case "Reconciliation":
                    await this.doReconciliation(workflowId);
                    break;
            }
        }
        catch (err) {
            const reason = err instanceof Error ? err.message : String(err);
            const w = this.deps.store.getWorkflow(workflowId);
            if (w) {
                w.status = "failed";
                this.deps.store.upsertWorkflow(w);
            }
            this.deps.bus.emit({ type: "workflow.phase.failed", workflowId, phase, reason });
            return;
        }
        const end = Date.now();
        this.deps.store.updatePhase(workflowId, phase, { status: "completed", completedAt: end });
        const span = mkSpan(workflowId, phase, `phase:${phase}`, start, end);
        this.deps.store.appendSpan(span);
        this.deps.bus.emit({ type: "otel.span.emitted", span });
        this.deps.bus.emit({ type: "workflow.phase.completed", workflowId, phase, durationMs: end - start });
    }
    // ---- Phases ----
    async doIntake(workflowId) {
        await this.sleep(1000, 3000);
        const w = this.deps.store.getWorkflow(workflowId);
        await this.traceTool(workflowId, "Intake", "workday.getVendor", async () => callMcp(this.deps.env.workdayUrl, "getVendor", { vendorId: w.vendor.id }));
        await this.traceTool(workflowId, "Intake", "d365.parseInvoice", async () => callMcp(this.deps.env.d365Url, "parseInvoice", { raw: w.invoice.number }));
    }
    async doValidation(workflowId, scenario) {
        await this.sleep(3000, 8000);
        const w = this.deps.store.getWorkflow(workflowId);
        if (scenario === "duplicate-invoice") {
            this.emitException(workflowId, "duplicate-invoice", "high");
            return;
        }
        const match = await this.traceTool(workflowId, "Validation", "d365.matchPO", async () => callMcp(this.deps.env.d365Url, "matchPO", { invoiceAmount: w.invoice.amount, poId: w.invoice.poRef }));
        if (scenario === "po-mismatch") {
            this.emitException(workflowId, "po-mismatch", "high");
            return;
        }
        void match;
        if (scenario === "sanctions-flag") {
            this.emitException(workflowId, "sanctions-flag", "critical");
            return;
        }
        if (scenario === "compliance") {
            this.emitException(workflowId, "compliance", "critical");
            return;
        }
    }
    async doRouting(workflowId, _scenario) {
        await this.sleep(2000, 5000);
        await this.traceTool(workflowId, "Routing", "workday.getCostCentre", async () => callMcp(this.deps.env.workdayUrl, "getCostCentre", { costCentreId: "CC-001" }));
        await this.traceTool(workflowId, "Routing", "d365.postGLEntry", async () => callMcp(this.deps.env.d365Url, "postGLEntry", { glAccountId: "GL-5000", amount: 0, workflowId }));
    }
    async doApproval(workflowId, scenario) {
        await this.sleep(2000, 5000);
        if (scenario === "threshold-exceeded") {
            this.deps.bus.emit({ type: "workflow.hitl.requested", workflowId, reason: "threshold_exceeded" });
            const w = this.deps.store.getWorkflow(workflowId);
            w.status = "awaiting_hitl";
            this.deps.store.upsertWorkflow(w);
            return;
        }
        await this.traceTool(workflowId, "Approval", "workday.getApprovalChain", async () => callMcp(this.deps.env.workdayUrl, "getApprovalChain", { scenario: "default" }));
    }
    async doPayment(workflowId, scenario) {
        await this.sleep(1000, 2000);
        const w = this.deps.store.getWorkflow(workflowId);
        const file = await this.traceTool(workflowId, "Payment", "payment.createPaymentFile", async () => callMcp(this.deps.env.paymentUrl, "createPaymentFile", { workflowId, amount: w.invoice.amount }));
        const simulateTimeout = scenario === "payment-timeout";
        try {
            await this.traceTool(workflowId, "Payment", "payment.submitPayment", async () => callMcp(this.deps.env.paymentUrl, "submitPayment", {
                paymentFileId: file.paymentFileId,
                simulateTimeout: simulateTimeout && !this.paymentTimeoutDone.has(workflowId)
            }));
        }
        catch {
            this.paymentTimeoutDone.add(workflowId);
            await this.sleep(500, 1000);
            await this.traceTool(workflowId, "Payment", "payment.submitPayment.retry", async () => callMcp(this.deps.env.paymentUrl, "submitPayment", { paymentFileId: file.paymentFileId, simulateTimeout: false }));
        }
    }
    async doReconciliation(workflowId) {
        await this.sleep(1000, 4000);
        await this.traceTool(workflowId, "Reconciliation", "payment.reconcileStatement", async () => callMcp(this.deps.env.paymentUrl, "reconcileStatement", { statementId: "STMT-2026-04-10" }));
    }
    async traceTool(workflowId, phase, name, fn) {
        const start = Date.now();
        let ok = true;
        try {
            const out = await fn();
            return out;
        }
        catch (e) {
            ok = false;
            throw e;
        }
        finally {
            const end = Date.now();
            const span = {
                traceId: workflowId, spanId: nanoid(12),
                name, startMs: start, endMs: end,
                attributes: { "workflow.id": workflowId, "workflow.phase": phase, "tool.name": name },
                status: ok ? "ok" : "error"
            };
            this.deps.store.appendSpan(span);
            this.deps.bus.emit({ type: "otel.span.emitted", span });
        }
    }
    emitException(workflowId, category, severity) {
        const w = this.deps.store.getWorkflow(workflowId);
        if (!w)
            return;
        w.status = "awaiting_hitl";
        this.deps.store.upsertWorkflow(w);
        this.deps.bus.emit({ type: "workflow.exception.detected", workflowId, category, severity });
    }
}
