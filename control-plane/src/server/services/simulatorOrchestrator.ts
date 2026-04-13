// src/server/services/simulatorOrchestrator.ts
import type { WorkflowSimulator } from "./workflowSimulator";

export class SimulatorOrchestrator {
  private timer: NodeJS.Timeout | null = null;
  constructor(private sim: WorkflowSimulator, private opts: { target: number; rampMs: number }) {}

  start(): void {
    const scheduleNext = () => {
      const delay = 3000 + Math.random() * 5000;
      this.timer = setTimeout(async () => {
        await this.sim.spawn();
        scheduleNext();
      }, delay);
    };
    // Ramp: spawn quickly until target
    (async () => {
      for (let i = 0; i < this.opts.target; i++) {
        await this.sim.spawn();
        await new Promise(r => setTimeout(r, this.opts.rampMs / this.opts.target));
      }
      scheduleNext();
    })();
  }

  stop(): void { if (this.timer) clearTimeout(this.timer); }
}
