"""Mount the built blueprint Vite bundle on FastAPI.

Production deployment serves the page from FastAPI directly so a single
container handles both the API and the static bundle. Dev mode (Vite on
:5175 proxying to FastAPI on :3001) is unaffected — the dist directory
won't exist locally, and ``mount_blueprint_static()`` is a no-op when
absent.

Mount layout:

    /                     → index.html        (SPA shell)
    /assets/...           → hashed JS/CSS    (Vite output)
    /gutenberg.png        → Gutenberg image  (web/blueprint/public/)
    /vite.svg, etc.       → other public/    files

The catchall at /<anything>  serves index.html so SPA-style deep links
work (this app currently only has one route, but the pattern is correct
for the future).

API routes (anything under /api/...) are registered before this static
mount, so they take precedence and the static catchall never shadows them.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

# api/server/static_blueprint.py  →  parents[2] = repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "web" / "blueprint" / "dist"


def mount_blueprint_static(app: FastAPI) -> bool:
    """Mount the built blueprint bundle if present.

    Returns True when mounted, False when the dist directory is absent
    (typical dev case — Vite is serving the page on :5175 and proxying
    /api back to FastAPI).
    """
    if not DIST_DIR.is_dir():
        return False

    index_html = DIST_DIR / "index.html"
    if not index_html.is_file():
        return False

    # Mount the assets folder explicitly so cache headers etc. are honoured
    # by Starlette's StaticFiles handler. The other entries in dist/ (e.g.
    # vite.svg, gutenberg.png) are served by the catchall below.
    assets_dir = DIST_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="blueprint-assets")

    @app.get("/", include_in_schema=False)
    async def blueprint_root() -> FileResponse:
        return FileResponse(index_html, media_type="text/html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def blueprint_catchall(full_path: str) -> Response:
        # API and internal routes were registered first; FastAPI matches
        # them before this catchall. We only get here for static assets
        # inside dist/ or for SPA deep links.
        if full_path.startswith(("api/", "internal/")):
            # Defensive: should never trigger because API routers were
            # mounted first, but if a request leaks here we 404 it
            # rather than serving index.html (which would be very
            # confusing in the browser dev tools).
            return Response(status_code=404)

        # Try to serve the file from dist/ verbatim. This covers
        # public/* assets (e.g. gutenberg.png) that Vite copies into
        # the dist root at build time.
        candidate = DIST_DIR / full_path
        if candidate.is_file() and candidate.resolve().is_relative_to(DIST_DIR.resolve()):
            return FileResponse(candidate)

        # SPA deep link — return the shell, the client-side router takes over.
        return FileResponse(index_html, media_type="text/html")

    return True
