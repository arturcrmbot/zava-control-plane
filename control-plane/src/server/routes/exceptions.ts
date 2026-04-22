// src/server/routes/exceptions.ts
import { Router } from "express";
import type { StateStore } from "../services/stateStore";

export function exceptionsRouter(store: StateStore): Router {
  const r = Router();
  r.get("/", (req, res) => {
    res.json(store.listExceptions({ includeResolved: req.query.includeResolved === "true" }));
  });
  r.post("/bulk-resolve", (req, res) => {
    const { exceptionIds, resolution, resolvedBy } = req.body as {
      exceptionIds: string[]; resolution: string; resolvedBy: string;
    };
    for (const id of exceptionIds) {
      store.resolveException(id, resolvedBy);
      const exc = store.getException(id);
      if (!exc) continue;
      const w = store.getWorkflow(exc.workflowId);
      if (w && w.status === "awaiting_hitl") {
        w.status = "in_progress";
        w.actionLedger.push({
          workflowId: w.id, timestamp: Date.now(),
          actorKind: "human", actorId: resolvedBy,
          action: `bulk-resolve:${resolution}`, revocable: false, details: { exceptionId: id }
        });
      }
    }
    res.json({ resolved: exceptionIds.length });
  });
  return r;
}
