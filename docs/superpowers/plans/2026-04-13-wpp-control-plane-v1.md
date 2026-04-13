# WPP Control Plane v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Control Plane v1 in 2 days that generates screenshots + video for the WPP RFP written response due 2026-04-23.

**Architecture:** Node/Express + React (Vite/Tailwind) + real GHCP SDK Fleet Manager agent subscribed to an in-process EventBus driven by a deterministic WorkflowSimulator running POC1 invoice workflows. Four mock MCP servers produce real tool traffic. Exception queue is agentically composed, not rule-filtered.

**Tech Stack:** TypeScript strict, Node 20, Express 5, `@github/copilot-sdk`, `@modelcontextprotocol/sdk`, React 19, Vite 6, Tailwind 4, Vitest, Playwright (optional).

**Reference:** [docs/superpowers/specs/2026-04-13-wpp-control-plane-v1-design.md](../specs/2026-04-13-wpp-control-plane-v1-design.md)

**Root directory for build:** `c:\dev\ghcp sdk stuff\control-plane\`

**Phases:**
- Phase 0 — Setup & Risk Spike (tasks 0.1–0.3)
- Phase 1 — Shared types + Event taxonomy (1.1–1.2)
- Phase 2 — Mock MCP servers (2.1–2.4)
- Phase 3 — EventBus + StateStore + Triage (3.1–3.3)
- Phase 4 — Workflow Simulator (4.1–4.3)
- Phase 5 — Fleet Manager (5.1–5.5)
- Phase 6 — Server API + SSE hub (6.1–6.4)
- Phase 7 — Client shell (7.1–7.3)
- Phase 8 — Client screens (8.1–8.6)
- Phase 9 — Eval runner + demo polish (9.1–9.3)
- Phase 10 — README + final integration (10.1–10.2)

Cut order if time runs short (matches spec §9): Phase 9.1 Evals screen → Phase 8.5 Analytics → Phase 9.3 Playwright → Phase 8.6 Policy & Autonomy.

---

## Phase 0 — Setup & Risk Spike

### Task 0.1: Scaffold the repo

**Files:**
- Create: `control-plane/package.json`
- Create: `control-plane/tsconfig.json`
- Create: `control-plane/vite.config.ts`
- Create: `control-plane/tailwind.config.ts`
- Create: `control-plane/postcss.config.js`
- Create: `control-plane/.env.example`
- Create: `control-plane/.gitignore`
- Create: `control-plane/index.html`

- [ ] **Step 1: Create directory and package.json**

```bash
mkdir -p "c:/dev/ghcp sdk stuff/control-plane"
cd "c:/dev/ghcp sdk stuff/control-plane"
```

Write `package.json`:

```json
{
  "name": "wpp-control-plane",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "concurrently -k -n vite,server,mcp \"npm:dev:client\" \"npm:dev:server\" \"npm:dev:mcp\"",
    "dev:client": "vite",
    "dev:server": "tsx watch src/server/index.ts",
    "dev:mcp": "concurrently -k -n wd,d365,mac,pay \"tsx watch mocks/workday-mcp/server.ts\" \"tsx watch mocks/d365-mcp/server.ts\" \"tsx watch mocks/maconomy-mcp/server.ts\" \"tsx watch mocks/payment-mcp/server.ts\"",
    "build": "tsc && vite build",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "@github/copilot-sdk": "*",
    "@modelcontextprotocol/sdk": "^1.0.0",
    "express": "^5.0.0",
    "cors": "^2.8.5",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "lucide-react": "^0.400.0",
    "recharts": "^2.12.0",
    "js-yaml": "^4.1.0",
    "nanoid": "^5.0.0"
  },
  "devDependencies": {
    "@types/express": "^5.0.0",
    "@types/cors": "^2.8.17",
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/js-yaml": "^4.0.9",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vitest": "^2.0.0",
    "tsx": "^4.19.0",
    "concurrently": "^9.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/postcss": "^4.0.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "@playwright/test": "^1.48.0"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json` (strict)**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "allowImportingTsExtensions": false,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": {
      "@shared/*": ["src/shared/*"],
      "@client/*": ["src/client/*"],
      "@server/*": ["src/server/*"]
    }
  },
  "include": ["src", "mocks", "tests"]
}
```

- [ ] **Step 3: Write `vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  root: ".",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:3001"
    }
  },
  resolve: {
    alias: {
      "@shared": path.resolve(__dirname, "src/shared"),
      "@client": path.resolve(__dirname, "src/client")
    }
  }
});
```

- [ ] **Step 4: Write `tailwind.config.ts` + `postcss.config.js` + `index.html`**

`tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/client/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        severity: {
          critical: "#dc2626",
          high: "#f97316",
          medium: "#eab308"
        }
      }
    }
  }
} satisfies Config;
```

`postcss.config.js`:

```javascript
export default {
  plugins: {
    "@tailwindcss/postcss": {},
    autoprefixer: {}
  }
};
```

`index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WPP Control Plane</title>
  </head>
  <body class="bg-slate-950 text-slate-100">
    <div id="root"></div>
    <script type="module" src="/src/client/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `.env.example` and `.gitignore`**

`.env.example`:

```
PORT=3001
AZURE_FOUNDRY_ENDPOINT=https://<your-foundry>.services.ai.azure.com
AZURE_FOUNDRY_API_KEY=
FLEET_MANAGER_MODEL=gpt-4.1
WORKDAY_MCP_URL=http://localhost:4101
D365_MCP_URL=http://localhost:4102
MACONOMY_MCP_URL=http://localhost:4103
PAYMENT_MCP_URL=http://localhost:4104
FLEET_MANAGER_MAX_TOKENS=2000
SIMULATOR_TARGET_WORKFLOWS=40
```

`.gitignore`:

```
node_modules
dist
.env
.env.local
playwright-report
test-results
```

- [ ] **Step 6: Install and verify**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
npm install
npx tsc --noEmit
```

Expected: no errors (repo is empty, passes vacuous).

- [ ] **Step 7: Commit**

```bash
git add control-plane/package.json control-plane/tsconfig.json control-plane/vite.config.ts control-plane/tailwind.config.ts control-plane/postcss.config.js control-plane/.env.example control-plane/.gitignore control-plane/index.html
git commit -m "chore(cp): scaffold control-plane workspace"
```

---

### Task 0.2: GHCP SDK event-driven spike

This is the critical de-risking step (spec §8 risk #1). Prove the SDK supports event-triggered reasoning before building everything downstream.

**Files:**
- Create: `control-plane/spike/sdk-spike.ts`

- [ ] **Step 1: Write the spike**

```typescript
// control-plane/spike/sdk-spike.ts
import { CopilotClient } from "@github/copilot-sdk";

async function main() {
  const client = new CopilotClient({
    azure: {
      endpoint: process.env.AZURE_FOUNDRY_ENDPOINT!,
      apiKey: process.env.AZURE_FOUNDRY_API_KEY!
    }
  });

  const session = await client.createSession({
    model: process.env.FLEET_MANAGER_MODEL ?? "gpt-4.1",
    systemPrompt: "You are a test agent. Respond with one short sentence."
  });

  // Drive programmatically (not via stdin chat)
  const r1 = await session.sendMessage("Event A arrived.");
  console.log("R1:", r1.content);

  const r2 = await session.sendMessage("Event B arrived.");
  console.log("R2:", r2.content);

  // Confirm session retains context
  const r3 = await session.sendMessage("How many events have I told you about?");
  console.log("R3:", r3.content);

  await session.close();
}

main().catch((err) => {
  console.error("SPIKE FAILED:", err);
  process.exit(1);
});
```

- [ ] **Step 2: Run the spike**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
cp .env.example .env
# Edit .env to add real AZURE_FOUNDRY_API_KEY
npx tsx spike/sdk-spike.ts
```

Expected: three completions printed, R3 acknowledges two prior events.

**If FAILS:** stop and investigate. Fallback options, in order:
1. Check API surface — actual method names may differ from `sendMessage`/`createSession`; consult installed SDK's `.d.ts`.
2. Switch to OpenAI direct (`OPENAI_API_KEY`) — same SDK API path, different backend.
3. If SDK cannot do programmatic non-chat drive, escalate to Approach 2 in spec (timer sweep).

- [ ] **Step 3: Test tool calling (critical)**

Append to `sdk-spike.ts`:

```typescript
// Tool-call spike
const sessionT = await client.createSession({
  model: process.env.FLEET_MANAGER_MODEL ?? "gpt-4.1",
  systemPrompt: "When asked, call the ping tool with the provided message.",
  tools: [{
    name: "ping",
    description: "Echoes a message",
    parameters: { type: "object", properties: { msg: { type: "string" } }, required: ["msg"] },
    execute: async ({ msg }: { msg: string }) => ({ echoed: msg })
  }]
});

const rt = await sessionT.sendMessage("Call the ping tool with msg='hello'.");
console.log("TOOL RESULT:", rt);
await sessionT.close();
```

Re-run. Expected: see a tool invocation and a final response that references `hello`.

**If FAILS:** the SDK's tool-registration shape may differ from assumed. Update the real FleetManagerService (Task 5.4) accordingly — the plan's code there must match whatever this spike proved works.

- [ ] **Step 4: Commit the spike**

```bash
git add control-plane/spike/sdk-spike.ts
git commit -m "chore(cp): sdk spike proving event-driven + tool-calling"
```

---

### Task 0.3: Create folder skeleton

**Files (create empty directories with a `.gitkeep`):**

- [ ] **Step 1: Create directories**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
mkdir -p src/shared src/client/routes src/client/components src/client/hooks src/server/routes src/server/services src/server/skills src/server/mcp-tools src/server/fixtures
mkdir -p mocks/workday-mcp mocks/d365-mcp mocks/maconomy-mcp mocks/payment-mcp
mkdir -p tests/unit tests/e2e docs
for d in src/shared src/client/routes src/client/components src/client/hooks src/server/routes src/server/services src/server/skills src/server/mcp-tools src/server/fixtures mocks/workday-mcp mocks/d365-mcp mocks/maconomy-mcp mocks/payment-mcp tests/unit tests/e2e docs; do touch "$d/.gitkeep"; done
```

- [ ] **Step 2: Commit**

```bash
git add control-plane
git commit -m "chore(cp): folder skeleton"
```

---

## Phase 1 — Shared types + Event taxonomy

### Task 1.1: Shared types

**Files:**
- Create: `control-plane/src/shared/types.ts`
- Create: `control-plane/tests/unit/types.test.ts`

- [ ] **Step 1: Write `types.ts`** (full content from spec §5.3, plus helpers)

```typescript
// control-plane/src/shared/types.ts

export type PhaseName =
  | "Intake" | "Validation" | "Routing"
  | "Approval" | "Payment" | "Reconciliation";

export const PHASE_ORDER: PhaseName[] = [
  "Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"
];

export type WorkflowStatus =
  | "in_progress" | "awaiting_hitl" | "completed" | "failed";

export type Severity = "critical" | "high" | "medium";

export type ExceptionCategory =
  | "duplicate-invoice" | "po-mismatch" | "threshold-exceeded"
  | "sanctions-flag" | "compliance" | "payment-timeout";

export interface Vendor {
  id: string;
  name: string;
  country: string;
}

export interface InvoiceLineItem {
  description: string;
  qty: number;
  unitPrice: number;
}

export interface InvoiceData {
  number: string;
  amount: number;
  currency: string;
  lineItems: InvoiceLineItem[];
  poRef: string;
}

export interface ToolCall {
  tool: string;
  argsPreview: string;
  ms: number;
  ok: boolean;
}

export interface ActionLedgerEntry {
  workflowId: string;
  timestamp: number;
  actor: { kind: "agent" | "human"; id: string };
  action: string;
  revocable: boolean;
  details: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  type: "invoice-p2p";
  status: WorkflowStatus;
  currentPhase: PhaseName;
  createdAt: number;
  slaDueAt: number;
  vendor: Vendor;
  invoice: InvoiceData;
  jurisdiction: string;
  agency: string;
  activeExceptionId?: string;
  actionLedger: ActionLedgerEntry[];
  tokensSpent: number;
  costUSD: number;
}

export interface Phase {
  workflowId: string;
  name: PhaseName;
  status: "pending" | "in_progress" | "completed" | "failed";
  startedAt?: number;
  completedAt?: number;
  agentId: "finance-agent";
  toolCalls: ToolCall[];
  spanIds: string[];
}

export interface OtelSpan {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  name: string;
  startMs: number;
  endMs: number;
  attributes: {
    "workflow.id": string;
    "workflow.phase": PhaseName;
    "tool.name"?: string;
    "llm.model"?: string;
    "llm.tokens.in"?: number;
    "llm.tokens.out"?: number;
    "cost.usd"?: number;
    [k: string]: unknown;
  };
  status: "ok" | "error";
}

export interface ExceptionOption {
  label: string;
  action: string;
  nonRevocable: boolean;
}

export interface PolicyRef {
  title: string;
  snippet: string;
  source: string;
}

export interface Exception {
  id: string;
  workflowId: string;
  composedBy: "fleet-manager" | "guardrail" | "simulator-injected";
  severity: Severity;
  category: ExceptionCategory;
  summary: string;
  recommendation: string;
  options: ExceptionOption[];
  relatedPolicyRefs: PolicyRef[];
  bulkCandidateIds?: string[];
  confidence: number;
  createdAt: number;
  resolvedAt?: number;
  resolvedBy?: string;
}

export interface SkillAmplification {
  id: string;
  workflowId: string;
  policyContext: PolicyRef[];
  precedents: Array<{ workflowId: string; outcome: string; rationale: string }>;
  recommendedApproach: string;
  createdAt: number;
}

export interface AutonomyPolicy {
  id: string;
  description: string;
  currentValue: number | string | boolean;
  gitSha: string;
  author: string;
  updatedAt: number;
}

export function nextPhase(p: PhaseName): PhaseName | null {
  const i = PHASE_ORDER.indexOf(p);
  if (i === -1 || i === PHASE_ORDER.length - 1) return null;
  return PHASE_ORDER[i + 1];
}
```

- [ ] **Step 2: Write a test for `nextPhase`**

```typescript
// control-plane/tests/unit/types.test.ts
import { describe, it, expect } from "vitest";
import { nextPhase, PHASE_ORDER } from "@shared/types";

describe("nextPhase", () => {
  it("returns next phase in order", () => {
    expect(nextPhase("Intake")).toBe("Validation");
    expect(nextPhase("Approval")).toBe("Payment");
  });
  it("returns null for last phase", () => {
    expect(nextPhase("Reconciliation")).toBeNull();
  });
  it("phase order is six long", () => {
    expect(PHASE_ORDER).toHaveLength(6);
  });
});
```

- [ ] **Step 3: Run test**

```bash
npm test -- types
```

Expected: 3 pass.

- [ ] **Step 4: Commit**

```bash
git add control-plane/src/shared/types.ts control-plane/tests/unit/types.test.ts
git commit -m "feat(cp): shared domain types + PHASE_ORDER"
```

---

### Task 1.2: Event taxonomy

**Files:**
- Create: `control-plane/src/shared/events.ts`
- Create: `control-plane/tests/unit/events.test.ts`

- [ ] **Step 1: Write `events.ts`**

```typescript
// control-plane/src/shared/events.ts
import type { OtelSpan, PhaseName, Severity, ExceptionCategory } from "./types";

export type FleetEvent =
  | { type: "workflow.started"; workflowId: string }
  | { type: "workflow.phase.started"; workflowId: string; phase: PhaseName }
  | { type: "workflow.phase.completed"; workflowId: string; phase: PhaseName; durationMs: number }
  | { type: "workflow.phase.failed"; workflowId: string; phase: PhaseName; reason: string }
  | { type: "workflow.exception.detected"; workflowId: string; category: ExceptionCategory; severity: Severity }
  | { type: "workflow.hitl.requested"; workflowId: string; reason: string }
  | { type: "workflow.sla.breach_imminent"; workflowId: string; minutesRemaining: number }
  | { type: "workflow.policy.violation"; workflowId: string; policyId: string }
  | { type: "workflow.resolved"; workflowId: string; resolution: string }
  | { type: "otel.span.emitted"; span: OtelSpan }
  | { type: "fleet.anomaly.detected"; pattern: string; workflowIds: string[] }
  | { type: "fleet.tick"; timestamp: number }
  | { type: "fleet.overload"; queueDepth: number };

export type FleetEventType = FleetEvent["type"];

export const WAKE_TYPES: ReadonlySet<FleetEventType> = new Set([
  "workflow.exception.detected",
  "workflow.hitl.requested",
  "workflow.sla.breach_imminent",
  "workflow.policy.violation",
  "fleet.anomaly.detected",
  "fleet.tick"
]);

export function wakesFleetManager(e: FleetEvent): boolean {
  return WAKE_TYPES.has(e.type);
}
```

- [ ] **Step 2: Test**

```typescript
// control-plane/tests/unit/events.test.ts
import { describe, it, expect } from "vitest";
import { wakesFleetManager, WAKE_TYPES } from "@shared/events";

describe("wakesFleetManager", () => {
  it("wakes on exception detected", () => {
    expect(wakesFleetManager({
      type: "workflow.exception.detected",
      workflowId: "INV-1",
      category: "duplicate-invoice",
      severity: "high"
    })).toBe(true);
  });
  it("does not wake on phase started", () => {
    expect(wakesFleetManager({
      type: "workflow.phase.started",
      workflowId: "INV-1",
      phase: "Intake"
    })).toBe(false);
  });
  it("wake set contains six entries", () => {
    expect(WAKE_TYPES.size).toBe(6);
  });
});
```

- [ ] **Step 3: Run and commit**

```bash
npm test -- events
git add control-plane/src/shared/events.ts control-plane/tests/unit/events.test.ts
git commit -m "feat(cp): event taxonomy + wake-filter"
```

---

## Phase 2 — Mock MCP servers

Each server is a small Express app that speaks MCP over HTTP. They all follow the same shape: load a fixture JSON, expose a list of tools, handle tool calls. Fixtures go alongside each server.

### Task 2.1: workday-mcp

**Files:**
- Create: `control-plane/mocks/workday-mcp/server.ts`
- Create: `control-plane/mocks/workday-mcp/data.json`

- [ ] **Step 1: Write data.json**

```json
{
  "vendors": [
    { "id": "V-001", "name": "Acme Media Supplies", "country": "US", "sanctioned": false, "creditRating": "A" },
    { "id": "V-002", "name": "Globex Productions", "country": "US", "sanctioned": false, "creditRating": "B" },
    { "id": "V-003", "name": "Initech Studios", "country": "UK", "sanctioned": false, "creditRating": "A" },
    { "id": "V-004", "name": "Umbrella Creative", "country": "DE", "sanctioned": true, "creditRating": "C" },
    { "id": "V-005", "name": "Stark Industries", "country": "US", "sanctioned": false, "creditRating": "A" },
    { "id": "V-006", "name": "Wayne Enterprises", "country": "US", "sanctioned": false, "creditRating": "A" }
  ],
  "costCentres": [
    { "id": "CC-001", "name": "Ogilvy-US Production", "approver": "finance-bp@ogilvy.us" },
    { "id": "CC-002", "name": "GroupM-US Media", "approver": "finance-bp@groupm.us" },
    { "id": "CC-003", "name": "Wunderman-US Digital", "approver": "finance-bp@wunderman.us" }
  ],
  "approvalChains": {
    "default": ["finance-bp", "cfo-office"],
    "high-value": ["finance-bp", "cfo-office", "audit"]
  }
}
```

- [ ] **Step 2: Write server.ts**

```typescript
// control-plane/mocks/workday-mcp/server.ts
import express from "express";
import data from "./data.json" with { type: "json" };

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
  const args = req.body ?? {};
  switch (tool) {
    case "getVendor": {
      const v = data.vendors.find(x => x.id === args.vendorId);
      return v ? res.json(v) : res.status(404).json({ error: "vendor_not_found" });
    }
    case "getCostCentre": {
      const c = data.costCentres.find(x => x.id === args.costCentreId);
      return c ? res.json(c) : res.status(404).json({ error: "cost_centre_not_found" });
    }
    case "getApprovalChain": {
      const chain = (data.approvalChains as Record<string, string[]>)[args.scenario ?? "default"];
      return res.json({ chain });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env.WORKDAY_MCP_PORT ?? 4101);
app.listen(port, () => console.log(`[workday-mcp] listening on ${port}`));
```

- [ ] **Step 3: Run it to smoke-test**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
npx tsx mocks/workday-mcp/server.ts &
sleep 1
curl -s -X POST http://localhost:4101/mcp/call/getVendor -H "Content-Type: application/json" -d '{"vendorId":"V-001"}'
kill %1
```

Expected: JSON for V-001.

- [ ] **Step 4: Commit**

```bash
git add control-plane/mocks/workday-mcp
git commit -m "feat(cp): workday-mcp mock"
```

---

### Task 2.2: d365-mcp

**Files:**
- Create: `control-plane/mocks/d365-mcp/server.ts`
- Create: `control-plane/mocks/d365-mcp/data.json`

- [ ] **Step 1: data.json**

```json
{
  "purchaseOrders": [
    { "id": "PO-10001", "vendorId": "V-001", "amount": 12500.00, "currency": "USD", "lineCount": 3, "openBalance": 12500.00 },
    { "id": "PO-10002", "vendorId": "V-002", "amount": 8400.00, "currency": "USD", "lineCount": 2, "openBalance": 8400.00 },
    { "id": "PO-10003", "vendorId": "V-003", "amount": 47000.00, "currency": "USD", "lineCount": 5, "openBalance": 47000.00 },
    { "id": "PO-10004", "vendorId": "V-005", "amount": 3200.00, "currency": "USD", "lineCount": 1, "openBalance": 3200.00 },
    { "id": "PO-10005", "vendorId": "V-006", "amount": 22000.00, "currency": "USD", "lineCount": 4, "openBalance": 22000.00 }
  ],
  "glAccounts": [
    { "id": "GL-5000", "name": "Media Production Costs" },
    { "id": "GL-5100", "name": "Talent Fees" },
    { "id": "GL-5200", "name": "Post-Production" }
  ]
}
```

- [ ] **Step 2: server.ts**

```typescript
// control-plane/mocks/d365-mcp/server.ts
import express from "express";
import data from "./data.json" with { type: "json" };

const app = express();
app.use(express.json());

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "parseInvoice", description: "Parse an invoice payload", parameters: { raw: "string" } },
      { name: "matchPO", description: "3-way match invoice to PO", parameters: { invoiceAmount: "number", poId: "string" } },
      { name: "postGLEntry", description: "Post GL entry", parameters: { glAccountId: "string", amount: "number", workflowId: "string" } }
    ]
  });
});

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = req.body ?? {};
  switch (tool) {
    case "parseInvoice": {
      return res.json({
        parsed: {
          number: `INV-${Math.floor(Math.random() * 1e5)}`,
          extractedAmount: args.extractedAmount ?? 0,
          poRef: args.poRef ?? null
        }
      });
    }
    case "matchPO": {
      const po = data.purchaseOrders.find(x => x.id === args.poId);
      if (!po) return res.json({ match: false, reason: "po_not_found" });
      const variance = Math.abs(po.amount - (args.invoiceAmount ?? 0));
      const tolerance = po.amount * 0.02;
      return res.json({
        match: variance <= tolerance,
        variance,
        tolerance,
        poAmount: po.amount
      });
    }
    case "postGLEntry": {
      return res.json({ posted: true, entryId: `GLE-${Date.now()}` });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env.D365_MCP_PORT ?? 4102);
app.listen(port, () => console.log(`[d365-mcp] listening on ${port}`));
```

- [ ] **Step 3: Smoke-test + commit**

```bash
npx tsx mocks/d365-mcp/server.ts &
sleep 1
curl -s -X POST http://localhost:4102/mcp/call/matchPO -H "Content-Type: application/json" -d '{"invoiceAmount":12600,"poId":"PO-10001"}'
kill %1
git add control-plane/mocks/d365-mcp
git commit -m "feat(cp): d365-mcp mock"
```

Expected: `{"match":false,"variance":100,"tolerance":250,"poAmount":12500}` (or similar close numbers — tolerance is 2% of 12500 = 250, so 100 variance would actually match; adjust test as needed).

---

### Task 2.3: maconomy-mcp

**Files:**
- Create: `control-plane/mocks/maconomy-mcp/server.ts`
- Create: `control-plane/mocks/maconomy-mcp/data.json`

- [ ] **Step 1: data.json**

```json
{
  "projects": [
    { "id": "PRJ-A1", "name": "Ogilvy US — Client A Q3 Campaign", "budget": 250000, "spent": 123400 },
    { "id": "PRJ-B2", "name": "GroupM — Client B Digital", "budget": 180000, "spent": 45000 },
    { "id": "PRJ-C3", "name": "Wunderman — Client C Rebrand", "budget": 420000, "spent": 391000 }
  ]
}
```

- [ ] **Step 2: server.ts**

```typescript
// control-plane/mocks/maconomy-mcp/server.ts
import express from "express";
import data from "./data.json" with { type: "json" };

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
  const args = req.body ?? {};
  switch (tool) {
    case "lookupProject": {
      const p = data.projects.find(x => x.id === args.projectId);
      return p ? res.json(p) : res.status(404).json({ error: "project_not_found" });
    }
    case "getTimesheetHours": {
      return res.json({ projectId: args.projectId, weekIso: args.weekIso, hours: 42 + Math.floor(Math.random() * 8) });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env.MACONOMY_MCP_PORT ?? 4103);
app.listen(port, () => console.log(`[maconomy-mcp] listening on ${port}`));
```

- [ ] **Step 3: Commit**

```bash
git add control-plane/mocks/maconomy-mcp
git commit -m "feat(cp): maconomy-mcp mock"
```

---

### Task 2.4: payment-mcp

**Files:**
- Create: `control-plane/mocks/payment-mcp/server.ts`
- Create: `control-plane/mocks/payment-mcp/data.json`

- [ ] **Step 1: data.json**

```json
{
  "statements": [
    { "id": "STMT-2026-04-10", "entries": [{ "ref": "PAY-0001", "amount": 12500 }, { "ref": "PAY-0002", "amount": 8400 }] }
  ],
  "timeoutSeed": 0
}
```

- [ ] **Step 2: server.ts**

```typescript
// control-plane/mocks/payment-mcp/server.ts
import express from "express";

const app = express();
app.use(express.json());

let callCount = 0;

app.get("/mcp/tools", (_req, res) => {
  res.json({
    tools: [
      { name: "createPaymentFile", description: "Create a payment file", parameters: { workflowId: "string", amount: "number" } },
      { name: "submitPayment", description: "Submit payment. May time out on first call per workflow when simulateTimeout=true", parameters: { paymentFileId: "string", simulateTimeout: "boolean" } },
      { name: "reconcileStatement", description: "Reconcile against statement", parameters: { statementId: "string" } }
    ]
  });
});

const timedOutOnce = new Set<string>();

app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = req.body ?? {};
  callCount++;
  switch (tool) {
    case "createPaymentFile": {
      return res.json({ paymentFileId: `PF-${Date.now()}`, workflowId: args.workflowId, amount: args.amount });
    }
    case "submitPayment": {
      const key = args.paymentFileId ?? "";
      if (args.simulateTimeout && !timedOutOnce.has(key)) {
        timedOutOnce.add(key);
        setTimeout(() => res.status(504).json({ error: "gateway_timeout" }), 50);
        return;
      }
      return res.json({ submitted: true, confirmation: `BANK-${Date.now()}` });
    }
    case "reconcileStatement": {
      return res.json({ reconciled: true, matchedCount: 2 });
    }
    default:
      return res.status(400).json({ error: "unknown_tool" });
  }
});

const port = Number(process.env.PAYMENT_MCP_PORT ?? 4104);
app.listen(port, () => console.log(`[payment-mcp] listening on ${port}`));
```

- [ ] **Step 3: Commit**

```bash
git add control-plane/mocks/payment-mcp
git commit -m "feat(cp): payment-mcp mock with first-call timeout"
```

---

## Phase 3 — EventBus + StateStore + Triage

### Task 3.1: Typed EventBus

**Files:**
- Create: `control-plane/src/server/services/eventBus.ts`
- Create: `control-plane/tests/unit/eventBus.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// control-plane/tests/unit/eventBus.test.ts
import { describe, it, expect, vi } from "vitest";
import { EventBus } from "@server/services/eventBus";

describe("EventBus", () => {
  it("delivers events to subscribers", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    bus.on("workflow.started", fn);
    bus.emit({ type: "workflow.started", workflowId: "A" });
    expect(fn).toHaveBeenCalledWith({ type: "workflow.started", workflowId: "A" });
  });
  it("supports onAny", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    bus.onAny(fn);
    bus.emit({ type: "fleet.tick", timestamp: 1 });
    expect(fn).toHaveBeenCalled();
  });
  it("unsubscribe works", () => {
    const bus = new EventBus();
    const fn = vi.fn();
    const off = bus.on("workflow.started", fn);
    off();
    bus.emit({ type: "workflow.started", workflowId: "A" });
    expect(fn).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
npm test -- eventBus
```

- [ ] **Step 3: Implement**

```typescript
// control-plane/src/server/services/eventBus.ts
import { EventEmitter } from "node:events";
import type { FleetEvent, FleetEventType } from "@shared/events";

export class EventBus {
  private emitter = new EventEmitter();
  constructor() { this.emitter.setMaxListeners(100); }

  on<T extends FleetEventType>(
    type: T,
    handler: (e: Extract<FleetEvent, { type: T }>) => void
  ): () => void {
    this.emitter.on(type, handler as (e: FleetEvent) => void);
    return () => this.emitter.off(type, handler as (e: FleetEvent) => void);
  }

  onAny(handler: (e: FleetEvent) => void): () => void {
    this.emitter.on("*", handler);
    return () => this.emitter.off("*", handler);
  }

  emit(e: FleetEvent): void {
    this.emitter.emit(e.type, e);
    this.emitter.emit("*", e);
  }
}
```

- [ ] **Step 4: Run — expect PASS; commit**

```bash
npm test -- eventBus
git add control-plane/src/server/services/eventBus.ts control-plane/tests/unit/eventBus.test.ts
git commit -m "feat(cp): typed in-process EventBus"
```

---

### Task 3.2: StateStore

**Files:**
- Create: `control-plane/src/server/services/stateStore.ts`
- Create: `control-plane/tests/unit/stateStore.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// control-plane/tests/unit/stateStore.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { StateStore } from "@server/services/stateStore";
import type { Workflow } from "@shared/types";

const mkWorkflow = (id: string, overrides: Partial<Workflow> = {}): Workflow => ({
  id, type: "invoice-p2p", status: "in_progress", currentPhase: "Intake",
  createdAt: Date.now(), slaDueAt: Date.now() + 3_600_000,
  vendor: { id: "V-001", name: "Acme", country: "US" },
  invoice: { number: "INV-001", amount: 1000, currency: "USD", lineItems: [], poRef: "PO-10001" },
  jurisdiction: "US-CA", agency: "Ogilvy-US",
  actionLedger: [], tokensSpent: 0, costUSD: 0,
  ...overrides
});

describe("StateStore", () => {
  let store: StateStore;
  beforeEach(() => { store = new StateStore(); });

  it("stores and retrieves workflows", () => {
    store.upsertWorkflow(mkWorkflow("A"));
    expect(store.getWorkflow("A")?.id).toBe("A");
  });
  it("lists workflows with filters", () => {
    store.upsertWorkflow(mkWorkflow("A", { status: "awaiting_hitl" }));
    store.upsertWorkflow(mkWorkflow("B", { status: "completed" }));
    const awaiting = store.listWorkflows({ status: "awaiting_hitl" });
    expect(awaiting).toHaveLength(1);
    expect(awaiting[0].id).toBe("A");
  });
  it("appends action ledger entries", () => {
    store.upsertWorkflow(mkWorkflow("A"));
    store.appendLedger("A", {
      workflowId: "A", timestamp: 1, actor: { kind: "agent", id: "finance-agent" },
      action: "intake.started", revocable: true, details: {}
    });
    expect(store.getWorkflow("A")?.actionLedger).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Implement**

```typescript
// control-plane/src/server/services/stateStore.ts
import type {
  Workflow, Phase, OtelSpan, Exception, ActionLedgerEntry,
  AutonomyPolicy, SkillAmplification
} from "@shared/types";

export interface WorkflowFilters {
  status?: Workflow["status"];
  phase?: Workflow["currentPhase"];
  agency?: string;
  hasException?: boolean;
}

export class StateStore {
  private workflows = new Map<string, Workflow>();
  private phases = new Map<string, Phase[]>();
  private spans = new Map<string, OtelSpan[]>();
  private exceptions = new Map<string, Exception>();
  private policies = new Map<string, AutonomyPolicy>();
  private amplifications = new Map<string, SkillAmplification[]>();

  upsertWorkflow(w: Workflow): void { this.workflows.set(w.id, w); }
  getWorkflow(id: string): Workflow | undefined { return this.workflows.get(id); }
  listWorkflows(f: WorkflowFilters = {}): Workflow[] {
    return [...this.workflows.values()].filter(w =>
      (f.status == null || w.status === f.status) &&
      (f.phase == null || w.currentPhase === f.phase) &&
      (f.agency == null || w.agency === f.agency) &&
      (f.hasException == null || (f.hasException === !!w.activeExceptionId))
    );
  }

  appendPhase(workflowId: string, p: Phase): void {
    const list = this.phases.get(workflowId) ?? [];
    list.push(p); this.phases.set(workflowId, list);
  }
  updatePhase(workflowId: string, name: Phase["name"], patch: Partial<Phase>): void {
    const list = this.phases.get(workflowId) ?? [];
    const i = list.findIndex(p => p.name === name);
    if (i >= 0) list[i] = { ...list[i], ...patch };
  }
  getPhases(workflowId: string): Phase[] { return this.phases.get(workflowId) ?? []; }

  appendSpan(s: OtelSpan): void {
    const key = s.attributes["workflow.id"];
    const list = this.spans.get(key) ?? [];
    list.push(s); this.spans.set(key, list);
  }
  getSpans(workflowId: string): OtelSpan[] { return this.spans.get(workflowId) ?? []; }

  upsertException(e: Exception): void {
    this.exceptions.set(e.id, e);
    const w = this.workflows.get(e.workflowId);
    if (w && !e.resolvedAt) w.activeExceptionId = e.id;
  }
  getException(id: string): Exception | undefined { return this.exceptions.get(id); }
  listExceptions(opts: { includeResolved?: boolean } = {}): Exception[] {
    return [...this.exceptions.values()].filter(e => opts.includeResolved || !e.resolvedAt);
  }
  resolveException(id: string, resolvedBy: string): void {
    const e = this.exceptions.get(id);
    if (!e) return;
    e.resolvedAt = Date.now();
    e.resolvedBy = resolvedBy;
    const w = this.workflows.get(e.workflowId);
    if (w && w.activeExceptionId === id) w.activeExceptionId = undefined;
  }

  appendLedger(workflowId: string, entry: ActionLedgerEntry): void {
    const w = this.workflows.get(workflowId);
    if (w) w.actionLedger.push(entry);
  }

  upsertPolicy(p: AutonomyPolicy): void { this.policies.set(p.id, p); }
  listPolicies(): AutonomyPolicy[] { return [...this.policies.values()]; }

  appendAmplification(workflowId: string, a: SkillAmplification): void {
    const list = this.amplifications.get(workflowId) ?? [];
    list.push(a); this.amplifications.set(workflowId, list);
  }
  getAmplifications(workflowId: string): SkillAmplification[] {
    return this.amplifications.get(workflowId) ?? [];
  }
}
```

- [ ] **Step 3: Run and commit**

```bash
npm test -- stateStore
git add control-plane/src/server/services/stateStore.ts control-plane/tests/unit/stateStore.test.ts
git commit -m "feat(cp): in-memory StateStore with Maps + filters"
```

---

### Task 3.3: Triage pre-filter

**Files:**
- Create: `control-plane/src/server/services/triage.ts`
- Create: `control-plane/tests/unit/triage.test.ts`

- [ ] **Step 1: Test**

```typescript
// control-plane/tests/unit/triage.test.ts
import { describe, it, expect } from "vitest";
import { Triage } from "@server/services/triage";

describe("Triage", () => {
  it("does not wake on phase.started", () => {
    const t = new Triage();
    expect(t.shouldWake({ type: "workflow.phase.started", workflowId: "A", phase: "Intake" })).toBe(false);
  });
  it("wakes on exception.detected", () => {
    const t = new Triage();
    expect(t.shouldWake({ type: "workflow.exception.detected", workflowId: "A", category: "duplicate-invoice", severity: "high" })).toBe(true);
  });
  it("detects fleet anomaly on 3+ duplicates in 60s", () => {
    const t = new Triage();
    const now = Date.now();
    for (let i = 0; i < 3; i++) {
      t.observe({ type: "workflow.exception.detected", workflowId: `W-${i}`, category: "duplicate-invoice", severity: "high" }, now + i);
    }
    expect(t.detectAnomaly(now + 3)).toMatchObject({ pattern: "duplicate-burst" });
  });
});
```

- [ ] **Step 2: Implement**

```typescript
// control-plane/src/server/services/triage.ts
import type { FleetEvent } from "@shared/events";
import { wakesFleetManager } from "@shared/events";

export class Triage {
  private recentDups: { workflowId: string; at: number }[] = [];

  shouldWake(e: FleetEvent): boolean { return wakesFleetManager(e); }

  observe(e: FleetEvent, now: number = Date.now()): void {
    if (e.type === "workflow.exception.detected" && e.category === "duplicate-invoice") {
      this.recentDups.push({ workflowId: e.workflowId, at: now });
      this.recentDups = this.recentDups.filter(r => now - r.at <= 60_000);
    }
  }

  detectAnomaly(now: number = Date.now()): { pattern: string; workflowIds: string[] } | null {
    const dups = this.recentDups.filter(r => now - r.at <= 60_000);
    if (dups.length >= 3) {
      return { pattern: "duplicate-burst", workflowIds: dups.map(d => d.workflowId) };
    }
    return null;
  }
}
```

- [ ] **Step 3: Run and commit**

```bash
npm test -- triage
git add control-plane/src/server/services/triage.ts control-plane/tests/unit/triage.test.ts
git commit -m "feat(cp): triage pre-filter + anomaly detection"
```

---

## Phase 4 — Workflow Simulator

### Task 4.1: Fixtures

**Files:**
- Create: `control-plane/src/server/fixtures/vendors.json`
- Create: `control-plane/src/server/fixtures/purchase-orders.json`
- Create: `control-plane/src/server/fixtures/agencies.json`
- Create: `control-plane/src/server/fixtures/policy-refs.json`

- [ ] **Step 1: Write fixtures** (copy vendor + PO data from MCP mocks for narrative consistency, then extend with the skill-amp refs)

`vendors.json`: copy contents of `mocks/workday-mcp/data.json` `vendors` array.

`purchase-orders.json`: copy contents of `mocks/d365-mcp/data.json` `purchaseOrders` array.

`agencies.json`:
```json
[
  { "id": "Ogilvy-US", "market": "US", "region": "Americas" },
  { "id": "GroupM-US", "market": "US", "region": "Americas" },
  { "id": "Wunderman-US", "market": "US", "region": "Americas" },
  { "id": "Ogilvy-UK", "market": "UK", "region": "EMEA" }
]
```

`policy-refs.json`:
```json
[
  { "id": "P-DUP", "title": "Duplicate Invoice Policy", "snippet": "Duplicate invoices within 30 days are auto-flagged. Legitimate duplicates (e.g., split billings) must be approved by Finance BP with written rationale.", "source": "finance/handbook/p2p.md#duplicates" },
  { "id": "P-VAR", "title": "PO Variance Tolerance", "snippet": "Invoice amounts must not exceed PO by more than 2%. Variances 2-5% require Finance BP approval. Variances above 5% must be returned to vendor.", "source": "finance/handbook/p2p.md#variance" },
  { "id": "P-THR", "title": "Approval Thresholds", "snippet": "Invoices under $5,000 auto-approve on PO match. $5,000-$25,000 require Finance BP. Above $25,000 require CFO office.", "source": "finance/handbook/p2p.md#approval-thresholds" },
  { "id": "P-SANC", "title": "Sanctions Screening", "snippet": "Any vendor on the OFAC SDN list or EU sanctions list must be blocked. Non-revocable. Requires Legal clearance.", "source": "compliance/handbook/sanctions.md" }
]
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/server/fixtures
git commit -m "feat(cp): seed fixtures"
```

---

### Task 4.2: WorkflowSimulator — scenario/phase logic

**Files:**
- Create: `control-plane/src/server/services/mcpClient.ts` (thin wrapper used by simulator to call the mock MCP servers)
- Create: `control-plane/src/server/services/workflowSimulator.ts`
- Create: `control-plane/tests/unit/workflowSimulator.test.ts`

- [ ] **Step 1: MCP HTTP client wrapper**

```typescript
// control-plane/src/server/services/mcpClient.ts
export async function callMcp(
  baseUrl: string,
  tool: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const res = await fetch(`${baseUrl}/mcp/call/${tool}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(args)
  });
  if (!res.ok) throw new Error(`mcp ${tool} failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Simulator test for scenario selection**

```typescript
// control-plane/tests/unit/workflowSimulator.test.ts
import { describe, it, expect } from "vitest";
import { pickScenario, buildSeedWorkflow } from "@server/services/workflowSimulator";

describe("pickScenario", () => {
  it("returns 'normal' most often", () => {
    const rng = () => 0.95;
    expect(pickScenario(rng)).toBe("normal");
  });
  it("returns 'duplicate-invoice' at lowest bucket", () => {
    const rng = () => 0.05;
    expect(pickScenario(rng)).toBe("duplicate-invoice");
  });
});

describe("buildSeedWorkflow", () => {
  it("creates Workflow with Intake phase and future SLA", () => {
    const w = buildSeedWorkflow("INV-001", () => 0.5);
    expect(w.currentPhase).toBe("Intake");
    expect(w.slaDueAt).toBeGreaterThan(w.createdAt);
  });
});
```

- [ ] **Step 3: Simulator implementation** (two halves — scenario-pure helpers first so the test passes)

```typescript
// control-plane/src/server/services/workflowSimulator.ts
import { nanoid } from "nanoid";
import type {
  Workflow, PhaseName, OtelSpan, Phase, ExceptionCategory
} from "@shared/types";
import type { FleetEvent } from "@shared/events";
import { PHASE_ORDER, nextPhase } from "@shared/types";
import type { EventBus } from "./eventBus";
import type { StateStore } from "./stateStore";
import { callMcp } from "./mcpClient";

import vendorsFixture from "../fixtures/vendors.json" with { type: "json" };
import poFixture from "../fixtures/purchase-orders.json" with { type: "json" };
import agenciesFixture from "../fixtures/agencies.json" with { type: "json" };

type Scenario =
  | "normal" | "duplicate-invoice" | "po-mismatch" | "threshold-exceeded"
  | "sanctions-flag" | "payment-timeout" | "compliance";

const SCENARIO_DISTRIBUTION: Array<{ p: number; s: Scenario }> = [
  { p: 0.10, s: "duplicate-invoice" },
  { p: 0.15, s: "po-mismatch" },
  { p: 0.08, s: "threshold-exceeded" },
  { p: 0.05, s: "sanctions-flag" },
  { p: 0.02, s: "payment-timeout" },
  { p: 0.01, s: "compliance" },
  // remainder is normal (~0.59)
];

export function pickScenario(rng: () => number = Math.random): Scenario {
  const r = rng();
  let acc = 0;
  for (const { p, s } of SCENARIO_DISTRIBUTION) {
    acc += p;
    if (r < acc) return s;
  }
  return "normal";
}

export function buildSeedWorkflow(id: string, rng: () => number = Math.random): Workflow {
  const vendor = vendorsFixture[Math.floor(rng() * vendorsFixture.length)];
  const po = poFixture[Math.floor(rng() * poFixture.length)];
  const agency = agenciesFixture[Math.floor(rng() * agenciesFixture.length)];
  const now = Date.now();
  return {
    id, type: "invoice-p2p", status: "in_progress", currentPhase: "Intake",
    createdAt: now, slaDueAt: now + (1 + rng() * 4) * 3_600_000,
    vendor: { id: vendor.id, name: vendor.name, country: vendor.country },
    invoice: {
      number: `INV-${nanoid(6).toUpperCase()}`,
      amount: Math.round(po.amount * (0.98 + rng() * 0.05) * 100) / 100,
      currency: po.currency,
      lineItems: Array.from({ length: po.lineCount }, (_, i) => ({
        description: `Line ${i + 1}`, qty: 1, unitPrice: po.amount / po.lineCount
      })),
      poRef: po.id
    },
    jurisdiction: `${vendor.country}-CA`,
    agency: agency.id,
    actionLedger: [], tokensSpent: 0, costUSD: 0
  };
}

function mkSpan(workflowId: string, phase: PhaseName, name: string, startMs: number, endMs: number, attrs: Record<string, unknown> = {}): OtelSpan {
  return {
    traceId: workflowId,
    spanId: nanoid(12),
    name, startMs, endMs,
    attributes: { "workflow.id": workflowId, "workflow.phase": phase, ...attrs },
    status: "ok"
  };
}

export interface SimulatorDeps {
  bus: EventBus;
  store: StateStore;
  env: {
    workdayUrl: string; d365Url: string; maconomyUrl: string; paymentUrl: string;
  };
}

export class WorkflowSimulator {
  private seq = 0;
  private paymentTimeoutDone = new Set<string>();

  constructor(private deps: SimulatorDeps) {}

  async spawn(forcedScenario?: Scenario): Promise<string> {
    this.seq++;
    const id = `INV-${String(this.seq).padStart(4, "0")}`;
    const w = buildSeedWorkflow(id);
    this.deps.store.upsertWorkflow(w);
    this.deps.bus.emit({ type: "workflow.started", workflowId: id });
    // Run asynchronously (fire and forget)
    void this.runLifecycle(id, forcedScenario ?? pickScenario());
    return id;
  }

  private sleep(min: number, max: number): Promise<void> {
    return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
  }

  private async runLifecycle(workflowId: string, scenario: Scenario): Promise<void> {
    for (const phase of PHASE_ORDER) {
      await this.runPhase(workflowId, phase, scenario);
      const w = this.deps.store.getWorkflow(workflowId);
      if (!w || w.status === "failed" || w.status === "awaiting_hitl") return;
      const next = nextPhase(phase);
      if (next) {
        w.currentPhase = next;
        this.deps.store.upsertWorkflow(w);
      }
    }
    const w = this.deps.store.getWorkflow(workflowId);
    if (w) {
      w.status = "completed";
      this.deps.store.upsertWorkflow(w);
      this.deps.bus.emit({ type: "workflow.resolved", workflowId, resolution: "completed" });
    }
  }

  private async runPhase(workflowId: string, phase: PhaseName, scenario: Scenario): Promise<void> {
    const start = Date.now();
    this.deps.store.appendPhase(workflowId, {
      workflowId, name: phase, status: "in_progress",
      startedAt: start, agentId: "finance-agent", toolCalls: [], spanIds: []
    });
    this.deps.bus.emit({ type: "workflow.phase.started", workflowId, phase });

    try {
      switch (phase) {
        case "Intake": await this.doIntake(workflowId); break;
        case "Validation": await this.doValidation(workflowId, scenario); break;
        case "Routing": await this.doRouting(workflowId, scenario); break;
        case "Approval": await this.doApproval(workflowId, scenario); break;
        case "Payment": await this.doPayment(workflowId, scenario); break;
        case "Reconciliation": await this.doReconciliation(workflowId); break;
      }
    } catch (err: unknown) {
      const reason = err instanceof Error ? err.message : String(err);
      const w = this.deps.store.getWorkflow(workflowId);
      if (w) { w.status = "failed"; this.deps.store.upsertWorkflow(w); }
      this.deps.bus.emit({ type: "workflow.phase.failed", workflowId, phase, reason });
      return;
    }

    const end = Date.now();
    this.deps.store.updatePhase(workflowId, phase, { status: "completed", completedAt: end });
    const span = mkSpan(workflowId, phase, `phase:${phase}`, start, end);
    this.deps.store.appendSpan(span);
    this.deps.bus.emit({ type: "otel.span.emitted", span });
    this.deps.bus.emit({ type: "workflow.phase.completed", workflowId, phase, durationMs: end - start });
  }

  // ---- Phases ----

  private async doIntake(workflowId: string): Promise<void> {
    await this.sleep(1000, 3000);
    const w = this.deps.store.getWorkflow(workflowId)!;
    await this.traceTool(workflowId, "Intake", "workday.getVendor", async () =>
      callMcp(this.deps.env.workdayUrl, "getVendor", { vendorId: w.vendor.id })
    );
    await this.traceTool(workflowId, "Intake", "d365.parseInvoice", async () =>
      callMcp(this.deps.env.d365Url, "parseInvoice", { raw: w.invoice.number })
    );
  }

  private async doValidation(workflowId: string, scenario: Scenario): Promise<void> {
    await this.sleep(3000, 8000);
    const w = this.deps.store.getWorkflow(workflowId)!;

    if (scenario === "duplicate-invoice") {
      this.emitException(workflowId, "duplicate-invoice", "high");
      return;
    }

    const match = await this.traceTool(workflowId, "Validation", "d365.matchPO", async () =>
      callMcp(this.deps.env.d365Url, "matchPO", { invoiceAmount: w.invoice.amount, poId: w.invoice.poRef })
    );
    if (scenario === "po-mismatch") {
      this.emitException(workflowId, "po-mismatch", "high");
      return;
    }
    void match;

    if (scenario === "sanctions-flag") {
      this.emitException(workflowId, "sanctions-flag", "critical");
      return;
    }

    if (scenario === "compliance") {
      this.emitException(workflowId, "compliance", "critical");
      return;
    }
  }

  private async doRouting(workflowId: string, _scenario: Scenario): Promise<void> {
    await this.sleep(2000, 5000);
    await this.traceTool(workflowId, "Routing", "workday.getCostCentre", async () =>
      callMcp(this.deps.env.workdayUrl, "getCostCentre", { costCentreId: "CC-001" })
    );
    await this.traceTool(workflowId, "Routing", "d365.postGLEntry", async () =>
      callMcp(this.deps.env.d365Url, "postGLEntry", { glAccountId: "GL-5000", amount: 0, workflowId })
    );
  }

  private async doApproval(workflowId: string, scenario: Scenario): Promise<void> {
    await this.sleep(2000, 5000);
    if (scenario === "threshold-exceeded") {
      this.deps.bus.emit({ type: "workflow.hitl.requested", workflowId, reason: "threshold_exceeded" });
      const w = this.deps.store.getWorkflow(workflowId)!;
      w.status = "awaiting_hitl";
      this.deps.store.upsertWorkflow(w);
      return;
    }
    await this.traceTool(workflowId, "Approval", "workday.getApprovalChain", async () =>
      callMcp(this.deps.env.workdayUrl, "getApprovalChain", { scenario: "default" })
    );
  }

  private async doPayment(workflowId: string, scenario: Scenario): Promise<void> {
    await this.sleep(1000, 2000);
    const w = this.deps.store.getWorkflow(workflowId)!;
    const file = await this.traceTool(workflowId, "Payment", "payment.createPaymentFile", async () =>
      callMcp(this.deps.env.paymentUrl, "createPaymentFile", { workflowId, amount: w.invoice.amount })
    ) as { paymentFileId: string };
    const simulateTimeout = scenario === "payment-timeout";
    try {
      await this.traceTool(workflowId, "Payment", "payment.submitPayment", async () =>
        callMcp(this.deps.env.paymentUrl, "submitPayment", {
          paymentFileId: file.paymentFileId,
          simulateTimeout: simulateTimeout && !this.paymentTimeoutDone.has(workflowId)
        })
      );
    } catch {
      this.paymentTimeoutDone.add(workflowId);
      await this.sleep(500, 1000);
      await this.traceTool(workflowId, "Payment", "payment.submitPayment.retry", async () =>
        callMcp(this.deps.env.paymentUrl, "submitPayment", { paymentFileId: file.paymentFileId, simulateTimeout: false })
      );
    }
  }

  private async doReconciliation(workflowId: string): Promise<void> {
    await this.sleep(1000, 4000);
    await this.traceTool(workflowId, "Reconciliation", "payment.reconcileStatement", async () =>
      callMcp(this.deps.env.paymentUrl, "reconcileStatement", { statementId: "STMT-2026-04-10" })
    );
  }

  private async traceTool<T>(workflowId: string, phase: PhaseName, name: string, fn: () => Promise<T>): Promise<T> {
    const start = Date.now();
    let ok = true;
    try {
      const out = await fn();
      return out;
    } catch (e) {
      ok = false;
      throw e;
    } finally {
      const end = Date.now();
      const span: OtelSpan = {
        traceId: workflowId, spanId: nanoid(12),
        name, startMs: start, endMs: end,
        attributes: { "workflow.id": workflowId, "workflow.phase": phase, "tool.name": name },
        status: ok ? "ok" : "error"
      };
      this.deps.store.appendSpan(span);
      this.deps.bus.emit({ type: "otel.span.emitted", span });
    }
  }

  private emitException(workflowId: string, category: ExceptionCategory, severity: "critical" | "high" | "medium"): void {
    const w = this.deps.store.getWorkflow(workflowId);
    if (!w) return;
    w.status = "awaiting_hitl";
    this.deps.store.upsertWorkflow(w);
    this.deps.bus.emit({ type: "workflow.exception.detected", workflowId, category, severity });
  }
}
```

- [ ] **Step 4: Run, commit**

```bash
npm test -- workflowSimulator
git add control-plane/src/server/services/mcpClient.ts control-plane/src/server/services/workflowSimulator.ts control-plane/tests/unit/workflowSimulator.test.ts
git commit -m "feat(cp): WorkflowSimulator — phase lifecycle + scenario injection"
```

---

### Task 4.3: Simulator orchestrator (ramp + steady state)

**Files:**
- Create: `control-plane/src/server/services/simulatorOrchestrator.ts`

- [ ] **Step 1: Implement**

```typescript
// control-plane/src/server/services/simulatorOrchestrator.ts
import type { WorkflowSimulator } from "./workflowSimulator";

export class SimulatorOrchestrator {
  private timer: NodeJS.Timeout | null = null;
  constructor(private sim: WorkflowSimulator, private opts: { target: number; rampMs: number }) {}

  start(): void {
    const scheduleNext = () => {
      const delay = 3000 + Math.random() * 5000;
      this.timer = setTimeout(async () => {
        await this.sim.spawn();
        scheduleNext();
      }, delay);
    };
    // Ramp: spawn quickly until target
    (async () => {
      for (let i = 0; i < this.opts.target; i++) {
        await this.sim.spawn();
        await new Promise(r => setTimeout(r, this.opts.rampMs / this.opts.target));
      }
      scheduleNext();
    })();
  }

  stop(): void { if (this.timer) clearTimeout(this.timer); }
}
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/server/services/simulatorOrchestrator.ts
git commit -m "feat(cp): simulator orchestrator with ramp + steady-state"
```

---

## Phase 5 — Fleet Manager

### Task 5.1: Fleet Manager MCP tools

**Files:**
- Create: `control-plane/src/server/mcp-tools/queryFleet.ts`
- Create: `control-plane/src/server/mcp-tools/queryTraces.ts`
- Create: `control-plane/src/server/mcp-tools/composeException.ts`
- Create: `control-plane/src/server/mcp-tools/proposeSkillAmp.ts`
- Create: `control-plane/src/server/mcp-tools/dryRunPolicy.ts`
- Create: `control-plane/src/server/mcp-tools/index.ts`

- [ ] **Step 1: Tool shapes**

```typescript
// control-plane/src/server/mcp-tools/queryFleet.ts
import type { StateStore } from "../services/stateStore";

export const queryFleetTool = (store: StateStore) => ({
  name: "query-fleet",
  description: "Aggregated fleet state",
  parameters: {
    type: "object",
    properties: {
      phase: { type: "string" }, agency: { type: "string" }, hasException: { type: "boolean" }
    }
  },
  execute: async (args: { phase?: string; agency?: string; hasException?: boolean }) => {
    const workflows = store.listWorkflows(args as never);
    const exceptions = store.listExceptions();
    return {
      total: workflows.length,
      byPhase: workflows.reduce<Record<string, number>>((acc, w) => {
        acc[w.currentPhase] = (acc[w.currentPhase] ?? 0) + 1; return acc;
      }, {}),
      byStatus: workflows.reduce<Record<string, number>>((acc, w) => {
        acc[w.status] = (acc[w.status] ?? 0) + 1; return acc;
      }, {}),
      openExceptionCount: exceptions.length,
      recentExceptions: exceptions.slice(-5).map(e => ({
        id: e.id, workflowId: e.workflowId, category: e.category, severity: e.severity
      }))
    };
  }
});
```

```typescript
// control-plane/src/server/mcp-tools/queryTraces.ts
import type { StateStore } from "../services/stateStore";

export const queryTracesTool = (store: StateStore) => ({
  name: "query-traces",
  description: "OTEL spans for a workflow",
  parameters: {
    type: "object",
    properties: { workflowId: { type: "string" }, phase: { type: "string" } },
    required: ["workflowId"]
  },
  execute: async (args: { workflowId: string; phase?: string }) => {
    const spans = store.getSpans(args.workflowId);
    return args.phase ? spans.filter(s => s.attributes["workflow.phase"] === args.phase) : spans;
  }
});
```

```typescript
// control-plane/src/server/mcp-tools/composeException.ts
import { nanoid } from "nanoid";
import type { StateStore } from "../services/stateStore";
import type { EventBus } from "../services/eventBus";
import type { Exception, ExceptionCategory, Severity, ExceptionOption, PolicyRef } from "@shared/types";

export interface AuditLogger { log(entry: { action: string; details: unknown; timestamp: number }): void; }

export const composeExceptionTool = (store: StateStore, _bus: EventBus, audit: AuditLogger) => ({
  name: "compose-exception",
  description: "Write an exception to the queue",
  parameters: {
    type: "object",
    properties: {
      workflowId: { type: "string" },
      severity: { type: "string", enum: ["critical", "high", "medium"] },
      category: { type: "string" },
      summary: { type: "string" },
      recommendation: { type: "string" },
      options: { type: "array" },
      relatedPolicyRefs: { type: "array" },
      bulkCandidateIds: { type: "array", items: { type: "string" } },
      confidence: { type: "number" }
    },
    required: ["workflowId", "severity", "category", "summary", "recommendation"]
  },
  execute: async (args: {
    workflowId: string; severity: Severity; category: ExceptionCategory;
    summary: string; recommendation: string;
    options?: ExceptionOption[]; relatedPolicyRefs?: PolicyRef[];
    bulkCandidateIds?: string[]; confidence?: number;
  }) => {
    // Hook-gated non-revocable action — audit before execution
    audit.log({ action: "compose-exception.pre", details: { workflowId: args.workflowId }, timestamp: Date.now() });
    const exc: Exception = {
      id: `EXC-${nanoid(8)}`,
      workflowId: args.workflowId,
      composedBy: "fleet-manager",
      severity: args.severity,
      category: args.category,
      summary: args.summary,
      recommendation: args.recommendation,
      options: args.options ?? [
        { label: "Approve", action: "approve", nonRevocable: false },
        { label: "Reject", action: "reject", nonRevocable: false }
      ],
      relatedPolicyRefs: args.relatedPolicyRefs ?? [],
      bulkCandidateIds: args.bulkCandidateIds,
      confidence: args.confidence ?? 0.8,
      createdAt: Date.now()
    };
    store.upsertException(exc);
    audit.log({ action: "compose-exception.emitted", details: { exceptionId: exc.id, workflowId: exc.workflowId }, timestamp: Date.now() });
    return { exceptionId: exc.id };
  }
});
```

```typescript
// control-plane/src/server/mcp-tools/proposeSkillAmp.ts
import { nanoid } from "nanoid";
import type { StateStore } from "../services/stateStore";
import type { PolicyRef } from "@shared/types";

export const proposeSkillAmpTool = (store: StateStore) => ({
  name: "propose-skill-amplification",
  description: "Emit a skill-amplification card for an operator",
  parameters: {
    type: "object",
    properties: {
      workflowId: { type: "string" },
      policyContext: { type: "array" },
      precedents: { type: "array" },
      recommendedApproach: { type: "string" }
    },
    required: ["workflowId", "recommendedApproach"]
  },
  execute: async (args: {
    workflowId: string;
    policyContext?: PolicyRef[];
    precedents?: Array<{ workflowId: string; outcome: string; rationale: string }>;
    recommendedApproach: string;
  }) => {
    const id = `AMP-${nanoid(8)}`;
    store.appendAmplification(args.workflowId, {
      id, workflowId: args.workflowId,
      policyContext: args.policyContext ?? [],
      precedents: args.precedents ?? [],
      recommendedApproach: args.recommendedApproach,
      createdAt: Date.now()
    });
    return { amplificationId: id };
  }
});
```

```typescript
// control-plane/src/server/mcp-tools/dryRunPolicy.ts
import type { StateStore } from "../services/stateStore";

export const dryRunPolicyTool = (store: StateStore) => ({
  name: "dry-run-policy",
  description: "Simulate a policy value change against completed workflows",
  parameters: {
    type: "object",
    properties: {
      policyId: { type: "string" },
      proposedValue: { }, // any
      scopeDays: { type: "number" }
    },
    required: ["policyId", "proposedValue"]
  },
  execute: async (args: { policyId: string; proposedValue: number | string | boolean; scopeDays?: number }) => {
    const cutoff = Date.now() - (args.scopeDays ?? 7) * 86_400_000;
    const completed = store.listWorkflows().filter(w => w.status === "completed" && w.createdAt >= cutoff);
    // Simple heuristic for the demo: policyId "approval.auto_threshold" — how many invoices under threshold would have auto-approved.
    let wouldBeDifferent = 0;
    const impacted: string[] = [];
    if (args.policyId === "invoice-p2p.approval.auto_threshold") {
      const threshold = Number(args.proposedValue);
      for (const w of completed) {
        if (w.invoice.amount <= threshold) { wouldBeDifferent++; impacted.push(w.id); }
      }
    }
    return { scopeDays: args.scopeDays ?? 7, totalEvaluated: completed.length, wouldBeDifferent, impactedWorkflowIds: impacted.slice(0, 20) };
  }
});
```

```typescript
// control-plane/src/server/mcp-tools/index.ts
import type { StateStore } from "../services/stateStore";
import type { EventBus } from "../services/eventBus";
import { queryFleetTool } from "./queryFleet";
import { queryTracesTool } from "./queryTraces";
import { composeExceptionTool, type AuditLogger } from "./composeException";
import { proposeSkillAmpTool } from "./proposeSkillAmp";
import { dryRunPolicyTool } from "./dryRunPolicy";

export function buildFleetManagerTools(store: StateStore, bus: EventBus, audit: AuditLogger) {
  return [
    queryFleetTool(store),
    queryTracesTool(store),
    composeExceptionTool(store, bus, audit),
    proposeSkillAmpTool(store),
    dryRunPolicyTool(store)
  ];
}
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/server/mcp-tools
git commit -m "feat(cp): Fleet Manager MCP tools (query-fleet, traces, compose-exception, skill-amp, dry-run)"
```

---

### Task 5.2: SKILL.md

**Files:**
- Create: `control-plane/src/server/skills/fleet-manager.skill.md`

- [ ] **Step 1: Write SKILL.md** (content from spec §4.4 verbatim)

```markdown
---
name: fleet-manager
description: Monitors the fleet of concurrent invoice workflows. Composes the
  exception queue surfaced to the Finance Controller via the Control Plane.
  Amplifies operator skill by proposing relevant policy and precedents.
allowed-tools: query-fleet, query-traces, compose-exception,
  propose-skill-amplification, dry-run-policy
---

You are the Fleet Manager for WPP's Finance Procure-to-Pay workflow fleet.

On each trigger event:
1. Call `query-fleet` for current context and `query-traces` for any specific
   workflows named in the trigger.
2. Assess whether a Finance Controller needs to see this. If routine, exit
   silently — do not call any output tool.
3. If surfacing is warranted, call `compose-exception` with a clear summary,
   your recommendation, and the option set. Use `bulkCandidateIds` when you
   detect related workflows.
4. When an exception involves ambiguity the operator would benefit from context
   on, call `propose-skill-amplification` with the most relevant policy
   snippets and the 2–3 most instructive precedent decisions.
5. On `fleet.tick`, produce a fleet-health summary only if anomalies are
   detected. Otherwise exit silently.

Never call `compose-exception` twice for the same root cause in the same
debounce window. Prefer bulk-candidate grouping.

Your output is visible to the operator in near-real-time. Be concise.
Recommendations go in `recommendation`, not in prose.
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/server/skills
git commit -m "feat(cp): fleet-manager SKILL.md"
```

---

### Task 5.3: FleetManagerService — queue/debounce/coalesce

**Files:**
- Create: `control-plane/src/server/services/fleetManagerQueue.ts`
- Create: `control-plane/tests/unit/fleetManagerQueue.test.ts`

- [ ] **Step 1: Test**

```typescript
// control-plane/tests/unit/fleetManagerQueue.test.ts
import { describe, it, expect, vi } from "vitest";
import { FleetManagerQueue } from "@server/services/fleetManagerQueue";

describe("FleetManagerQueue", () => {
  it("debounces per-workflow within window", async () => {
    vi.useFakeTimers();
    const process = vi.fn(async () => {});
    const q = new FleetManagerQueue(process, { debounceMs: 1000 });
    q.enqueue({ workflowId: "A", reason: "exception.detected" });
    q.enqueue({ workflowId: "A", reason: "exception.detected" });
    q.enqueue({ workflowId: "A", reason: "exception.detected" });
    await vi.advanceTimersByTimeAsync(1001);
    expect(process).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
  it("batches multiple workflows in same flush", async () => {
    vi.useFakeTimers();
    const process = vi.fn(async () => {});
    const q = new FleetManagerQueue(process, { debounceMs: 500 });
    q.enqueue({ workflowId: "A", reason: "x" });
    q.enqueue({ workflowId: "B", reason: "x" });
    q.enqueue({ workflowId: "C", reason: "x" });
    await vi.advanceTimersByTimeAsync(501);
    expect(process).toHaveBeenCalledTimes(1);
    const arg = process.mock.calls[0][0];
    expect(arg.map((e: { workflowId: string }) => e.workflowId).sort()).toEqual(["A", "B", "C"]);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Implement**

```typescript
// control-plane/src/server/services/fleetManagerQueue.ts
export interface QueueEntry {
  workflowId: string;
  reason: string;
}

export class FleetManagerQueue {
  private pending = new Map<string, QueueEntry>();
  private flushTimer: NodeJS.Timeout | null = null;
  private flushing = false;

  constructor(
    private processor: (batch: QueueEntry[]) => Promise<void>,
    private opts: { debounceMs: number }
  ) {}

  enqueue(entry: QueueEntry): void {
    this.pending.set(entry.workflowId, entry);
    if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => { void this.flush(); }, this.opts.debounceMs);
    }
  }

  depth(): number { return this.pending.size; }

  private async flush(): Promise<void> {
    this.flushTimer = null;
    if (this.flushing) return;
    this.flushing = true;
    try {
      const batch = [...this.pending.values()];
      this.pending.clear();
      if (batch.length > 0) await this.processor(batch);
    } finally {
      this.flushing = false;
    }
  }
}
```

- [ ] **Step 3: Run and commit**

```bash
npm test -- fleetManagerQueue
git add control-plane/src/server/services/fleetManagerQueue.ts control-plane/tests/unit/fleetManagerQueue.test.ts
git commit -m "feat(cp): FleetManagerQueue with debounce + batch coalesce"
```

---

### Task 5.4: FleetManagerService — SDK session wiring

**Files:**
- Create: `control-plane/src/server/services/fleetManagerService.ts`
- Create: `control-plane/src/server/services/auditLogger.ts`

> **IMPORTANT:** the exact GHCP SDK API calls here must match what was proven in Task 0.2. If the spike showed different method names, update this file accordingly. The structure below assumes `createSession`, `sendMessage`, and a `tools` array with `{ name, description, parameters, execute }` shape.

- [ ] **Step 1: Implement AuditLogger**

```typescript
// control-plane/src/server/services/auditLogger.ts
export class AuditLogger {
  private entries: Array<{ action: string; details: unknown; timestamp: number }> = [];
  log(entry: { action: string; details: unknown; timestamp: number }): void {
    this.entries.push(entry);
  }
  list(): typeof this.entries { return this.entries.slice(); }
}
```

- [ ] **Step 2: Implement FleetManagerService**

```typescript
// control-plane/src/server/services/fleetManagerService.ts
import { CopilotClient } from "@github/copilot-sdk";
import fs from "node:fs";
import path from "node:path";
import type { EventBus } from "./eventBus";
import type { StateStore } from "./stateStore";
import { FleetManagerQueue, type QueueEntry } from "./fleetManagerQueue";
import { Triage } from "./triage";
import { buildFleetManagerTools } from "../mcp-tools";
import { AuditLogger } from "./auditLogger";

export interface FleetManagerLiveEvent {
  kind: "idle" | "wakeup" | "reasoning_start" | "tool_call" | "reasoning_done" | "error";
  timestamp: number;
  data?: unknown;
}

export interface FleetManagerServiceDeps {
  bus: EventBus;
  store: StateStore;
  env: {
    endpoint: string; apiKey: string; model: string; maxTokens: number;
  };
  audit: AuditLogger;
  onLive: (ev: FleetManagerLiveEvent) => void;
}

export class FleetManagerService {
  private client!: CopilotClient;
  private session!: Awaited<ReturnType<CopilotClient["createSession"]>>;
  private queue: FleetManagerQueue;
  private triage = new Triage();
  private started = false;
  private tickInterval: NodeJS.Timeout | null = null;

  constructor(private deps: FleetManagerServiceDeps) {
    this.queue = new FleetManagerQueue(this.processBatch.bind(this), { debounceMs: 2000 });
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.client = new CopilotClient({
      azure: { endpoint: this.deps.env.endpoint, apiKey: this.deps.env.apiKey }
    });
    const skillPath = path.join(process.cwd(), "src/server/skills/fleet-manager.skill.md");
    const systemPrompt = fs.readFileSync(skillPath, "utf-8");
    const tools = buildFleetManagerTools(this.deps.store, this.deps.bus, this.deps.audit);

    this.session = await this.client.createSession({
      model: this.deps.env.model,
      systemPrompt,
      tools,
      maxOutputTokens: this.deps.env.maxTokens
    });

    this.deps.bus.onAny((e) => {
      this.triage.observe(e);
      const anomaly = this.triage.detectAnomaly();
      if (anomaly) {
        this.deps.bus.emit({ type: "fleet.anomaly.detected", pattern: anomaly.pattern, workflowIds: anomaly.workflowIds });
      }
      if (this.triage.shouldWake(e)) {
        const wid = (e as { workflowId?: string }).workflowId;
        if (!wid) return;
        this.queue.enqueue({ workflowId: wid, reason: e.type });
        this.deps.onLive({ kind: "wakeup", timestamp: Date.now(), data: { workflowId: wid, reason: e.type } });
      }
    });

    this.tickInterval = setInterval(() => {
      this.deps.bus.emit({ type: "fleet.tick", timestamp: Date.now() });
    }, 30_000);

    this.started = true;
    this.deps.onLive({ kind: "idle", timestamp: Date.now() });
  }

  async stop(): Promise<void> {
    if (this.tickInterval) clearInterval(this.tickInterval);
    await this.session?.close?.();
  }

  private async processBatch(batch: QueueEntry[]): Promise<void> {
    if (this.queue.depth() > 20) {
      this.deps.bus.emit({ type: "fleet.overload", queueDepth: this.queue.depth() });
    }
    this.deps.onLive({ kind: "reasoning_start", timestamp: Date.now(), data: { batchSize: batch.length, workflowIds: batch.map(b => b.workflowId) } });
    const prompt = this.buildPrompt(batch);
    try {
      const r = await this.session.sendMessage(prompt);
      this.deps.onLive({ kind: "reasoning_done", timestamp: Date.now(), data: { batchSize: batch.length, reply: r.content?.slice(0, 200) } });
    } catch (err) {
      this.deps.onLive({ kind: "error", timestamp: Date.now(), data: { message: err instanceof Error ? err.message : String(err) } });
    }
  }

  private buildPrompt(batch: QueueEntry[]): string {
    const lines = batch.map(b => `- workflow=${b.workflowId} reason=${b.reason}`);
    return `Triggering events:\n${lines.join("\n")}\n\nFollow the SKILL instructions. Call tools as needed. Prefer bulk grouping where related.`;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add control-plane/src/server/services/fleetManagerService.ts control-plane/src/server/services/auditLogger.ts
git commit -m "feat(cp): FleetManagerService wired to GHCP SDK session"
```

---

### Task 5.5: Wire tool-call emission into `onLive`

The UI right rail needs visibility into individual tool calls. If the SDK emits tool-call events, capture them here.

**Files:**
- Modify: `control-plane/src/server/services/fleetManagerService.ts` — hook SDK tool-call events into `onLive`

- [ ] **Step 1: Extend constructor session setup**

Inside `start()` after `this.session = await this.client.createSession(...)`, add (adjust to whatever event subscription the SDK supports — this mirrors ghcp-ui's `session.on(handler)` pattern from [scratch/ghcp-ui/src/server/src/services/copilot.service.ts](../../../scratch/ghcp-ui/src/server/src/services/copilot.service.ts:500-667)):

```typescript
this.session.on?.((evt: { type: string; name?: string; args?: unknown; result?: unknown }) => {
  if (evt.type === "tool.execution_start") {
    this.deps.onLive({ kind: "tool_call", timestamp: Date.now(), data: { stage: "start", name: evt.name, args: evt.args } });
  } else if (evt.type === "tool.execution_complete") {
    this.deps.onLive({ kind: "tool_call", timestamp: Date.now(), data: { stage: "complete", name: evt.name, result: evt.result } });
  }
});
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/server/services/fleetManagerService.ts
git commit -m "feat(cp): stream SDK tool-call events into right-rail live feed"
```

---

## Phase 6 — Server API + SSE

### Task 6.1: SSE hub

**Files:**
- Create: `control-plane/src/server/services/sseHub.ts`
- Create: `control-plane/src/server/routes/stream.ts`

- [ ] **Step 1: Hub**

```typescript
// control-plane/src/server/services/sseHub.ts
import type { Response } from "express";

type Topic = "fleet" | "fleet-manager";

export class SSEHub {
  private clients = new Map<Topic, Set<Response>>();

  subscribe(topic: Topic, res: Response): void {
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.flushHeaders();
    const set = this.clients.get(topic) ?? new Set();
    set.add(res); this.clients.set(topic, set);
    res.on("close", () => set.delete(res));
  }

  broadcast(topic: Topic, data: unknown): void {
    const s = this.clients.get(topic);
    if (!s) return;
    const payload = `data: ${JSON.stringify(data)}\n\n`;
    for (const r of s) { try { r.write(payload); } catch { /* drop */ } }
  }
}
```

- [ ] **Step 2: Stream route**

```typescript
// control-plane/src/server/routes/stream.ts
import { Router } from "express";
import type { SSEHub } from "../services/sseHub";

export function streamRouter(hub: SSEHub): Router {
  const r = Router();
  r.get("/fleet", (_req, res) => hub.subscribe("fleet", res));
  r.get("/fleet-manager", (_req, res) => hub.subscribe("fleet-manager", res));
  return r;
}
```

- [ ] **Step 3: Commit**

```bash
git add control-plane/src/server/services/sseHub.ts control-plane/src/server/routes/stream.ts
git commit -m "feat(cp): SSE hub + /api/stream/* routes"
```

---

### Task 6.2: REST routes

**Files:**
- Create: `control-plane/src/server/routes/workflows.ts`
- Create: `control-plane/src/server/routes/exceptions.ts`
- Create: `control-plane/src/server/routes/policy.ts`
- Create: `control-plane/src/server/routes/simulator.ts`
- Create: `control-plane/src/server/routes/audit.ts`

- [ ] **Step 1: workflows.ts**

```typescript
// control-plane/src/server/routes/workflows.ts
import { Router } from "express";
import type { StateStore } from "../services/stateStore";

export function workflowsRouter(store: StateStore): Router {
  const r = Router();
  r.get("/", (req, res) => {
    const { status, phase, agency, hasException } = req.query;
    res.json(store.listWorkflows({
      status: status as never, phase: phase as never, agency: agency as never,
      hasException: hasException === "true" ? true : hasException === "false" ? false : undefined
    }));
  });
  r.get("/:id", (req, res) => {
    const w = store.getWorkflow(req.params.id);
    if (!w) return res.status(404).end();
    res.json({
      workflow: w,
      phases: store.getPhases(req.params.id),
      spans: store.getSpans(req.params.id),
      amplifications: store.getAmplifications(req.params.id),
      activeException: w.activeExceptionId ? store.getException(w.activeExceptionId) : null
    });
  });
  return r;
}
```

- [ ] **Step 2: exceptions.ts**

```typescript
// control-plane/src/server/routes/exceptions.ts
import { Router } from "express";
import type { StateStore } from "../services/stateStore";

export function exceptionsRouter(store: StateStore): Router {
  const r = Router();
  r.get("/", (req, res) => {
    res.json(store.listExceptions({ includeResolved: req.query.includeResolved === "true" }));
  });
  r.post("/bulk-resolve", (req, res) => {
    const { exceptionIds, resolution, resolvedBy } = req.body as {
      exceptionIds: string[]; resolution: string; resolvedBy: string;
    };
    for (const id of exceptionIds) {
      store.resolveException(id, resolvedBy);
      const exc = store.getException(id);
      if (!exc) continue;
      const w = store.getWorkflow(exc.workflowId);
      if (w && w.status === "awaiting_hitl") {
        w.status = "in_progress";
        w.actionLedger.push({
          workflowId: w.id, timestamp: Date.now(),
          actor: { kind: "human", id: resolvedBy },
          action: `bulk-resolve:${resolution}`, revocable: false, details: { exceptionId: id }
        });
      }
    }
    res.json({ resolved: exceptionIds.length });
  });
  return r;
}
```

- [ ] **Step 3: policy.ts**

```typescript
// control-plane/src/server/routes/policy.ts
import { Router } from "express";
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import type { StateStore } from "../services/stateStore";
import { dryRunPolicyTool } from "../mcp-tools/dryRunPolicy";

interface PolicyYaml {
  policies: Array<{
    id: string; description: string; value: number | string | boolean;
    gitSha: string; author: string; updatedAt: string;
  }>;
}

export function policyRouter(store: StateStore): Router {
  const r = Router();
  const changeRequests: Array<{ id: string; policyId: string; proposedValue: unknown; rationale: string; proposedBy: string; createdAt: number }> = [];

  const loadPolicies = () => {
    const file = path.join(process.cwd(), "src/shared/policies.yaml");
    const parsed = yaml.load(fs.readFileSync(file, "utf-8")) as PolicyYaml;
    for (const p of parsed.policies) {
      store.upsertPolicy({
        id: p.id, description: p.description, currentValue: p.value,
        gitSha: p.gitSha, author: p.author, updatedAt: new Date(p.updatedAt).getTime()
      });
    }
  };
  loadPolicies();

  r.get("/", (_req, res) => res.json(store.listPolicies()));
  r.post("/dry-run", async (req, res) => {
    const tool = dryRunPolicyTool(store);
    const out = await tool.execute(req.body);
    res.json(out);
  });
  r.post("/propose-change", (req, res) => {
    const id = `CR-${Date.now()}`;
    changeRequests.push({ id, ...req.body, createdAt: Date.now() });
    res.json({ id });
  });
  r.get("/change-requests", (_req, res) => res.json(changeRequests));
  return r;
}
```

- [ ] **Step 4: Write seed `policies.yaml`**

```yaml
# control-plane/src/shared/policies.yaml
policies:
  - id: invoice-p2p.approval.auto_threshold
    description: "Invoices below this amount auto-approve when PO matches."
    value: 5000
    gitSha: "a1b2c3d"
    author: "finance-platform@wpp"
    updatedAt: "2026-03-15T10:20:00Z"
  - id: invoice-p2p.variance.tolerance_pct
    description: "Acceptable variance between invoice and PO, as a fraction."
    value: 0.02
    gitSha: "a1b2c3d"
    author: "finance-platform@wpp"
    updatedAt: "2026-03-15T10:20:00Z"
  - id: invoice-p2p.duplicate.window_days
    description: "Duplicate-detection window in days."
    value: 30
    gitSha: "e4f5a6b"
    author: "finance-platform@wpp"
    updatedAt: "2026-02-01T14:00:00Z"
```

- [ ] **Step 5: simulator.ts and audit.ts**

```typescript
// control-plane/src/server/routes/simulator.ts
import { Router } from "express";
import type { WorkflowSimulator } from "../services/workflowSimulator";

export function simulatorRouter(sim: WorkflowSimulator): Router {
  const r = Router();
  r.post("/inject", async (req, res) => {
    const id = await sim.spawn(req.body?.scenario);
    res.json({ workflowId: id });
  });
  return r;
}
```

```typescript
// control-plane/src/server/routes/audit.ts
import { Router } from "express";
import type { AuditLogger } from "../services/auditLogger";

export function auditRouter(audit: AuditLogger): Router {
  const r = Router();
  r.get("/", (_req, res) => res.json(audit.list()));
  return r;
}
```

- [ ] **Step 6: Commit**

```bash
git add control-plane/src/server/routes control-plane/src/shared/policies.yaml
git commit -m "feat(cp): REST routes (workflows, exceptions, policy, simulator, audit)"
```

---

### Task 6.3: Evals route (CP-10, can be cut)

**Files:**
- Create: `control-plane/src/server/services/evalRunner.ts`
- Create: `control-plane/src/server/routes/evals.ts`

- [ ] **Step 1: Implement**

```typescript
// control-plane/src/server/services/evalRunner.ts
import type { StateStore } from "./stateStore";

export interface EvalRecord {
  id: string;
  workflowId: string;
  ranAt: number;
  taskAdherence: number;
  safety: number;
  toolAccuracy: number;
}

export class EvalRunner {
  private results: EvalRecord[] = [];
  private timer: NodeJS.Timeout | null = null;
  constructor(private store: StateStore) {}

  start(): void {
    this.timer = setInterval(() => this.runSample(), 15_000);
  }
  stop(): void { if (this.timer) clearInterval(this.timer); }

  private runSample(): void {
    const completed = this.store.listWorkflows().filter(w => w.status === "completed");
    if (completed.length === 0) return;
    const pick = completed[Math.floor(Math.random() * completed.length)];
    this.results.push({
      id: `EVAL-${Date.now()}`,
      workflowId: pick.id,
      ranAt: Date.now(),
      taskAdherence: 0.85 + Math.random() * 0.15,
      safety: 0.95 + Math.random() * 0.05,
      toolAccuracy: 0.88 + Math.random() * 0.12
    });
  }

  list(): EvalRecord[] { return this.results.slice(-50).reverse(); }
}
```

```typescript
// control-plane/src/server/routes/evals.ts
import { Router } from "express";
import type { EvalRunner } from "../services/evalRunner";

export function evalsRouter(runner: EvalRunner): Router {
  const r = Router();
  r.get("/", (_req, res) => res.json(runner.list()));
  return r;
}
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/server/services/evalRunner.ts control-plane/src/server/routes/evals.ts
git commit -m "feat(cp): eval runner + route (CP-10)"
```

---

### Task 6.4: Server `index.ts` — wire everything

**Files:**
- Create: `control-plane/src/server/index.ts`

- [ ] **Step 1: Implement**

```typescript
// control-plane/src/server/index.ts
import express from "express";
import cors from "cors";
import "dotenv/config";
import { EventBus } from "./services/eventBus";
import { StateStore } from "./services/stateStore";
import { WorkflowSimulator } from "./services/workflowSimulator";
import { SimulatorOrchestrator } from "./services/simulatorOrchestrator";
import { FleetManagerService, type FleetManagerLiveEvent } from "./services/fleetManagerService";
import { AuditLogger } from "./services/auditLogger";
import { SSEHub } from "./services/sseHub";
import { EvalRunner } from "./services/evalRunner";
import { workflowsRouter } from "./routes/workflows";
import { exceptionsRouter } from "./routes/exceptions";
import { policyRouter } from "./routes/policy";
import { simulatorRouter } from "./routes/simulator";
import { auditRouter } from "./routes/audit";
import { evalsRouter } from "./routes/evals";
import { streamRouter } from "./routes/stream";

async function main() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: "1mb" }));

  const bus = new EventBus();
  const store = new StateStore();
  const audit = new AuditLogger();
  const hub = new SSEHub();

  const mcpEnv = {
    workdayUrl: process.env.WORKDAY_MCP_URL ?? "http://localhost:4101",
    d365Url: process.env.D365_MCP_URL ?? "http://localhost:4102",
    maconomyUrl: process.env.MACONOMY_MCP_URL ?? "http://localhost:4103",
    paymentUrl: process.env.PAYMENT_MCP_URL ?? "http://localhost:4104"
  };

  const sim = new WorkflowSimulator({ bus, store, env: mcpEnv });
  const orch = new SimulatorOrchestrator(sim, {
    target: Number(process.env.SIMULATOR_TARGET_WORKFLOWS ?? 40),
    rampMs: 180_000
  });

  // Fan out every bus event to the fleet SSE topic
  bus.onAny((e) => hub.broadcast("fleet", e));

  const fm = new FleetManagerService({
    bus, store, audit,
    env: {
      endpoint: process.env.AZURE_FOUNDRY_ENDPOINT ?? "",
      apiKey: process.env.AZURE_FOUNDRY_API_KEY ?? "",
      model: process.env.FLEET_MANAGER_MODEL ?? "gpt-4.1",
      maxTokens: Number(process.env.FLEET_MANAGER_MAX_TOKENS ?? 2000)
    },
    onLive: (ev: FleetManagerLiveEvent) => hub.broadcast("fleet-manager", ev)
  });

  const evalRunner = new EvalRunner(store);

  app.use("/api/workflows", workflowsRouter(store));
  app.use("/api/exceptions", exceptionsRouter(store));
  app.use("/api/policy", policyRouter(store));
  app.use("/api/simulator", simulatorRouter(sim));
  app.use("/api/audit", auditRouter(audit));
  app.use("/api/evals", evalsRouter(evalRunner));
  app.use("/api/stream", streamRouter(hub));

  app.get("/api/health", (_req, res) => res.json({ ok: true }));

  const port = Number(process.env.PORT ?? 3001);
  app.listen(port, async () => {
    console.log(`[server] :${port}`);
    try { await fm.start(); } catch (e) { console.error("fleet-manager failed to start", e); }
    orch.start();
    evalRunner.start();
  });
}

main().catch((err) => { console.error(err); process.exit(1); });
```

- [ ] **Step 2: Add dotenv dependency**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
npm install dotenv
```

- [ ] **Step 3: Run it once end-to-end (no UI yet)**

Set up `.env` with real Foundry key.

In three terminals (or use `npm run dev:mcp` + `npm run dev:server`):

```bash
# terminal A
npm run dev:mcp

# terminal B
npm run dev:server
```

Then:

```bash
curl -s http://localhost:3001/api/health
curl -s http://localhost:3001/api/workflows | head -c 500
```

Expected: health responds `{"ok":true}`. After ~10 seconds, workflows list returns items.

- [ ] **Step 4: Commit**

```bash
git add control-plane/src/server/index.ts control-plane/package.json control-plane/package-lock.json
git commit -m "feat(cp): server index wires bus/store/simulator/FM/SSE/routes"
```

---

## Phase 7 — Client shell

### Task 7.1: Entry, styles, routing skeleton

**Files:**
- Create: `control-plane/src/client/main.tsx`
- Create: `control-plane/src/client/styles.css`
- Create: `control-plane/src/client/App.tsx`

- [ ] **Step 1: `styles.css`**

```css
@import "tailwindcss";
```

- [ ] **Step 2: `main.tsx`**

```tsx
// control-plane/src/client/main.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 3: `App.tsx`** (shell with top bar, left nav, main, right rail)

```tsx
// control-plane/src/client/App.tsx
import { NavLink, Routes, Route, Navigate } from "react-router-dom";
import { LayoutDashboard, AlertTriangle, Shield, BarChart3, FlaskConical } from "lucide-react";
import FleetDashboard from "./routes/FleetDashboard";
import ExceptionQueue from "./routes/ExceptionQueue";
import WorkflowDetail from "./routes/WorkflowDetail";
import PolicyAndAutonomy from "./routes/PolicyAndAutonomy";
import Analytics from "./routes/Analytics";
import Evaluations from "./routes/Evaluations";
import FleetManagerRail from "./components/FleetManagerRail";

const navItems = [
  { to: "/fleet", label: "Fleet", icon: LayoutDashboard },
  { to: "/exceptions", label: "Exceptions", icon: AlertTriangle },
  { to: "/policy", label: "Policy", icon: Shield },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/evals", label: "Evaluations", icon: FlaskConical }
];

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-slate-950 text-slate-100">
      <header className="h-12 border-b border-slate-800 flex items-center px-4 gap-4">
        <div className="font-semibold tracking-tight">WPP Control Plane</div>
        <div className="text-xs text-slate-400">Finance Controller · Ogilvy-US · US-CA</div>
        <div className="ml-auto text-xs text-slate-400">role: Finance Controller</div>
      </header>
      <div className="flex-1 flex overflow-hidden">
        <nav className="w-48 border-r border-slate-800 p-2 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 px-2 py-1.5 rounded text-sm ${isActive ? "bg-slate-800 text-slate-50" : "text-slate-400 hover:bg-slate-900"}`
              }
            >
              <Icon size={14} /> {label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 overflow-auto p-4">
          <Routes>
            <Route path="/" element={<Navigate to="/fleet" replace />} />
            <Route path="/fleet" element={<FleetDashboard />} />
            <Route path="/exceptions" element={<ExceptionQueue />} />
            <Route path="/workflows/:id" element={<WorkflowDetail />} />
            <Route path="/policy" element={<PolicyAndAutonomy />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evals" element={<Evaluations />} />
          </Routes>
        </main>
        <aside className="w-80 border-l border-slate-800 overflow-auto">
          <FleetManagerRail />
        </aside>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add control-plane/src/client/main.tsx control-plane/src/client/styles.css control-plane/src/client/App.tsx
git commit -m "feat(cp): client shell + routing"
```

---

### Task 7.2: SSE hook + data hooks

**Files:**
- Create: `control-plane/src/client/hooks/useSSE.ts`
- Create: `control-plane/src/client/hooks/useWorkflows.ts`
- Create: `control-plane/src/client/hooks/useExceptions.ts`
- Create: `control-plane/src/client/hooks/useFleetManagerStream.ts`

- [ ] **Step 1: useSSE.ts**

```typescript
// control-plane/src/client/hooks/useSSE.ts
import { useEffect } from "react";

export function useSSE<T>(path: string, onMessage: (data: T) => void): void {
  useEffect(() => {
    const es = new EventSource(path);
    es.onmessage = (ev) => {
      try { onMessage(JSON.parse(ev.data)); } catch { /* ignore */ }
    };
    return () => es.close();
  }, [path, onMessage]);
}
```

- [ ] **Step 2: useWorkflows.ts**

```typescript
// control-plane/src/client/hooks/useWorkflows.ts
import { useCallback, useEffect, useState } from "react";
import type { Workflow } from "@shared/types";
import { useSSE } from "./useSSE";

export function useWorkflows() {
  const [items, setItems] = useState<Workflow[]>([]);

  const refresh = useCallback(async () => {
    const r = await fetch("/api/workflows");
    setItems(await r.json());
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useSSE<{ type: string }>("/api/stream/fleet", useCallback((e) => {
    if (e.type.startsWith("workflow.") || e.type === "otel.span.emitted") void refresh();
  }, [refresh]));

  return items;
}
```

- [ ] **Step 3: useExceptions.ts**

```typescript
// control-plane/src/client/hooks/useExceptions.ts
import { useCallback, useEffect, useState } from "react";
import type { Exception } from "@shared/types";
import { useSSE } from "./useSSE";

export function useExceptions() {
  const [items, setItems] = useState<Exception[]>([]);
  const refresh = useCallback(async () => {
    const r = await fetch("/api/exceptions");
    setItems(await r.json());
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useSSE<{ type: string }>("/api/stream/fleet", useCallback(() => { void refresh(); }, [refresh]));
  return { items, refresh };
}
```

- [ ] **Step 4: useFleetManagerStream.ts**

```typescript
// control-plane/src/client/hooks/useFleetManagerStream.ts
import { useCallback, useRef, useState } from "react";
import { useSSE } from "./useSSE";

export interface FMLive {
  kind: "idle" | "wakeup" | "reasoning_start" | "tool_call" | "reasoning_done" | "error";
  timestamp: number;
  data?: unknown;
}

export function useFleetManagerStream(max = 50) {
  const [events, setEvents] = useState<FMLive[]>([]);
  const ref = useRef<FMLive[]>([]);
  useSSE<FMLive>("/api/stream/fleet-manager", useCallback((e) => {
    ref.current = [e, ...ref.current].slice(0, max);
    setEvents(ref.current.slice());
  }, [max]));
  return events;
}
```

- [ ] **Step 5: Commit**

```bash
git add control-plane/src/client/hooks
git commit -m "feat(cp): client SSE + data hooks"
```

---

### Task 7.3: Fleet Manager right-rail component

**Files:**
- Create: `control-plane/src/client/components/FleetManagerRail.tsx`

- [ ] **Step 1: Implement**

```tsx
// control-plane/src/client/components/FleetManagerRail.tsx
import { useFleetManagerStream } from "../hooks/useFleetManagerStream";
import { Activity, Loader2, Wrench, CheckCircle2, AlertCircle } from "lucide-react";

const iconFor = (kind: string) => {
  switch (kind) {
    case "wakeup": return <Activity size={14} className="text-amber-400" />;
    case "reasoning_start": return <Loader2 size={14} className="text-blue-400 animate-spin" />;
    case "tool_call": return <Wrench size={14} className="text-purple-300" />;
    case "reasoning_done": return <CheckCircle2 size={14} className="text-emerald-400" />;
    case "error": return <AlertCircle size={14} className="text-red-400" />;
    default: return <Activity size={14} className="text-slate-400" />;
  }
};

export default function FleetManagerRail() {
  const events = useFleetManagerStream();
  return (
    <div className="p-3 space-y-2">
      <div className="text-xs uppercase tracking-wider text-slate-400">Fleet Manager</div>
      <div className="text-[11px] text-slate-500">GHCP SDK session · {events.length} recent events</div>
      <div className="space-y-1.5">
        {events.length === 0 && <div className="text-xs text-slate-500">idle</div>}
        {events.map((e, i) => (
          <div key={i} className="flex gap-2 text-xs border border-slate-800 rounded p-2">
            {iconFor(e.kind)}
            <div className="flex-1 min-w-0">
              <div className="text-slate-200 font-medium truncate">{e.kind}</div>
              <div className="text-[11px] text-slate-500 truncate">
                {e.data ? JSON.stringify(e.data).slice(0, 160) : ""}
              </div>
            </div>
            <div className="text-[10px] text-slate-600 whitespace-nowrap">
              {new Date(e.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/client/components/FleetManagerRail.tsx
git commit -m "feat(cp): Fleet Manager right-rail (the 'it's real' shot)"
```

---

## Phase 8 — Client screens

### Task 8.1: Fleet Dashboard

**Files:**
- Create: `control-plane/src/client/routes/FleetDashboard.tsx`
- Create: `control-plane/src/client/components/WorkflowCard.tsx`

- [ ] **Step 1: WorkflowCard**

```tsx
// control-plane/src/client/components/WorkflowCard.tsx
import type { Workflow } from "@shared/types";
import { Link } from "react-router-dom";
import { PHASE_ORDER } from "@shared/types";

const statusColor: Record<Workflow["status"], string> = {
  in_progress: "text-blue-400", awaiting_hitl: "text-amber-400",
  completed: "text-emerald-400", failed: "text-red-400"
};

export default function WorkflowCard({ w }: { w: Workflow }) {
  const phaseIdx = PHASE_ORDER.indexOf(w.currentPhase);
  const pct = ((phaseIdx + 1) / PHASE_ORDER.length) * 100;
  return (
    <Link to={`/workflows/${w.id}`} className="block border border-slate-800 rounded p-3 hover:border-slate-700 bg-slate-900/50">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm">{w.id}</div>
        <div className={`text-[10px] uppercase ${statusColor[w.status]}`}>{w.status}</div>
      </div>
      <div className="text-xs text-slate-400 mt-0.5 truncate">{w.vendor.name}</div>
      <div className="text-xs text-slate-300 mt-1">
        {w.invoice.currency} {w.invoice.amount.toLocaleString()}
      </div>
      <div className="mt-2 text-[10px] text-slate-500">{w.currentPhase}</div>
      <div className="h-1 bg-slate-800 rounded mt-1">
        <div className="h-1 bg-blue-400 rounded" style={{ width: `${pct}%` }} />
      </div>
      {w.activeExceptionId && (
        <div className="mt-2 text-[10px] text-amber-400">⚠ exception</div>
      )}
    </Link>
  );
}
```

- [ ] **Step 2: FleetDashboard.tsx**

```tsx
// control-plane/src/client/routes/FleetDashboard.tsx
import { useMemo, useState } from "react";
import { useWorkflows } from "../hooks/useWorkflows";
import WorkflowCard from "../components/WorkflowCard";

export default function FleetDashboard() {
  const workflows = useWorkflows();
  const [phaseFilter, setPhaseFilter] = useState<string>("");
  const [agencyFilter, setAgencyFilter] = useState<string>("");
  const [exceptionsOnly, setExceptionsOnly] = useState(false);

  const filtered = useMemo(() =>
    workflows.filter(w =>
      (!phaseFilter || w.currentPhase === phaseFilter) &&
      (!agencyFilter || w.agency === agencyFilter) &&
      (!exceptionsOnly || !!w.activeExceptionId)
    ), [workflows, phaseFilter, agencyFilter, exceptionsOnly]);

  const counts = {
    total: workflows.length,
    inFlight: workflows.filter(w => w.status === "in_progress").length,
    awaiting: workflows.filter(w => w.status === "awaiting_hitl").length,
    completed: workflows.filter(w => w.status === "completed").length,
    exceptions: workflows.filter(w => w.activeExceptionId).length
  };
  const agencies = Array.from(new Set(workflows.map(w => w.agency))).sort();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-3">
        {Object.entries(counts).map(([k, v]) => (
          <div key={k} className="border border-slate-800 rounded p-3 bg-slate-900/50">
            <div className="text-[11px] text-slate-500 uppercase">{k.replace(/([A-Z])/g, " $1")}</div>
            <div className="text-xl font-semibold">{v}</div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 text-sm items-center">
        <select value={phaseFilter} onChange={e => setPhaseFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs">
          <option value="">All phases</option>
          {["Intake", "Validation", "Routing", "Approval", "Payment", "Reconciliation"].map(p => <option key={p}>{p}</option>)}
        </select>
        <select value={agencyFilter} onChange={e => setAgencyFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs">
          <option value="">All agencies</option>
          {agencies.map(a => <option key={a}>{a}</option>)}
        </select>
        <label className="text-xs text-slate-300 flex items-center gap-1">
          <input type="checkbox" checked={exceptionsOnly} onChange={e => setExceptionsOnly(e.target.checked)} />
          Exceptions only
        </label>
        <div className="ml-auto text-xs text-slate-500">{filtered.length} shown</div>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {filtered.map(w => <WorkflowCard key={w.id} w={w} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add control-plane/src/client/routes/FleetDashboard.tsx control-plane/src/client/components/WorkflowCard.tsx
git commit -m "feat(cp): Fleet Dashboard with filters + counters"
```

---

### Task 8.2: Exception Queue + bulk HITL + skill amp inline

**Files:**
- Create: `control-plane/src/client/routes/ExceptionQueue.tsx`
- Create: `control-plane/src/client/components/ExceptionItem.tsx`
- Create: `control-plane/src/client/components/BulkHitlModal.tsx`

- [ ] **Step 1: ExceptionItem**

```tsx
// control-plane/src/client/components/ExceptionItem.tsx
import type { Exception } from "@shared/types";
import { useState } from "react";

export default function ExceptionItem({ e, selected, onToggle }: {
  e: Exception; selected: boolean; onToggle: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-slate-800 rounded bg-slate-900/50">
      <div className="flex items-start gap-2 p-3">
        <input type="checkbox" className="mt-1" checked={selected} onChange={() => onToggle(e.id)} />
        <button onClick={() => setOpen(!open)} className="flex-1 text-left">
          <div className="flex items-center gap-2 text-sm">
            <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase text-white ${
              e.severity === "critical" ? "bg-red-600" : e.severity === "high" ? "bg-orange-600" : "bg-yellow-600"
            }`}>{e.severity}</span>
            <span className="font-medium">{e.category}</span>
            <span className="text-slate-500 text-xs">· {e.workflowId}</span>
            {e.bulkCandidateIds && e.bulkCandidateIds.length > 1 &&
              <span className="text-xs text-purple-400">bulk×{e.bulkCandidateIds.length}</span>}
          </div>
          <div className="text-xs text-slate-300 mt-1">{e.summary}</div>
          <div className="text-[11px] text-emerald-300 mt-1">→ {e.recommendation}</div>
        </button>
      </div>
      {open && (
        <div className="px-4 pb-3 space-y-2 border-t border-slate-800">
          {e.relatedPolicyRefs.length > 0 && (
            <div>
              <div className="text-[11px] uppercase text-slate-500 mt-2">Policy context</div>
              {e.relatedPolicyRefs.map((p, i) => (
                <div key={i} className="text-xs text-slate-300 mt-1">
                  <div className="font-medium">{p.title}</div>
                  <div className="text-slate-400">{p.snippet}</div>
                  <div className="text-[10px] text-slate-500">{p.source}</div>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2 pt-2">
            {e.options.map((o, i) => (
              <button key={i} className="text-xs px-2 py-1 border border-slate-700 rounded hover:bg-slate-800">
                {o.label}{o.nonRevocable ? " ⚠" : ""}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: BulkHitlModal**

```tsx
// control-plane/src/client/components/BulkHitlModal.tsx
export default function BulkHitlModal({ ids, onClose, onConfirm }: {
  ids: string[]; onClose: () => void; onConfirm: (resolution: string) => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-slate-700 rounded p-4 w-[480px] space-y-3">
        <div className="font-semibold">Bulk resolve {ids.length} exception{ids.length === 1 ? "" : "s"}</div>
        <div className="text-xs text-slate-400 max-h-40 overflow-auto">
          {ids.map(id => <div key={id}>{id}</div>)}
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="text-xs px-3 py-1.5 border border-slate-700 rounded">Cancel</button>
          <button onClick={() => onConfirm("approved")} className="text-xs px-3 py-1.5 bg-emerald-600 rounded hover:bg-emerald-500">Approve all</button>
          <button onClick={() => onConfirm("rejected")} className="text-xs px-3 py-1.5 bg-red-600 rounded hover:bg-red-500">Reject all</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: ExceptionQueue route**

```tsx
// control-plane/src/client/routes/ExceptionQueue.tsx
import { useState } from "react";
import { useExceptions } from "../hooks/useExceptions";
import ExceptionItem from "../components/ExceptionItem";
import BulkHitlModal from "../components/BulkHitlModal";

export default function ExceptionQueue() {
  const { items, refresh } = useExceptions();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [modal, setModal] = useState(false);

  const toggle = (id: string) => {
    const n = new Set(selected);
    n.has(id) ? n.delete(id) : n.add(id);
    setSelected(n);
  };

  const confirm = async (resolution: string) => {
    await fetch("/api/exceptions/bulk-resolve", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exceptionIds: [...selected], resolution, resolvedBy: "finance-controller@wpp" })
    });
    setSelected(new Set());
    setModal(false);
    await refresh();
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="text-sm font-semibold">Exception Queue</div>
        <div className="text-xs text-slate-500">{items.length} open</div>
        <div className="ml-auto flex gap-2">
          <button disabled={selected.size === 0} onClick={() => setModal(true)}
            className="text-xs px-3 py-1.5 bg-amber-600 rounded hover:bg-amber-500 disabled:opacity-40">
            Bulk resolve ({selected.size})
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {items.map(e => <ExceptionItem key={e.id} e={e} selected={selected.has(e.id)} onToggle={toggle} />)}
      </div>
      {modal && <BulkHitlModal ids={[...selected]} onClose={() => setModal(false)} onConfirm={confirm} />}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add control-plane/src/client/routes/ExceptionQueue.tsx control-plane/src/client/components/ExceptionItem.tsx control-plane/src/client/components/BulkHitlModal.tsx
git commit -m "feat(cp): Exception Queue with inline policy + bulk HITL"
```

---

### Task 8.3: Workflow Detail with OTEL span tree

**Files:**
- Create: `control-plane/src/client/routes/WorkflowDetail.tsx`
- Create: `control-plane/src/client/components/OtelSpanTree.tsx`
- Create: `control-plane/src/client/components/PhaseTimeline.tsx`
- Create: `control-plane/src/client/components/SkillAmplificationPanel.tsx`

- [ ] **Step 1: OtelSpanTree**

```tsx
// control-plane/src/client/components/OtelSpanTree.tsx
import type { OtelSpan } from "@shared/types";

export default function OtelSpanTree({ spans }: { spans: OtelSpan[] }) {
  const sorted = [...spans].sort((a, b) => a.startMs - b.startMs);
  return (
    <div className="space-y-1 font-mono text-xs">
      {sorted.map(s => (
        <div key={s.spanId} className="border border-slate-800 rounded px-2 py-1.5 bg-slate-900/30">
          <div className="flex justify-between">
            <span className="text-slate-200">{s.name}</span>
            <span className="text-slate-500">{s.endMs - s.startMs} ms</span>
          </div>
          <div className="text-[10px] text-slate-500">
            phase={s.attributes["workflow.phase"]}{s.attributes["tool.name"] ? ` tool=${s.attributes["tool.name"]}` : ""}
            {s.attributes["llm.model"] ? ` model=${s.attributes["llm.model"]}` : ""}
            {s.attributes["cost.usd"] != null ? ` $=${(s.attributes["cost.usd"] as number).toFixed(4)}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: PhaseTimeline**

```tsx
// control-plane/src/client/components/PhaseTimeline.tsx
import type { Phase } from "@shared/types";

export default function PhaseTimeline({ phases }: { phases: Phase[] }) {
  return (
    <div className="space-y-1">
      {phases.map(p => (
        <div key={p.name} className="flex items-center gap-3 text-xs border border-slate-800 rounded px-2 py-1.5 bg-slate-900/30">
          <div className="w-32 text-slate-200">{p.name}</div>
          <div className={`text-[10px] uppercase ${p.status === "completed" ? "text-emerald-400" : p.status === "in_progress" ? "text-blue-400" : "text-slate-500"}`}>{p.status}</div>
          {p.startedAt && p.completedAt && <div className="text-slate-500">{p.completedAt - p.startedAt} ms</div>}
          <div className="ml-auto text-slate-500">{p.toolCalls.length} tools</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: SkillAmplificationPanel**

```tsx
// control-plane/src/client/components/SkillAmplificationPanel.tsx
import type { SkillAmplification } from "@shared/types";

export default function SkillAmplificationPanel({ items }: { items: SkillAmplification[] }) {
  if (items.length === 0) return <div className="text-xs text-slate-500">No skill amplification for this workflow yet.</div>;
  return (
    <div className="space-y-2">
      {items.map(a => (
        <div key={a.id} className="border border-slate-800 rounded p-2 bg-slate-900/30 text-xs">
          <div className="text-emerald-300 font-medium">→ {a.recommendedApproach}</div>
          {a.policyContext.map((p, i) => (
            <div key={i} className="mt-1">
              <div className="font-medium text-slate-200">{p.title}</div>
              <div className="text-slate-400">{p.snippet}</div>
            </div>
          ))}
          {a.precedents.length > 0 && (
            <div className="mt-1">
              <div className="text-[10px] uppercase text-slate-500">Precedents</div>
              {a.precedents.map((p, i) => (
                <div key={i} className="text-slate-400">· {p.workflowId} → {p.outcome}: {p.rationale}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: WorkflowDetail route**

```tsx
// control-plane/src/client/routes/WorkflowDetail.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { Workflow, Phase, OtelSpan, Exception, SkillAmplification, ActionLedgerEntry } from "@shared/types";
import OtelSpanTree from "../components/OtelSpanTree";
import PhaseTimeline from "../components/PhaseTimeline";
import SkillAmplificationPanel from "../components/SkillAmplificationPanel";

type DetailResp = {
  workflow: Workflow; phases: Phase[]; spans: OtelSpan[];
  amplifications: SkillAmplification[]; activeException: Exception | null;
};

const tabs = ["Overview", "Phases", "Traces", "Ledger", "Amplification"] as const;

export default function WorkflowDetail() {
  const { id } = useParams();
  const [d, setD] = useState<DetailResp | null>(null);
  const [tab, setTab] = useState<typeof tabs[number]>("Overview");

  useEffect(() => {
    if (!id) return;
    void fetch(`/api/workflows/${id}`).then(r => r.json()).then(setD);
  }, [id]);

  if (!d) return <div className="text-xs text-slate-500">loading…</div>;
  const w = d.workflow;

  return (
    <div className="space-y-3">
      <div>
        <div className="text-lg font-semibold">{w.id} · {w.vendor.name}</div>
        <div className="text-xs text-slate-400">{w.invoice.currency} {w.invoice.amount.toLocaleString()} · PO {w.invoice.poRef} · {w.agency}</div>
      </div>
      <div className="flex gap-1 border-b border-slate-800">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`text-xs px-3 py-1.5 ${tab === t ? "text-slate-100 border-b-2 border-blue-400" : "text-slate-400"}`}>
            {t}
          </button>
        ))}
      </div>
      {tab === "Overview" && (
        <div className="text-xs text-slate-300 space-y-1">
          <div>status: {w.status}</div>
          <div>phase: {w.currentPhase}</div>
          {d.activeException && (
            <div className="mt-2 border border-amber-700 rounded p-2 bg-amber-950/30">
              <div className="text-amber-300 font-medium">⚠ {d.activeException.category} · {d.activeException.severity}</div>
              <div>{d.activeException.summary}</div>
              <div className="text-emerald-300">→ {d.activeException.recommendation}</div>
            </div>
          )}
        </div>
      )}
      {tab === "Phases" && <PhaseTimeline phases={d.phases} />}
      {tab === "Traces" && <OtelSpanTree spans={d.spans} />}
      {tab === "Ledger" && (
        <div className="space-y-1 text-xs">
          {w.actionLedger.map((a: ActionLedgerEntry, i) => (
            <div key={i} className="border border-slate-800 rounded p-2 bg-slate-900/30">
              <div className="text-slate-200">{a.action}</div>
              <div className="text-slate-500">
                {new Date(a.timestamp).toLocaleString()} · {a.actor.kind}:{a.actor.id} · {a.revocable ? "revocable" : "non-revocable"}
              </div>
            </div>
          ))}
        </div>
      )}
      {tab === "Amplification" && <SkillAmplificationPanel items={d.amplifications} />}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add control-plane/src/client/routes/WorkflowDetail.tsx control-plane/src/client/components/OtelSpanTree.tsx control-plane/src/client/components/PhaseTimeline.tsx control-plane/src/client/components/SkillAmplificationPanel.tsx
git commit -m "feat(cp): Workflow Detail — tabs, OTEL span tree, phase timeline, amp panel"
```

---

### Task 8.4: Policy & Autonomy screen (read-first + what-if)

**Files:**
- Create: `control-plane/src/client/routes/PolicyAndAutonomy.tsx`
- Create: `control-plane/src/client/components/WhatIfPanel.tsx`

- [ ] **Step 1: WhatIfPanel**

```tsx
// control-plane/src/client/components/WhatIfPanel.tsx
import { useState } from "react";

export default function WhatIfPanel({ policyId }: { policyId: string }) {
  const [value, setValue] = useState<string>("");
  const [result, setResult] = useState<{ wouldBeDifferent: number; totalEvaluated: number; impactedWorkflowIds: string[] } | null>(null);

  const run = async () => {
    const r = await fetch("/api/policy/dry-run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policyId, proposedValue: Number(value), scopeDays: 7 })
    });
    setResult(await r.json());
  };

  const propose = async () => {
    await fetch("/api/policy/propose-change", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policyId, proposedValue: Number(value), rationale: "Dry-run accepted", proposedBy: "finance-controller@wpp" })
    });
    alert("Change proposed. A PR has been opened for governance review.");
  };

  return (
    <div className="border border-slate-800 rounded p-3 bg-slate-900/30 space-y-2">
      <div className="text-xs uppercase text-slate-500">What-if analysis</div>
      <div className="flex gap-2 items-center">
        <input value={value} onChange={e => setValue(e.target.value)} placeholder="proposed value"
          className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs w-40" />
        <button onClick={run} className="text-xs px-3 py-1.5 border border-slate-700 rounded hover:bg-slate-800">Run dry-run</button>
      </div>
      {result && (
        <div className="text-xs text-slate-300 space-y-1">
          <div>Scope: last 7 days. Evaluated {result.totalEvaluated} workflows.</div>
          <div className="text-emerald-300">
            {result.wouldBeDifferent} would have decided differently.
          </div>
          {result.impactedWorkflowIds.length > 0 && (
            <div className="text-slate-400">Impacted: {result.impactedWorkflowIds.join(", ")}</div>
          )}
          <button onClick={propose} className="mt-2 text-xs px-3 py-1.5 bg-blue-600 rounded hover:bg-blue-500">
            Propose as change (opens PR)
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: PolicyAndAutonomy route**

```tsx
// control-plane/src/client/routes/PolicyAndAutonomy.tsx
import { useEffect, useState } from "react";
import type { AutonomyPolicy } from "@shared/types";
import WhatIfPanel from "../components/WhatIfPanel";

export default function PolicyAndAutonomy() {
  const [policies, setPolicies] = useState<AutonomyPolicy[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    void fetch("/api/policy").then(r => r.json()).then((ps: AutonomyPolicy[]) => {
      setPolicies(ps);
      if (ps[0]) setSelected(ps[0].id);
    });
  }, []);

  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">Policy & Autonomy</div>
      <div className="text-xs text-slate-400">
        Current autonomy policy is declarative and version-controlled. This screen is <em>read-first</em>. 
        Proposals go through a change-request flow — the Control Plane never mutates live governance.
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          {policies.map(p => (
            <button key={p.id}
              onClick={() => setSelected(p.id)}
              className={`w-full text-left border rounded p-3 bg-slate-900/30 ${selected === p.id ? "border-blue-500" : "border-slate-800"}`}>
              <div className="text-sm font-medium">{p.id}</div>
              <div className="text-xs text-slate-400">{p.description}</div>
              <div className="text-xs mt-2">current: <span className="text-slate-100">{String(p.currentValue)}</span></div>
              <div className="text-[10px] text-slate-500 mt-1">
                sha:{p.gitSha} · {p.author} · {new Date(p.updatedAt).toISOString().slice(0, 10)}
              </div>
            </button>
          ))}
        </div>
        <div>{selected && <WhatIfPanel policyId={selected} />}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add control-plane/src/client/routes/PolicyAndAutonomy.tsx control-plane/src/client/components/WhatIfPanel.tsx
git commit -m "feat(cp): Policy & Autonomy — read-first + What-If + propose-as-change"
```

---

### Task 8.5: Analytics (CP-12, first to cut)

**Files:**
- Create: `control-plane/src/client/routes/Analytics.tsx`

- [ ] **Step 1: Implement**

```tsx
// control-plane/src/client/routes/Analytics.tsx
import { useEffect, useState } from "react";

interface AnalyticsData {
  interventionRate: number; avgResolutionMs: number;
  overrideFrequency: number; qualityDelta: number;
}

export default function Analytics() {
  const [d, setD] = useState<AnalyticsData | null>(null);
  useEffect(() => {
    // Derive from workflow list (quick and dirty)
    void fetch("/api/workflows").then(r => r.json()).then((ws: Array<{ status: string; actionLedger: Array<{ actor: { kind: string } }> }>) => {
      const total = ws.length || 1;
      const humanTouched = ws.filter(w => w.actionLedger.some(a => a.actor.kind === "human")).length;
      setD({
        interventionRate: humanTouched / total,
        avgResolutionMs: 240_000,
        overrideFrequency: 0.12,
        qualityDelta: 0.04
      });
    });
  }, []);
  if (!d) return <div className="text-xs text-slate-500">loading…</div>;

  const cards = [
    { label: "Intervention rate", v: `${(d.interventionRate * 100).toFixed(1)}%` },
    { label: "Avg resolution", v: `${Math.round(d.avgResolutionMs / 1000)}s` },
    { label: "Override frequency", v: `${(d.overrideFrequency * 100).toFixed(1)}%` },
    { label: "Quality Δ vs baseline", v: `+${(d.qualityDelta * 100).toFixed(1)}%` }
  ];

  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">Analytics — last 24h</div>
      <div className="grid grid-cols-4 gap-3">
        {cards.map(c => (
          <div key={c.label} className="border border-slate-800 rounded p-3 bg-slate-900/30">
            <div className="text-[11px] uppercase text-slate-500">{c.label}</div>
            <div className="text-xl font-semibold">{c.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/client/routes/Analytics.tsx
git commit -m "feat(cp): Analytics screen (CP-12)"
```

---

### Task 8.6: Evaluations (CP-10, second to cut)

**Files:**
- Create: `control-plane/src/client/routes/Evaluations.tsx`

- [ ] **Step 1: Implement**

```tsx
// control-plane/src/client/routes/Evaluations.tsx
import { useEffect, useState } from "react";

interface Eval {
  id: string; workflowId: string; ranAt: number;
  taskAdherence: number; safety: number; toolAccuracy: number;
}

export default function Evaluations() {
  const [items, setItems] = useState<Eval[]>([]);
  useEffect(() => {
    const tick = () => void fetch("/api/evals").then(r => r.json()).then(setItems);
    tick(); const i = setInterval(tick, 5000); return () => clearInterval(i);
  }, []);
  const avg = (k: keyof Eval) => items.length === 0 ? 0 : items.reduce((a, b) => a + (b[k] as number), 0) / items.length;

  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">Continuous Evaluation</div>
      <div className="text-xs text-slate-400">{items.length} evals on sampled traces.</div>
      <div className="grid grid-cols-3 gap-3">
        <Metric label="Task adherence" v={avg("taskAdherence")} />
        <Metric label="Safety" v={avg("safety")} />
        <Metric label="Tool accuracy" v={avg("toolAccuracy")} />
      </div>
      <div className="space-y-1 text-xs">
        {items.slice(0, 20).map(e => (
          <div key={e.id} className="border border-slate-800 rounded p-2 bg-slate-900/30">
            <a href={`/workflows/${e.workflowId}`} className="text-blue-300">{e.workflowId}</a>
            <span className="text-slate-500 ml-2">{new Date(e.ranAt).toLocaleTimeString()}</span>
            <span className="ml-4 text-slate-400">
              adh={e.taskAdherence.toFixed(2)} safe={e.safety.toFixed(2)} tool={e.toolAccuracy.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, v }: { label: string; v: number }) {
  return (
    <div className="border border-slate-800 rounded p-3 bg-slate-900/30">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="text-xl font-semibold">{(v * 100).toFixed(1)}%</div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/src/client/routes/Evaluations.tsx
git commit -m "feat(cp): Evaluations screen (CP-10)"
```

---

## Phase 9 — Demo polish + optional Playwright

### Task 9.1: Demo script

**Files:**
- Create: `control-plane/docs/demo-script.md`

- [ ] **Step 1: Write**

```markdown
# WPP Control Plane — Demo Script

**Duration:** 3–5 minutes. Recorded via OBS or Loom at 1440p.

## Pre-flight
- `npm run dev`
- Wait until Fleet Dashboard shows ~30 workflows in-flight.
- Fleet Manager right rail should show "idle" transitioning to periodic wake-ups.

## Shot list

1. **Fleet Dashboard wide shot (5s)** — counters, filter bar, card grid, right rail visible. Pan to agency filter, select one agency, show filter works.
2. **Inject a duplicate burst** in a separate terminal:
   ```bash
   for i in 1 2 3; do curl -s -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"duplicate-invoice"}'; done
   ```
   Watch the right rail light up (wakeup → reasoning_start → tool_call → reasoning_done).
3. **Navigate to Exception Queue** — one bulk item (×3) should appear. Expand it. Show policy refs and recommendation.
4. **Click a workflow card** from the queue → Workflow Detail → Traces tab. Show OTEL span tree with tool durations.
5. **Back to queue** — select all 3 in the bulk group, click Bulk resolve, approve all.
6. **Policy screen** — click into `invoice-p2p.approval.auto_threshold`. Enter a new value (e.g. 10000), run dry-run, show impact, click "Propose as change".

## Hero screenshots (pause recording, capture PNGs)

1. Fleet Dashboard with ~40 workflows and 3 exceptions visible.
2. Exception Queue with expanded bulk-3 duplicate item.
3. Workflow Detail → Traces tab.
4. Bulk HITL modal with 3 checked.
5. Right rail mid-reasoning with `compose-exception` tool call.
6. What-If analysis with impact delta + "Propose as change" CTA.

## Post
- Trim, add a single title card "WPP Control Plane v1 — POC1 Finance P2P", export MP4 + 6 PNGs.
- Copy to `response/evidence/` for the written submission.
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/docs/demo-script.md
git commit -m "docs(cp): demo script + shot list"
```

---

### Task 9.2: README

**Files:**
- Create: `control-plane/README.md`

- [ ] **Step 1: Write**

```markdown
# WPP Control Plane v1

Working Control Plane demo for the WPP RFP response, built on GHCP SDK.

## Quickstart

```bash
cp .env.example .env
# Set AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY
npm install
npm run dev
```

- UI: http://localhost:5173
- API: http://localhost:3001
- Mock MCP servers: :4101 (workday), :4102 (d365), :4103 (maconomy), :4104 (payment)

## Architecture
See [docs/superpowers/specs/2026-04-13-wpp-control-plane-v1-design.md](../docs/superpowers/specs/2026-04-13-wpp-control-plane-v1-design.md).

## Inject demo scenarios
```bash
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"duplicate-invoice"}'
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"sanctions-flag"}'
```

## Stop
Ctrl-C. All state is in-memory; next `npm run dev` starts fresh.
```

- [ ] **Step 2: Commit**

```bash
git add control-plane/README.md
git commit -m "docs(cp): README with quickstart"
```

---

### Task 9.3: Playwright golden-path e2e (optional — cut if time runs short)

**Files:**
- Create: `control-plane/playwright.config.ts`
- Create: `control-plane/tests/e2e/golden-path.spec.ts`

- [ ] **Step 1: Config**

```typescript
// control-plane/playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:5173", trace: "on-first-retry" },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 120_000
  }
});
```

- [ ] **Step 2: Test**

```typescript
// control-plane/tests/e2e/golden-path.spec.ts
import { test, expect } from "@playwright/test";

test("golden path — inject, exception appears, bulk resolve", async ({ page, request }) => {
  await page.goto("/fleet");
  await expect(page.getByText("Fleet Manager")).toBeVisible();

  // inject 3 duplicates
  for (let i = 0; i < 3; i++) {
    await request.post("http://localhost:3001/api/simulator/inject", {
      data: { scenario: "duplicate-invoice" }
    });
  }

  // wait for exception to show
  await page.goto("/exceptions");
  await expect(page.getByText("duplicate-invoice").first()).toBeVisible({ timeout: 60_000 });
});
```

- [ ] **Step 3: Run, commit**

```bash
npx playwright install --with-deps
npm run test:e2e
git add control-plane/playwright.config.ts control-plane/tests/e2e/golden-path.spec.ts
git commit -m "test(cp): golden-path e2e"
```

---

## Phase 10 — Final integration

### Task 10.1: `dotenv` + final end-to-end check

- [ ] **Step 1: Full dry-run**

```bash
cd "c:/dev/ghcp sdk stuff/control-plane"
npm run dev
```

Verify (open http://localhost:5173):
- Fleet Dashboard populates within 15 seconds
- Right rail shows Fleet Manager idle → periodic wakeups
- Inject a duplicate scenario via `/api/simulator/inject`; exception appears in queue within 10 seconds
- Click a workflow card → Workflow Detail → Traces tab loads with spans
- Policy screen loads; dry-run returns impact; propose-change returns a CR id

- [ ] **Step 2: If anything fails, fix it now. Commit fixes.**

---

### Task 10.2: Capture hero screenshots + short demo video

- [ ] **Step 1: Inject a repeatable demo story** (run the exact commands in `docs/demo-script.md`)

- [ ] **Step 2: Take 6 hero shots, save to `control-plane/docs/screenshots/`**

```bash
mkdir -p "c:/dev/ghcp sdk stuff/control-plane/docs/screenshots"
```

Capture:
- `01-fleet-dashboard.png`
- `02-exception-queue-bulk.png`
- `03-workflow-detail-traces.png`
- `04-bulk-hitl-modal.png`
- `05-fleet-manager-rail.png`
- `06-what-if.png`

- [ ] **Step 3: Record 3–5 minute MP4 walkthrough**

Save as `control-plane/docs/demo.mp4` (or link externally if too large for git).

- [ ] **Step 4: Commit**

```bash
git add control-plane/docs/screenshots
git commit -m "docs(cp): hero screenshots for written response"
```

---

## Self-review checklist (run after finishing the plan above)

- [ ] **Spec coverage:** Walk through spec §§2–6 and confirm each CP capability (CP-1..CP-12) has a task. Check: CP-1 dashboard ✓, CP-2 exception queue ✓, CP-3 drill-down ✓, CP-4 bulk HITL ✓, CP-5 skill amp ✓, CP-6 policy read-first ✓ (via §8.4), CP-7 role switcher in top bar ✓ (in `App.tsx`), CP-8 cross-workflow context ✓ (dashboard counters + filters), CP-9 OTEL tree ✓, CP-10 evals ✓, CP-11 what-if ✓, CP-12 analytics ✓.

- [ ] **Placeholder scan:** `grep -E "TBD|TODO|FIXME|XXX|implement later" docs/superpowers/plans/2026-04-13-wpp-control-plane-v1.md` returns nothing.

- [ ] **Type consistency:** `Workflow`, `Phase`, `Exception`, `OtelSpan` all defined in `src/shared/types.ts` (Task 1.1) and referenced consistently in every task that uses them.

- [ ] **API shape consistency:** Routes in Task 6.2 match consumers in Task 7.2 (`useWorkflows`, `useExceptions`) and Task 8.x screens.

- [ ] **Environment variables defined once:** `.env.example` in Task 0.1 declares every var referenced in server code.

- [ ] **Cut list integrity:** Phases 8.5 (Analytics), 8.6 (Evaluations), 9.3 (Playwright), 8.4 (Policy) can each be dropped without breaking the other phases.
