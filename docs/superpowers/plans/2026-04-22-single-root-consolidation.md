# Single-Root Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse `control-plane/` (TS) and `control-plane-py/` (Python) into a single repo root with flat `api/`, `web/`, `mocks/`, `tests/`, `docs/` directories and no duplicated code, with a unified README and a full docs set.

**Architecture:** The TypeScript v1 Express backend (`control-plane/src/server/`) is superseded by the Python POC1 backend and is deleted outright. What survives from the TS side is the React UI (`web/`) and the four Node mock MCP servers (`mocks/`). Python code (FastAPI server, Azure Durable Functions, MAF Pregel graphs) hoists to top-level `api/`. All root-level configs (`pyproject.toml`, `package.json`, `host.json`, `function_app.py`, `vite.config.ts`, `Makefile`, `docker-compose.yml`) live at the single repo root.

**Tech Stack:** Python 3.11 + FastAPI + Azure Durable Functions + Microsoft Agent Framework + GHCP SDK Python. React 19 + Vite 6 + TailwindCSS 4. Node-based MCP mocks. Pytest + Vitest + Playwright.

---

## Target Structure

```
wpp-control-plane-poc1/
├── api/                          # Python: FastAPI + Durable Functions + MAF
│   ├── __init__.py
│   ├── server/                   # FastAPI (Fleet Manager + simulator + REST API)
│   │   ├── main.py
│   │   ├── state.py
│   │   ├── routes/               # /api/workflows, /api/exceptions, /api/policy, ...
│   │   ├── services/             # eventBus, fleetManagerService, simulator, sseHub
│   │   ├── skills/               # fleet-manager + 9 finance skills (*.skill.md)
│   │   ├── mcp_tools/            # Fleet Manager's 5 MCP tools
│   │   └── fixtures/             # vendors, POs, agencies, policy-refs
│   ├── functions/                # Azure Durable Functions + MAF graphs
│   │   ├── webhook.py
│   │   ├── workflows/            # InvoiceP2POrchestrator + activities
│   │   └── graphs/               # Per-phase MAF Pregel graphs
│   └── shared/
│       ├── types.py
│       ├── events.py
│       ├── constants.py
│       ├── otel.py
│       └── policies.yaml
├── web/                          # React 19 + Vite 6
│   ├── client/
│   │   ├── App.tsx, main.tsx
│   │   ├── components/
│   │   ├── routes/
│   │   └── hooks/
│   └── shared/                   # TS shared types mirroring api/shared
│       ├── types.ts
│       └── events.ts
├── mocks/                        # Node/TS MCP mocks
│   ├── workday-mcp/
│   ├── d365-mcp/
│   ├── maconomy-mcp/
│   └── payment-mcp/
├── tests/
│   ├── api/                      # pytest
│   ├── web/                      # vitest
│   └── e2e/                      # Playwright
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   ├── DEMO.md
│   └── superpowers/
├── scripts/
│   └── boot-demo.sh
├── function_app.py               # Azure Functions v2 entry (must be at root)
├── host.json
├── local.settings.json.example
├── pyproject.toml / uv.lock
├── requirements.txt              # Functions worker venv
├── package.json / package-lock.json
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.js
├── index.html
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

### Task 1: Verify clean baseline

**Files:** none (read-only check)

- [ ] **Step 1: Confirm working tree is clean**

Run: `git status --short`
Expected: At most the pre-existing `M control-plane/src/client/components/FleetManagerRail.js` line. No other uncommitted changes.

- [ ] **Step 2: Confirm both stacks currently run**

Run: `cd control-plane-py && uv run pytest -q && cd ../control-plane && npm test --silent`
Expected: Both test suites pass. Record the test counts as baseline for later comparison.

- [ ] **Step 3: Create a consolidation branch**

```bash
git checkout -b chore/single-root-consolidation
```

No commit — this is a branch marker only.

---

### Task 2: Delete the superseded TypeScript v1 server

**Files:**
- Delete: `control-plane/src/server/` (entire tree)
- Delete: `control-plane/src/shared/policies.yaml` (identical to `control-plane-py/src/shared/policies.yaml`; the Python copy survives as `api/shared/policies.yaml`)
- Delete: `control-plane/spike/` (v1 SDK de-risk artefacts — superseded by `control-plane-py/spike/`)
- Delete: `control-plane/docs/SOLUTION-AUDIT.md` (v1-specific audit)
- Keep: `control-plane/src/client/`, `control-plane/src/shared/types.ts` + `types.js` + `events.ts` + `events.js` (heavy UI import surface via `@shared/*`; these move to `web/shared/` in Task 4), `control-plane/mocks/`, `control-plane/tests/`, `control-plane/docs/ARCHITECTURE.md`, `control-plane/docs/demo-script.md`
- Modify: `control-plane/package.json` — remove `dev:server`, `dev`, server-only deps (`express`, `cors`, `@github/copilot-sdk`, `js-yaml`, `@types/express`, `@types/cors`, `@types/js-yaml`); rewire `dev` to mean UI + mocks only. Keep `tsx` (mocks still use it).

- [ ] **Step 1: Delete the TS v1 server, its spike, and the duplicate policies.yaml**

```bash
rm -rf control-plane/src/server
rm -rf control-plane/spike
rm -f control-plane/src/shared/policies.yaml
rm -f control-plane/docs/SOLUTION-AUDIT.md
```

- [ ] **Step 2: Confirm the UI does not import anything from the deleted server**

Run: `cd control-plane && grep -r "from ['\"].*@server" src/client tests/unit || true`
Expected: No matches. UI only hits the backend over HTTP/SSE; any tests that imported from `@server/*` were server-only and will be removed with the server in Step 1.

Also run: `grep -r "from ['\"]@shared" src/client | wc -l`
Expected: Non-zero (UI heavily uses `@shared/types` and `@shared/events`). Confirms the shared files were rightly kept for the Task 4 move.

- [ ] **Step 3: Rewrite `control-plane/package.json` scripts + prune server-only deps**

Replace `scripts` block:

```json
"scripts": {
  "dev:client": "vite",
  "dev:mcp": "concurrently -k -n wd,d365,mac,pay \"tsx watch mocks/workday-mcp/server.ts\" \"tsx watch mocks/d365-mcp/server.ts\" \"tsx watch mocks/maconomy-mcp/server.ts\" \"tsx watch mocks/payment-mcp/server.ts\"",
  "demo:mcp": "concurrently -k -n wd,d365,mac,pay \"tsx mocks/workday-mcp/server.ts\" \"tsx mocks/d365-mcp/server.ts\" \"tsx mocks/maconomy-mcp/server.ts\" \"tsx mocks/payment-mcp/server.ts\"",
  "demo:ui": "vite preview --host 0.0.0.0 --port 5173",
  "build": "tsc && vite build",
  "test": "vitest run",
  "test:watch": "vitest",
  "test:e2e": "playwright test",
  "test:e2e:install": "playwright install chromium"
}
```

Remove from `dependencies`: `@github/copilot-sdk`, `cors`, `express`, `js-yaml`.
Remove from `devDependencies`: `@types/cors`, `@types/express`, `@types/js-yaml`.
Keep `tsx` (mocks still use it).

- [ ] **Step 4: Reinstall to prune lockfile**

Run: `cd control-plane && rm -rf node_modules package-lock.json && npm install`
Expected: Install completes; no peer-dep warnings referencing the removed packages.

- [ ] **Step 5: Verify vitest still passes with the pruned surface**

Run: `cd control-plane && npm test --silent`
Expected: Same test count as Task 1 Step 2, or fewer if any test was exercising the deleted server. If fewer, list which tests disappeared and confirm they were server-only.

- [ ] **Step 6: Verify vite build still succeeds**

Run: `cd control-plane && npm run build`
Expected: `dist/` produced, no errors.

- [ ] **Step 7: Commit**

```bash
git add -A control-plane/
git commit -m "refactor: delete superseded TypeScript v1 server

The Python POC1 backend has full feature parity and is the demo target.
Keeps the React UI, mock MCP servers, and UI tests from control-plane/."
```

---

### Task 3: Hoist Python backend to top-level `api/`

**Files:**
- Move: `control-plane-py/src/` → `api/`
- Move: `control-plane-py/function_app.py` → `./function_app.py`
- Move: `control-plane-py/host.json` → `./host.json`
- Move: `control-plane-py/local.settings.json.example` → `./local.settings.json.example`
- Move: `control-plane-py/pyproject.toml` → `./pyproject.toml`
- Move: `control-plane-py/uv.lock` → `./uv.lock`
- Move: `control-plane-py/requirements.txt` → `./requirements.txt`
- Move: `control-plane-py/docker-compose.yml` → `./docker-compose.yml`
- Move: `control-plane-py/.env.example` → `./.env.example`
- Move: `control-plane-py/scripts/boot-demo.sh` → `./scripts/boot-demo.sh`
- Move: `control-plane-py/spike/` → `./spike/` (kept as reference; may be dropped in a future cleanup)
- Modify: `function_app.py` imports (3 lines, `src.*` → `api.*`)
- Modify: `pyproject.toml` (`packages = ["src"]` → `packages = ["api"]`)
- Modify: every `from src.` / `import src.` in Python source → `from api.` / `import api.`

- [ ] **Step 1: Move the directory tree**

```bash
git mv control-plane-py/src api
git mv control-plane-py/function_app.py ./
git mv control-plane-py/host.json ./
git mv control-plane-py/local.settings.json.example ./
git mv control-plane-py/pyproject.toml ./
git mv control-plane-py/uv.lock ./
git mv control-plane-py/requirements.txt ./
git mv control-plane-py/docker-compose.yml ./
git mv control-plane-py/.env.example ./
mkdir -p scripts
git mv control-plane-py/scripts/boot-demo.sh scripts/boot-demo.sh
git mv control-plane-py/spike ./spike
git mv control-plane-py/Makefile ./Makefile
git mv control-plane-py/docs/demo-script.md docs/demo-script.md.py-tmp
git mv control-plane-py/tests ./tests-py-tmp
rm -rf control-plane-py
```

(Makefile and tests and demo-script get final placement in Tasks 7 and 8; the `*-tmp` suffixes just stage them.)

- [ ] **Step 2: Rewrite `function_app.py` imports**

Replace lines 7-12 of `function_app.py`:

```python
from api.shared.otel import init_otel
from api.functions.workflows.invoice_p2p import invoice_p2p_orchestration
from api.functions.workflows.activities import (
    intake_activity, validation_activity, routing_activity, approval_activity,
    payment_activity, reconciliation_activity, checkpoint_activity,
)
```

- [ ] **Step 3: Rewrite `pyproject.toml` wheel packages**

Change `[tool.hatch.build.targets.wheel]` block:

```toml
[tool.hatch.build.targets.wheel]
packages = ["api"]
```

- [ ] **Step 4: Find-and-replace absolute `src.` imports across Python sources**

```bash
grep -rl --include='*.py' -E '^(from|import)\s+src\.' api/ tests-py-tmp/ \
  | xargs sed -i 's/^from src\./from api./g; s/^import src\./import api./g'
```

- [ ] **Step 5: Verify no `from src.` / `import src.` remain**

Run: `grep -rn --include='*.py' -E '^(from|import)\s+src\.' api/ tests-py-tmp/ || echo OK`
Expected: `OK`.

- [ ] **Step 6: Sync the uv environment at the new root**

```bash
rm -rf .venv
uv sync
```

Expected: `.venv/` created at repo root; no import errors during `uv sync`.

- [ ] **Step 7: Verify Python imports resolve**

Run: `uv run python -c "from api.server.main import app; from api.functions.workflows.invoice_p2p import invoice_p2p_orchestration; print('OK')"`
Expected: `OK`.

- [ ] **Step 8: Run pytest against the hoisted tree**

Update `pyproject.toml` `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests-py-tmp"]
```

Run: `uv run pytest -q`
Expected: Same test count as Task 1 Step 2.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: hoist Python backend from control-plane-py/ to api/

function_app.py, host.json, pyproject.toml, uv.lock, requirements.txt,
docker-compose.yml, .env.example all now live at repo root. All
'from src.*' imports rewritten to 'from api.*'."
```

---

### Task 4: Hoist React UI to top-level `web/`

**Files:**
- Move: `control-plane/src/client/` → `web/client/`
- Move: `control-plane/src/shared/` → `web/shared/` (contains `types.ts`, `types.js`, `events.ts`, `events.js` — UI import target via `@shared/*`)
- Move: `control-plane/index.html` → `./index.html`
- Move: `control-plane/vite.config.ts` → `./vite.config.ts`
- Move: `control-plane/vitest.config.ts` → `./vitest.config.ts`
- Move: `control-plane/playwright.config.ts` → `./playwright.config.ts` (no root stub — was deleted with `62eec63` RFP cleanup)
- Move: `control-plane/tsconfig.json` → `./tsconfig.json`
- Move: `control-plane/tailwind.config.ts` → `./tailwind.config.ts`
- Move: `control-plane/postcss.config.js` → `./postcss.config.js`
- Move: `control-plane/package.json` + `package-lock.json` → `./`
- Merge: `control-plane/.env.example`, `control-plane/.env.local` into root `.env.example` (Task 6 handles; no conflict: Py uses `./.env`, web uses `VITE_*` vars)
- Modify: `tsconfig.json` — rewrite `paths` (`@shared/*`, `@client/*`; delete `@server/*`) and `include` to target new locations
- Modify: `vite.config.ts` — rewrite `resolve.alias` for `@shared` and `@client` to point at `web/shared` and `web/client`
- Modify: `index.html` script src if it references `/src/client/main.tsx` → `/web/client/main.tsx`

- [ ] **Step 1: Move the UI tree and root configs**

```bash
git mv control-plane/src/client web/client
git mv control-plane/src/shared web/shared
git mv control-plane/index.html ./index.html
git mv control-plane/vite.config.ts ./vite.config.ts
git mv control-plane/vitest.config.ts ./vitest.config.ts
git mv control-plane/playwright.config.ts ./playwright.config.ts
git mv control-plane/tsconfig.json ./tsconfig.json
git mv control-plane/tailwind.config.ts ./tailwind.config.ts
git mv control-plane/postcss.config.js ./postcss.config.js
git mv control-plane/package.json ./package.json
git mv control-plane/package-lock.json ./package-lock.json
```

- [ ] **Step 2: Rewrite `index.html` entry path**

If `index.html` references `/src/client/main.tsx`, change to `/web/client/main.tsx`. Read the file; edit the `<script type="module" src="...">` line.

- [ ] **Step 3: Rewrite `vite.config.ts` aliases**

The existing config (pre-move) has:

```ts
resolve: {
  alias: {
    "@shared": path.resolve(__dirname, "src/shared"),
    "@client": path.resolve(__dirname, "src/client")
  }
}
```

Rewrite both alias targets to point at the new locations:

```ts
resolve: {
  alias: {
    "@shared": path.resolve(__dirname, "web/shared"),
    "@client": path.resolve(__dirname, "web/client")
  }
}
```

Leave `plugins`, `server.proxy`, and `preview.proxy` blocks unchanged.

- [ ] **Step 4: Rewrite `tsconfig.json` paths and include**

Replace `compilerOptions.paths` and the root `include` array so they target the new layout:

```json
"paths": {
  "@shared/*": ["web/shared/*"],
  "@client/*": ["web/client/*"]
},
```

```json
"include": ["web", "mocks", "tests/web", "tests/e2e"]
```

Delete the `@server/*` path entry entirely (TS server is gone).

- [ ] **Step 5: Rewrite `package.json` `dev:mcp` / `demo:mcp` paths**

Change every `mocks/<name>-mcp/server.ts` to `mocks/<name>-mcp/server.ts` (unchanged once mocks move in Task 5). If `test:e2e` path refers to `tests/e2e/`, it will align after Task 7.

- [ ] **Step 6: Reinstall npm deps at new root**

```bash
rm -rf node_modules
npm install
```

- [ ] **Step 7: Verify Vite build and vitest**

```bash
npm run build
npm test --silent
```

Expected: Build produces `dist/`; vitest reports the Task 1 baseline count.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: hoist React UI from control-plane/src/client to web/

Root now owns vite.config.ts, index.html, tsconfig.json, tailwind/
postcss configs, package.json, and package-lock.json."
```

---

### Task 5: Hoist mocks to top-level `mocks/`

**Files:**
- Move: `control-plane/mocks/` → `./mocks/`
- Delete: `control-plane/` (should be empty after the moves; verify)

- [ ] **Step 1: Move mocks**

```bash
git mv control-plane/mocks ./mocks
```

- [ ] **Step 2: Verify `control-plane/` is empty and delete it**

Run: `ls -la control-plane/ 2>&1`
Expected: Either "No such file or directory" or only `node_modules/`, `dist/`, `test-results/`, `.env.local`, `.gitignore`, `docs/` (docs handled in Task 8).

```bash
rm -rf control-plane/node_modules control-plane/dist control-plane/test-results
git mv control-plane/docs/demo-script.md docs/demo-script.md.ts-tmp 2>/dev/null || true
git mv control-plane/docs/ARCHITECTURE.md docs/ARCHITECTURE.md.ts-tmp 2>/dev/null || true
rm -f control-plane/.env.example control-plane/.env.local control-plane/.gitignore control-plane/README.md
rmdir control-plane/src 2>/dev/null || rm -rf control-plane/src
rmdir control-plane/docs 2>/dev/null || true
rmdir control-plane 2>/dev/null || true
```

Expected: `control-plane/` no longer exists.

- [ ] **Step 3: Verify MCP mocks still run**

Run: `npm run demo:mcp &` (sleep 3; curl http://localhost:4101/health; kill %1)

Replace with platform-appropriate invocation if `&` / `%1` don't apply. Expected: All four mock servers respond `200` within 3 seconds.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: hoist mocks to top-level mocks/; delete empty control-plane/"
```

---

### Task 6: Consolidate root configs

**Files:**
- Modify: `.gitignore` — merge entries from both deleted per-folder `.gitignore` files
- Modify: `.env.example` — combine the Python `.env` keys (GHCP/OTEL/etc.) with the `VITE_API_BASE_URL` web key, commented by section
- Modify: `local.settings.json.example` — no changes (Azurite connection string stays)
- Delete: any orphaned `.env` / `.env.local` / `.env.example` left behind under former `control-plane/` or `control-plane-py/` (done in prior tasks; re-check)

- [ ] **Step 1: Merge `.gitignore` entries**

Read the existing root `.gitignore` and ensure it contains (append any missing):

```
# Node
node_modules/
dist/
test-results/
.playwright-mcp/

# Python
__pycache__/
*.py[cod]
.venv/
.funcvenv/
.python_packages/
.pytest_cache/
.ruff_cache/

# Azure Functions / Azurite
azurite-data/
local.settings.json
.env
.env.local

# Examples (keep)
!.env.example
!local.settings.json.example

# OS / editor
Thumbs.db
.DS_Store
.claude-cache/

# MCP session data
.playwright-mcp/

# Old workbench dir (deleted, leave rule defensive)
scratch/
```

- [ ] **Step 2: Merge `.env.example` entries**

Read both source files (already moved to root + the old web `.env.example`) and produce a single file with commented sections:

```env
# ── FastAPI + Functions (Python) ──────────────────────────────────
# (existing keys from control-plane-py/.env.example go here)

# ── Vite (React UI) ───────────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:3001
```

- [ ] **Step 3: Verify no stray env files**

Run: `find . -maxdepth 3 -name '.env*' -not -path './.git/*' -not -path './node_modules/*' -not -path './.venv/*'`
Expected: `./.env.example`, `./.env` (if user created one), `./local.settings.json.example`, `./local.settings.json` (if user created one). No files under former `control-plane*/`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: unify .gitignore and .env.example at repo root"
```

---

### Task 7: Consolidate tests at top-level `tests/`

**Files:**
- Move: `tests-py-tmp/unit/` → `tests/api/`
- Move: `tests-py-tmp/__init__.py` → `tests/__init__.py`
- Move: `control-plane/tests/unit/` (already moved in Task 4 rename path? — verify) → `tests/web/`
- Move: `control-plane/tests/e2e/` → `tests/e2e/`
- Delete: `tests-py-tmp/`
- Modify: `pyproject.toml` `testpaths` → `["tests/api"]`
- Modify: `vitest.config.ts` include → `tests/web/**/*`
- Modify: `playwright.config.ts` `testDir` → `./tests/e2e`
- Modify: `package.json` `test:e2e` if it hardcodes a path

- [ ] **Step 1: Move Python tests**

```bash
mkdir -p tests/api
git mv tests-py-tmp/unit tests/api/unit
git mv tests-py-tmp/__init__.py tests/__init__.py 2>/dev/null || true
rm -rf tests-py-tmp
touch tests/api/__init__.py
```

- [ ] **Step 2: Move Vitest tests**

The Task 4 moves already dragged `control-plane/tests/` up. If not, run:

```bash
[[ -d tests/unit ]] && git mv tests/unit tests/web || true
[[ -d control-plane/tests/unit ]] && git mv control-plane/tests/unit tests/web || true
[[ -d control-plane/tests/e2e ]] && git mv control-plane/tests/e2e tests/e2e || true
```

- [ ] **Step 3: Update `pyproject.toml` testpaths**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests/api"]
```

- [ ] **Step 4: Update `vitest.config.ts`**

Ensure `test.include` is `['tests/web/**/*.{test,spec}.{ts,tsx}']`.

- [ ] **Step 5: Update `playwright.config.ts`**

Ensure `testDir` is `'./tests/e2e'`.

- [ ] **Step 6: Run all three suites**

```bash
uv run pytest -q
npm test --silent
# Playwright runs against live stack — exercise in Task 9, not here.
```

Expected: Pytest and Vitest counts match Task 1 baseline.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: consolidate tests under tests/{api,web,e2e}"
```

---

### Task 8: Rewire Makefile + boot-demo.sh + consolidate docs

**Files:**
- Modify: `Makefile` — strip `cd ../control-plane` references; update `uvicorn` module path; update `test-e2e` path; drop `mcp` target's cross-folder `cd`
- Modify: `scripts/boot-demo.sh` — same cross-folder fixes; `uv run uvicorn api.server.main:app`; MCPs are now `npm run demo:mcp` from repo root
- Delete: `docs/demo-script.md.py-tmp` and `docs/demo-script.md.ts-tmp` after folding content into `docs/DEMO.md` (Task 13)
- Delete: `docs/ARCHITECTURE.md.ts-tmp` after Task 11 uses it as source material

- [ ] **Step 1: Rewrite `Makefile`**

Replace the file with:

```makefile
.PHONY: install dev mcp server functions funcvenv test test-e2e clean azurite-up azurite-down reset up

install:
	uv sync
	npm install

azurite-up:
	docker compose up -d azurite

azurite-down:
	docker compose down

reset:
	docker compose stop azurite
	rm -rf azurite-data/*
	docker compose up -d azurite
	@echo "azurite reset — restart func + uvicorn to clear in-memory state"

mcp:
	npm run dev:mcp

server:
	uv run uvicorn api.server.main:app --port 3001 --reload

funcvenv:
	py -3.11 -m venv .funcvenv
	.funcvenv/Scripts/pip install -r requirements.txt --quiet

functions:
	source .funcvenv/Scripts/activate && PYTHONPATH="$$(pwd)" func start --port 7071

dev: azurite-up
	@echo "Start in 3 terminals: 'make mcp' / 'make server' / 'make functions'"

up:
	bash scripts/boot-demo.sh

test:
	uv run pytest -q
	npm test --silent

test-e2e:
	npx playwright test --reporter=list

clean:
	docker compose down -v
	rm -rf .venv .funcvenv .python_packages node_modules dist __pycache__ .pytest_cache .ruff_cache azurite-data test-results
```

- [ ] **Step 2: Rewrite `scripts/boot-demo.sh`**

Replace every `( cd ../control-plane && npm run demo:mcp )` with `npm run demo:mcp`, every `( cd ../control-plane && npm run demo:ui )` with `npm run demo:ui`, and `uv run uvicorn src.server.main:app` with `uv run uvicorn api.server.main:app`. The `cd "$(dirname "$0")/.."` at line 17 already targets repo root now; verify and simplify if needed.

- [ ] **Step 3: Verify Makefile targets**

```bash
make install
make azurite-up
make server &
sleep 4
curl -sf http://localhost:3001/healthz && echo "server OK"
kill %1
make azurite-down
```

Expected: Server boots on 3001 and `/healthz` returns 200.

- [ ] **Step 4: Commit**

```bash
git add Makefile scripts/boot-demo.sh
git commit -m "chore: rewire Makefile and boot-demo.sh for single-root layout"
```

---

### Task 9: Full-stack smoke test

**Files:** none (integration check)

- [ ] **Step 1: Boot the stack**

```bash
make up &
BOOT_PID=$!
sleep 30
```

- [ ] **Step 2: Hit each port**

```bash
curl -sf http://localhost:5173 >/dev/null && echo "ui OK"
curl -sf http://localhost:3001/healthz && echo "api OK"
curl -sf http://localhost:7071/ >/dev/null && echo "func OK"
curl -sf http://localhost:4101/health && echo "workday OK"
curl -sf http://localhost:4102/health && echo "d365 OK"
curl -sf http://localhost:4103/health && echo "maconomy OK"
curl -sf http://localhost:4104/health && echo "payment OK"
```

Expected: All seven "OK" lines printed.

- [ ] **Step 3: Inject a demo scenario end-to-end**

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
sleep 10
curl -s http://localhost:3001/api/workflows | head -c 500
```

Expected: JSON response with at least one workflow whose status reflects the demo-fail path (exception raised at validate_gl_active).

- [ ] **Step 4: Run Playwright**

```bash
npx playwright test --reporter=list
```

Expected: All e2e tests pass against the live stack.

- [ ] **Step 5: Shut down**

```bash
kill $BOOT_PID
wait $BOOT_PID 2>/dev/null || true
make azurite-down
```

- [ ] **Step 6: Commit (no code changes — tag the consolidation)**

No commit. Proceed to documentation tasks.

---

### Task 10: Write `README.md` at repo root

**Files:**
- Create: `README.md` (replaces both former READMEs)
- Delete: any remaining `control-plane*/README.md` (should be gone by now; verify)

- [ ] **Step 1: Write the root README**

Content for `README.md`:

````markdown
# WPP Control Plane — POC1 (Finance Procure-to-Pay)

Production-shaped demo of a six-phase invoice P2P pipeline driven by
[Microsoft Agent Framework](https://learn.microsoft.com/agent-framework)
durable workflows, with a GHCP-SDK-powered Fleet Manager supervising
every exception in real time.

**Stack**
- Python 3.11 · FastAPI · Azure Durable Functions · MAF · GHCP SDK
- React 19 · Vite 6 · TailwindCSS 4
- Node mock MCP servers (Workday, D365, Maconomy, Payment)

## Ports

| Service         | Port    |
|-----------------|---------|
| Vite (UI)       | 5173    |
| FastAPI         | 3001    |
| Functions host  | 7071    |
| Azurite         | 10000-10002 |
| Mock MCPs       | 4101-4104 |

## Quickstart

Prerequisites: Python 3.11 + 3.13, Node 20+, [`uv`](https://astral.sh/uv),
Azure Functions Core Tools v4.9+, Docker (for Azurite — or `npm i -g azurite`),
GitHub Copilot license (`gh auth login`).

```bash
make install        # uv sync + npm install
make funcvenv       # Windows: one-time Py 3.11 venv for func
cp local.settings.json.example local.settings.json
cp .env.example .env
gh auth login
make up             # boots the full stack in one terminal
```

UI at http://localhost:5173. Inject scenarios:

```bash
curl -X POST http://localhost:3001/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario":"demo-fail"}'
```

## Layout

```
api/     — Python: FastAPI + Durable Functions + MAF graphs + skills
web/     — React 19 + Vite 6 UI
mocks/   — Node MCP servers (Workday, D365, Maconomy, Payment)
tests/   — pytest (api/), vitest (web/), Playwright (e2e/)
docs/    — ARCHITECTURE, DEVELOPMENT, DEMO
scripts/ — boot-demo.sh
```

More:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the three tiers + how events flow
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local dev, terminals, debugging
- [docs/DEMO.md](docs/DEMO.md) — injection scenarios + expected UI flow

## Stop

`Ctrl-C` the `make up` terminal. In-memory Fleet Manager + simulator state
clears; Durable Functions state persists in `azurite-data/`. `make reset`
wipes it.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add unified root README.md"
```

---

### Task 11: Write `docs/ARCHITECTURE.md`

**Files:**
- Create: `docs/ARCHITECTURE.md`
- Source: fold in content from `docs/ARCHITECTURE.md.ts-tmp` (former control-plane ARCHITECTURE) and the architecture section of `control-plane-py/README.md` (already committed in previous task)
- Delete: `docs/ARCHITECTURE.md.ts-tmp` after merging

- [ ] **Step 1: Draft `docs/ARCHITECTURE.md` from both sources**

Produce a single document covering:

1. **Three tiers (with diagram reference to `docs/superpowers/specs/2026-04-13-wpp-control-plane-py-poc1-design.md`):**
   - MAF Durable Workflow — single orchestrator per invoice, six phase activities, HITL via `wait_for_external_event`, checkpointing by Azure Durable Functions runtime, Azurite-backed locally.
   - Per-phase MAF Pregel graphs — `WorkflowBuilder` + typed Executors + validators; agent executors load `*.skill.md` files via `GitHubCopilotAgent`.
   - Fleet Manager — always-on GHCP SDK session in FastAPI; consumes triage-filtered telemetry; debounces; reasons over batches via `send_and_wait`; calls five MCP tools.

2. **Runtime boundaries:**
   - FastAPI process (port 3001) — Fleet Manager + simulator + REST API + SSE hub.
   - Azure Functions host (port 7071) — Durable orchestrator + activities.
   - Vite dev server (port 5173) — React UI; talks to FastAPI over HTTP + SSE.
   - Four Node mock MCPs (ports 4101-4104) — Express + JSON fixtures.
   - Azurite (ports 10000-10002) — Durable Functions state.

3. **Event flow** — diagram: invoice injection → orchestrator start → phase activities → OTEL events → in-process EventBus → Triage → Fleet Manager → MCP tool calls → SSE to UI right rail.

4. **Identities** — `finance-agent` (9 skills) + `fleet-manager-agent` (1 skill), both GHCP Hosted Agents.

5. **Known limitations** — single-worker uvicorn cache; sync activity wrappers; no persistence beyond Azurite.

- [ ] **Step 2: Delete the temporary source file**

```bash
rm -f docs/ARCHITECTURE.md.ts-tmp
```

- [ ] **Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add docs/ARCHITECTURE.md (three tiers + runtime + events)"
```

---

### Task 12: Write `docs/DEVELOPMENT.md`

**Files:**
- Create: `docs/DEVELOPMENT.md`

- [ ] **Step 1: Draft `docs/DEVELOPMENT.md`**

Sections:

1. **Setup (expanded quickstart)** — every prereq, Windows-specific Core Tools gotcha (the v4.0.5455 PATH shadow — carry over from former `control-plane-py/README.md:29-31`), `gh auth login`.

2. **Running individual processes (5 terminals)** — exact commands, with port table:
   - `docker compose up -d azurite` (or `azurite --silent --location azurite-data`)
   - `npm run dev:mcp`
   - `make functions`
   - `make server`
   - `npm run dev:client`

3. **Hot reload** — FastAPI has `--reload`; Vite HMR; Functions host does **not** reload on Python changes (restart `func start`); MCP mocks use `tsx watch`.

4. **Running tests** — `make test` (both suites); Playwright against live stack; single test invocations (`uv run pytest tests/api/unit/test_events.py -v`, `npm test -- tests/web/components/FleetManagerRail.test.tsx`).

5. **Resetting state** — `make reset` for Azurite; re-inject scenarios from scratch.

6. **Debugging** — FastAPI logs to stdout; Functions host logs to the `func start` terminal; Fleet Manager tool calls stream to UI right rail; OTEL spans export to Foundry (App Insights) if `AZURE_MONITOR_CONNECTION_STRING` is set in `.env`.

- [ ] **Step 2: Commit**

```bash
git add docs/DEVELOPMENT.md
git commit -m "docs: add docs/DEVELOPMENT.md (setup, hot reload, tests, debugging)"
```

---

### Task 13: Write `docs/DEMO.md`

**Files:**
- Create: `docs/DEMO.md`
- Source: `docs/demo-script.md.py-tmp` and `docs/demo-script.md.ts-tmp`
- Delete: both `.tmp` files after folding in

- [ ] **Step 1: Draft `docs/DEMO.md`**

Sections:

1. **Pre-flight** — `make reset` to wipe Azurite; `make up` to boot; wait for "All services should be up" banner.

2. **Scenario catalogue** — list all injectable scenarios with expected UI behaviour:
   - `{}` (default) — happy path; watch six phases complete, see events stream in right rail.
   - `{"scenario":"demo-fail"}` — bounded-probabilism case; `agent_gl_coder` picks GL-9999 (inactive), `validate_gl_active` blocks, Fleet Manager wakes and composes an exception card in the right rail.
   - Any other scenarios from `api/server/services/simulator.py` — document each.

3. **UI tour** — routes to show: Workflows, Orchestration, Exception Queue, Analytics, Policy, Evaluations. Fleet Manager right rail always visible.

4. **Reset between takes** — `make reset` + Ctrl-C the boot terminal + `make up` again.

- [ ] **Step 2: Delete temporary source files**

```bash
rm -f docs/demo-script.md.py-tmp docs/demo-script.md.ts-tmp
```

- [ ] **Step 3: Commit**

```bash
git add docs/DEMO.md
git commit -m "docs: add docs/DEMO.md (scenarios, UI tour, reset flow)"
```

---

### Task 14: Final verification, merge, push

**Files:** none (just verification + VCS)

- [ ] **Step 1: Final tree check**

Run: `ls -la`
Expected top-level entries: `.azure`, `.claude`, `.git`, `.github`, `.gitignore`, `.env.example`, `Makefile`, `README.md`, `api`, `azurite-data` (if up), `docker-compose.yml`, `docs`, `function_app.py`, `host.json`, `index.html`, `local.settings.json.example`, `mocks`, `node_modules`, `package.json`, `package-lock.json`, `playwright.config.ts`, `postcss.config.js`, `pyproject.toml`, `requirements.txt`, `scripts`, `spike`, `tailwind.config.ts`, `tests`, `tsconfig.json`, `uv.lock`, `.venv`, `vite.config.ts`, `vitest.config.ts`, `web`. No `control-plane*` directories.

- [ ] **Step 2: Final test sweep**

```bash
make test
```

Expected: Pytest + Vitest both green.

- [ ] **Step 3: Final stack smoke test**

Repeat Task 9 Steps 1–5 end-to-end.

- [ ] **Step 4: Merge to `main`**

```bash
git checkout main
git merge --no-ff chore/single-root-consolidation -m "chore: consolidate repo to single root (api/ + web/ + mocks/)"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```

- [ ] **Step 6: Delete the consolidation branch**

```bash
git branch -d chore/single-root-consolidation
```

---

## Rollback

If any task breaks the stack irrecoverably:

```bash
git reset --hard HEAD~1   # drops the last task's commit
```

Or to abandon the consolidation entirely:

```bash
git checkout main
git branch -D chore/single-root-consolidation
```

All prior work lives in commit `62eec63` on `main`.
