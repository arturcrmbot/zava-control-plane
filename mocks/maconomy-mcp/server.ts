// mocks/maconomy-mcp/server.ts
//
// Maconomy EMS mock — single-endpoint stub for the AC #10 extensibility
// demo. The premise: a third EMS lands on the platform with no skill
// changes; only the lookup adapter and the mock are touched. Returns one
// expense claim under the canonical synthetic-corpus shape so the
// Python claim_lookup adapter can normalise it identically to Workday.
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));

type ExpenseClaim = {
  claim_id: string;
  employee_id: string;
  submitted_at: string;
  market: string;
  currency: string;
  category: string;
  vendor: string;
  amount: number;
  attendees?: number;
  narrative?: string;
  receipt_filename: string;
  ems_source: "maconomy";
  receipt_mismatch_flavour?: string;
};

const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  claims: ExpenseClaim[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      {
        name: "getExpenseLine",
        description: "Lookup a single expense line by claim id",
        parameters: { claimId: "string" },
      },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "getExpenseLine": {
      const id = args["claimId"];
      const c = data.claims.find(x => x.claim_id === id);
      return c ? res.json(c) : res.status(404).json({ error: "claim_not_found" });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["MACONOMY_MCP_PORT"] ?? 4103);
app.listen(port, () => console.log(`[maconomy-mcp] listening on ${port}`));
