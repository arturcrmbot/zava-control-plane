import { wakesFleetManager } from "@shared/events";
export class Triage {
    recentDups = [];
    shouldWake(e) { return wakesFleetManager(e); }
    observe(e, now = Date.now()) {
        if (e.type === "workflow.exception.detected" && e.category === "duplicate-invoice") {
            this.recentDups.push({ workflowId: e.workflowId, at: now });
            this.recentDups = this.recentDups.filter(r => now - r.at <= 60_000);
        }
    }
    detectAnomaly(now = Date.now()) {
        const dups = this.recentDups.filter(r => now - r.at <= 60_000);
        if (dups.length >= 3) {
            return { pattern: "duplicate-burst", workflowIds: dups.map(d => d.workflowId) };
        }
        return null;
    }
}
