// src/server/routes/stream.ts
import { Router } from "express";
import type { SSEHub } from "../services/sseHub";

export function streamRouter(hub: SSEHub): Router {
  const r = Router();
  r.get("/fleet", (_req, res) => hub.subscribe("fleet", res));
  r.get("/fleet-manager", (_req, res) => hub.subscribe("fleet-manager", res));
  return r;
}
