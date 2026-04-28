# Development

## One-time setup

Prereqs:
- Python 3.11 (for the Azure Functions worker) AND Python 3.13 (for the main uv env)
- Node 20+
- [`uv`](https://astral.sh/uv/) — Python package manager
- Azure Functions Core Tools v4.9+ (`npm i -g azure-functions-core-tools@4 --unsafe-perm true`)
- Docker (for Azurite) — alternatively `npm i -g azurite`
- GitHub Copilot license + `gh auth login`

```bash
make install                                      # uv sync + npm install
make funcvenv                                     # Windows: Python 3.11 venv for func
cp local.settings.json.example local.settings.json
cp .env.example .env
gh auth login
```

### Windows gotcha: Core Tools v4.0.5455

If `func --version` reports 4.0.5455 (old MSI), the Python worker +
Durable extension bundle fail at startup. The MSI copy at
`C:\Program Files\Microsoft\Azure Functions Core Tools\` shadows the
npm-installed one. Either:

- Uninstall the MSI via *Add or Remove Programs*, or
- Prepend npm's bin to PATH: `export PATH="/c/Users/$USER/AppData/Roaming/npm:$PATH"`

Re-run `func --version`; it should report 4.9.0 or newer.

## Running the stack — 5 terminals

The full stack runs as five processes. Use `make up` in one terminal
for the convenience launcher, or run each explicitly for easier
debugging.

| # | Terminal | Port |
|---|---|---|
| 1 | `docker compose up -d azurite` (or `azurite --silent --location azurite-data`) | 10000-10002 |
| 2 | `make mcp` — 3 mock MCPs (tsx watch) | 4101-4103 |
| 3 | `make functions` — Azure Functions host | 7071 |
| 4 | `make server` — FastAPI + Fleet Manager (uvicorn --reload) | 3001 |
| 5 | `npm run dev:client` — Vite HMR | 5173 |

`make up` chains these without watchers (Azurite via npm, no Docker,
UI served from built bundle) — the fastest boot for demo takes.

### Hot reload

- **FastAPI**: `--reload` flag in `make server`; edits under `api/server/`
  restart uvicorn on save.
- **Vite HMR**: any `web/` edit reloads the UI without page refresh.
- **MCP mocks**: `tsx watch` restarts each mock when `mocks/*/server.ts`
  changes.
- **Functions host**: does *not* reload on Python changes — you must
  Ctrl-C and restart `func start` after editing `api/functions/*.py`.

## Tests

```bash
make test              # pytest + vitest (no live stack needed)
make test-e2e          # Playwright (requires `make up` in another terminal)
```

Run a single file:

```bash
uv run pytest tests/api/unit/test_events.py -v
npm test -- tests/web/types.test.ts
npx playwright test tests/e2e/smoke.spec.ts --reporter=list
```

Layout:

| Path | Framework | What |
|---|---|---|
| [tests/api/](../tests/api/) | pytest | Python unit tests (30) |
| [tests/web/](../tests/web/) | vitest | TS shared-types + events unit tests (12) |
| [tests/e2e/](../tests/e2e/) | Playwright | Live-stack smoke + API contract |

## Reset between demo takes

```bash
make reset   # wipes Azurite state (azurite-data/)
```

Then Ctrl-C `make up` and restart — that clears in-memory Fleet
Manager + simulator state (not persisted).

## Debugging

- **FastAPI logs** — stdout of the `make server` terminal; `--reload`
  shows uvicorn boot.
- **Functions host logs** — the `make functions` terminal. Look for
  `Worker process started` (Python worker OK), `Host lock lease
  acquired` (singleton election OK), and `ExpenseClaimOrchestrator:
  Started` on orchestrator start.
- **Fleet Manager trace** — the `/api/stream/fleet-manager` SSE feed;
  UI right rail subscribes.
- **OTEL spans** — set `APPLICATIONINSIGHTS_CONNECTION_STRING` in
  `.env` and spans export to Foundry Tracing (App Insights). Leave
  unset locally to keep `init_otel` a no-op.
- **Inject to trigger flow** — `POST /api/simulator/inject` (see
  [DEMO.md](DEMO.md)).

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'src'` | Stale venv from pre-consolidation code | `rm -rf .venv && uv sync` |
| Functions host exits with `Could not load file or assembly ...` | Core Tools too old (4.0.5455) | Upgrade to v4.9+ |
| `func start` picks Python 3.13 then crashes | uv env dominates PATH | Activate `.funcvenv` first, or set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |
| `failed to schedule` on inject | Functions host not running | `make functions` |
| `azurite` refuses connections on 10000 | Docker/npm azurite not up | `make azurite-up` or `npm i -g azurite && azurite --silent --location azurite-data` |
| UI shows empty workflows | No stack / API proxy misrouted | Check `VITE_API_BASE_URL` in `.env`; default is `http://localhost:3001` |
