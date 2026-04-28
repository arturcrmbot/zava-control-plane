// mocks/heygen-mcp/server.ts — HeyGen avatar render stub for POC2 onboarding
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const dir = path.dirname(fileURLToPath(import.meta.url));
type Avatar = { id: string; name: string; language: string };
type Render = { id: string; avatar_id: string; script: string; mp4_url: string; rendered_at: string };
const data = JSON.parse(readFileSync(path.join(dir, "data.json"), "utf-8")) as {
  avatars: Avatar[]; renders: Render[];
};

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "heygen_render", description: "Render a 30-second avatar welcome video", parameters: { script: "string", avatar_id: "string?", new_hire_name: "string?" } },
      { name: "heygen_list_avatars", description: "List available avatar templates", parameters: {} },
    ],
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "heygen_render": {
      const avatarId = (args["avatar_id"] as string | undefined) ?? "welcome-default";
      const script = (args["script"] as string | undefined) ?? "";
      const id = `RND-${Date.now().toString(36).toUpperCase()}`;
      const rec: Render = {
        id, avatar_id: avatarId, script,
        mp4_url: `https://heygen-mock.local/renders/${id}.mp4`,
        rendered_at: new Date().toISOString(),
      };
      data.renders.push(rec);
      return res.json(rec);
    }
    case "heygen_list_avatars":
      return res.json({ avatars: data.avatars });
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env["HEYGEN_MCP_PORT"] ?? 4207);
app.listen(port, () => console.log(`[heygen-mcp] listening on ${port}`));
