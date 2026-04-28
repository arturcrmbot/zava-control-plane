// mocks/workday-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  vendors: { id: string; name: string; country: string; sanctioned: boolean; creditRating: string }[];
  costCentres: { id: string; name: string; approver: string }[];
  approvalChains: Record<string, string[]>;
};

type Justification = { claim_id: string; text: string; submitted_by: string; submitted_at: string };
type ExpenseClaim = {
  claim_id: string; employee_id: string; market: string; currency: string;
  amount: number; category: string; vendor: string; attendees?: number;
  receipt_filename: string; receipt_mismatch_flavour?: string;
  ems_source: "workday" | "concur"; submitted_at: string;
  justifications?: Justification[];
};
type Employee = {
  id: string; name: string; market: string; department: string; agency: string;
  breach_history: { date: string; category: string; tier: string }[];
};

const expense = JSON.parse(readFileSync(path.join(dir, "data.expense.json"), "utf-8")) as {
  claims: ExpenseClaim[]; employees: Employee[]; justifications: Justification[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "getVendor", description: "Lookup a vendor by id", parameters: { vendorId: "string" } },
      { name: "getCostCentre", description: "Lookup a cost centre by id", parameters: { costCentreId: "string" } },
      { name: "getApprovalChain", description: "Get approval chain for a scenario", parameters: { scenario: "string" } },
      { name: "getExpenseClaim", description: "Lookup an expense claim by id", parameters: { claimId: "string" } },
      { name: "listClaimsForApproval", description: "List claims pending approval", parameters: { market: "string?", limit: "number?" } },
      { name: "submitJustification", description: "Submit a business justification", parameters: { claimId: "string", text: "string", submittedBy: "string" } },
      { name: "listEmployeeClaimHistory", description: "Recent claims + breach history for an employee", parameters: { employeeId: "string" } }
    ]
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "getVendor": {
      const v = data.vendors.find(x => x.id === args["vendorId"]);
      return v ? res.json(v) : res.status(404).json({ error: "vendor_not_found" });
    }
    case "getCostCentre": {
      const c = data.costCentres.find(x => x.id === args["costCentreId"]);
      return c ? res.json(c) : res.status(404).json({ error: "cost_centre_not_found" });
    }
    case "getApprovalChain": {
      const scenario = (args["scenario"] as string | undefined) ?? "default";
      const chain = data.approvalChains[scenario] ?? data.approvalChains["default"];
      return res.json({ chain });
    }
    case "getExpenseClaim": {
      const id = args["claimId"];
      const c = expense.claims.find(x => x.claim_id === id);
      if (!c) return res.status(404).json({ error: "claim_not_found" });
      const justifications = expense.justifications.filter(j => j.claim_id === c.claim_id);
      return res.json({ ...c, justifications });
    }
    case "listClaimsForApproval": {
      const market = args["market"] as string | undefined;
      const limit = Number(args["limit"] ?? 30);
      let pool = expense.claims;
      if (market) pool = pool.filter(c => c.market === market);
      return res.json({ claims: pool.slice(0, limit) });
    }
    case "submitJustification": {
      const claimId = args["claimId"] as string | undefined;
      const text = args["text"] as string | undefined;
      const submittedBy = args["submittedBy"] as string | undefined;
      if (!claimId || !text || !submittedBy) {
        return res.status(400).json({ error: "missing_fields" });
      }
      if (!expense.claims.find(x => x.claim_id === claimId)) {
        return res.status(404).json({ error: "claim_not_found" });
      }
      const submitted_at = new Date().toISOString();
      expense.justifications.push({
        claim_id: claimId, text, submitted_by: submittedBy, submitted_at,
      });
      return res.json({ ok: true, receivedAt: submitted_at });
    }
    case "listEmployeeClaimHistory": {
      const employeeId = args["employeeId"] as string | undefined;
      if (!employeeId) return res.status(400).json({ error: "missing_employeeId" });
      const emp = expense.employees.find(e => e.id === employeeId);
      if (!emp) return res.status(404).json({ error: "employee_not_found" });
      const recent = expense.claims.filter(c => c.employee_id === employeeId).slice(-10);
      return res.json({
        employee_id: employeeId,
        breach_history: emp.breach_history,
        recent_claims: recent.map(c => ({
          claim_id: c.claim_id, amount: c.amount, category: c.category, submitted_at: c.submitted_at,
        })),
      });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["WORKDAY_MCP_PORT"] ?? 4101);
app.listen(port, () => console.log(`[workday-mcp] listening on ${port}`));
