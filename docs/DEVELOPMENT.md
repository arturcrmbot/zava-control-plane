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
| 4 | `make server` — FastAPI + Fleet Manager (uvicorn --reload) | 3101 | |
| 5 | `npm run dev:client` — Control Plane UI (Vite HMR) | 5273 | |
| 6 | `npm run dev:portal` — Candidate Portal (Vite HMR) | 5274 | Required for POC2 candidate flows |
| 7 | `npm run dev:mcp:poc2` — 7 POC2 mock MCPs (tsx watch) | 4201-4207 | greenhouse, linkedin, workday-hr, graph, servicenow, acs, heygen |
| 8 | `npm run dev:blueprint` — Blueprint microsite (Vite HMR) | 5275 | Optional — only if iterating on the editorial page or the live observatory |

`make up` chains terminals 1–6 without watchers (Azurite via npm, no
Docker, UI + portal served from built bundles) — the fastest boot for
demo takes. POC2 mocks and the blueprint microsite are not in `make up`;
boot them separately when needed.

For the blueprint microsite, an alternative to `make server` is
`scripts/run-fastapi-blueprint.sh`, which starts uvicorn on `:3101`
backgrounded with no access log (handy when iterating on `:5275` and
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

## Demo data

The Plane-1 entity graph that powers the portal is generated programmatically
from `api/server/data_fabric/` (per
[plan/archive/feature-enterprise-pitch-readiness-1.md](../plan/archive/feature-enterprise-pitch-readiness-1.md);
active plans now live under [docs/superpowers/plans/](../docs/superpowers/plans/)).
A single `DataPack.materialise()` call orchestrates every generator and
writes the result to `data/portal/entity_graph.kuzu`; a snapshot bundles
that directory into a portable tarball for fast cold-start restore.

```bash
# One-off: build the canonical Zava demo state and snapshot it
# (deletes any existing data/portal/entity_graph.kuzu first).
make data-pack-save
# → writes data/snapshots/zava-baseline.tgz (≈ 1500 nodes, 5000+ edges)

# Boot the stack from that snapshot. If the snapshot doesn't exist yet,
# `boot-demo.sh` materialises + saves it on the fly before restoring.
BOOT_DEMO_SNAPSHOT=zava-baseline make up

# Inspect available snapshots
make snapshot-list
```

`make data-pack-save` is deterministic: same code → same node + edge
counts. Re-run it whenever the generators or schema change so the
checked-in snapshot stays in sync.

## Governance (AGT)

The substrate's runtime governance is the [Microsoft Agent Governance
Toolkit](https://github.com/microsoft/agent-governance-toolkit) (AGT,
v3.4.x), wired in per
[plan/archive/feature-agent-governance-toolkit-1.md](../plan/archive/feature-agent-governance-toolkit-1.md).
The kernel lives at
[api/server/services/governance/](../api/server/services/governance/);
that package is the **only** import surface for `agent_os.*`,
`agentmesh.*`, and friends across the codebase (CON-002).

Smoke targets:

```bash
make agt-doctor   # diagnostic — installed packages + plugin health
make agt-verify   # OWASP Agentic Top 10 self-check (ASI-01..ASI-10)
```

Both run against whatever's installed in the project venv (`uv sync`).
The `agt` binary lives at `.venv/bin/agt`.

Phase status: see the per-phase status badge at the top of
[plan/archive/feature-agent-governance-toolkit-1.md](../plan/archive/feature-agent-governance-toolkit-1.md).
Phase 1 is wiring-only — the kernel is constructed at FastAPI startup
and at Functions worker module load but returns ALLOW for everything;
real policy enforcement lands in Phase 2 onwards.

### Authority resolution backend (Phase 3)

Authority `resolve` / `check` calls — both from agent skills via
`api.server.mcp_tools.delegated_authority` and from persona
`decision_policy` blocks via the sandbox `authority_check` builtin —
default to the **in-process governance kernel**. No HTTP hop, no Node
mock required to boot the substrate.

The Foundry-IQ engagement-POC swap-in seam (REQ-002) is preserved via
a single env var:

```bash
# Default — in-process kernel walks data/synthetic/authority/matrix.json
unset AUTHORITY_MCP_URL

# Engagement-POC swap-in — HTTP path to a Foundry-IQ-backed MCP
export AUTHORITY_MCP_URL=https://your-foundry-mcp.example/authority
```

The local Node mock at `mocks/authority-mcp/` (port 4108) is no longer
started by `make up` / `scripts/boot-demo.sh` (TASK-025a). Two ways to
bring it up alongside, when you want to either run the live parity test
or rehearse the engagement-POC swap-in:

```bash
make up-with-authority-mock      # boots the full stack + authority-mcp on :4108
# OR
BOOT_DEMO_WITH_AUTHORITY_MOCK=1 bash scripts/boot-demo.sh
# OR (mock standalone, no other services)
make mcp-authority
```

To make the substrate actually call the mock once it's up, set
`AUTHORITY_MCP_URL=http://127.0.0.1:4108`. To run the parity test
suite against it:

```bash
AUTHORITY_MCP_LIVE=1 \
  uv run pytest tests/api/server/services/governance/test_authority_parity.py -v
```

### Audit ledger hash chain (Phase 4)

Every audit ledger entry written via `AuditLogger.log()` carries a
`prev_hash` + `entry_hash` (SHA-256 over canonical JSON). The chain is
per-workflow; tampering with any field of any historical entry is
detected by `AuditLogger.verify_chain(workflow_id)` and surfaces on
`GET /api/governance/verify/{workflow_id}` and the Control Plane
workflow drawer's Audit section.

Backfill historical workflows that pre-date this wiring with:

```bash
# Walks azurite-data/__blobstorage__/audit-ledger/*.jsonl by default.
uv run python scripts/agt_backfill_chain.py

# Dry-run first if you want to see what would change.
uv run python scripts/agt_backfill_chain.py --dry-run

# Or point at a different root.
uv run python scripts/agt_backfill_chain.py --root /path/to/blobs
```

Idempotent — re-running on already-chained blobs is a no-op. Each
rewrite goes through a `.bak` sibling + atomic rename so a crash
mid-run leaves the original intact.

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
  cards for FM events appear in the Feed of Work when "Show all activity"
  is on.
- **OTEL spans** — set `APPLICATIONINSIGHTS_CONNECTION_STRING` in
  `.env` and spans export to Foundry Tracing (App Insights). Leave
  unset locally to keep `init_otel` a no-op.
- **Inject to trigger flow** — `POST /api/simulator/inject` (the
  simulator's domain-aware ramp loop also trickles workflows in
  automatically when the substrate is up).

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'src'` | Stale venv from pre-consolidation code | `rm -rf .venv && uv sync` |
| Functions host exits with `Could not load file or assembly ...` | Core Tools too old (4.0.5455) | Upgrade to v4.9+ |
| `func start` picks Python 3.13 then crashes | uv env dominates PATH | Activate `.funcvenv` first, or set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |
| `failed to schedule` on inject | Functions host not running | `make functions` |
| `azurite` refuses connections on 10000 | Docker/npm azurite not up | `make azurite-up` or `npm i -g azurite && azurite --silent --location azurite-data` |
| UI shows empty workflows | No stack / API proxy misrouted | Check `VITE_API_BASE_URL` in `.env`; default is `http://localhost:3101` |

## ⚠️ Not safe for public exposure (yet)

This is a **proof of concept**. It must NOT be bound to a public network
interface (no public Azure App Service ingress, no Container App with
external ingress enabled, no exposing port `3101` outside `localhost`).
A `POC_UNSAFE_FOR_PUBLIC_DEPLOY=1` marker lives at
[`.poc-safety`](../.poc-safety) at the repo root so any future CI guard
can fail a deployment manifest that wires a public ingress while that
marker is still present.

### Still-unsafe surfaces

| Surface | Why it's unsafe | Code path | Plan |
|---|---|---|---|
| `find_by_pattern` raw-Cypher MCP tool | Lets a tool caller execute arbitrary Cypher fragments against the substrate graph | [`api/server/mcp_tools/find_entities.py`](../api/server/mcp_tools/find_entities.py), [`api/server/services/entity_graph.py`](../api/server/services/entity_graph.py) (`find_by_pattern`) | C2 (pending) — see [`plan/refactor-repo-coherence-remediation-1.md`](../plan/refactor-repo-coherence-remediation-1.md) |
| `POST /api/durable-event` internal route | Mutates Durable Functions state with no HMAC / actor check | [`api/server/routes/internal_durable_event.py`](../api/server/routes/internal_durable_event.py) | C4 (pending) — see [`plan/refactor-repo-coherence-remediation-1.md`](../plan/refactor-repo-coherence-remediation-1.md) |
| Persona `decision_policy` `exec()` / `eval()` loader | Compiles + `exec()`s YAML-loaded Python from `data/personae/*` — code-execution surface coupled to a data file | [`api/server/services/persona_responder.py`](../api/server/services/persona_responder.py) (`compile(..., "exec")` / `exec(code, ...)`) | Master-plan persona-loader review/replacement (pending) |

### Hardening switches that exist today

| Env flag | Gates | Default |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | Browser-facing CORS allowlist; no wildcard-with-credentials (C3, commit `5271fb94`) | empty / restrictive |
| `SERVICENOW_WEBHOOK_SECRET` | HMAC-signed ServiceNow webhook ingress (C5, commit `cb5b507c`) | unset → endpoint refuses |
| `FINANCE_BP_WEBHOOK_SECRET` | HMAC-signed Finance Business Partner webhook ingress (C5, commit `cb5b507c`) | unset → endpoint refuses |
| `READ_ROUTE_AUTH` | Set to `enforce` to require an authenticated actor on `audit` / `evals` / `entities` / `cities` reads (C6, commit `c71f590c`) | off (local PoC) |

### Deployment gate

Any public binding (Azure App Service public ingress, Container App with
public ingress, exposing port `3101` outside `localhost`) requires **all**
of the following:

1. **C2 complete** — `find_by_pattern` raw-Cypher MCP tool removed or
   gated. See [`plan/refactor-repo-coherence-remediation-1.md`](../plan/refactor-repo-coherence-remediation-1.md).
2. **C4 complete** — `POST /api/durable-event` requires HMAC. See
   [`plan/refactor-repo-coherence-remediation-1.md`](../plan/refactor-repo-coherence-remediation-1.md).
3. **All hardening switches in enforce mode** — `CORS_ALLOWED_ORIGINS`
   set to a non-wildcard origin list, both webhook secrets set,
   `READ_ROUTE_AUTH=enforce`.
4. **Persona loader review/replacement complete** — the
   `exec()`/`eval()` surface in `persona_responder.py` either removed,
   sandboxed, or replaced with a declarative policy DSL.
5. **`.poc-safety` marker removed** — delete the
   `POC_UNSAFE_FOR_PUBLIC_DEPLOY=1` line in
   [`.poc-safety`](../.poc-safety) (or delete the file). A CI guard
   should fail any deployment manifest with public ingress while that
   marker is present.

## Helper scripts

In `scripts/`:

| Script | Purpose |
|---|---|
| `boot-demo.sh` | What `make up` runs — boots azurite + POC1 mocks + FastAPI + control-plane UI + portal + functions in one terminal |
| `run-fastapi-blueprint.sh` | Backgrounded uvicorn on `:3101` with no access log; pairs with `npm run dev:blueprint` when iterating on the microsite |
| `blueprint-ticker.sh` | Drives synthetic blueprint events for visual smoke-testing |
| `build-blueprint-image.sh` | `az acr build` of the blueprint container into `blueprintacrapexdemo` |
| `deploy-blueprint.sh` | Proof-gated wrapper around `azd up` — requires `ZAVA_MODE=replay`, tenant verification, and all proof artefacts. Deploys the full read-only replay ACA application, not an nginx-only microsite. See [blueprint-microsite-contributor-guide.md §Deploying to Azure](blueprint-microsite-contributor-guide.md#deploying-to-azure) |
| `profile-autonomous.sh`, `profile-friday.sh` | Profiling helpers for the autonomous demo loop |
| `preclassify_corpus.py` | One-shot preclassification of the 300-claim accuracy corpus |
| `generate_blueprint_image.py` | Renders the social/preview image for the blueprint page |
| `generate_cv_pdfs.py` | Generates the synthetic CV corpus for POC2 |
| `prewarm_avatar.py` | Warms the avatar render cache before a POC2 demo |
