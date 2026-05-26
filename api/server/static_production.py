"""Mount the three built SPA bundles for the production (containerised)
deploy of the Zava control plane.

Dev mode is unaffected — this module is a no-op unless ``ZAVA_STATIC_BUNDLE_DIR``
points at an existing directory containing ``client/``, ``portal/`` and
``blueprint/`` subfolders. In local dev, Vite serves each SPA on its own
port (5273/5274/5275) and proxies ``/api`` back to FastAPI on :3101.

### Why this exists (vs ``app.mount("/", StaticFiles(html=True))``)

A bare ``StaticFiles(directory=..., html=True)`` mount at ``/`` returns
``index.html`` for **any** unmatched path — including ``/api/typo``,
``/healthz``, ``/api/this/does/not/exist``. That makes:

* ACA liveness probes pass against a broken API (HTML 200 instead of failure)
* Frontend code see 200 + HTML when it expects 404 + JSON, often surfacing
  as a baffling "Unexpected token < in JSON" instead of an obvious 404

So this module explicitly:

1. Mounts the ``/portal`` and ``/blueprint`` bundles (their own
   ``/`` is a prefixed root, so SPA deep links work)
2. Adds an **API catch-all** at ``/api/{rest:path}`` that returns a real
   404 JSON for any ``/api/...`` request that didn't match a registered
   FastAPI route — guaranteeing the root SPA mount **cannot** swallow API
   misroutes.
3. Mounts the root operator-UI bundle LAST so it only serves real static
   files and SPA shell HTML.

The same pattern is already used by ``static_blueprint.py`` for the
single-bundle "blueprint microsite" deploy. This module is its multi-SPA
sibling for the full Zava control plane container.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles


def _bundle_root() -> Path | None:
    env = os.environ.get("ZAVA_STATIC_BUNDLE_DIR")
    if not env:
        return None
    p = Path(env)
    return p if p.is_dir() else None


def mount_production_static(app: FastAPI) -> bool:
    """Mount the 3 SPA bundles for production deploys.

    Returns True when at least the operator client bundle is found and
    mounted, False when ``ZAVA_STATIC_BUNDLE_DIR`` is unset / empty
    (typical dev case).
    """
    root = _bundle_root()
    if root is None:
        return False

    client_dir = root / "client"
    portal_dir = root / "portal"
    blueprint_dir = root / "blueprint"

    if not (client_dir / "index.html").is_file():
        # Nothing useful to serve — keep behaviour identical to dev.
        return False

    # ── 1. Prefixed SPA mounts (order before the root mount matters) ──
    if (portal_dir / "index.html").is_file():
        app.mount(
            "/portal",
            StaticFiles(directory=str(portal_dir), html=True),
            name="zava-portal-bundle",
        )

    if (blueprint_dir / "index.html").is_file():
        app.mount(
            "/blueprint",
            StaticFiles(directory=str(blueprint_dir), html=True),
            name="zava-blueprint-bundle",
        )

    # ── 2. API catch-all — MUST be registered before the root SPA mount
    #       OR before any explicit `/{full_path}` SPA shell route. FastAPI
    #       matches routes in registration order, so this gives /api/*
    #       priority over the bare StaticFiles "/" mount below.
    @app.api_route(
        "/api/{rest_of_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def _api_not_found(rest_of_path: str) -> JSONResponse:
        # Real FastAPI API routes were all registered before this module
        # is imported (see api/server/main.py). If we end up here it means
        # the request didn't match any real handler. Return a real JSON
        # 404 instead of letting the root SPA mount silently serve
        # index.html (which causes the classic "Unexpected token < in
        # JSON at position 0" on the client).
        raise HTTPException(
            status_code=404,
            detail=f"API route /api/{rest_of_path} not found",
        )

    # ── 3. Root operator UI — explicit assets mount + route-based fallback.
    #
    #  We deliberately DON'T use `app.mount("/", StaticFiles(html=True))`
    #  here. That pattern returns 404 for any path that doesn't resolve
    #  to a literal file (SPA deep links break) AND it would shadow the
    #  `/{spa_path:path}` fallback below since mounts win over routes.
    #
    #  Instead: mount only `/assets/` for Vite's hashed bundle (so cache
    #  headers are honoured), and use an explicit route to serve the
    #  shell — which lets us implement true SPA-style fallback.
    assets_dir = client_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="zava-client-assets",
        )

    client_index = client_dir / "index.html"

    @app.get("/", include_in_schema=False)
    async def _client_root() -> FileResponse:
        return FileResponse(client_index, media_type="text/html")

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def _spa_fallback(spa_path: str) -> Response:
        # Defensive: never serve the operator shell for an API path.
        # (The /api/* catch-all above should always win, but belt + braces.)
        if spa_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        # Try to serve the literal file from the client bundle if it
        # exists — covers public/ assets Vite copies to the dist root
        # (favicons, manifests, vite.svg etc.).
        candidate = client_dir / spa_path
        if candidate.is_file() and candidate.resolve().is_relative_to(
            client_dir.resolve()
        ):
            return FileResponse(candidate)
        # SPA deep link — return the shell, the client-side router takes over.
        return FileResponse(client_index, media_type="text/html")

    return True
