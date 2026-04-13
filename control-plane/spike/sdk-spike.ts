/**
 * @github/copilot-sdk@0.2.2 — de-risk spike
 *
 * Demonstrates:
 *   1. Programmatic session creation (no interactive chat)
 *   2. Sequential sendAndWait calls that share session state
 *   3. Tool registration with typed parameters (via Zod v4)
 *   4. Tool-call event observation (tool.execution_start / tool.execution_complete)
 *
 * Run:
 *   cd "c:/dev/ghcp sdk stuff/control-plane"
 *   npx tsx spike/sdk-spike.ts
 *
 * Auth: uses gh CLI token via GITHUB_TOKEN env var → githubToken constructor option.
 *       The SDK also supports useLoggedInUser:true (default) which reads gh CLI stored creds.
 *       We prefer explicit token to make the auth path auditable.
 */

import { execSync } from "node:child_process";
import { CopilotClient, defineTool, approveAll } from "@github/copilot-sdk";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Auth: resolve GitHub token from gh CLI (least friction, no env var required)
// ---------------------------------------------------------------------------
function resolveGithubToken(): string | undefined {
  // Prefer explicit env var if the caller set it
  if (process.env.GITHUB_TOKEN) {
    console.log("[auth] Using GITHUB_TOKEN from environment");
    return process.env.GITHUB_TOKEN;
  }
  // Fall back to gh CLI
  try {
    const token = execSync("gh auth token", { encoding: "utf-8" }).trim();
    if (token) {
      console.log("[auth] Using token from 'gh auth token'");
      return token;
    }
  } catch {
    console.warn("[auth] 'gh auth token' failed — falling back to useLoggedInUser");
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Tool definition: ping
// ---------------------------------------------------------------------------
const pingTool = defineTool("ping", {
  description: "Echoes a message back to the caller. Use this when the user asks you to call the ping tool.",
  parameters: z.object({
    msg: z.string().describe("The message to echo back"),
  }),
  skipPermission: true,
  handler: async ({ msg }, invocation) => {
    console.log("\n╔══════════════════════════════════════════════════");
    console.log("║ TOOL CALL OBSERVED (via handler execution)");
    console.log(`║  tool     : ${invocation.toolName}`);
    console.log(`║  toolCallId: ${invocation.toolCallId}`);
    console.log(`║  args     : ${JSON.stringify({ msg })}`);
    console.log("╚══════════════════════════════════════════════════");
    const result = { echoed: msg };
    console.log(`[ping handler] returning: ${JSON.stringify(result)}`);
    return result;
  },
});

// ---------------------------------------------------------------------------
// Main spike
// ---------------------------------------------------------------------------
async function main() {
  console.log("=== GHCP SDK SPIKE — @github/copilot-sdk@0.2.2 ===\n");

  // 1. Create client
  const githubToken = resolveGithubToken();
  const client = new CopilotClient({
    ...(githubToken ? { githubToken } : { useLoggedInUser: true }),
    logLevel: "warning", // reduce noise; change to "debug" if troubleshooting
  });

  console.log("[client] Starting CopilotClient...");
  await client.start();
  console.log("[client] Started. State:", client.getState());

  // 2. Create a session with the ping tool registered
  console.log("\n[session] Creating session with ping tool...");
  const session = await client.createSession({
    model: "gpt-4.1",                  // use a model available on your Copilot licence
    onPermissionRequest: approveAll,    // required — approve all tool executions
    tools: [pingTool],
    systemMessage: {
      mode: "append",
      content: "You are a concise assistant. When asked to call the ping tool, call it immediately without preamble.",
    },
    infiniteSessions: { enabled: false }, // keep the spike simple — no compaction
  });

  console.log(`[session] Created. sessionId=${session.sessionId}`);

  // ---------------------------------------------------------------------------
  // Wire up event listeners for tool-call observation BEFORE sending any message.
  // This is the event-subscription pattern the Control Plane right-rail UI needs.
  // ---------------------------------------------------------------------------
  const toolEvents: Array<{ type: string; data: unknown }> = [];

  session.on("tool.execution_start", (event) => {
    console.log("\n[EVENT] tool.execution_start");
    console.log(`        toolName  : ${event.data.toolName}`);
    console.log(`        toolCallId: ${event.data.toolCallId}`);
    console.log(`        arguments : ${JSON.stringify(event.data.arguments ?? {})}`);
    toolEvents.push({ type: "tool.execution_start", data: event.data });
  });

  session.on("tool.execution_complete", (event) => {
    console.log("\n[EVENT] tool.execution_complete");
    console.log(`        toolCallId: ${event.data.toolCallId}`);
    console.log(`        success   : ${event.data.success}`);
    if (event.data.result) {
      console.log(`        result    : ${event.data.result.content}`);
    }
    toolEvents.push({ type: "tool.execution_complete", data: event.data });
  });

  // ---------------------------------------------------------------------------
  // MESSAGE 1 — establish context
  // ---------------------------------------------------------------------------
  console.log("\n━━━ MESSAGE 1 ━━━");
  const r1 = await session.sendAndWait(
    { prompt: "My name is Alice. Please just say 'Hello Alice'." },
    30_000,
  );
  console.log(`[R1] ${r1?.data.content ?? "(no response)"}`);

  // ---------------------------------------------------------------------------
  // MESSAGE 2 — test session context retention
  // ---------------------------------------------------------------------------
  console.log("\n━━━ MESSAGE 2 ━━━");
  const r2 = await session.sendAndWait(
    { prompt: "What is my name? Just give me the name, nothing else." },
    30_000,
  );
  console.log(`[R2] ${r2?.data.content ?? "(no response)"}`);

  const contextRetained = r2?.data.content?.toLowerCase().includes("alice");
  console.log(`[check] Session context retained: ${contextRetained ? "YES ✓" : "NO ✗ — INVESTIGATE"}`);

  // ---------------------------------------------------------------------------
  // MESSAGE 3 — tool invocation
  // ---------------------------------------------------------------------------
  console.log("\n━━━ MESSAGE 3 — tool call ━━━");
  const r3 = await session.sendAndWait(
    { prompt: "Call the ping tool with msg='hello'. Then tell me what it returned." },
    60_000,
  );
  console.log(`[R3] ${r3?.data.content ?? "(no response)"}`);

  // ---------------------------------------------------------------------------
  // Summary
  // ---------------------------------------------------------------------------
  console.log("\n=== SPIKE SUMMARY ===");
  console.log(`Session ID           : ${session.sessionId}`);
  console.log(`Context retained (R2): ${contextRetained ? "YES" : "NO"}`);
  console.log(`Tool events observed : ${toolEvents.length}`);
  console.log("Tool event log:");
  for (const e of toolEvents) {
    console.log(`  - ${e.type}: ${JSON.stringify(e.data).slice(0, 120)}`);
  }

  const pingStartSeen = toolEvents.some((e) => e.type === "tool.execution_start");
  const pingCompleteSeen = toolEvents.some((e) => e.type === "tool.execution_complete");
  console.log(`\ntool.execution_start seen  : ${pingStartSeen ? "YES ✓" : "NO ✗"}`);
  console.log(`tool.execution_complete seen: ${pingCompleteSeen ? "YES ✓" : "NO ✗"}`);

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------
  await session.disconnect();
  await client.stop();
  console.log("\n[done] Spike complete.");
}

main().catch((err) => {
  console.error("\n[FATAL]", err);
  process.exit(1);
});
