export class FleetManagerQueue {
    processor;
    opts;
    pending = new Map();
    flushTimer = null;
    flushing = false;
    constructor(processor, opts) {
        this.processor = processor;
        this.opts = opts;
    }
    enqueue(entry) {
        this.pending.set(entry.workflowId, entry);
        if (!this.flushTimer) {
            this.flushTimer = setTimeout(() => { void this.flush(); }, this.opts.debounceMs);
        }
    }
    depth() { return this.pending.size; }
    async flush() {
        this.flushTimer = null;
        if (this.flushing)
            return;
        this.flushing = true;
        try {
            const batch = [...this.pending.values()];
            this.pending.clear();
            if (batch.length > 0)
                await this.processor(batch);
        }
        finally {
            this.flushing = false;
        }
    }
}
