// mocks/linkedin-mcp/server.ts
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type Profile = {
  linkedin_url: string; name: string; current_title: string;
  current_employer: string; tenure_years_total: number;
  skills: string[]; education: { institution: string; degree: string; year: number }[];
  headline: string;
};
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  profiles: Profile[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "linkedin_search", description: "Search passive candidates by role / level / market / comp band", parameters: { role: "string", level: "string?", market: "string?", limit: "number?" } },
      { name: "linkedin_profile_fetch", description: "Fetch the structured LinkedIn profile by URL", parameters: { url: "string" } },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "linkedin_search": {
      const role = ((args["role"] as string | undefined) ?? "").toLowerCase();
      const limit = Number(args["limit"] ?? 10);
      const matched = data.profiles
        .filter(p => !role || p.headline.toLowerCase().includes(role) || p.current_title.toLowerCase().includes(role))
        .slice(0, limit);
      return res.json({ profiles: matched, total: matched.length });
    }
    case "linkedin_profile_fetch": {
      const url = args["url"] as string | undefined;
      if (!url) return res.status(400).json({ error: "missing_url" });
      const p = data.profiles.find(x => x.linkedin_url === url);
      return p ? res.json(p) : res.status(404).json({ error: "profile_not_found" });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["LINKEDIN_MCP_PORT"] ?? 4202);
app.listen(port, () => console.log(`[linkedin-mcp] listening on ${port}`));
