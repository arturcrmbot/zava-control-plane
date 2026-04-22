# Phase 0.2 Spike — MAF Durable Notes

**Date:** 2026-04-13  
**Status:** DONE_WITH_CONCERNS  
**Spikes:** `spike/copilot_sdk_spike.py` (PASS), `spike/maf_durable_spike.py` (PARTIAL — imports OK, E2E blocked on Docker)

---

## 1. Resolved Package Names

All packages are on PyPI and installed successfully via `uv add`.

| Role | PyPI package name | Installed version | Import root |
|------|------------------|-------------------|-------------|
| Python GHCP SDK | `github-copilot-sdk` | 0.2.1 | `copilot` |
| MAF meta-package | `agent-framework` | 1.0.1 | `agent_framework` |
| MAF core | `agent-framework-core` | 1.0.1 | `agent_framework` |
| MAF + GitHub Copilot | `agent-framework-github-copilot` | 1.0.0b260409 | `agent_framework_github_copilot` |
| MAF + Azure Functions hosting | `agent-framework-azurefunctions` | 1.0.0b260409 | `agent_framework_azurefunctions` |
| MAF + Durable Task | `agent-framework-durabletask` | 1.0.0b260409 | `agent_framework_durabletask` |
| Durable Task Python SDK | `durabletask` | 1.4.0 | `durabletask` |
| Durable Task managed scheduler | `durabletask-azuremanaged` | 1.4.0 | `durabletask.azuremanaged` |
| MAF orchestration patterns | `agent-framework-orchestrations` | 1.0.0b260409 | `agent_framework_orchestrations` |

**Note:** `github-copilot-sdk==0.2.1` was installed (not 0.2.2 as the npm counterpart). The npm package is `0.2.2`; the Python package's latest is `0.2.1`. They appear to be near-identical in API surface (same repo, same release train).

**Note:** `agent-framework==1.0.1` (the meta-package) installs `agent-framework-core[all]` which pulls in all optional integrations. For production, constrain to only the integrations needed.

---

## 2. GHCP SDK Python API

The Python package `github-copilot-sdk` is the direct Python sibling of `@github/copilot-sdk` npm. The import root is `copilot` (same as npm). The API differs from the npm version in key ways.

### Auth pattern

```python
import subprocess
from copilot import CopilotClient
from copilot.client import SubprocessConfig

token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
config = SubprocessConfig(github_token=token, log_level="warning")
client = CopilotClient(config)
```

`CopilotClient` supports async context manager (preferred) or explicit `start()`/`stop()`:

```python
async with client:
    session = await client.create_session(...)
```

### Session creation

```python
from copilot.session import PermissionHandler  # NOT from copilot.client

session = await client.create_session(
    on_permission_request=PermissionHandler.approve_all,  # REQUIRED
    model="gpt-4.1",
    tools=[my_tool],
    system_message={"mode": "append", "content": "..."},
)
```

`on_permission_request` is required (no default). `PermissionHandler.approve_all` is a staticmethod on `copilot.session.PermissionHandler` that returns `PermissionRequestResult(kind="approved")`.

### Sending messages

```python
# Fire and forget — returns message_id str
msg_id = await session.send("Hello Alice.")

# Block until session.idle — returns SessionEvent | None
event = await session.send_and_wait("Hello Alice.", timeout=60.0)
# event.data.content  →  the assistant text response
```

### Tool registration — Pydantic only (NOT Zod, NOT raw JSON Schema)

The Python SDK's `define_tool` decorator uses **Pydantic BaseModel** for parameter schemas, not Zod (npm) or raw JSON Schema (possible in npm). There is no `params_type=` shortcut either; the decorator infers it from the first argument's type hint.

```python
from copilot.tools import define_tool, ToolInvocation, ToolResult
from pydantic import BaseModel, Field

class PingParams(BaseModel):
    msg: str = Field(description="The message to echo back")

@define_tool(description="Echoes a message back", skip_permission=True)
def ping_tool(params: PingParams, invocation: ToolInvocation) -> ToolResult:
    return ToolResult(
        text_result_for_llm=f'{{"echoed": "{params.msg}"}}',
        result_type="success",
    )
```

Handler signature detection:
- `fn()` — zero params
- `fn(invocation: ToolInvocation)` — invocation only
- `fn(params: SomePydanticModel)` — params only
- `fn(params: SomePydanticModel, invocation: ToolInvocation)` — both (recommended)

`ToolResult` dataclass fields: `text_result_for_llm`, `result_type` (`"success"|"failure"|"rejected"|"denied"|"timeout"`), `error`, `session_log`.

### Event subscription

```python
from copilot.generated.session_events import SessionEventType

# Subscribe BEFORE sending. Returns an unsubscribe callable.
def handle_event(event):  # event: SessionEvent
    if event.type == SessionEventType.TOOL_EXECUTION_START:
        print(event.data.tool_name, event.data.tool_call_id, event.data.arguments)
    elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
        print(event.data.success, event.data.result.content)

unsub = session.on(handle_event)
```

**Key difference from npm:** The Python SDK `session.on()` takes a **single handler for all events** — there is no `session.on(event_type_string, handler)` typed overload. You filter inside the handler by `event.type`.

`SessionEvent` fields: `.type` (SessionEventType enum), `.data` (Data object with many optional fields), `.id` (UUID), `.timestamp` (datetime).

Key `SessionEventType` enum members for tool observability:
- `TOOL_EXECUTION_START` — `event.data.tool_name`, `.tool_call_id`, `.arguments`
- `TOOL_EXECUTION_COMPLETE` — `event.data.tool_call_id`, `.success`, `.result.content`

### Session cleanup

```python
await session.disconnect()          # release memory, keep on-disk state
await client.delete_session(sid)    # purge on-disk state
```

### GitHub Copilot Agent via MAF (alternative higher-level API)

`agent-framework-github-copilot` wraps the low-level SDK as a MAF `Agent`:

```python
from agent_framework_github_copilot import GitHubCopilotAgent

agent = GitHubCopilotAgent(
    name="my-agent",
    instructions="Be helpful.",
    model="gpt-4.1",
)
response = await agent.run("Hello!")
print(response.text)
```

This is the correct API for wiring a Copilot-backed agent into MAF Workflows or Durable orchestrations.

---

## 3. MAF Durable Workflow API

**The spec skeleton's assumed API does not exist.** There is no `DurableWorkflow` base class, no `@workflow_step` decorator, no `DurableContext`, no `DurableRuntimeClient.from_environment()`.

The real MAF durable pattern uses a **generator function orchestration** backed by the Durable Task SDK.

### Orchestration function (replaces DurableWorkflow)

```python
from collections.abc import Generator
from typing import Any
from agent_framework.azure import DurableAIAgentOrchestrationContext
from durabletask.task import OrchestrationContext, Task, when_any

def my_orchestration(
    context: OrchestrationContext, input_str: str
) -> Generator[Task[Any], Any, str]:
    """Must be a synchronous generator (def, not async def)."""

    # Wrap to get agent access
    agent_ctx = DurableAIAgentOrchestrationContext(context)
    agent = agent_ctx.get_agent("MyAgent")  # replaces agent.run via entity proxy

    # yield a Task to await it (replaces await)
    result: str = yield context.call_activity(some_activity_fn, input=input_str)

    # HITL: wait for an external event (replaces ctx.wait_for_external_event)
    approval_task = context.wait_for_external_event("approve_step")
    timeout_task = context.create_timer(
        context.current_utc_datetime + timedelta(hours=72)
    )
    winner = yield when_any([approval_task, timeout_task])

    if winner != approval_task:
        raise TimeoutError("HITL timed out")
    timeout_task.cancel()

    decision = approval_task.get_result()
    return f"{result} (approved: {decision})"  # noqa: B901
```

### Activity functions (replaces workflow_step)

```python
from durabletask.task import ActivityContext

def my_activity(ctx: ActivityContext, input_val: str) -> str:
    """Synchronous function — registered with worker.add_activity()."""
    return f"processed: {input_val}"
```

### Worker setup (replaces DurableRuntimeClient.from_environment + start)

```python
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from agent_framework.azure import DurableAIAgentWorker
from agent_framework.openai import OpenAIChatCompletionClient  # or FoundryChatClient
from agent_framework import Agent

# 1. Create the low-level gRPC worker
worker = DurableTaskSchedulerWorker(
    host_address="http://localhost:8080",  # or Azure managed endpoint
    secure_channel=False,
    taskhub="my-hub",
)

# 2. Wrap with MAF agent worker (registers agents as durable entities)
agent_worker = DurableAIAgentWorker(worker)

# 3. Register agents
my_agent = Agent(client=OpenAIChatCompletionClient(...), name="MyAgent")
agent_worker.add_agent(my_agent)

# 4. Register activities and orchestrations on the low-level worker
worker.add_activity(my_activity)
worker.add_orchestrator(my_orchestration)

# 5. Start (blocks)
worker.start()
```

### Client API (replaces DurableRuntimeClient.start_new / raise_event / get_status / get_output)

```python
from durabletask.azuremanaged.client import DurableTaskSchedulerClient

client = DurableTaskSchedulerClient(
    host_address="http://localhost:8080",
    secure_channel=False,
    taskhub="my-hub",
)

# start_new equivalent
instance_id = client.schedule_new_orchestration(
    orchestrator="my_orchestration",   # function name
    input="Alice",
)

# get_status equivalent
state = client.get_orchestration_state(instance_id=instance_id)
print(state.runtime_status.name)         # "RUNNING", "COMPLETED", "FAILED", etc.
print(state.serialized_custom_status)    # JSON string of custom status set via context.set_custom_status()

# raise_event equivalent
client.raise_orchestration_event(
    instance_id=instance_id,
    event_name="approve_step",
    data={"approved": True, "feedback": ""},
)

# get_output equivalent (via get_orchestration_state after COMPLETED)
output = state.serialized_output  # JSON string
import json; result = json.loads(output)

# Blocking wait equivalent
final_state = client.wait_for_orchestration_completion(
    instance_id=instance_id,
    timeout=60,
)
```

---

## 4. MAF Pregel Graph API (Workflow graphs for per-phase use)

The spec §4 Pregel BSP pattern is implemented via `agent_framework.Workflow` + `agent_framework.WorkflowBuilder`. This is a **separate** pattern from the Durable Task orchestration — it is an in-process async graph executor.

### Core classes (from `agent_framework`)

```python
from agent_framework import (
    Workflow,           # immutable graph instance; has .run(input) method
    WorkflowBuilder,    # fluent builder for assembling the graph
    WorkflowContext,    # passed into @handler methods
    Executor,           # base class for custom node types
    AgentExecutor,      # wraps SupportsAgentRun as a graph node
    FunctionExecutor,   # wraps a plain function as a graph node
    handler,            # decorator to mark the entry-point method of an Executor
    WorkflowRunResult,  # list of WorkflowEvent; .get_outputs(), .get_final_state()
)
from agent_framework._workflows._edge import (
    SingleEdgeGroup,       # 1:1 routing with optional condition
    FanOutEdgeGroup,       # broadcast to multiple targets
    FanInEdgeGroup,        # aggregate from multiple sources before delivery
    SwitchCaseEdgeGroup,   # first-match routing
)
```

### Example: simple sequential graph

```python
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

class UpperExecutor(Executor):
    @handler
    async def process(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text.upper())

class OutputExecutor(Executor):
    @handler
    async def process(self, text: str, ctx: WorkflowContext[None, str]) -> None:
        await ctx.yield_output(text)

upper = UpperExecutor(id="upper")
output = OutputExecutor(id="output")

workflow = WorkflowBuilder(start_executor=upper).add_edge(upper, output).build()

events = await workflow.run("hello world")
print(events.get_outputs())  # ["HELLO WORLD"]
```

### Executor types (vs spec "deterministic / agent / validator")

The spec's names map to MAF as follows:

| Spec term | MAF implementation |
|-----------|-------------------|
| deterministic | `FunctionExecutor` (wraps `@executor`-decorated function) OR `Executor` subclass |
| agent | `AgentExecutor` (wraps any `SupportsAgentRun` — Agent, GitHubCopilotAgent, etc.) |
| validator | Custom `Executor` subclass with validation logic in `@handler` |

### HITL in in-process Workflow (different from Durable)

For in-process workflows, HITL uses `ctx.request_info(event_payload)` and `@response_handler`:

```python
from agent_framework import Executor, WorkflowContext, handler, response_handler

class ReviewExecutor(Executor):
    @handler
    async def process(self, text: str, ctx: WorkflowContext) -> None:
        await ctx.request_info({"question": "Approve?", "content": text})

    @response_handler
    async def on_approved(self, request, response: str, ctx: WorkflowContext) -> None:
        await ctx.yield_output(f"{request['content']} (approved: {response})")
```

For Durable (Azure Functions / Durable Task) HITL, use `context.wait_for_external_event()` in the generator orchestration (see §3 above). The `agent-framework-azurefunctions` package's `run_workflow_orchestrator()` bridges both: it runs a MAF `Workflow` inside an Azure Durable Functions orchestrator and handles HITL via `wait_for_external_event`.

### Running a Workflow inside Azure Functions + Durable

```python
from agent_framework.azure import AgentFunctionApp  # wraps df.DFApp
from agent_framework import Workflow

app = AgentFunctionApp(agents=[my_agent])
app.add_workflow(my_workflow)   # registers orchestration + activity triggers

# OR: use run_workflow_orchestrator directly in a custom orchestration:
from agent_framework_azurefunctions._workflow import run_workflow_orchestrator

def my_orchestrator(context, input):
    yield from run_workflow_orchestrator(context, my_workflow, input)
```

**TO INVESTIGATE** for Phase 8 Workflow implementation:
- `agent_framework_azurefunctions._workflow.run_workflow_orchestrator` — full source read in this spike
- `agent_framework_azurefunctions._app.AgentFunctionApp` — top-level DFApp subclass
- Import path for `AgentFunctionApp`: `from agent_framework.azure import AgentFunctionApp`
- The `agent_framework.azure` namespace alias: check `agent_framework/azure/__init__.py`

---

## 5. Hosting Model

### MAF Durable Task — STANDALONE (no Azure Functions required)

The `agent-framework-durabletask` path uses the **Durable Task Scheduler** (a standalone gRPC service), not Azure Durable Functions. This is the simpler path.

**Infrastructure required:**
- Durable Task Scheduler process (Docker or Azure managed)
- Local: `docker run -d -p 8080:8080 mcr.microsoft.com/durabletask/scheduler:latest`
- Azure: Azure Durable Task Scheduler managed service (preview as of 2026-04)

**Registration pattern:**
```python
worker = DurableTaskSchedulerWorker(host_address=endpoint, taskhub=hub)
agent_worker = DurableAIAgentWorker(worker)
agent_worker.add_agent(my_agent)     # registers as durable entity "dafx-{name}"
worker.add_orchestrator(my_fn)       # registers orchestration generator
worker.add_activity(my_activity_fn)  # registers activity
worker.start()                       # blocks; run in thread or separate process
```

### MAF + Azure Functions — FUNCTIONS-REQUIRED path

`agent-framework-azurefunctions` uses Azure Durable Functions (azure-functions + azure-functions-durable) as the runtime. Agents are registered via `AgentFunctionApp` which extends `df.DFApp`.

**Infrastructure required:** Azure Functions Core Tools (`func start`) + Azurite (local storage emulator)

**Registration pattern:**
```python
from agent_framework.azure import AgentFunctionApp

app = AgentFunctionApp(agents=[weather_agent, math_agent])
# Registers entity triggers, orchestration triggers, HTTP endpoints automatically
```

**Recommendation for POC1:** Use the **Durable Task Scheduler** path (`agent-framework-durabletask`). It is simpler (no Functions toolchain), fully standalone, and the orchestration API is identical. Switch to `agent-framework-azurefunctions` only if Azure Functions are needed for HTTP triggers or timer triggers.

---

## 6. What Does NOT Work

| Issue | Detail |
|-------|--------|
| `PermissionHandler` import from `copilot.client` | `PermissionHandler` is in `copilot.session`, not `copilot.client`. The source code analysis showed it in `client.py`, but the installed 0.2.1 package has it in `session.py`. |
| `DurableWorkflow` / `@workflow_step` / `DurableContext` / `DurableRuntimeClient` | **None of these exist** in any installed package. They were hypothetical names in the spec skeleton. The real API is generator orchestrations + `DurableTaskSchedulerWorker`. |
| MAF durable E2E without Docker | `DurableTaskSchedulerWorker` requires the gRPC scheduler service running. Without Docker or the Azure managed endpoint, E2E is impossible locally. Import probe passes; full run is BLOCKED. |
| `github-copilot-sdk==0.2.2` | Only `0.2.1` is on PyPI. The npm package is at `0.2.2`. No functional difference found in source. |
| `define_tool` with raw JSON Schema dict | The Python `define_tool` decorator **requires a Pydantic BaseModel** as the first parameter type hint. Raw JSON Schema dicts (valid in the npm version) are not supported — the decorator calls `model_json_schema()` on the type. |
| `session.on(event_type_string, handler)` typed overload | Does NOT exist in Python SDK. Only `session.on(handler: Callable[[SessionEvent], None])`. Filter by `event.type` inside the handler. |
| `agent-framework-durable-functions==0.0.1` on PyPI | This package exists but is a placeholder with no content (`requires_dist: None`, homepage is `github.com/example/...`). Do not use it. |
| Windows console encoding | Spike files use ASCII-only output to avoid cp1252 encoding errors on Windows terminals with Unicode box-drawing chars. |

---

## 7. Updated `pyproject.toml` — Dependencies Section

```toml
[project]
name = "wpp-control-plane-py"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "httpx>=0.27",
  "sse-starlette>=2.1",
  "pyyaml>=6.0",
  "python-dotenv>=1.0",
  "nanoid>=2.0",
  # azure-functions 1.24+ required by agent-framework-azurefunctions
  "azure-functions>=1.24",
  "azure-functions-durable>=1.2",
  # Phase 0.2 spike resolved: github-copilot-sdk is the Python sibling of @github/copilot-sdk
  "github-copilot-sdk>=0.2.1",
  # Microsoft Agent Framework: meta-package pulls in agent-framework-core[all]
  "agent-framework>=1.0.1",
  # MAF GitHub Copilot integration (wraps copilot.CopilotClient as a MAF Agent)
  "agent-framework-github-copilot>=1.0.0b260409",
  # MAF Azure Durable Functions hosting + Durable Task integration
  "agent-framework-azurefunctions>=1.0.0b260409",
]
```

---

## Spike Outputs (Acceptance Criteria)

### Spike 1 — `copilot_sdk_spike.py`

```
=== GHCP SDK Python SPIKE (github-copilot-sdk==0.2.1) ===

[auth] Token obtained from 'gh auth token' (40 chars)
[client] type=CopilotClient
[client] Started (via async with). Connected to CLI subprocess.
[session] Created. sessionId=dc006732-daeb-4555-b298-683d5ad4ee2a

--- MESSAGE 1 ---
[R1] Hello, Alice! How can I assist you today?

--- MESSAGE 2 ---
[R2] You just told me your name is Alice.
[check] Session context retained (Alice in R2): YES OK

--- MESSAGE 3 - tool call ---
[EVENT] tool.execution_start
        toolName  : ping_tool
        toolCallId: call_ZbiYNy9sMZ86FYNys8p8cyhV
        arguments : {'msg': 'hello'}

[TOOL HANDLER CALLED]
  tool      : ping_tool
  toolCallId: call_ZbiYNy9sMZ86FYNys8p8cyhV
  args      : msg='hello'

[EVENT] tool.execution_complete
        toolCallId: call_ZbiYNy9sMZ86FYNys8p8cyhV
        success   : True
        result    : {"echoed": "hello"}

[R3] Ping tool called with msg='hello'. The response was: hello.

[session] Disconnected.
[ACCEPTANCE] ALL PASS
```

| Criterion | Result |
|-----------|--------|
| R1 greets Alice | PASS |
| R2 retains Alice (context) | PASS |
| R3 contains "hello" via tool | PASS |
| tool.execution_start event | PASS |
| tool.execution_complete event | PASS |

### Spike 2 — `maf_durable_spike.py`

```
=== MAF Durable SPIKE - API Surface Probe ===

[import] DurableAIAgentWorker      : agent_framework_durabletask._worker.DurableAIAgentWorker
[import] DurableAIAgentOrchestrationContext: agent_framework_durabletask._orchestration_context
[import] DurableTaskSchedulerClient: durabletask.azuremanaged.client.DurableTaskSchedulerClient
[import] DurableTaskSchedulerWorker: durabletask.azuremanaged.worker.DurableTaskSchedulerWorker
[probe]  hello_workflow_orchestration is generator: True
[import] when_any / OrchestrationContext: OK

[probe] All imports OK.

[BLOCKED] Scheduler not reachable at http://localhost:8080.
  API surface probe completed successfully (imports OK).
  Full E2E requires the Durable Task Scheduler Docker container.

[ACCEPTANCE] PARTIAL - imports verified; E2E requires scheduler.
```

| Criterion | Result |
|-----------|--------|
| All imports resolve | PASS |
| Orchestration function is a generator | PASS |
| Worker/client API verified | PASS |
| wait_for_external_event pattern coded | PASS |
| E2E: workflow starts, suspends, resumes | BLOCKED (needs Docker) |

---

## Key Concerns for Downstream Phases

### Concern 1 — CRITICAL: Spec skeleton needs full rewrite (Phase 9)

The `maf_durable_spike.py` spec skeleton (`DurableWorkflow`, `@workflow_step`, `DurableRuntimeClient`) maps to nothing in the installed packages. Phase 9 Durable Workflow code must use:
- Generator functions (not classes) for orchestrations
- `context.wait_for_external_event(name)` inside the generator for HITL
- `DurableTaskSchedulerWorker` + `DurableAIAgentWorker` for worker hosting
- `DurableTaskSchedulerClient.schedule_new_orchestration()` / `.raise_orchestration_event()` / `.get_orchestration_state()` for client operations

### Concern 2 — Infrastructure: Docker or Azure managed scheduler required

Local development requires either:
- Docker: `docker run -d -p 8080:8080 mcr.microsoft.com/durabletask/scheduler:latest`
- Azure Durable Task Scheduler managed service (in preview)

This adds a Docker dependency to developer onboarding. No `docker-compose.yml` service exists yet for the scheduler in this project (Azurite is defined, but not the DTS scheduler).

### Concern 3 — github-copilot-sdk version mismatch (minor)

npm is at `@github/copilot-sdk@0.2.2`; Python is at `github-copilot-sdk==0.2.1`. Both are from the same repo. No breaking API differences found. Monitor for `0.2.2` Python release.

### Concern 4 — define_tool Pydantic-only (Phase 5 FleetManager tools)

Phase 5 FleetManagerService tool definitions must use Pydantic `BaseModel` subclasses for parameter schemas. Raw dicts or JSON Schema objects are not accepted by the Python `define_tool` decorator. Existing TypedDict or dataclass param definitions in the JS service code will need Pydantic equivalents.

### Concern 5 — session.on() flat handler (no typed overloads)

The npm SDK's `session.on("tool.execution_start", handler)` typed overload does not exist in Python. All event types go to a single handler. For the right-rail UI fan-out, the Python server must multiplex internally. This is workable but changes the ergonomics.

### Concern 6 — agent-framework version is a beta pre-release

`agent-framework-github-copilot==1.0.0b260409` and related packages use a date-based beta versioning scheme (`b260409` = April 9, 2026). These are actively-developed pre-releases. Pin to exact versions in production.
