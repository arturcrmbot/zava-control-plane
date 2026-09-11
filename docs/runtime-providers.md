# LLMRuntime providers

`api/functions/graphs/executors/agents/runtime.py` defines a
provider-neutral Protocol (`LLMRuntime`) that
`_wrapper.py:run_agent_session` consumes via `_get_runtime()`. The
intent of the seam is to select providers without touching the orchestrators or
segments. `LLM_RUNTIME=ghcp` selects GitHub Copilot; `LLM_RUNTIME=aoai` selects
Azure OpenAI. `fake` is a canned test double, not evidence of live tool execution.

In practice the Protocol still leaks a few shapes from its first
implementation (`runtime_ghcp.GHCPRuntime`, the GitHub Copilot Python
SDK). This file documents those leaks so a future runtime author can
either match them or extend the Protocol explicitly rather than
guessing.

Both real providers must honour the contracts below.

## Fleet Manager provider selection

Fleet Manager and its function-scoped instances respect `LLM_RUNTIME`.
GitHub keeps its persistent Copilot session and uses `FLEET_MANAGER_MODEL`
unless the caller supplies an explicit model. Azure uses the existing
`LLMRuntime.run_session()` tool loop per batch without GitHub authentication
or a Copilot subprocess. Each Azure batch receives the supervisor instructions,
current triggering events and registered state-query/action tools; it does not
inherit GitHub's persistent conversation history.

`AZURE_OPENAI_FLEET_MANAGER_DEPLOYMENT` optionally selects a separate Azure
deployment. When empty, the supervisor uses `AZURE_OPENAI_DEPLOYMENT`, just
like workflow agents. This does not change other agents' default deployment.
Both settings are passed through the deployment template. `fake` remains a
canned, no-subprocess test mode, not evidence of live tool execution.

Startup failures are surfaced, provider tool-result payloads remain visible,
and stopping a manager cancels queued/in-progress batches before disconnecting
its session. Function-manager construction shares this implementation; the
separate `query_function_fm` delegation stub is not made executable by selecting
a provider.

## 1. `LLMRuntimeResult.raw_event` is provider-specific

```python
class LLMRuntimeResult(BaseModel):
    ...
    raw_event: Any = None
```

GHCP populates `raw_event` with the final `copilot.SessionEventType.*`
event so callers that need provider-native introspection can dig in
without re-running the session. **No callers downstream of
`run_agent_session` should consume `raw_event` across the seam.** Treat
it as a debugging/telemetry sidecar.

A new runtime is free to leave `raw_event=None`. If you need a
neutral, cross-provider event shape, add a new typed field rather than
overloading `raw_event`.

## 2. `event_subscriber` callbacks receive GHCP-shaped events

```python
event_subscriber: Callable[[Any], None] | None = None,
```

`_wrapper.py:_make_session_otel_bridge` returns a callable that
expects `copilot.SessionEventType.TOOL_EXECUTION_START` /
`TOOL_EXECUTION_COMPLETE` events (and similar). The bridge:

- emits OTEL spans for each tool call, and
- appends entries to `tool_calls_collected` which becomes
  `_raw_tool_calls` on the returned dict (consumed by
  `api/functions/segments/hiring_f.py:_tool_call_summary` for the
  Segment F reversibility check).

If you add a non-GHCP runtime and want tool-event telemetry, you have
two options:

1. **Translate at the runtime boundary.** Convert your provider's
   tool-event objects into instances that quack like the GHCP events
   the bridge expects (`.tool_name`, `.tool_call_id`, etc.). Cheapest.
2. **Extend the Protocol.** Introduce a neutral
   `ToolExecutionEvent` model in `runtime.py`, update
   `_make_session_otel_bridge` to dispatch on it, and translate from
   GHCP inside `runtime_ghcp.py`. Cleaner long-term but touches every
   call site that reads `_raw_tool_calls`.

`LLMRuntimeResult.tool_calls` exists on the model but is **always
empty** on the GHCP path — tool calls flow through `event_subscriber`,
not through the return value. A new runtime may populate
`tool_calls` directly **as well as** firing `event_subscriber`; just
do not assume the consumer reads both.

## 3. `permission_handler=None` means "approve every tool call"

```python
permission_handler: Callable | None = None,
```

`_wrapper.py:run_agent_session` builds a real `AGTPermissionHandler`
when `AGT_ENFORCE=1` (see `api/server/services/governance/permission_handler.py`)
and passes it in. Otherwise it forwards `permission_handler=None`,
which `GHCPRuntime` interprets as
`copilot.PermissionHandler.approve_all` — i.e. unconditional approval
for every tool call the model attempts.

This default is intentional for dev and CI ergonomics. **A new
provider implementation must preserve "None = approve all"** so the
AGT-off path keeps working. If your SDK has a different default
(e.g. "deny all unless allowlisted"), wrap it: when
`permission_handler is None`, install an "approve all" shim before
opening the session.

The handler is called with the SDK's `(request, invocation)` arguments and
returns a permission result. A provider that cannot pass those objects through
must adapt them at its boundary.

## 4. Required tools must actually succeed

`required_tool_names` names tools explicitly registered on the session. Both
real providers reject unknown names before starting a session or model call.
A final answer is accepted only after every required tool has a successful
execution; mentioning a tool in the answer is not sufficient. Denied, rejected,
failed, timed-out, or unknown results do not satisfy this requirement.

AOAI forces outstanding required tools through its tool loop. GHCP tracks SDK
tool-start/completion events while preserving the caller's event subscriber.
Missing registration raises `ValueError`; missing successful execution raises
`RuntimeError`. Neither guarantee proves that a business outcome was achieved
or that a write is safe to retry.

## Adding a new provider

1. Create `api/functions/graphs/executors/agents/runtime_<name>.py`
   implementing the `LLMRuntime` Protocol.
2. Add a branch in `runtime.py:_get_runtime()` matching
   `LLM_RUNTIME=<name>`.
3. Honour the four contracts above (or document the deviation in
   this file).
4. Add a smoke test in `tests/api/functions/agents/` that drives the
   new runtime through `_wrapper.py:run_agent_session` with
   `permission_handler=None` and asserts a non-empty `text` field.
