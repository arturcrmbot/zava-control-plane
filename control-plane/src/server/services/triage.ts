import type { FleetEvent } from "@shared/events";
import { wakesFleetManager } from "@shared/events";

export class Triage {
  private recentDups: { workflowId: string; at: number }[] = [];

  shouldWake(e: FleetEvent): boolean { return wakesFleetManager(e); }

  observe(e: FleetEvent, now: number = Date.now()): void {
    if (e.type === "workflow.exception.detected" && e.category === "duplicate-invoice") {
      this.recentDups.push({ workflowId: e.workflowId, at: now });
      this.recentDups = this.recentDups.filter(r => now - r.at <= 60_000);
    }
  }

  detectAnomaly(now: number = Date.now()): { pattern: string; workflowIds: string[] } | null {
    const dups = this.recentDups.filter(r => now - r.at <= 60_000);
    if (dups.length >= 3) {
      return { pattern: "duplicate-burst", workflowIds: dups.map(d => d.workflowId) };
    }
    return null;
  }
}
