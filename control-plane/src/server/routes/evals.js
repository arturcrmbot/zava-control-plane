// src/server/routes/evals.ts
import { Router } from "express";
export function evalsRouter(runner) {
    const r = Router();
    r.get("/", (_req, res) => res.json(runner.list()));
    return r;
}
