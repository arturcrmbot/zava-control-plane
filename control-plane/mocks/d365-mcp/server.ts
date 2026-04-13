// mocks/d365-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  purchaseOrders: { id: string; vendorId: string; amount: number; currency: string; lineCount: number; openBalance: number }[];
  glAccounts: { id: string; name: string }[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "parseInvoice", description: "Parse an invoice payload", parameters: { raw: "string" } },
      { name: "matchPO", description: "3-way match invoice to PO", parameters: { invoiceAmount: "number", poId: "string" } },
      { name: "postGLEntry", description: "Post GL entry", parameters: { glAccountId: "string", amount: "number", workflowId: "string" } }
    ]
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "parseInvoice": {
      return res.json({
        parsed: {
          number: `INV-${Math.floor(Math.random() * 1e5)}`,
          extractedAmount: args["extractedAmount"] ?? 0,
          poRef: args["poRef"] ?? null
        }
      });
    }
    case "matchPO": {
      const po = data.purchaseOrders.find(x => x.id === args["poId"]);
      if (!po) return res.json({ match: false, reason: "po_not_found" });
      const invoiceAmount = (args["invoiceAmount"] as number | undefined) ?? 0;
      const variance = Math.abs(po.amount - invoiceAmount);
      const tolerance = po.amount * 0.02;
      return res.json({
        match: variance <= tolerance,
        variance,
        tolerance,
        poAmount: po.amount
      });
    }
    case "postGLEntry": {
      return res.json({ posted: true, entryId: `GLE-${Date.now()}` });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["D365_MCP_PORT"] ?? 4102);
app.listen(port, () => console.log(`[d365-mcp] listening on ${port}`));
