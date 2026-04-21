import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { CopilotClient, approveAll } from "@github/copilot-sdk";
import { Triage } from "./triage";
import { FleetManagerQueue } from "./fleetManagerQueue";
import { buildFleetManagerTools } from "@server/mcp-tools/index";
function loadSkillMd() {
    // Resolve path relative to this file at runtime
    // __dirname equivalent in ESM:
    const __filename = fileURLToPath(import.meta.url);
    const __dir = dirname(__filename);
    const skillPath = join(__dir, "..", "skills", "fleet-manager.skill.md");
    return readFileSync(skillPath, "utf-8");
}
export class FleetManagerService {
    client = null;
    session = null;
    triage = new Triage();
    queue;
    tickInterval = null;
    busUnsub = null;
    bus;
    store;
    env;
    audit;
    onLive;
    constructor({ bus, store, env, audit, onLive }) {
        this.bus = bus;
        this.store = store;
        this.env = env;
        this.audit = audit;
        this.onLive = onLive;
        this.queue = new FleetManagerQueue(this.processBatch.bind(this), { debounceMs: 2000 });
    }
    async start() {
        // Build client
        this.client = new CopilotClient({ githubToken: this.env.githubToken });
        await this.client.start();
        // Load SKILL.md as system prompt
        const systemPrompt = loadSkillMd();
        // Build tools
        const tools = buildFleetManagerTools(this.store, this.bus, this.audit);
        // Create session
        this.session = await this.client.createSession({
            model: this.env.model,
            onPermissionRequest: approveAll,
            tools,
            systemMessage: {
                mode: "append",
                content: systemPrompt,
            },
            infiniteSessions: { enabled: false },
        });
        // Wire tool-call event listeners BEFORE any messages
        this.session.on("tool.execution_start", (event) => {
            this.onLive({
                kind: "tool_call",
                timestamp: Date.now(),
                data: {
                    stage: "start",
                    name: event.data.toolName,
                    toolCallId: event.data.toolCallId,
                    args: event.data.arguments,
                },
            });
        });
        this.session.on("tool.execution_complete", (event) => {
            this.onLive({
                kind: "tool_call",
                timestamp: Date.now(),
                data: {
                    stage: "complete",
                    toolCallId: event.data.toolCallId,
                    success: event.data.success,
                },
            });
        });
        // Subscribe to fleet events
        this.busUnsub = this.bus.onAny((event) => {
            this.triage.observe(event);
            // Only run anomaly detection for non-anomaly events to prevent recursive re-entry:
            // emitting fleet.anomaly.detected would re-invoke this handler via bus.emit("*"),
            // which would call detectAnomaly again while recentDups is still populated → stack overflow.
            if (event.type !== "fleet.anomaly.detected") {
                const anomaly = this.triage.detectAnomaly();
                if (anomaly) {
                    this.bus.emit({
                        type: "fleet.anomaly.detected",
                        pattern: anomaly.pattern,
                        workflowIds: anomaly.workflowIds,
                    });
                }
            }
            if (this.triage.shouldWake(event) && "workflowId" in event) {
                this.queue.enqueue({
                    workflowId: event.workflowId,
                    reason: event.type,
                });
                this.onLive({
                    kind: "wakeup",
                    timestamp: Date.now(),
                    data: { workflowId: event.workflowId, reason: event.type },
                });
            }
        });
        // 30-second tick
        this.tickInterval = setInterval(() => {
            this.bus.emit({ type: "fleet.tick", timestamp: Date.now() });
        }, 30_000);
        this.onLive({ kind: "idle", timestamp: Date.now() });
    }
    async processBatch(batch) {
        if (!this.session)
            return;
        if (this.queue.depth() > 20) {
            this.bus.emit({ type: "fleet.overload", queueDepth: this.queue.depth() });
        }
        const summary = batch.map(e => `workflow=${e.workflowId} reason=${e.reason}`).join(", ");
        this.onLive({
            kind: "reasoning_start",
            timestamp: Date.now(),
            data: { batchSize: batch.length, summary },
        });
        const promptLines = batch
            .map(e => `- workflow=${e.workflowId} reason=${e.reason}`)
            .join("\n");
        const prompt = `Triggering events:\n${promptLines}\n\nFollow the SKILL instructions. Call tools as needed. Prefer bulk grouping where related.`;
        try {
            const response = await this.session.sendAndWait({ prompt }, 60_000);
            const preview = (response?.data.content ?? "").slice(0, 200);
            this.onLive({
                kind: "reasoning_done",
                timestamp: Date.now(),
                data: { preview },
            });
        }
        catch (err) {
            this.onLive({
                kind: "error",
                timestamp: Date.now(),
                data: { message: err instanceof Error ? err.message : String(err) },
            });
        }
    }
    async stop() {
        if (this.tickInterval) {
            clearInterval(this.tickInterval);
            this.tickInterval = null;
        }
        if (this.busUnsub) {
            this.busUnsub();
            this.busUnsub = null;
        }
        if (this.session) {
            await this.session.disconnect();
            this.session = null;
        }
        if (this.client) {
            await this.client.stop();
            this.client = null;
        }
    }
}
