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
# Note: root `npm run build` runs `tsc --noEmit && vite build`, but root tsconfig
# sweeps `web/blueprint` + `web/portal` (which have their own tsconfigs + their own
# noUnusedLocals-strict TS that root npm install doesn't provide deps for).
# Use `npx vite build` directly — matches scripts/boot-demo.sh's local invocation.
RUN npx vite build

# Build portal → /src/web/portal/dist
RUN npm --prefix web/portal install --no-audit --no-fund \
    && npm --prefix web/portal run build

# Build blueprint → /src/web/blueprint/dist
RUN npm --prefix web/blueprint install --no-audit --no-fund \
    && npm --prefix web/blueprint run build


############################
# Stage 2 — Python deps via uv
############################
FROM python:3.11-slim-bookworm AS py-build

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
# Functions v2 programming model: function_app.py + host.json MUST live at
# the func project root (which is /app — we run `func host start` from /app
# in deploy/entrypoint.sh). Without these, the host reports "No job functions
# found" and every workflow spawn returns 404.
COPY function_app.py host.json ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


############################
# Stage 3 — runtime
############################
FROM python:3.11-slim-bookworm AS runtime

# Minimal runtime; tini for clean PID-1 signalling + Azure Functions Core Tools v4
# for the Durable orchestrator host (started alongside uvicorn — see entrypoint.sh).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini ca-certificates curl gnupg apt-transport-https lsb-release libicu72 \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/dotnetdev.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends azure-functions-core-tools-4 \
    && apt-get purge -y gnupg apt-transport-https lsb-release \
    && apt-get autoremove -y \
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

# Container entrypoint: backgrounds `func host start` (Durable orchestrator
# on :7071) then exec's uvicorn (:80). See deploy/entrypoint.sh.
COPY deploy/entrypoint.sh /usr/local/bin/zava-entrypoint
RUN chmod +x /usr/local/bin/zava-entrypoint

EXPOSE 80

# Probes hit /healthz directly (it's a pure JSON route, defined BEFORE
# any StaticFiles mount in main.py so it can never be shadowed).
# Increased start-period from 20s → 90s because func host needs ~30-60s
# to discover Python triggers and bind :7071 on a cold replica.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD curl -fsS http://127.0.0.1:80/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/zava-entrypoint"]
