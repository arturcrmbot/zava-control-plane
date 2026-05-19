# LLMRuntime providers

`api/functions/graphs/executors/agents/runtime.py` defines a
provider-neutral Protocol (`LLMRuntime`) that
`_wrapper.py:run_agent_session` consumes via `_get_runtime()`. The
intent of the seam is to let us swap in additional providers
(Anthropic, Azure OpenAI, …) without touching the orchestrators or the
segments.

In practice the Protocol still leaks a few shapes from its first
implementation (`runtime_ghcp.GHCPRuntime`, the GitHub Copilot Python
SDK). This file documents those leaks so a future runtime author can
either match them or extend the Protocol explicitly rather than
guessing.

We are 100% GHCP today. None of the items below are bugs to fix; they
are contracts to honour.

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

The signature is `Callable | None` rather than a Protocol because the
GHCP `PermissionHandler` is a class with two methods (`pre_tool_use`,
`post_tool_use`). A future neutralisation pass would type this as a
small Protocol; for now, runtime authors should accept the GHCP class
shape and only construct shims when they cannot pass it through.

## Adding a new provider

1. Create `api/functions/graphs/executors/agents/runtime_<name>.py`
   implementing the `LLMRuntime` Protocol.
2. Add a branch in `runtime.py:_get_runtime()` matching
   `LLM_RUNTIME=<name>`.
3. Honour the three contracts above (or document the deviation in
   this file).
4. Add a smoke test in `tests/api/functions/agents/` that drives the
   new runtime through `_wrapper.py:run_agent_session` with
   `permission_handler=None` and asserts a non-empty `text` field.
