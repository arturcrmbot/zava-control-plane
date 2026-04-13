// src/server/routes/audit.ts
import { Router } from "express";
export function auditRouter(audit) {
    const r = Router();
    r.get("/", (_req, res) => res.json(audit.list()));
    return r;
}
