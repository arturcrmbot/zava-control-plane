import { describe, it, expect, vi } from "vitest";
import { FleetManagerQueue } from "@server/services/fleetManagerQueue";
describe("FleetManagerQueue", () => {
    it("debounces per-workflow within window", async () => {
        vi.useFakeTimers();
        const process = vi.fn(async () => { });
        const q = new FleetManagerQueue(process, { debounceMs: 1000 });
        q.enqueue({ workflowId: "A", reason: "exception.detected" });
        q.enqueue({ workflowId: "A", reason: "exception.detected" });
        q.enqueue({ workflowId: "A", reason: "exception.detected" });
        await vi.advanceTimersByTimeAsync(1001);
        expect(process).toHaveBeenCalledTimes(1);
        vi.useRealTimers();
    });
    it("batches multiple workflows in same flush", async () => {
        vi.useFakeTimers();
        const process = vi.fn(async (_batch) => { });
        const q = new FleetManagerQueue(process, { debounceMs: 500 });
        q.enqueue({ workflowId: "A", reason: "x" });
        q.enqueue({ workflowId: "B", reason: "x" });
        q.enqueue({ workflowId: "C", reason: "x" });
        await vi.advanceTimersByTimeAsync(501);
        expect(process).toHaveBeenCalledTimes(1);
        const arg = process.mock.calls[0][0];
        expect(arg.map((e) => e.workflowId).sort()).toEqual(["A", "B", "C"]);
        vi.useRealTimers();
    });
});
