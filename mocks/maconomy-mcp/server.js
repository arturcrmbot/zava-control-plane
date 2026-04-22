// mocks/maconomy-mcp/server.ts
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
            { name: "lookupProject", description: "Lookup a project by id", parameters: { projectId: "string" } },
            { name: "getTimesheetHours", description: "Get timesheet hours for a project in a week", parameters: { projectId: "string", weekIso: "string" } }
        ]
    });
});
app.post("/mcp/call/:tool", (req, res) => {
    const tool = req.params.tool;
    const args = (req.body ?? {});
    switch (tool) {
        case "lookupProject": {
            const p = data.projects.find(x => x.id === args["projectId"]);
            return p ? res.json(p) : res.status(404).json({ error: "project_not_found" });
        }
        case "getTimesheetHours": {
            return res.json({
                projectId: args["projectId"],
                weekIso: args["weekIso"],
                hours: 42 + Math.floor(Math.random() * 8)
            });
        }
        default:
            return res.status(400).json({ error: "unknown_tool" });
    }
});
const port = Number(process.env["MACONOMY_MCP_PORT"] ?? 4103);
app.listen(port, () => console.log(`[maconomy-mcp] listening on ${port}`));
