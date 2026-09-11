# Zava control plane — supervised API + Functions, three React SPAs baked in.
#
# Stage 1 (node:20-slim)     → npm ci + vite build for 3 SPAs (client, portal, blueprint)
# Stage 2 (python:3.11-slim) → hash-checked dependencies from uv.lock
# Stage 3 (python:3.11-slim) → runtime: Functions :7071 + uvicorn :80 + SPAs
#
# Note: substrate is pinned to Python 3.11 (.python-version + pyproject requires-python).

############################
# Stage 1 — SPA bundles
############################
FROM node:20-slim AS spa-build

WORKDIR /src

ARG NPM_REGISTRY=https://registry.npmjs.org

# Operator UI (vite at repo root)
COPY package.json package-lock.json* tsconfig.json vite.config.ts tailwind.config.ts postcss.config.js index.html ./
COPY web ./web
RUN --mount=type=cache,target=/root/.npm \
    npm ci --include=dev --registry="${NPM_REGISTRY}" --no-audit --no-fund \
    && test -x node_modules/.bin/vite

# Build root operator UI → /src/dist
# Note: root `npm run build` runs `tsc --noEmit && vite build`, but root tsconfig
# sweeps `web/blueprint` + `web/portal` (which have their own tsconfigs + their own
# noUnusedLocals-strict TS that root npm install doesn't provide deps for).
# Use the installed binary: npx must not download an unlocked tool on failure.
RUN ./node_modules/.bin/vite build

# Build portal → /src/web/portal/dist
# BASE_PATH=/portal/ so emitted asset URLs match the /portal mount in
# api/server/static_production.py (otherwise index.html references /assets/*
# which collides with the root SPA's asset mount and 404s).
RUN --mount=type=cache,target=/root/.npm \
    npm --prefix web/portal ci --include=dev --registry="${NPM_REGISTRY}" --no-audit --no-fund \
    && BASE_PATH=/portal/ npm --prefix web/portal run build

# Build blueprint → /src/web/blueprint/dist
# VITE_DEMO_URL=/ tells the blueprint to use same-origin ACA routing;
# BASE_PATH=/blueprint/ aligns emitted asset URLs with the /blueprint mount.
COPY docs/media/aurora-recorded-walkthrough* ./docs/media/
RUN --mount=type=cache,target=/root/.npm \
    npm --prefix web/blueprint ci --include=dev --registry="${NPM_REGISTRY}" --no-audit --no-fund \
    && BASE_PATH=/blueprint/ VITE_DEMO_URL=/ npm --prefix web/blueprint run build


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

ARG PYPI_INDEX_URL=https://pypi.org/simple

# Cache deps layer (pyproject + lockfile only — fastest rebuilds)
COPY pyproject.toml uv.lock* ./
# Export preserves locked versions/hashes while allowing a different download
# index. uv sync --frozen otherwise uses the original artifact URLs in uv.lock.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --frozen --no-dev --no-emit-project --format requirements.txt \
        --output-file /tmp/runtime-requirements.txt > /dev/null \
    && uv venv .venv \
    && uv pip sync --python .venv/bin/python --require-hashes \
        --default-index "${PYPI_INDEX_URL}" /tmp/runtime-requirements.txt

# Now copy app source + install project (kept lean — no SPAs here)
COPY api ./api
COPY verticals ./verticals
COPY mocks ./mocks
COPY data ./data
COPY scripts ./scripts
# Functions v2 programming model: function_app.py + host.json MUST live at
# the func project root (which is /app — we run `func host start` from /app
# in deploy/entrypoint.sh). Without these, the host reports "No job functions
# found" and every workflow spawn returns 404.
COPY function_app.py host.json ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python .venv/bin/python --no-deps --editable . \
        --default-index "${PYPI_INDEX_URL}"


############################
# Stage 3 — runtime
############################
FROM python:3.11-slim-bookworm AS runtime

# Verified with the Python worker and bundled .NET 8 runtime; update deliberately.
ARG AZURE_FUNCTIONS_CORE_TOOLS_VERSION=4.9.0-1

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
    && apt-get install -y --no-install-recommends \
        azure-functions-core-tools-4="${AZURE_FUNCTIONS_CORE_TOOLS_VERSION}" \
    && apt-get purge -y gnupg apt-transport-https lsb-release \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Match host.json's [4.0.0, 4.18.0) range. Core Tools' connectivity probe
# can report offline even when the bundle CDN works; cold boots need a cache.
ARG AZURE_FUNCTIONS_EXTENSION_BUNDLE_VERSION=4.17.0
ARG AZURE_FUNCTIONS_EXTENSION_BUNDLE_SHA256=03978c7058cdf22458e23570e944a4f2636afe5ad2808081a53c3644332b7fbf
RUN bundle_dir="/root/.azure-functions-core-tools/Functions/ExtensionBundles/Microsoft.Azure.Functions.ExtensionBundle/${AZURE_FUNCTIONS_EXTENSION_BUNDLE_VERSION}" \
    && mkdir -p "${bundle_dir}" \
    && curl --fail --show-error --location --retry 3 \
        "https://cdn.functions.azure.com/public/ExtensionBundles/Microsoft.Azure.Functions.ExtensionBundle/${AZURE_FUNCTIONS_EXTENSION_BUNDLE_VERSION}/Microsoft.Azure.Functions.ExtensionBundle.${AZURE_FUNCTIONS_EXTENSION_BUNDLE_VERSION}_any-any.zip" \
        --output /app/extension-bundle.zip \
    && echo "${AZURE_FUNCTIONS_EXTENSION_BUNDLE_SHA256}  /app/extension-bundle.zip" | sha256sum --check \
    && python -m zipfile -e /app/extension-bundle.zip "${bundle_dir}" \
    && rm /app/extension-bundle.zip

# Copy resolved venv + project source from build stage
COPY --from=py-build /app /app

# Copy SPA bundles into the locations static_production.py expects
COPY --from=spa-build /src/dist                  /app/static/client
COPY --from=spa-build /src/web/portal/dist       /app/static/portal
COPY --from=spa-build /src/web/blueprint/dist    /app/static/blueprint

# Persist KuzuDB to a mounted Azure Files share at /data
RUN mkdir -p /data && chmod 0777 /data

# Bake the replay tape into the image. ACA replay mode reads this path
# via ZAVA_TAPE_PATH (set in infra/modules/aca-app.bicep). Keep .gitignored
# tapes out of the build context via .dockerignore; explicitly copy the
# named tape file we want to ship.
COPY tapes/demo.tar.gz /app/tape/tape.tar.gz

# Production marker — main.py loads static_production.py when this is set
ENV ZAVA_STATIC_BUNDLE_DIR=/app/static \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PORT=80

# Container entrypoint supervises Functions (:7071) and uvicorn (:80);
# replay mode runs only uvicorn. See deploy/entrypoint.sh.
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
