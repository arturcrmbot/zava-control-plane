// src/server/routes/simulator.ts
import { Router } from "express";
export function simulatorRouter(sim) {
    const r = Router();
    r.post("/inject", async (req, res) => {
        const id = await sim.spawn(req.body?.scenario);
        res.json({ workflowId: id });
    });
    return r;
}
