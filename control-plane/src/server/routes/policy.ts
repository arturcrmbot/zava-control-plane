// src/server/routes/policy.ts
import { Router } from "express";
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import type { StateStore } from "../services/stateStore";
import { dryRunPolicyImpl } from "../mcp-tools/dryRunPolicy";

interface PolicyYaml {
  policies: Array<{
    id: string; description: string; value: number | string | boolean;
    gitSha: string; author: string; updatedAt: string;
  }>;
}

export function policyRouter(store: StateStore): Router {
  const r = Router();
  const changeRequests: Array<{
    id: string; policyId: string; proposedValue: unknown;
    rationale: string; proposedBy: string; createdAt: number;
  }> = [];

  const loadPolicies = () => {
    const file = path.join(process.cwd(), "src/shared/policies.yaml");
    const parsed = yaml.load(fs.readFileSync(file, "utf-8")) as PolicyYaml;
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
    const out = await dryRunPolicyImpl(store, req.body as {
      policyId: string; proposedValue: unknown; scopeDays?: number;
    });
    res.json(out);
  });
  r.post("/propose-change", (req, res) => {
    const id = `CR-${Date.now()}`;
    changeRequests.push({ id, ...req.body as {
      policyId: string; proposedValue: unknown; rationale: string; proposedBy: string;
    }, createdAt: Date.now() });
    res.json({ id });
  });
  r.get("/change-requests", (_req, res) => res.json(changeRequests));
  return r;
}
