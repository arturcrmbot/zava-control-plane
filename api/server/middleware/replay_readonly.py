from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.server.services.replay.mode import is_replay

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_BLOCKED_RESPONSE = {
    "error": "replay",
    "message": "This is a replay — actions are observed, not made.",
}


class ReplayReadOnlyMiddleware(BaseHTTPMiddleware):
    """Reject non-read methods when the process is in replay mode."""

    async def dispatch(self, request: Request, call_next):
        if is_replay() and request.method.upper() in _WRITE_METHODS:
            return JSONResponse(status_code=403, content=_BLOCKED_RESPONSE)
        return await call_next(request)
