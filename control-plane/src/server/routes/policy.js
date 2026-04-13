// src/server/routes/policy.ts
import { Router } from "express";
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import { dryRunPolicyImpl } from "../mcp-tools/dryRunPolicy";
export function policyRouter(store) {
    const r = Router();
    const changeRequests = [];
    const loadPolicies = () => {
        const file = path.join(process.cwd(), "src/shared/policies.yaml");
        const parsed = yaml.load(fs.readFileSync(file, "utf-8"));
        for (const p of parsed.policies) {
            store.upsertPolicy({
                id: p.id, description: p.description, currentValue: p.value,
                gitSha: p.gitSha, author: p.author, updatedAt: new Date(p.updatedAt).getTime()
            });
        }
    };
    loadPolicies();
    r.get("/", (_req, res) => res.json(store.listPolicies()));
    r.post("/dry-run", async (req, res) => {
        const out = await dryRunPolicyImpl(store, req.body);
        res.json(out);
    });
    r.post("/propose-change", (req, res) => {
        const id = `CR-${Date.now()}`;
        changeRequests.push({ id, ...req.body, createdAt: Date.now() });
        res.json({ id });
    });
    r.get("/change-requests", (_req, res) => res.json(changeRequests));
    return r;
}
