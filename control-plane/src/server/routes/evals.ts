// src/server/routes/evals.ts
import { Router } from "express";
import type { EvalRunner } from "../services/evalRunner";

export function evalsRouter(runner: EvalRunner): Router {
  const r = Router();
  r.get("/", (_req, res) => res.json(runner.list()));
  return r;
}
