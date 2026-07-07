"""ComposeBridge: drive one `copilot --acp` run and stream normalized events.

Spawns the agent, runs the ACP handshake with the compose-bridge MCP attached,
sends the composition prompt, and folds `session/update` notifications into the
session's normalized event stream. The `copilot_cmd` seam lets tests inject a
fake ACP agent.
"""
from __future__ import annotations

import asyncio
import os

from api.shared import compose_config

from .acp_client import AcpClient
from .session import ComposeSession
from . import tape as compose_tape
from .translate import translate_update

COMPOSE_MCP_URL = os.getenv(
    # FastMCP's streamable-HTTP app serves the MCP endpoint at `/mcp` inside the
    # sub-app mounted at /api/compose/mcp, so the agent must target /mcp/mcp.
    "COMPOSE_MCP_URL", "http://127.0.0.1:3101/api/compose/mcp/mcp")
COMPOSE_MODEL = os.getenv("COMPOSE_MODEL", "claude-sonnet-4.6")


def _default_copilot_cmd() -> list[str]:
    return [os.getenv("COMPOSE_COPILOT_BIN", "copilot")]


class ComposeBridge:
    def __init__(
        self,
        session: ComposeSession,
        document_text: str,
        copilot_cmd: list[str] | None = None,
        repo_root: str | None = None,
    ) -> None:
        self.session = session
        self.document_text = document_text
        self.repo_root = repo_root or str(compose_config.repo_root())
        self._copilot_cmd = copilot_cmd or _default_copilot_cmd()
        self.client = AcpClient(self._on_notify, self._on_request)
        self._acp_session_id: str | None = None
        self._prompt_task: asyncio.Task | None = None

    async def start(self) -> None:
        cmd = [*self._copilot_cmd, "--acp", "-C", self.repo_root,
               "--allow-all", "--log-level", "none"]
        await self.client.start(cmd, cwd=self.repo_root)
        await self.client.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
        })
        res = await self.client.request("session/new", {
            "cwd": self.repo_root,
            "mcpServers": [{
                "name": "compose-bridge",
                "type": "http",
                "url": COMPOSE_MCP_URL,
                "headers": [],
            }],
        })
        self._acp_session_id = res.get("sessionId")
        self.session.emit({"type": "stage", "stage": "understanding",
                           "label": "Reading the document"})
        self._prompt_task = asyncio.create_task(self._run_prompt())

    async def _run_prompt(self) -> None:
        try:
            await self.client.request("session/prompt", {
                "sessionId": self._acp_session_id,
                "prompt": [{"type": "text", "text": self._build_prompt()}],
            })
        except Exception as ex:  # surface, never stall silently
            self.session.emit({"type": "error", "message": str(ex), "fatal": True})
        finally:
            self.session.finish()
            if os.getenv("COMPOSE_RECORD", "1") == "1":
                wt = next((e.get("workflow_type") for e in reversed(self.session.events)
                           if e.get("type") == "done"), "compose")
                try:
                    compose_tape.save_tape(self.session, wt)
                except Exception as ex:
                    print(f"[compose] tape save failed: {ex}")
            await self.client.stop()

    def _build_prompt(self) -> str:
        return (
            "Use the `compose-domain-live` skill to compose a new Zava domain "
            "from the process document below. Route ALL progress through the "
            "compose-bridge MCP tools: call `report_stage` at each phase, "
            "`ask_operator` only when the document is genuinely ambiguous, "
            "always `present_brief` before composing, and `composition_complete` "
            "after graduate.sh + verification pass.\n\n"
            "--- DOCUMENT ---\n" + self.document_text + "\n--- END DOCUMENT ---"
        )

    async def _on_notify(self, method: str, params: dict) -> None:
        if method == "session/update":
            for event in translate_update(params):
                self.session.emit(event)

    async def _on_request(self, method: str, params: dict) -> dict:
        # --allow-all means permission requests should not fire; auto-approve
        # defensively if they do.
        if method == "session/request_permission":
            opts = params.get("options") or []
            allow = next(
                (o for o in opts if str(o.get("kind", "")).startswith("allow")),
                opts[0] if opts else {"optionId": "allow"},
            )
            return {"outcome": {"outcome": "selected", "optionId": allow.get("optionId")}}
        return {}
