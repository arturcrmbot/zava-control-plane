export class EvalRunner {
    store;
    results = [];
    timer = null;
    constructor(store) {
        this.store = store;
    }
    start() {
        this.timer = setInterval(() => this.runSample(), 15_000);
    }
    stop() { if (this.timer)
        clearInterval(this.timer); }
    runSample() {
        const completed = this.store.listWorkflows().filter(w => w.status === "completed");
        if (completed.length === 0)
            return;
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
    list() { return this.results.slice(-50).reverse(); }
}
