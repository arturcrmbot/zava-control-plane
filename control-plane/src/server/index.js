// src/server/index.ts
import express from "express";
import cors from "cors";
import "dotenv/config";
import { execSync } from "node:child_process";
import { EventBus } from "./services/eventBus";
import { StateStore } from "./services/stateStore";
import { WorkflowSimulator } from "./services/workflowSimulator";
import { SimulatorOrchestrator } from "./services/simulatorOrchestrator";
import { FleetManagerService } from "./services/fleetManagerService";
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
    let githubToken = "";
    try {
        githubToken = execSync("gh auth token", { encoding: "utf-8" }).trim();
    }
    catch {
        console.error("[server] WARNING: 'gh auth token' failed. Fleet Manager will not start.");
    }
    const fm = new FleetManagerService({
        bus, store, audit,
        env: {
            githubToken,
            model: process.env.FLEET_MANAGER_MODEL ?? "gpt-4.1",
            maxTokens: Number(process.env.FLEET_MANAGER_MAX_TOKENS ?? 2000)
        },
        onLive: (ev) => hub.broadcast("fleet-manager", ev)
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
        if (githubToken) {
            try {
                await fm.start();
                console.log("[server] Fleet Manager started");
            }
            catch (e) {
                console.error("[server] Fleet Manager failed to start:", e);
            }
        }
        else {
            console.warn("[server] Fleet Manager skipped — no GitHub token.");
        }
        orch.start();
        evalRunner.start();
    });
}
main().catch((err) => { console.error(err); process.exit(1); });
