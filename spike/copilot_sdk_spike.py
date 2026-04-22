"""
Discover Python github-copilot-sdk (package: github-copilot-sdk==0.2.1) API surface.

Python equivalent of the npm @github/copilot-sdk@0.2.2.

Key differences from the npm version:
- Package name on PyPI: `github-copilot-sdk` (NOT `copilot-sdk`)
- Import module: `copilot` (same root as npm)
- `define_tool` uses Pydantic BaseModel for params, NOT Zod schemas
- `send_and_wait` returns `SessionEvent | None`, not a string
- `session.on()` takes `Callable[[SessionEvent], None]`, not (event_type, handler)
- `PermissionHandler.approve_all` is a staticmethod, not a const
- Constructor takes `SubprocessConfig(github_token=...)` or uses auto_start with gh credentials
"""

import asyncio
import subprocess

from copilot import CopilotClient
from copilot.client import SubprocessConfig
from copilot.generated.session_events import SessionEvent, SessionEventType
from copilot.session import PermissionHandler  # PermissionHandler is in session, NOT client
from copilot.tools import ToolInvocation, ToolResult, define_tool
from pydantic import BaseModel, Field


def gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


# ── Tool parameter schema via Pydantic (not Zod / raw JSON Schema) ──────────
class PingParams(BaseModel):
    msg: str = Field(description="The message to echo back")


# ── Tool definition ──────────────────────────────────────────────────────────
# @define_tool decorator infers name from function, params from first arg type hint.
@define_tool(description="Echoes a message back", skip_permission=True)
def ping_tool(params: PingParams, invocation: ToolInvocation) -> ToolResult:
    print(
        f"\n[TOOL HANDLER CALLED]"
        f"\n  tool      : {invocation.tool_name}"
        f"\n  toolCallId: {invocation.tool_call_id}"
        f"\n  args      : msg={params.msg!r}"
    )
    return ToolResult(text_result_for_llm=f'{{"echoed": "{params.msg}"}}', result_type="success")


async def main() -> None:
    print("=== GHCP SDK Python SPIKE (github-copilot-sdk==0.2.1) ===\n")

    token = gh_token()
    print(f"[auth] Token obtained from 'gh auth token' ({len(token)} chars)")

    # ── Client construction ──────────────────────────────────────────────────
    # SubprocessConfig wraps CLI subprocess options; github_token passes gh PAT.
    config = SubprocessConfig(github_token=token, log_level="warning")
    client = CopilotClient(config)
    print(f"[client] type={type(client).__name__}")

    # CopilotClient supports async context manager (auto start/stop)
    async with client:
        print("[client] Started (via async with). Connected to CLI subprocess.\n")

        # ── Session creation ─────────────────────────────────────────────────
        # on_permission_request is REQUIRED. Use PermissionHandler.approve_all
        # to silently approve all tool calls (appropriate for automated spikes).
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            tools=[ping_tool],
            system_message={
                "mode": "append",
                "content": "When asked, call the ping tool. Otherwise be brief.",
            },
        )
        print(f"[session] Created. sessionId={session.session_id}\n")

        # ── Event subscription ───────────────────────────────────────────────
        # session.on() takes a single callable[[SessionEvent], None].
        # There is NO typed overload by event type string (unlike the npm SDK).
        # Filter by event.type inside the handler.
        events: list[tuple[str, SessionEvent]] = []

        def handle_event(event: SessionEvent) -> None:
            if event.type == SessionEventType.TOOL_EXECUTION_START:
                events.append(("start", event))
                print(f"\n[EVENT] tool.execution_start")
                print(f"        toolName  : {event.data.tool_name}")
                print(f"        toolCallId: {event.data.tool_call_id}")
                print(f"        arguments : {event.data.arguments}")
            elif event.type == SessionEventType.TOOL_EXECUTION_COMPLETE:
                events.append(("complete", event))
                print(f"\n[EVENT] tool.execution_complete")
                print(f"        toolCallId: {event.data.tool_call_id}")
                print(f"        success   : {event.data.success}")
                if event.data.result:
                    print(f"        result    : {event.data.result.content}")

        # Subscribe BEFORE sending messages so events are captured
        _unsub = session.on(handle_event)

        # ── MESSAGE 1: Context seeding ───────────────────────────────────────
        print("--- MESSAGE 1 ---")
        r1 = await session.send_and_wait("Say hello to Alice.", timeout=60.0)
        # send_and_wait returns SessionEvent | None (the final assistant.message event)
        content_r1 = r1.data.content if r1 and r1.data else "(no content)"
        print(f"[R1] {content_r1}\n")

        # ── MESSAGE 2: Context retention check ──────────────────────────────
        print("--- MESSAGE 2 ---")
        r2 = await session.send_and_wait("What's the name I just told you?", timeout=60.0)
        content_r2 = r2.data.content if r2 and r2.data else "(no content)"
        print(f"[R2] {content_r2}")
        alice_retained = r2 is not None and "alice" in str(content_r2).lower()
        print(f"[check] Session context retained (Alice in R2): {'YES' if alice_retained else 'NO'} {'OK' if alice_retained else 'FAIL'}\n")

        # ── MESSAGE 3: Tool invocation ───────────────────────────────────────
        print("--- MESSAGE 3 - tool call ---")
        r3 = await session.send_and_wait("Call the ping tool with msg='hello'.", timeout=60.0)
        content_r3 = r3.data.content if r3 and r3.data else "(no content)"
        print(f"\n[R3] {content_r3}\n")

        # ── Session cleanup ──────────────────────────────────────────────────
        await session.disconnect()
        print("[session] Disconnected.\n")

    # ── Summary ─────────────────────────────────────────────────────────────
    print("=== SPIKE SUMMARY ===")
    print(f"Session ID           : {session.session_id}")
    print(f"Context retained (R2): {'YES' if alice_retained else 'NO'}")
    print(f"Tool events observed : {len(events)}")

    start_seen = any(k == "start" for k, _ in events)
    complete_seen = any(k == "complete" for k, _ in events)
    print(f"tool.execution_start seen  : {'YES OK' if start_seen else 'NO FAIL'}")
    print(f"tool.execution_complete seen: {'YES OK' if complete_seen else 'NO FAIL'}")

    all_pass = alice_retained and start_seen and complete_seen
    print(f"\n[ACCEPTANCE] {'ALL PASS' if all_pass else 'SOME CHECKS FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
