export class SimulatorOrchestrator {
    sim;
    opts;
    timer = null;
    constructor(sim, opts) {
        this.sim = sim;
        this.opts = opts;
    }
    start() {
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
    stop() { if (this.timer)
        clearTimeout(this.timer); }
}
