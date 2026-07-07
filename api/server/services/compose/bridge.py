"""ComposeBridge: drive one `copilot --acp` run and stream normalized events.

Phase 1 uses a simplified prompt and no MCP tools; the real add-domain prompt,
the compose-bridge MCP, document intake, and the safety guard land in Phase 2.
The `copilot_cmd` seam lets tests inject a fake ACP agent.
"""
from __future__ import annotations

import asyncio
import os

from .acp_client import AcpClient
from .session import ComposeSession
from .translate import translate_update

REPO_ROOT = os.getenv("ZAVA_REPO_ROOT", os.getcwd())


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
        self.repo_root = repo_root or REPO_ROOT
        self._copilot_cmd = copilot_cmd or _default_copilot_cmd()
        self.client = AcpClient(self._on_notify, self._on_request)
        self._acp_session_id: str | None = None

    async def start(self) -> None:
        cmd = [*self._copilot_cmd, "--acp", "-C", self.repo_root,
               "--allow-all", "--log-level", "none"]
        await self.client.start(cmd, cwd=self.repo_root)
        await self.client.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
        })
        res = await self.client.request(
            "session/new", {"cwd": self.repo_root, "mcpServers": []})
        self._acp_session_id = res.get("sessionId")
        self.session.emit({"type": "stage", "stage": "understanding",
                           "label": "Reading the document"})
        asyncio.create_task(self._run_prompt())

    async def _run_prompt(self) -> None:
        try:
            await self.client.request("session/prompt", {
                "sessionId": self._acp_session_id,
                "prompt": [{"type": "text", "text": self._build_prompt()}],
            })
        except Exception as ex:  # surface, never stall silently
            self.session.emit({"type": "error", "message": str(ex), "fatal": True})
        finally:
            self.session.done = True
            self.session.emit({"type": "stage", "stage": "ready", "label": "Run complete"})
            await self.client.stop()

    def _build_prompt(self) -> str:
        return (
            "Compose a new Zava domain from the following process document by "
            "running the add-domain skill. Ask clarifying questions only if the "
            "document is genuinely ambiguous; always present the drafted brief "
            "before composing.\n\n---\n" + self.document_text + "\n---"
        )

    async def _on_notify(self, method: str, params: dict) -> None:
        if method == "session/update":
            for event in translate_update(params):
                self.session.emit(event)

    async def _on_request(self, method: str, params: dict) -> dict:
        # Phase 1 runs with --allow-all so permission requests should not fire;
        # auto-approve defensively if they do.
        if method == "session/request_permission":
            opts = params.get("options") or []
            allow = next(
                (o for o in opts if str(o.get("kind", "")).startswith("allow")),
                opts[0] if opts else {"optionId": "allow"},
            )
            return {"outcome": {"outcome": "selected", "optionId": allow.get("optionId")}}
        return {}
