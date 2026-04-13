// src/server/routes/audit.ts
import { Router } from "express";
import type { AuditLogger } from "../services/auditLogger";

export function auditRouter(audit: AuditLogger): Router {
  const r = Router();
  r.get("/", (_req, res) => res.json(audit.list()));
  return r;
}
