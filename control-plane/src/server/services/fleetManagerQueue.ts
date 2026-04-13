export interface QueueEntry {
  workflowId: string;
  reason: string;
}

export class FleetManagerQueue {
  private pending = new Map<string, QueueEntry>();
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private flushing = false;

  constructor(
    private processor: (batch: QueueEntry[]) => Promise<void>,
    private opts: { debounceMs: number }
  ) {}

  enqueue(entry: QueueEntry): void {
    this.pending.set(entry.workflowId, entry);
    if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => { void this.flush(); }, this.opts.debounceMs);
    }
  }

  depth(): number { return this.pending.size; }

  private async flush(): Promise<void> {
    this.flushTimer = null;
    if (this.flushing) return;
    this.flushing = true;
    try {
      const batch = [...this.pending.values()];
      this.pending.clear();
      if (batch.length > 0) await this.processor(batch);
    } finally {
      this.flushing = false;
    }
  }
}
