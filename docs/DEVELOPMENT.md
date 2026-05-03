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

## Running the stack — terminals

The POC1 + portal stack runs as six processes; POC2 hiring needs a
seventh (POC2 mocks); the blueprint microsite is a separate eighth.
Use `make up` in one terminal for the convenience launcher (it boots
the first six), or run each explicitly for easier debugging.

| # | Terminal | Port | Notes |
|---|---|---|---|
| 1 | `docker compose up -d azurite` (or `azurite --silent --location azurite-data`) | 10000-10002 | |
| 2 | `make mcp` — 3 POC1 mock MCPs (tsx watch) | 4101-4103 | |
| 3 | `make functions` — Azure Functions host | 7071 | Hosts ALL durable orchestrators (expense, hiring, fleet-travel-preapproval) |
| 4 | `make server` — FastAPI + Fleet Manager (uvicorn --reload) | 3001 | |
| 5 | `npm run dev:client` — Control Plane UI (Vite HMR) | 5173 | |
| 6 | `npm run dev:portal` — Candidate Portal (Vite HMR) | 5174 | Required for POC2 candidate flows |
| 7 | `npm run dev:mcp:poc2` — 7 POC2 mock MCPs (tsx watch) | 4201-4207 | greenhouse, linkedin, workday-hr, graph, servicenow, acs, heygen |
| 8 | `npm run dev:blueprint` — Blueprint microsite (Vite HMR) | 5175 | Optional — only if iterating on the editorial page or the live observatory |

`make up` chains terminals 1–6 without watchers (Azurite via npm, no
Docker, UI + portal served from built bundles) — the fastest boot for
demo takes. POC2 mocks and the blueprint microsite are not in `make up`;
boot them separately when needed.

For the blueprint microsite, an alternative to `make server` is
`scripts/run-fastapi-blueprint.sh`, which starts uvicorn on `:3001`
backgrounded with no access log (handy when iterating on `:5175` and
you don't want noise in the terminal).

### Hot reload

- **FastAPI**: `--reload` flag in `make server`; edits under `api/server/`
  restart uvicorn on save.
- **Vite HMR**: any `web/client/`, `web/portal/`, or `web/blueprint/`
  edit reloads the relevant UI without page refresh.
- **MCP mocks**: `tsx watch` restarts each mock when `mocks/*/server.ts`
  changes (both `dev:mcp` and `dev:mcp:poc2` variants).
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

## Helper scripts

In `scripts/`:

| Script | Purpose |
|---|---|
| `boot-demo.sh` | What `make up` runs — boots azurite + POC1 mocks + FastAPI + control-plane UI + portal + functions in one terminal |
| `run-fastapi-blueprint.sh` | Backgrounded uvicorn on `:3001` with no access log; pairs with `npm run dev:blueprint` when iterating on the microsite |
| `blueprint-ticker.sh` | Drives synthetic blueprint events for visual smoke-testing |
| `build-blueprint-image.sh` | `az acr build` of the blueprint container into `blueprintacrapexdemo` |
| `deploy-blueprint.sh` | Single-command deploy of the microsite to Azure Container Apps (resource group `project-apex-demo`, container `blueprint`). See [blueprint-microsite-contributor-guide.md §Deploying to Azure](blueprint-microsite-contributor-guide.md#deploying-to-azure) |
| `profile-autonomous.sh`, `profile-friday.sh` | Profiling helpers for the autonomous demo loop |
| `preclassify_corpus.py` | One-shot preclassification of the 300-claim accuracy corpus |
| `generate_blueprint_image.py` | Renders the social/preview image for the blueprint page |
| `generate_cv_pdfs.py` | Generates the synthetic CV corpus for POC2 |
| `prewarm_avatar.py` | Warms the avatar render cache before a POC2 demo |
