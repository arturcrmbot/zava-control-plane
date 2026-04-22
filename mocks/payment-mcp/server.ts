// mocks/payment-mcp/server.ts
import express from "express";

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "createPaymentFile", description: "Create a payment file", parameters: { workflowId: "string", amount: "number" } },
      { name: "submitPayment", description: "Submit payment. May time out on first call per workflow when simulateTimeout=true", parameters: { paymentFileId: "string", simulateTimeout: "boolean" } },
      { name: "reconcileStatement", description: "Reconcile against statement", parameters: { statementId: "string" } }
    ]
  });
});

const timedOutOnce = new Set<string>();

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "createPaymentFile": {
      return res.json({ paymentFileId: `PF-${Date.now()}`, workflowId: args["workflowId"], amount: args["amount"] });
    }
    case "submitPayment": {
      const key = (args["paymentFileId"] as string | undefined) ?? "";
      if (args["simulateTimeout"] && !timedOutOnce.has(key)) {
        timedOutOnce.add(key);
        setTimeout(() => res.status(504).json({ error: "gateway_timeout" }), 50);
        return;
      }
      return res.json({ submitted: true, confirmation: `BANK-${Date.now()}` });
    }
    case "reconcileStatement": {
      return res.json({ reconciled: true, matchedCount: 2 });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["PAYMENT_MCP_PORT"] ?? 4104);
app.listen(port, () => console.log(`[payment-mcp] listening on ${port}`));
