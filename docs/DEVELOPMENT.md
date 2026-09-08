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
make test-harness      # focused, offline presales harness contracts
make test-e2e          # Playwright (requires `make up` in another terminal)
```

`make test-harness` covers pack registration/packaging, checkpoint delivery,
validation and terminal outcomes, required-tool evidence, supervisor batching,
feed action cancellation, prefixed SPA navigation, and release provenance.
It uses installed dependencies without syncing
them, synthetic stores, mocked providers and callback/memory boundaries. The
delivery cases use HTTP transport mocks rather than bypassing the client.
Live-state and replay cohorts run in separate processes to avoid their
import-time state configurations interfering.

This is a regression gate, not proof of production failover, live-model quality,
or complete industry modelling. Image-copy checks do not replace building and
starting the canonical container when Docker is available.

Live checkpoint callbacks require the same `DURABLE_EVENT_SECRET` in FastAPI and
the Functions worker. Delivery/authentication failures now stop the checkpoint
instead of being silently accepted. Optional trace delivery remains best-effort.
Feed Undo cancels only an unsent action; once dispatch begins it is unavailable,
and pending actions are not restored as completed history after a reload.

### Container verification before publishing

On macOS, a missing Docker socket can mean the existing Colima profile is
stopped. Start it without deleting or resetting its disks:

```bash
colima start --profile default
docker version
docker build --platform linux/amd64 --progress=plain \
  -f deploy/Dockerfile -t zava-control-plane:local .
```

The AMD64 build matches the deployment target. A successful unit suite or image
build alone is not a runtime proof: the built image must start, serve the UI and
runtime APIs, and pass browser checks for the selected live or replay mode.
Do not proceed to publication after a failed build or startup.

If package downloads fail during TLS negotiation, compare the exact URL from
the build log on the host and inside the Linux base image. If both fail while
the package index works, restore network/VPN access or use an approved package
mirror. Do not disable certificate verification or relabel that build as passed.

The Dockerfile accepts an alternate HTTPS index without changing `uv.lock`:

```bash
docker build --platform linux/amd64 --progress=plain \
  --build-arg PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg NPM_REGISTRY=https://repo.huaweicloud.com/repository/npm/ \
  -f deploy/Dockerfile -t zava-control-plane:local .
```

The example mirror serves the same pinned wheel bytes; the build exports frozen
requirements and enforces their hashes during installation. The default remains
PyPI. `NPM_REGISTRY` similarly overrides the download registry while all three
frontends use `npm ci` and their checked-in integrity hashes. The build invokes
the installed Vite binary rather than allowing `npx` to fetch an unlocked
replacement. These are build-local choices, not machine-wide network settings.

For a loopback-only replay preview of the tape baked into that image:

```bash
docker run --rm --name zava-replay-local -p 127.0.0.1:8080:80 \
  -e ZAVA_MODE=replay -e ZAVA_VERTICAL=agency \
  -e PORTAL_DATA_DIR=/tmp/zava-replay \
  -e MEMORY_BACKEND=fallback -e LLM_RUNTIME=fake \
  -e ENTITY_GRAPH_BUFFER_POOL_MB=256 \
  -e ENTITY_GRAPH_MAX_DB_SIZE_MB=4096 \
  zava-control-plane:local
```

The two graph settings are deliberately separate. The buffer pool controls
working memory; the optional maximum DB size bounds Kuzu's address-space
reservation. Kuzu's default 8 TiB reservation caused an actual OOM when running
the AMD64 image through QEMU on Apple Silicon. A 4096 MiB limit permits the
small demo graph to open there. Unset or zero retains the library default;
do not copy this capacity limit into a larger deployment without sizing it.

The container pins Azure Functions Core Tools **4.9.0-1** and pre-caches
extension bundle **4.17.0**, verified by SHA-256, rather than depending on the
CLI's first-boot connectivity probe. For **local AMD64/QEMU live execution
only**, pass `-e ZAVA_FUNCTIONS_QEMU_COMPAT=1`. This disables .NET's W^X mapping
in the Functions subprocess to avoid the observed emulation/reflection
failure; native deployments retain the default protection. Replay does not
start Functions and needs neither that opt-in nor Azurite.

In live mode the entrypoint supervises both Functions and Uvicorn: either
child exiting stops the container and its owned worker processes. An API
health response alone is not a Durable proof. Also require Functions host
state `Running` and an actual workflow completion with its instance ID and
observable outcome. A boot-only overlay can demonstrate that boundary, but
does not prove that a subsequent full-source image was built successfully.

In another terminal, inspect the actual runtime rather than just the container
process:

```bash
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/api/runtime
curl -fsS http://127.0.0.1:8080/api/replay/meta
curl -fsS -H 'Accept: text/html' http://127.0.0.1:8080/portal/recruiter
```

Open `/`, `/blueprint/`, and `/portal/recruiter` in a browser, then reload the
portal deep link. Packaged portal navigation stays under `/portal/`; the
standalone Vite app still uses `/`. Set `PORTAL_PUBLIC_URL` to the externally
reachable portal root **including `/portal`** when the backend generates
candidate links. Unknown `/api/*` and `/assets/*` must remain errors, not
HTML success responses. In replay, a POST to `/api/workflows` must return 403.

Before a public release, commit the intended source, obtain fresh live/replay
proof for that exact commit and selected vertical, and complete the
operator-owned seller review. Generate and verify `proof/public-replay.json`
with `tools/public_replay_manifest.py`; do not edit a PASS into the manifest.
Then use the existing proof-gated `scripts/deploy-blueprint.sh` path with
`ZAVA_MODE=replay` and the explicitly selected tenant. The wrapper refuses stale
source, missing evidence, or incomplete review before deployment.

Committing reviewed source is a checkpoint, not permission to deploy. Do not
hold all source changes uncommitted while investigating a machine-specific
build issue; record the remaining image/release gate explicitly.

`public-replay.json` schema 2 binds the full source commit, vertical, pack
fingerprint, and SHA-256 digests of the tape, machine proof, and seller review.
The tape's `app_sha`, `selected_vertical`, and `pack_fingerprint` must agree
with the proof. Missing metadata, short SHAs, different packs, and
dirty-development proof are rejected. `scripts/record_tape.sh` now stamps the
full commit and adds `-dirty` for uncommitted source; that recording remains
usable locally but cannot approve a release. Legacy tapes remain readable,
not silently upgraded into current evidence.

Keep old evidence under `proof/archive/` and old recordings under
`tapes/archive/`, outside the image build context. The pre-harness Fashion
proof is archived at `proof/archive/2026-07-27-fashion-dirty/`; its historical
PASS results do not approve an Agency release. The May 28 Agency tape is
preserved under `tapes/archive/pre-harness/`. Do not fix freshness by renaming
a tape, changing its date, or editing PASS into a JSON file.

**Container evidence from September 8, 2026:** the canonical image built from
`3fe95702` served all three browser surfaces, including portal deep-link reload.
A real deterministic Telco Durable run rerouted 184 sessions and recovered
SITE-03; terminating Functions stopped the whole live container and finalized
the recording. Local evidence is under `proof/harness/source-3fe95702/`.
This is shared-harness evidence, not an Agency seller-story approval.

The older historical-replay container exhausted its **4 GiB memory limit after
about 131 minutes**. Replay was still subscribed to the live entity and
meta-workflow reflectors. Every tape cycle re-ran graph writes and minted new
governance/audit evidence. A six-cycle reproduction grew from 335 MiB to
2,563 MiB; a minimal Kuzu write probe reproduced native memory retention.

Replay now leaves those live reflectors unsubscribed. Recorded workflow
mutations and event delivery continue; live mode retains its projections.
Twelve accelerated full-tape cycles stayed at about 410 MiB after warmup.
This is a replay isolation fix, not a claim that sustained write-heavy Kuzu
workloads are bounded. A normal-speed container soak is a separate release
gate and must not be inferred from accelerated coverage.

Format-v1 tapes restore workflow, phase, span, tool-call, memory and audit
snapshot data. They do **not** reconstruct a historical entity graph or actor
world. The Knowledge surface shows the selected pack's seed graph, not
recomputed decisions attributed to the old recording. Capture any live graph
outcome separately and keep that limitation explicit in the seller review.

Run a single file:

```bash
uv run pytest tests/api/unit/test_events.py -v
npm test -- tests/web/types.test.ts
npx playwright test tests/e2e/smoke.spec.ts --reporter=list
```

Layout:

| Path | Framework | What |
|---|---|---|
| [tests/api/](../tests/api/) | pytest | Python unit and integration tests |
| [tests/web/](../tests/web/) | vitest | TS shared-types and events |
| `web/**/__tests__/` | vitest | Frontend components and hooks |
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

## Live deployment safety

Writable live mode remains a localhost/private demonstration, not an approved
unauthenticated public service. The authoritative surface inventory, hardening
switches, and remaining live deployment gate are in
[README.md](../README.md#deployment-gate). The old raw-Cypher and unsigned
Durable-callback findings are not current: query templates and HMAC callback
authentication already exist. This does not certify the rest of the live API.

Leave [`.poc-safety`](../.poc-safety) in place. Public read-only replay is a
different mode and must pass the
[source/tape/proof/review gates above](#container-verification-before-publishing).
Its write rejection does not authorize exposing writable live mode.

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
