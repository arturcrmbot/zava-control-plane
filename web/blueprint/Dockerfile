# Blueprint microsite — single-container deploy.
#
# Two-stage build:
#   1. Node stage: install deps + run `vite build` for web/blueprint/.
#   2. Python stage: install runtime deps via uv, copy api/ + the
#      built bundle from stage 1, run uvicorn on $PORT (default 80).
#
# What this image contains:
#   - The FastAPI control plane (api/server/) with the blueprint route
#     and the always-on demo trickle.
#   - The composition tree built from api/server/skills/ and
#     api/server/mcp_tools/ at request time.
#   - Any captured event recordings under data/blueprint-recordings/.
#   - The built React bundle, served from / by FastAPI.
#
# What it does NOT contain:
#   - The Functions host (no real workflows in the deployed env;
#     events are replayed from recordings or the synthetic fallback).
#   - Azurite (not needed; no Durable state).
#   - The candidate portal (web/portal/) or admin client (web/client/).
#   - Synthetic data fixtures, tests, dev scripts.
# These are excluded via .dockerignore.

# --------------------------------------------------------------------------
# Stage 1 — build the Vite bundle
# --------------------------------------------------------------------------
FROM node:20-alpine AS bundle

WORKDIR /build

# Install deps first (better Docker cache hit when only source changes).
COPY web/blueprint/package.json web/blueprint/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy sources and build.
COPY web/blueprint/index.html ./
COPY web/blueprint/tsconfig.json ./
COPY web/blueprint/vite.config.ts ./
COPY web/blueprint/src/ ./src/
COPY web/blueprint/public/ ./public/

RUN npm run build

# --------------------------------------------------------------------------
# Stage 2 — Python runtime
# --------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Tell uvicorn-style libraries we have no terminal; cleaner logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

# Minimal runtime libs. weasyprint (used by hiring-offer PDF) needs cairo +
# pango + libffi; we keep them out because no offer-letter rendering happens
# in the blueprint deploy. If you ever boot the full stack here, add them.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv is the fastest way to install pinned deps from the lockfile.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# --- Python deps ---------------------------------------------------------
# Copy only the lockfile + project metadata first so the pip resolve cache
# survives source changes.
COPY pyproject.toml uv.lock ./
# Install only the runtime extras the blueprint route actually needs.
# We deliberately skip the full project install (uv sync) because that would
# pull in azure-functions / agent-framework / sentence-transformers / etc.
# — heavy and unused by the blueprint deploy.
RUN uv pip install --system --no-cache \
        "fastapi>=0.115" \
        "uvicorn[standard]>=0.32" \
        "pydantic>=2.9" \
        "httpx>=0.27" \
        "sse-starlette>=2.1" \
        "pyyaml>=6.0" \
        "python-dotenv>=1.0" \
        "nanoid>=2.0" \
        "azure-identity>=1.25.3" \
        "azure-storage-blob>=12.20"
# (azure-* are pulled by api/server/state.py at import time; they fail fast
# if absent. We don't need real credentials — the BlobStore degrades to None
# and the blueprint route doesn't use it.)

# --- Application code ----------------------------------------------------
# Copy api/ and shared bits the blueprint surface depends on.
COPY api/ ./api/
COPY data/blueprint-recordings/ ./data/blueprint-recordings/

# Built bundle from stage 1.
COPY --from=bundle /build/dist/ ./web/blueprint/dist/

# --- Runtime config ------------------------------------------------------
# Container Apps sets PORT (often 80). Default for non-CA hosts.
ENV PORT=80 \
    BLUEPRINT_AUTOSTART_STREAM=1

EXPOSE 80

# Start FastAPI. --workers 1 because EventBus + recorder + stream task are
# all in-process state; multiple workers would split the bus.
# blueprint_app:app is the lean entry point — only the routes the page needs,
# none of the heavy GHCP / MAF / sentence-transformers imports.
CMD ["sh", "-c", "uvicorn api.server.blueprint_app:app --host 0.0.0.0 --port ${PORT:-80} --workers 1 --no-access-log"]
