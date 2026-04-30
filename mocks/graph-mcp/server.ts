// mocks/graph-mcp/server.ts — Microsoft Graph (calendar + mail + invite) mock for POC2
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type Slot = { start: string; end: string; status: "free" | "busy" };
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  free_busy: Record<string, Slot[]>;
  messages_sent: { id: string; to: string[]; subject: string; sent_at: string }[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "graph_calendar", description: "Free/busy lookup for a list of attendees", parameters: { attendees: "string[]", window_start: "string", window_end: "string" } },
      { name: "graph_mail", description: "Send a templated email; gated by onPreToolUse hook for non-revocable sends", parameters: { recipients: "string[]", subject: "string", body: "string" } },
      { name: "graph_invite", description: "Send a calendar invite", parameters: { attendees: "string[]", start: "string", end: "string", subject: "string", agenda: "string?" } },
    ],
  });
});

function nextId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36).toUpperCase()}`;
}

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "graph_calendar": {
      const attendees = (args["attendees"] as string[] | undefined) ?? [];
      const result: Record<string, Slot[]> = {};
      for (const a of attendees) result[a] = data.free_busy[a] ?? [];
      return res.json({ free_busy: result });
    }
    case "graph_mail": {
      const recipients = (args["recipients"] as string[] | undefined) ?? [];
      const subject = (args["subject"] as string | undefined) ?? "";
      const id = nextId("MSG");
      data.messages_sent.push({ id, to: recipients, subject, sent_at: new Date().toISOString() });
      return res.json({ message_id: id, sent: true });
    }
    case "graph_invite": {
      const id = nextId("INV");
      return res.json({ invite_id: id, sent: true, sent_at: new Date().toISOString() });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["GRAPH_MCP_PORT"] ?? 4204);
app.listen(port, () => console.log(`[graph-mcp] listening on ${port}`));
