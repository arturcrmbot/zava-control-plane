// src/server/routes/workflows.ts
import { Router } from "express";
import type { StateStore } from "../services/stateStore";

export function workflowsRouter(store: StateStore): Router {
  const r = Router();
  r.get("/", (req, res) => {
    const { status, phase, agency, hasException } = req.query;
    res.json(store.listWorkflows({
      status: status as never, phase: phase as never, agency: agency as never,
      hasException: hasException === "true" ? true : hasException === "false" ? false : undefined
    }));
  });
  r.get("/:id", (req, res) => {
    const w = store.getWorkflow(req.params.id);
    if (!w) return res.status(404).end();
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
