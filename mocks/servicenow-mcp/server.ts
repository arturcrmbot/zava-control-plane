// mocks/servicenow-mcp/server.ts — ServiceNow (JML + incidents + IT Ops webhook) for POC2
import express from "express";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type JmlTicket = {
  id: string; candidate_id: string; manager: string; role: string;
  start_date: string; jurisdiction: string;
  status: "filed" | "provisioning" | "complete";
  filed_at: string;
};
type Incident = {
  id: string; subject: string; severity: "P1" | "P2" | "P3" | "P4";
  workflow_id: string | null; opened_at: string; status: "open" | "resolved";
};
const dataPath = path.join(dir, "data.json");
const data = JSON.parse(readFileSync(dataPath, "utf-8")) as {
  incidents: Incident[]; jml_tickets: JmlTicket[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "servicenow_jml", description: "File a joiner request (laptop + accounts + access)", parameters: { candidate_id: "string", role: "string", manager: "string", start_date: "string", jurisdiction: "string" } },
      { name: "servicenow_incident_open", description: "Open an IT Ops incident", parameters: { subject: "string", severity: "string", workflow_id: "string?" } },
      { name: "servicenow_jml_status", description: "Lookup JML ticket status", parameters: { id: "string" } },
    ],
  });
});

function flush() {
  writeFileSync(dataPath, JSON.stringify(data, null, 2), "utf-8");
}

function nextId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36).toUpperCase()}`;
}

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "servicenow_jml": {
      const t: JmlTicket = {
        id: nextId("JML"),
        candidate_id: (args["candidate_id"] as string) ?? "?",
        role: (args["role"] as string) ?? "?",
        manager: (args["manager"] as string) ?? "?",
        start_date: (args["start_date"] as string) ?? new Date().toISOString().slice(0, 10),
        jurisdiction: (args["jurisdiction"] as string) ?? "USA",
        status: "filed",
        filed_at: new Date().toISOString(),
      };
      data.jml_tickets.push(t);
      flush();
      return res.json(t);
    }
    case "servicenow_incident_open": {
      const inc: Incident = {
        id: nextId("INC"),
        subject: (args["subject"] as string) ?? "(no subject)",
        severity: ((args["severity"] as string) ?? "P3") as Incident["severity"],
        workflow_id: (args["workflow_id"] as string | null) ?? null,
        opened_at: new Date().toISOString(),
        status: "open",
      };
      data.incidents.push(inc);
      flush();
      return res.json(inc);
    }
    case "servicenow_jml_status": {
      const id = args["id"] as string | undefined;
      const t = data.jml_tickets.find(x => x.id === id);
      return t ? res.json(t) : res.status(404).json({ error: "jml_not_found" });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

// Inbound IT-Ops webhook surface for §4.6 multi-surface convergence:
// FastAPI's webhooks_servicenow.py receives signed callbacks at this shape.
app.post("/webhook/itops/:incident_id", (req, res) => {
  const id = req.params.incident_id;
  const inc = data.incidents.find(x => x.id === id);
  if (!inc) return res.status(404).json({ error: "incident_not_found" });
  inc.status = "resolved";
  flush();
  return res.json({ ok: true, incident_id: id });
});

const port = Number(process.env["SERVICENOW_MCP_PORT"] ?? 4205);
app.listen(port, () => console.log(`[servicenow-mcp] listening on ${port}`));
