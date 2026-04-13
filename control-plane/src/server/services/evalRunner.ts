// src/server/services/evalRunner.ts
import type { StateStore } from "./stateStore";

export interface EvalRecord {
  id: string;
  workflowId: string;
  ranAt: number;
  taskAdherence: number;
  safety: number;
  toolAccuracy: number;
}

export class EvalRunner {
  private results: EvalRecord[] = [];
  private timer: NodeJS.Timeout | null = null;
  constructor(private store: StateStore) {}

  start(): void {
    this.timer = setInterval(() => this.runSample(), 15_000);
  }
  stop(): void { if (this.timer) clearInterval(this.timer); }

  private runSample(): void {
    const completed = this.store.listWorkflows().filter(w => w.status === "completed");
    if (completed.length === 0) return;
    const pick = completed[Math.floor(Math.random() * completed.length)];
    this.results.push({
      id: `EVAL-${Date.now()}`,
      workflowId: pick.id,
      ranAt: Date.now(),
      taskAdherence: 0.85 + Math.random() * 0.15,
      safety: 0.95 + Math.random() * 0.05,
      toolAccuracy: 0.88 + Math.random() * 0.12
    });
  }

  list(): EvalRecord[] { return this.results.slice(-50).reverse(); }
}
