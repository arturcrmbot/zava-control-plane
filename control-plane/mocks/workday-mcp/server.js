// mocks/workday-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
const dir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8"));
const app = express();
app.use(express.json());
app.get("/mcp/tools", (_req, res) => {
    res.json({
        tools: [
            { name: "getVendor", description: "Lookup a vendor by id", parameters: { vendorId: "string" } },
            { name: "getCostCentre", description: "Lookup a cost centre by id", parameters: { costCentreId: "string" } },
            { name: "getApprovalChain", description: "Get approval chain for a scenario", parameters: { scenario: "string" } }
        ]
    });
});
app.post("/mcp/call/:tool", (req, res) => {
    const tool = req.params.tool;
    const args = (req.body ?? {});
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
            const scenario = args["scenario"] ?? "default";
            const chain = data.approvalChains[scenario] ?? data.approvalChains["default"];
            return res.json({ chain });
        }
        default:
            return res.status(400).json({ error: "unknown_tool" });
    }
});
const port = Number(process.env["WORKDAY_MCP_PORT"] ?? 4101);
app.listen(port, () => console.log(`[workday-mcp] listening on ${port}`));
