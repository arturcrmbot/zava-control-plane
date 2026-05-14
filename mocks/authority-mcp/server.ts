// mocks/authority-mcp/server.ts
//
// Delegated Authority mock — read-only resolver over an ordered rule list.
// Backs the `delegated_authority` MCP tool used by skills (resolved_approver
// in agent context) and personae (threshold checks via context.authority).
//
// The matrix data lives in data/synthetic/authority/matrix.json. Live
// editing is supported via the /reload endpoint — useful when demoing
// "authority changes take effect without a restart".
import express from "express";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { resolve, checkAuthority, AuthorityRule, ResolveRequest, CheckRequest } from "./resolver.js";

const dir = path.dirname(fileURLToPath(import.meta.url));
const MATRIX_PATH = path.resolve(dir, "..", "..", "data", "synthetic", "authority", "matrix.json");

let matrix: AuthorityRule[] = loadMatrix();

function loadMatrix(): AuthorityRule[] {
  const raw = readFileSync(MATRIX_PATH, "utf-8");
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) {
    throw new Error(`authority matrix at ${MATRIX_PATH} must be a JSON array`);
  }
  return parsed as AuthorityRule[];
}

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ ok: true, rules: matrix.length, source: MATRIX_PATH });
});

app.post("/reload", (_req, res) => {
  try {
    matrix = loadMatrix();
    res.json({ ok: true, rules: matrix.length });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
});

// MCP-style tool descriptor for any client that introspects the surface.
app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      {
        name: "resolve_approver",
        description: "Walk the authority matrix and return the first rule that matches the request.",
        parameters: {
          action: "string",
          value: "number?",
          category: "string?",
          requester_role: "string?",
          business_unit: "string?",
          geography: "string?",
        },
      },
      {
        name: "check_authority",
        description: "Check whether a specific role is authorised for a given action+value+scope.",
        parameters: {
          role: "string",
          action: "string",
          value: "number?",
          category: "string?",
          business_unit: "string?",
          geography: "string?",
        },
      },
    ],
  });
});

app.post("/resolve_approver", (req, res) => {
  const body = (req.body ?? {}) as ResolveRequest;
  if (!body.action || typeof body.action !== "string") {
    return res.status(400).json({ matched: false, reason: "missing required field: action" });
  }
  const result = resolve(matrix, body);
  return res.json(result);
});

app.post("/check_authority", (req, res) => {
  const body = (req.body ?? {}) as CheckRequest;
  if (!body.role || !body.action) {
    return res.status(400).json({ allowed: false, reason: "missing required field: role or action" });
  }
  const result = checkAuthority(matrix, body);
  return res.json(result);
});

// MCP-call style passthrough so callers using the /mcp/call/:tool convention
// (matching workday-mcp / concur-mcp) work too.
app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const body = req.body ?? {};
  switch (tool) {
    case "resolve_approver":
      return res.json(resolve(matrix, body));
    case "check_authority":
      return res.json(checkAuthority(matrix, body));
    default:
      return res.status(404).json({ error: `unknown tool: ${tool}` });
  }
});

const PORT = Number(process.env.PORT ?? 4108);
app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[authority-mcp] listening on :${PORT} (rules=${matrix.length}, src=${MATRIX_PATH})`);
});
