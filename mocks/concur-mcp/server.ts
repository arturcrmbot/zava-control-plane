// mocks/concur-mcp/server.ts
//
// Concur EMS mock — OAuth-flavoured surface that mirrors the Workday claim
// endpoints structurally but uses Concur's idiomatic terminology
// (expense reports, expense lines).
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));

type Justification = { claim_id: string; text: string; submitted_by: string; submitted_at: string };
type ExpenseClaim = {
  claim_id: string; employee_id: string; market: string; currency: string;
  amount: number; category: string; vendor: string; attendees?: number;
  receipt_filename: string; receipt_mismatch_flavour?: string;
  ems_source: "workday" | "concur"; submitted_at: string;
  justifications?: Justification[];
};

const expense = JSON.parse(readFileSync(path.join(dir, "data.expense.json"), "utf-8")) as {
  claims: ExpenseClaim[]; justifications: Justification[];
};

const app = express();
app.use(express.json());

// Concur-style OAuth check — Bearer token on every request. We treat any
// non-empty token as valid for the demo; the structure documents the surface.
app.use((req, res, next) => {
  const auth = req.header("Authorization");
  if (!auth || !auth.toLowerCase().startsWith("bearer ")) {
    return res.status(401).json({ error: "missing_bearer_token" });
  }
  next();
});

// Token endpoint — issued bearer is opaque. Reflects Concur's OAuth2 client-credentials shape.
app.post("/oauth/token", (req, res) => {
  const grant = (req.body ?? {})["grant_type"];
  if (grant !== "client_credentials") {
    return res.status(400).json({ error: "unsupported_grant_type" });
  }
  return res.json({
    access_token: "concur-mock-token-" + Date.now(),
    token_type: "Bearer",
    expires_in: 3600,
  });
});

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "listExpenseReports", description: "List expense reports filtered by market and status", parameters: { market: "string?", limit: "number?" } },
      { name: "getExpenseLine", description: "Lookup a single expense line by id", parameters: { reportItemId: "string" } },
      { name: "getReceipt", description: "Fetch the receipt metadata for an expense line", parameters: { reportItemId: "string" } },
      { name: "submitJustification", description: "Submit a business justification on a flagged line", parameters: { reportItemId: "string", text: "string", submittedBy: "string" } },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "listExpenseReports": {
      const market = args["market"] as string | undefined;
      const limit = Number(args["limit"] ?? 30);
      let pool = expense.claims;
      if (market) pool = pool.filter(c => c.market === market);
      return res.json({
        reports: pool.slice(0, limit).map(c => ({
          reportItemId: c.claim_id,
          submitter: c.employee_id,
          totalAmount: c.amount,
          currencyCode: c.currency,
          submittedAt: c.submitted_at,
          status: "Pending",
        })),
      });
    }
    case "getExpenseLine": {
      const id = args["reportItemId"];
      const c = expense.claims.find(x => x.claim_id === id);
      if (!c) return res.status(404).json({ error: "expense_line_not_found" });
      // Re-shape into Concur's idiomatic field names.
      return res.json({
        reportItemId: c.claim_id,
        submitter: c.employee_id,
        market: c.market,
        currencyCode: c.currency,
        totalAmount: c.amount,
        category: c.category,
        merchantName: c.vendor,
        attendeeCount: c.attendees ?? 1,
        transactionDate: c.submitted_at,
        // Underlying claim fields preserved for the Python claim_lookup
        // adapter that normalises across both EMSs.
        _normalised: c,
      });
    }
    case "getReceipt": {
      const id = args["reportItemId"];
      const c = expense.claims.find(x => x.claim_id === id);
      if (!c) return res.status(404).json({ error: "expense_line_not_found" });
      return res.json({
        reportItemId: c.claim_id,
        receiptFilename: c.receipt_filename,
        mismatchFlavour: c.receipt_mismatch_flavour ?? null,
      });
    }
    case "submitJustification": {
      const reportItemId = args["reportItemId"] as string | undefined;
      const text = args["text"] as string | undefined;
      const submittedBy = args["submittedBy"] as string | undefined;
      if (!reportItemId || !text || !submittedBy) {
        return res.status(400).json({ error: "missing_fields" });
      }
      if (!expense.claims.find(x => x.claim_id === reportItemId)) {
        return res.status(404).json({ error: "expense_line_not_found" });
      }
      const submitted_at = new Date().toISOString();
      expense.justifications.push({
        claim_id: reportItemId, text, submitted_by: submittedBy, submitted_at,
      });
      return res.json({ ok: true, receivedAt: submitted_at });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["CONCUR_MCP_PORT"] ?? 4102);
app.listen(port, () => console.log(`[concur-mcp] listening on ${port}`));
