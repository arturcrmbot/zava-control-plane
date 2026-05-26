# Zava control plane — single uvicorn container, three React SPAs baked in.
#
# Stage 1 (node:20-slim)     → npm ci + vite build for 3 SPAs (client, portal, blueprint)
# Stage 2 (python:3.11-slim) → uv sync — lean Python deps (no torch, no weasyprint)
# Stage 3 (python:3.11-slim) → runtime: copy venv + SPA dist bundles → uvicorn :80
#
# Note: substrate is pinned to Python 3.11 (.python-version + pyproject requires-python).

############################
# Stage 1 — SPA bundles
############################
FROM node:20-slim AS spa-build

WORKDIR /src

# Operator UI (vite at repo root)
COPY package.json package-lock.json* tsconfig.json vite.config.ts tailwind.config.ts postcss.config.js index.html ./
COPY web ./web
RUN npm ci --no-audit --no-fund

# Build root operator UI → /src/dist
RUN npm run build

# Build portal → /src/web/portal/dist
RUN npm --prefix web/portal install --no-audit --no-fund \
    && npm --prefix web/portal run build

# Build blueprint → /src/web/blueprint/dist
RUN npm --prefix web/blueprint install --no-audit --no-fund \
    && npm --prefix web/blueprint run build


############################
# Stage 2 — Python deps via uv
############################
FROM python:3.11-slim AS py-build

# uv from official multi-stage image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Cache deps layer (pyproject + lockfile only — fastest rebuilds)
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy app source + install project (kept lean — no SPAs here)
COPY api ./api
COPY mocks ./mocks
COPY data ./data
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


############################
# Stage 3 — runtime
############################
FROM python:3.11-slim AS runtime

# Minimal runtime; tini for clean PID-1 signalling
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy resolved venv + project source from build stage
COPY --from=py-build /app /app

# Copy SPA bundles into the locations static_production.py expects
COPY --from=spa-build /src/dist                  /app/static/client
COPY --from=spa-build /src/web/portal/dist       /app/static/portal
COPY --from=spa-build /src/web/blueprint/dist    /app/static/blueprint

# Persist KuzuDB to a mounted Azure Files share at /data
RUN mkdir -p /data && chmod 0777 /data

# Production marker — main.py loads static_production.py when this is set
ENV ZAVA_STATIC_BUNDLE_DIR=/app/static \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PORT=80

EXPOSE 80

# Probes hit /healthz directly (it's a pure JSON route, defined BEFORE
# any StaticFiles mount in main.py so it can never be shadowed).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:80/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "api.server.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "1"]
