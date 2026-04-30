// mocks/greenhouse-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type Posting = { posting_id: string; title: string; market: string; applicants_so_far: number; status: string; created_at: string };
type Applicant = { candidate_id: string; posting_id: string; name: string; email: string; linkedin_url: string; cv_url: string; applied_at: string };
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  postings: Posting[];
  applicants: Applicant[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "greenhouse_post", description: "Publish a JD on the WPP careers feed", parameters: { jd: "object", market: "string" } },
      { name: "greenhouse_applicants", description: "List applicants for a posting", parameters: { posting_id: "string" } },
      { name: "greenhouse_status", description: "Lookup posting status", parameters: { posting_id: "string" } },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "greenhouse_post": {
      const jd = args["jd"] as { title?: string } | undefined;
      const market = (args["market"] as string | undefined) ?? "Unknown";
      const id = `GH-${1000 + data.postings.length + 1}`;
      const posting: Posting = {
        posting_id: id,
        title: jd?.title ?? "Untitled Role",
        market,
        applicants_so_far: 0,
        status: "open",
        created_at: new Date().toISOString(),
      };
      data.postings.push(posting);
      return res.json(posting);
    }
    case "greenhouse_applicants": {
      const id = args["posting_id"] as string | undefined;
      if (!id) return res.status(400).json({ error: "missing_posting_id" });
      return res.json({ applicants: data.applicants.filter(a => a.posting_id === id) });
    }
    case "greenhouse_status": {
      const id = args["posting_id"] as string | undefined;
      const p = data.postings.find(x => x.posting_id === id);
      return p ? res.json(p) : res.status(404).json({ error: "posting_not_found" });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["GREENHOUSE_MCP_PORT"] ?? 4201);
app.listen(port, () => console.log(`[greenhouse-mcp] listening on ${port}`));
