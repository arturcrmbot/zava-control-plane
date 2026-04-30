// mocks/acs-mcp/server.ts — ACS / GPT-Realtime stub for POC2 voice screening + A2A
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type Transcript = {
  candidate_id: string;
  transcript: { speaker: "agent" | "candidate"; text: string }[];
  duration_sec: number;
};
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  transcripts: Transcript[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "acs_dial", description: "Place an outbound voice call (mock — returns canned transcript)", parameters: { phone_number: "string", prompt: "string", candidate_id: "string?" } },
      { name: "transcript_score", description: "Score a transcript against the rubric", parameters: { transcript: "object[]", rubric: "object" } },
      { name: "a2a_message", description: "External Personal Agent → internal hiring agent boundary message (§4.19)", parameters: { from_pa: "string", message: "string", correlation_id: "string?" } },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "acs_dial": {
      const id = (args["candidate_id"] as string | undefined) ?? "C-101";
      const t = data.transcripts.find(x => x.candidate_id === id) ?? data.transcripts[0];
      return res.json({ candidate_id: id, transcript: t.transcript, duration_sec: t.duration_sec });
    }
    case "transcript_score": {
      // Deterministic stub — Track C replaces with a real scoring path.
      return res.json({
        scores: { motivation: 0.85, technical: 0.78, soft: 0.80, comp_fit: 0.90 },
        overall: 0.83,
        verdict: "advance",
      });
    }
    case "a2a_message": {
      const corr = (args["correlation_id"] as string | undefined) ?? `A2A-${Date.now().toString(36).toUpperCase()}`;
      return res.json({
        correlation_id: corr,
        accepted: true,
        reply: "I can confirm the candidate's availability for an interview Friday 14:00 GMT.",
      });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["ACS_MCP_PORT"] ?? 4206);
app.listen(port, () => console.log(`[acs-mcp] listening on ${port}`));
