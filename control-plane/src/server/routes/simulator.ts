// src/server/routes/simulator.ts
import { Router } from "express";
import type { WorkflowSimulator } from "../services/workflowSimulator";

export function simulatorRouter(sim: WorkflowSimulator): Router {
  const r = Router();
  r.post("/inject", async (req, res) => {
    const id = await sim.spawn((req.body as { scenario?: string })?.scenario as never);
    res.json({ workflowId: id });
  });
  return r;
}
