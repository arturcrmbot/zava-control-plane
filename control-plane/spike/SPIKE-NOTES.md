# SPIKE-NOTES — @github/copilot-sdk@0.2.2

**Date:** 2026-04-13  
**Branch:** main  
**Working dir:** `c:/dev/ghcp sdk stuff/control-plane`  
**Spike script:** `spike/sdk-spike.ts`  
**Run command:** `npx tsx spike/sdk-spike.ts`  

All four acceptance criteria passed on first run. Full output is pasted at the bottom of this document.

---

## 1. Package surface

Entry points from `package.json`:
- ESM: `dist/index.js` / types: `dist/index.d.ts`
- CJS: `dist/cjs/index.js`
- Extension entry: `dist/extension.js`

**Named exports from `@github/copilot-sdk`:**

| Export | Kind | Notes |
|--------|------|-------|
| `CopilotClient` | class | Main entry point. Spawns/connects to the Copilot CLI subprocess via stdio (default) or TCP. |
| `CopilotSession` | class | Returned by `client.createSession()`. Not constructed directly. |
| `defineTool` | function | Helper to register a tool with typed Zod parameters. |
| `approveAll` | const | Pre-built `PermissionHandler` that approves every tool execution. |
| `SYSTEM_PROMPT_SECTIONS` | const | Enum of prompt section IDs for `systemMessage.mode:"customize"`. |
| Many `type`/`interface` exports | types | See `dist/index.d.ts` for full list. |

**Key types:**
- `CopilotClientOptions` — constructor options (see §2)
- `SessionConfig` — `createSession` argument (see §3)
- `Tool<TArgs>` / `ToolHandler<TArgs>` / `ToolInvocation` / `ToolResultObject`
- `SessionEvent` — discriminated union of all event types (generated from schema)
- `SessionEventType` — union of all event-type string literals
- `AssistantMessageEvent` — `Extract<SessionEvent, { type:"assistant.message" }>`

---

## 2. Auth pattern that worked

### Winning pattern: explicit `githubToken` from `gh auth token`

```typescript
import { execSync } from "node:child_process";
import { CopilotClient } from "@github/copilot-sdk";

const githubToken = execSync("gh auth token", { encoding: "utf-8" }).trim();

const client = new CopilotClient({ githubToken });
await client.start();
```

The SDK passes the token to the Copilot CLI subprocess via an environment variable internally. This works as long as:
- `gh` CLI is installed and `gh auth login` has been run (personal Copilot license).
- The token scopes include `repo` and `read:org` (the standard `gh auth login` scopes are sufficient).

### Alternative that also works (and is the SDK default)

```typescript
const client = new CopilotClient({ useLoggedInUser: true }); // default
await client.start();
```

This lets the CLI subprocess pick up OAuth credentials from the `gh` CLI keychain automatically. No token handling needed. Slightly less explicit but zero friction.

### What does NOT apply here

- `AZURE_FOUNDRY_API_KEY` / `DefaultAzureCredential` — not used by this SDK; only relevant for BYOK (`provider:` config inside `createSession`).
- `GITHUB_TOKEN` env var — the SDK itself does not read this. You must pass it as `githubToken` in the constructor OR let `useLoggedInUser` pick up stored `gh` creds.

---

## 3. Session API

### Client lifecycle

```typescript
const client = new CopilotClient(options?: CopilotClientOptions);
await client.start();     // spawns CLI subprocess, establishes JSON-RPC connection
await client.stop();      // graceful shutdown; returns Error[]
await client.forceStop(); // non-graceful
client.getState();        // returns "connected" | "disconnected" | ...
```

### Session creation

```typescript
const session: CopilotSession = await client.createSession({
  sessionId?: string,                // optional custom ID; SDK generates UUID if omitted
  model?: string,                    // "gpt-4.1", "claude-sonnet-4.5", etc.
  onPermissionRequest: PermissionHandler,  // REQUIRED
  tools?: Tool[],                    // custom tools
  systemMessage?: SystemMessageConfig,
  infiniteSessions?: InfiniteSessionConfig, // default: enabled; disable for simple cases
  provider?: ProviderConfig,         // BYOK — Azure OpenAI / Ollama / custom
  // ... more options
});
```

### Sending messages

```typescript
// Fire-and-forget (returns messageId string):
const msgId = await session.send({ prompt: string, attachments?: [...] });

// Send and block until session.idle (returns final AssistantMessageEvent | undefined):
const response = await session.sendAndWait(
  { prompt: string },
  timeoutMs?: number  // default 60_000
);
console.log(response?.data.content);  // assistant's text
```

### Session properties

```typescript
session.sessionId: string
session.workspacePath: string | undefined   // populated only when infiniteSessions enabled
session.capabilities: SessionCapabilities   // live-updated
```

### Session cleanup

```typescript
await session.disconnect();  // releases memory; session on-disk state preserved for resume
await client.deleteSession(session.sessionId);  // purges on-disk state
```

### Resume

```typescript
const session = await client.resumeSession(sessionId, config?: ResumeSessionConfig);
```

---

## 4. Tool registration shape

### Using `defineTool` + Zod (recommended for type safety)

```typescript
import { defineTool } from "@github/copilot-sdk";
import { z } from "zod";  // zod v4.3.6 is available in node_modules

const myTool = defineTool("ping", {
  description: "Echoes a message back",
  parameters: z.object({
    msg: z.string().describe("The message to echo back"),
  }),
  skipPermission: true,    // optional: skips the permission prompt
  handler: async ({ msg }, invocation) => {
    // invocation: { sessionId, toolCallId, toolName, arguments, traceparent?, tracestate? }
    return { echoed: msg };  // any JSON-serialisable value; string also accepted
  },
});

const session = await client.createSession({
  onPermissionRequest: approveAll,
  tools: [myTool],
});
```

**SDK `ZodSchema` interface** the `defineTool` helper expects:
```typescript
interface ZodSchema<T> {
  _output: T;
  toJSONSchema(): Record<string, unknown>;
}
```
Zod v4 satisfies this — `z.object({...})` instances have `toJSONSchema()` that returns a JSON Schema draft-2020-12 object.

### Using raw JSON Schema (no Zod needed)

```typescript
const myTool = defineTool("ping", {
  description: "Echoes a message back",
  parameters: {
    type: "object",
    properties: {
      msg: { type: "string", description: "The message to echo back" }
    },
    required: ["msg"],
  },
  handler: async (args) => {
    const { msg } = args as { msg: string };
    return { echoed: msg };
  },
});
```

### Tool result types

```typescript
// Simple: return a string or any JSON-serialisable object
handler: async (args) => "done"
handler: async (args) => ({ echoed: args.msg })

// Full control:
handler: async (args): Promise<ToolResultObject> => ({
  textResultForLlm: "Echoed: " + args.msg,
  resultType: "success",          // "success" | "failure" | "rejected" | "denied" | "timeout"
  sessionLog: "optional UI note",
})
```

### Tool override flag

If registering a tool with the same name as a built-in CLI tool (e.g. `edit_file`), you **must** set:
```typescript
defineTool("edit_file", { ..., overridesBuiltInTool: true, handler: ... })
```
Otherwise the SDK throws at `createSession`.

---

## 5. Tool-call event subscription

There are **two complementary observation paths**:

### Path A: Event listeners on the session (the right-rail UI path)

```typescript
// Subscribe BEFORE sending any messages:

session.on("tool.execution_start", (event) => {
  // event.data: { toolCallId, toolName, arguments?, mcpServerName?, mcpToolName?, parentToolCallId? }
  console.log(event.data.toolName, event.data.arguments);
});

session.on("tool.execution_complete", (event) => {
  // event.data: { toolCallId, success, model?, interactionId?, result? }
  // event.data.result: { content, detailedContent?, contents? }
  console.log(event.data.success, event.data.result?.content);
});

// Catch-all (all event types):
const unsub = session.on((event) => {
  console.log(event.type, event.data);
});
unsub(); // call to unsubscribe
```

**Other observable tool events:**
- `tool.user_requested` — user manually triggered a tool
- `tool.execution_partial_result` — streaming partial output (ephemeral)
- `tool.execution_progress` — progress message from MCP tools (ephemeral)
- `external_tool.requested` / `external_tool.completed` — for MCP tools

The `session.on(eventType, handler)` overload provides **full type inference** — `event.data` is narrowed to the correct shape automatically.

### Path B: ToolHandler function (side-effect observation)

The `handler` callback in `defineTool` receives a `ToolInvocation` object with the exact args. This fires synchronously when the model invokes the tool, before the result is sent back. It is the definitive "which tool, what args, what result" hook.

```typescript
handler: async (args, invocation) => {
  // invocation.toolName, invocation.toolCallId, invocation.arguments
  // invocation.traceparent, invocation.tracestate (for OTel linkage)
  emit("tool-call", { tool: invocation.toolName, args, sessionId: invocation.sessionId });
  const result = await doWork(args);
  return result;
}
```

**Recommendation for Control Plane right-rail UI:** use event listeners (Path A). They fire even for built-in CLI tools (e.g. `read_file`, `edit_file`, `run_command`) that have no custom handler. The `tool.execution_start` event gives you tool name + arguments; `tool.execution_complete` gives you success/failure + the result content shown to the model.

---

## 6. What does NOT work / gotchas

| Issue | Detail |
|-------|--------|
| `tsconfig.json` does not include `spike/` | The root `tsconfig.json` has `"include": ["src", "mocks", "tests"]` — excludes `spike/`. `tsx` still runs it fine because `tsx` does not use `tsc` for resolution. Do not add spike files to the main tsconfig include without renaming the path mappings. |
| Zod v4 not v3 | The project has Zod **v4.3.6** (not v3). In Zod v4, `z.string().describe(...)` works. In Zod v3 you'd use the same API but the `toJSONSchema()` method did not exist on instances — you'd need the separate `zodToJsonSchema` package. The SDK's `ZodSchema` interface only requires `_output` + `toJSONSchema()`, which Zod v4 satisfies natively. |
| `useLoggedInUser` + `githubToken` are mutually exclusive | Setting `githubToken` implicitly sets `useLoggedInUser: false`. Don't pass both. |
| `configDir` option | Not in the published 0.2.2 type definitions (the reference `copilot.service.ts` used it). It may be an internal option or available on a different SDK version. Spike omitted it without issue. |
| `model: "gpt-5"` in README examples | The README uses `"gpt-5"` as an example model name. On the standard Copilot license the actual available model identifiers (confirmed in spike) include `"gpt-4.1"`. Use `client.listModels()` to enumerate. |
| `infiniteSessions` enabled by default | The SDK enables context compaction by default. This is fine for production but adds `session.compaction_start` / `session.compaction_complete` events. Set `{ enabled: false }` in the spike to keep output clean. |
| CLI subprocess SQLite warning | The Copilot CLI subprocess logs `ExperimentalWarning: SQLite is an experimental feature` to stderr at startup. This is from Node.js v24 and is harmless — it surfaces in the output as `[CLI subprocess]` lines. |
| No Azure Foundry auth needed | The SDK talks directly to GitHub's Copilot API. Azure credentials (`az login`, `AZURE_FOUNDRY_API_KEY`) are only needed if you configure a custom `provider:` (BYOK). The user's personal Copilot license is sufficient for the spike. |

---

## Verified output from successful run

```
=== GHCP SDK SPIKE — @github/copilot-sdk@0.2.2 ===

[auth] Using token from 'gh auth token'
[client] Starting CopilotClient...
[CLI subprocess] (node:21488) ExperimentalWarning: SQLite is an experimental feature and might change at any time
[client] Started. State: connected

[session] Creating session with ping tool...
[session] Created. sessionId=ff75f00d-00a1-419e-aff6-ca80181a6d6e

━━━ MESSAGE 1 ━━━
[R1] Hello Alice.

━━━ MESSAGE 2 ━━━
[R2] Alice
[check] Session context retained: YES ✓

━━━ MESSAGE 3 — tool call ━━━

[EVENT] tool.execution_start
        toolName  : ping
        toolCallId: call_cbVFXcGu5j78o89NfE8dBAuQ
        arguments : {"msg":"hello"}

╔══════════════════════════════════════════════════
║ TOOL CALL OBSERVED (via handler execution)
║  tool     : ping
║  toolCallId: call_cbVFXcGu5j78o89NfE8dBAuQ
║  args     : {"msg":"hello"}
╚══════════════════════════════════════════════════
[ping handler] returning: {"echoed":"hello"}

[EVENT] tool.execution_complete
        toolCallId: call_cbVFXcGu5j78o89NfE8dBAuQ
        success   : true
        result    : {"echoed":"hello"}
[R3] The ping tool returned: hello

=== SPIKE SUMMARY ===
Session ID           : ff75f00d-00a1-419e-aff6-ca80181a6d6e
Context retained (R2): YES
Tool events observed : 2
Tool event log:
  - tool.execution_start: {"toolCallId":"call_cbVFXcGu5j78o89NfE8dBAuQ","toolName":"ping","arguments":{"msg":"hello"}}
  - tool.execution_complete: {"toolCallId":"call_cbVFXcGu5j78o89NfE8dBAuQ","model":"gpt-4.1",...

tool.execution_start seen  : YES ✓
tool.execution_complete seen: YES ✓

[done] Spike complete.
```

---

## Fitness assessment for event-driven Fleet Manager design

The SDK is **fit for purpose** for the Control Plane's event-driven right-rail UI with the following notes:

1. **Event subscription is push-based, not polling.** `session.on(eventType, handler)` fires synchronously on every event. This maps cleanly to SSE or WebSocket fan-out in the Control Plane server.

2. **Tool events fire for ALL tools**, including built-in CLI tools (`read_file`, `edit_file`, `run_command`). The right-rail can display the complete agentic action timeline without any special wiring per tool.

3. **toolCallId is stable across start/complete.** You can correlate `tool.execution_start` → `tool.execution_complete` by `toolCallId` to build a latency timeline.

4. **No streaming tool results by default.** `tool.execution_partial_result` is ephemeral and only emitted for long-running tools. For most tools you get start → complete atomically.

5. **Session resumption is first-class.** `client.resumeSession(sessionId)` restores conversation history. Fleet Manager can store `sessionId` in Cosmos DB and resume agent sessions after server restart.

6. **BYOK (Azure OpenAI / Foundry) is one `provider:` object.** If the WPP deployment needs to route through Azure AI Foundry instead of GitHub's Copilot API, replace the `githubToken` auth with a `provider: { type: "azure", baseUrl, apiKey }` inside `createSession`. The session API surface does not change.

7. **Concern: single process per client.** `CopilotClient` spawns one CLI subprocess. At fleet scale (many concurrent agents), each `CopilotClient` instance is a subprocess. You will likely want a pool or a shared CLI server (`cliUrl` option) — investigate before Tasks 5.4/5.5.
