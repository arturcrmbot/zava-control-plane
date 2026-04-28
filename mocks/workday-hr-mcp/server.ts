// mocks/workday-hr-mcp/server.ts — POC2 HR-flavoured Workday surface (positions + JML)
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type Position = {
  position_id: string; cost_centre_id: string; title: string; level: string;
  market: string; jurisdiction: "USA" | "DE";
  comp_band_gbp: { min: number; midpoint: number; max: number };
  headcount_approved: number; headcount_filled: number;
  envelope_remaining_gbp: number; manager_id: string;
};
type Employee = { id: string; name: string; title: string; market: string; jurisdiction: string };
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  positions: Position[];
  employees: Employee[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "workday_position", description: "Get position by id (or by cost-centre)", parameters: { position_id: "string?", cost_centre_id: "string?" } },
      { name: "workday_employee", description: "Get employee by id", parameters: { employee_id: "string" } },
      { name: "workday_jml_create", description: "File a joiner request (Phase 10 onboarding)", parameters: { candidate: "object", position_id: "string", start_date: "string" } },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "workday_position": {
      const id = args["position_id"] as string | undefined;
      const cc = args["cost_centre_id"] as string | undefined;
      const p = data.positions.find(x => (id && x.position_id === id) || (cc && x.cost_centre_id === cc));
      return p ? res.json(p) : res.status(404).json({ error: "position_not_found" });
    }
    case "workday_employee": {
      const id = args["employee_id"] as string | undefined;
      const e = data.employees.find(x => x.id === id);
      return e ? res.json(e) : res.status(404).json({ error: "employee_not_found" });
    }
    case "workday_jml_create": {
      const ticket = `JML-${Date.now().toString(36).toUpperCase()}`;
      return res.json({ ok: true, jml_ticket: ticket, filed_at: new Date().toISOString() });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["WORKDAY_HR_MCP_PORT"] ?? 4203);
app.listen(port, () => console.log(`[workday-hr-mcp] listening on ${port}`));
