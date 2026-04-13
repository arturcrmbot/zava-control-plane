// src/server/routes/workflows.ts
import { Router } from "express";
export function workflowsRouter(store) {
    const r = Router();
    r.get("/", (req, res) => {
        const { status, phase, agency, hasException } = req.query;
        res.json(store.listWorkflows({
            status: status, phase: phase, agency: agency,
            hasException: hasException === "true" ? true : hasException === "false" ? false : undefined
        }));
    });
    r.get("/:id", (req, res) => {
        const w = store.getWorkflow(req.params.id);
        if (!w)
            return res.status(404).end();
        res.json({
            workflow: w,
            phases: store.getPhases(req.params.id),
            spans: store.getSpans(req.params.id),
            amplifications: store.getAmplifications(req.params.id),
            activeException: w.activeExceptionId ? store.getException(w.activeExceptionId) : null
        });
    });
    return r;
}
