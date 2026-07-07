"""Async JSON-RPC 2.0 client over a subprocess' stdio (newline-delimited).

Verified against `copilot --acp` (protocolVersion 1): messages are single-line
JSON separated by '\\n'. Correlates request ids to responses; forwards
notifications and server->client requests to caller-supplied async callbacks.
"""
from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable

NotifyCB = Callable[[str, dict], Awaitable[None]]
RequestCB = Callable[[str, dict], Awaitable[dict]]


class AcpClient:
    def __init__(self, on_notify: NotifyCB, on_request: RequestCB) -> None:
        self._on_notify = on_notify
        self._on_request = on_request
        self._proc: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0

    def _fail_pending(self, exc: BaseException) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    async def start(self, cmd: list[str], cwd: str) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            while True:
                raw = await self._proc.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", "ignore").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                await self._dispatch(msg)
        finally:
            self._fail_pending(ConnectionError("ACP transport closed"))

    async def _dispatch(self, msg: dict) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            fut = self._pending.pop(msg["id"], None)
            if fut and not fut.done():
                fut.set_result(msg)
        elif msg.get("method") and "id" in msg:
            result = await self._on_request(msg["method"], msg.get("params") or {})
            await self._write({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        elif msg.get("method"):
            await self._on_notify(msg["method"], msg.get("params") or {})

    async def _write(self, obj: dict) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def request(self, method: str, params: dict) -> dict:
        self._next_id += 1
        rid = self._next_id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        resp = await fut
        if "error" in resp:
            raise RuntimeError(f"ACP error for {method}: {resp['error']}")
        return resp.get("result") or {}

    async def notify(self, method: str, params: dict) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
            except ProcessLookupError:
                pass
        if self._proc and self._proc.stdin and not self._proc.stdin.is_closing():
            self._proc.stdin.close()
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        self._fail_pending(ConnectionError("ACP client stopped"))
