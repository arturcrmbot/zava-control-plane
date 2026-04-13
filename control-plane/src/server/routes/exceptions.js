// src/server/routes/exceptions.ts
import { Router } from "express";
export function exceptionsRouter(store) {
    const r = Router();
    r.get("/", (req, res) => {
        res.json(store.listExceptions({ includeResolved: req.query.includeResolved === "true" }));
    });
    r.post("/bulk-resolve", (req, res) => {
        const { exceptionIds, resolution, resolvedBy } = req.body;
        for (const id of exceptionIds) {
            store.resolveException(id, resolvedBy);
            const exc = store.getException(id);
            if (!exc)
                continue;
            const w = store.getWorkflow(exc.workflowId);
            if (w && w.status === "awaiting_hitl") {
                w.status = "in_progress";
                w.actionLedger.push({
                    workflowId: w.id, timestamp: Date.now(),
                    actor: { kind: "human", id: resolvedBy },
                    action: `bulk-resolve:${resolution}`, revocable: false, details: { exceptionId: id }
                });
            }
        }
        res.json({ resolved: exceptionIds.length });
    });
    return r;
}
