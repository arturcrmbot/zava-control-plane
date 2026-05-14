# Zava Control Plane — Apex Substrate

[![OWASP Agentic AI Top 10 — 10/10 covered](https://img.shields.io/badge/OWASP%20Agentic%20Top%2010-10%2F10%20covered-brightgreen)](plan/archive/feature-agent-governance-toolkit-1.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status: PoC — runs on a laptop](https://img.shields.io/badge/status-PoC%20%E2%80%94%20runs%20on%20a%20laptop-blue)](#-safe-to-clone--run-locally--gated-for-public-deploy)

A composable agentic substrate (skills + MCP tools + harness + governance)
running on a single laptop, with multiple business domains composed on
top of it. Production-shaped — [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework)
durable workflows for orchestration, GHCP SDK Python for agent identities,
a long-lived Fleet Manager session supervising exceptions in real time.

**14 live domains in `main`, plus 5 strategic placeholders for future
graduation.** Two were hand-built (POC1 finance, POC2 hiring); twelve were
graduated end-to-end by the
[`compose-domain`](docs/superpowers/skills/compose-domain/SKILL.md) meta-skill
(v3) over a single weekend. The five `stub=True` placeholders
(hire-to-productive, vendor-risk-to-pay, lead-to-cash, fy-close, board-prep)
appear in the org-clone surface but are not spawned at runtime — graduate
them via `compose-domain` when ready. Every per-domain integration fact
(workflow_type, prefix, orchestrator, persona gates, persona, operator surface,
wake hints, spawner, realistic cadence) lives in a single registry —
[`api/shared/domains.py`](api/shared/domains.py) — so the substrate's
generic layers read every domain at runtime instead of switching on
hard-coded literals.

| Domain | Where it lives | Status |
|---|---|---|
| **POC1** — Finance expense compliance | [`api/functions/workflows/expense_claim.py`](api/functions/workflows/expense_claim.py) — 7 phases | Live · 13 ACs, brief in [docs/archive/poc1-brief.md](docs/archive/poc1-brief.md) |
| **POC2** — HR talent lifecycle | [`api/functions/workflows/hiring.py`](api/functions/workflows/hiring.py) — 10 phases | Live · 22 capabilities, archived status in [docs/archive/poc2-status.md](docs/archive/poc2-status.md) |
| **Fleet travel pre-approval** | [`api/functions/workflows/fleet_travel_preapproval.py`](api/functions/workflows/fleet_travel_preapproval.py) — 3 phases | Composed · `compose-domain` v1; first existence proof |
| **Fleet vendor onboarding & KYC** | [`api/functions/workflows/fleet_vendor_kyc.py`](api/functions/workflows/fleet_vendor_kyc.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet employee onboarding** | [`api/functions/workflows/fleet_employee_onboarding.py`](api/functions/workflows/fleet_employee_onboarding.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet IT access request** | [`api/functions/workflows/fleet_it_access_request.py`](api/functions/workflows/fleet_it_access_request.py) — 5 phases | Composed · `compose-domain` v3 |
| **Fleet contract renewal** | [`api/functions/workflows/fleet_contract_renewal.py`](api/functions/workflows/fleet_contract_renewal.py) — 5 phases | Composed · `compose-domain` v3 |
| **Fleet performance review** | [`api/functions/workflows/fleet_perf_review.py`](api/functions/workflows/fleet_perf_review.py) — 5 phases | Composed · `compose-domain` v3 |
| **Fleet AP invoice** | [`api/functions/workflows/fleet_ap_invoice.py`](api/functions/workflows/fleet_ap_invoice.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet purchase order** | [`api/functions/workflows/fleet_purchase_order.py`](api/functions/workflows/fleet_purchase_order.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet contract review** | [`api/functions/workflows/fleet_contract_review.py`](api/functions/workflows/fleet_contract_review.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet privacy DPIA** | [`api/functions/workflows/fleet_privacy_dpia.py`](api/functions/workflows/fleet_privacy_dpia.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet treasury FX** | [`api/functions/workflows/fleet_treasury_fx.py`](api/functions/workflows/fleet_treasury_fx.py) — 4 phases | Composed · `compose-domain` v3 |
| **Creative campaign** | [`api/functions/workflows/creative_campaign.py`](api/functions/workflows/creative_campaign.py) — 10 phases | Composed · `compose-domain` v3 |

> The 5 `stub=True` placeholders (hire-to-productive, vendor-risk-to-pay,
> lead-to-cash, fy-close, board-prep) appear in the org-clone surface but
> aren't spawned at runtime — graduate them via `compose-domain` when ready.
> Each domain spawns at its own realistic cadence (`realistic_interval_seconds`
> in [`api/shared/domains.py`](api/shared/domains.py)) scaled by
> `DEMO_TIME_WARP_FACTOR` (default 60) — so AP-invoice spawns every ~30s of
> demo, perf-review effectively dormant. See [`.env.example`](.env.example).

The pitch behind this is captured in [docs/archive/blueprint.md](docs/archive/blueprint.md);
the live editorial microsite that visualises the substrate is
[`web/blueprint/`](web/blueprint/) (deployed to Azure Container Apps —
see the [contributor guide](docs/blueprint-microsite-contributor-guide.md)).

**Stack**
- Python 3.11 (Functions worker) + 3.13 (FastAPI) · FastAPI · Azure Durable Functions · MAF · GHCP SDK Python
- React 19 · Vite 6 · TailwindCSS 4 — three frontends: control plane, candidate portal, blueprint microsite
- 10 Node mock MCP servers (3 finance + 7 HR/comms — see `mocks/`)
- Microsoft Agent Governance Toolkit (AGT) v3.4 — in-process policy
  kernel mediating every MCP tool call, hash-chained signed audit
  ledger, Ed25519 per-agent identities, operator kill switches.
  See [plan/archive/feature-agent-governance-toolkit-1.md](plan/archive/feature-agent-governance-toolkit-1.md)
  for the full architecture; CI runs `agt verify` on every PR and
  publishes an `agt-evidence.json` artefact.

## 🟢 Safe to clone & run locally — gated for public deploy

This is a **proof of concept** designed to run on a single laptop. It
is safe to clone, read, and run on `localhost`. It must NOT be bound
to a public network interface (no public Azure App Service ingress, no
Container App with external ingress enabled, no exposing port `3101`
outside `localhost`) without first walking the [deployment gate](#deployment-gate)
below. A `POC_UNSAFE_FOR_PUBLIC_DEPLOY=1` marker lives at
[`.poc-safety`](.poc-safety) so any future CI guard can fail a
deployment manifest that wires a public ingress while that marker is
still present.

### Surface inventory

The PoC ships hardening for almost every surface a public deploy
would care about. Two of the three originally-listed "still-unsafe"
surfaces have shipped fixes; the third is sandboxed but not
formally hardened. Status:

| Surface | Status | Code path |
|---|---|---|
| `find_entities` MCP tool | ✅ **Hardened** — free-form Cypher removed; only registered, parameter-validated query templates accepted (commit `680282a9`) | [`api/server/mcp_tools/find_entities.py`](api/server/mcp_tools/find_entities.py), [`api/server/services/find_patterns.py`](api/server/services/find_patterns.py) |
| `POST /api/durable-event` internal route | ✅ **Hardened** — requires `X-Durable-Event-Signature` HMAC; secret in `DURABLE_EVENT_SECRET` (commit `07882946`) | [`api/server/routes/internal_durable_event.py`](api/server/routes/internal_durable_event.py), [`api/server/services/webhook_auth.py`](api/server/services/webhook_auth.py) |
| Persona `decision_policy` `exec()` loader | 🟡 **Sandboxed** — `__builtins__` replaced with a 15-symbol whitelist (`_DECISION_BUILTINS`) blocking `__import__`, `open`, `eval`, `exec`, `compile`, `getattr`/`setattr`/`delattr`. AST-level attribute whitelist (blocks `__class__`/`__mro__`/`__subclasses__` reflection escapes) is the next planned hardening pass. | [`api/server/services/persona_responder.py`](api/server/services/persona_responder.py) (`_DECISION_BUILTINS` line 434) |

### Hardening switches that exist today

| Env flag | Gates | Default |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | Browser-facing CORS allowlist; no wildcard-with-credentials (C3, commit `5271fb94`) | empty / restrictive |
| `SERVICENOW_WEBHOOK_SECRET` | HMAC-signed ServiceNow webhook ingress (C5, commit `cb5b507c`) | unset → endpoint refuses |
| `FINANCE_BP_WEBHOOK_SECRET` | HMAC-signed Finance Business Partner webhook ingress (C5, commit `cb5b507c`) | unset → endpoint refuses |
| `DURABLE_EVENT_SECRET` | HMAC-signed `POST /api/durable-event` ingress (C4, commit `07882946`) | unset → endpoint refuses |
| `READ_ROUTE_AUTH` | Set to `enforce` to require an authenticated actor on `audit` / `evals` / `entities` / `cities` reads (C6, commit `c71f590c`) | off (local PoC) |

### Deployment gate

Any public binding (Azure App Service public ingress, Container App
with public ingress, exposing port `3101` outside `localhost`)
requires **all** of the following:

1. **All hardening switches in enforce mode** — `CORS_ALLOWED_ORIGINS`
   set to a non-wildcard origin list, both webhook secrets set,
   `READ_ROUTE_AUTH=enforce`, `DURABLE_EVENT_SECRET` set.
2. **Persona loader hardening complete** — the AST-level attribute
   whitelist landed in `persona_responder.py` (next planned pass) so
   sandbox-escape reflection paths (`__class__`/`__mro__`/
   `__subclasses__`) are blocked at compile time, not only at
   builtins-replacement time.
3. **`.poc-safety` marker removed** — delete the
   `POC_UNSAFE_FOR_PUBLIC_DEPLOY=1` line in [`.poc-safety`](.poc-safety)
   (or delete the file). A CI guard should fail any deployment
   manifest with public ingress while that marker is present.

## Ports

| Service                       | Port        | What |
|-------------------------------|-------------|------|
| Vite — Control Plane UI       | 5273        | Domain-neutral operator surface |
| Vite — Candidate Portal       | 5274        | POC2 candidate-facing app + recruiter view |
| Vite — Blueprint microsite    | 5275        | Editorial page + live observatory (local dev) |
| FastAPI                       | 3101        | Fleet Manager, simulator, REST, SSE, blueprint stream |
| Functions host                | 7071        | Durable orchestrators + activities |
| Azurite                       | 10000-10002 | Durable state |
| Mock MCPs (POC1 finance)      | 4101-4103   | Workday, Concur, Maconomy |
| Mock MCPs (POC2 HR + comms)   | 4201-4207   | Greenhouse, LinkedIn, Workday-HR, Graph, ServiceNow, ACS, HeyGen |

## Quickstart

Prerequisites: Python 3.11 + 3.13, Node 20+, [`uv`](https://astral.sh/uv),
Azure Functions Core Tools v4.9+, Docker (for Azurite — or `npm i -g azurite`),
GitHub Copilot license (`gh auth login`).

```bash
make install                                   # uv sync + npm install (root, web/portal, web/blueprint)
make funcvenv                                  # Windows: one-time Py 3.11 venv for func
cp local.settings.json.example local.settings.json
cp .env.example .env
gh auth login
make up                                        # boots azurite + POC1 mocks + FastAPI + control-plane UI + portal + functions
```

UI at http://localhost:5273, candidate portal at http://localhost:5274.
The simulator's domain-aware ramp loop trickles real workflows from
all 14 live domains into the dashboard automatically when the substrate
is up, each at its own realistic cadence (AP-invoice ~every 30s of demo,
hiring ~every 24min, perf-review effectively dormant — see
[`api/shared/domains.py`](api/shared/domains.py); tune via
`DEMO_TIME_WARP_FACTOR`). The
[persona responder](api/server/services/persona_responder.py) resolves
every persona gate autonomously — there is no human in the loop. A
small per-gate `wait_probability` produces visual variety (the gate
takes a moment to resolve) but never requires an operator click;
personae can also return an `escalate` verdict for high-risk inputs,
which produces an enriched FM exception for visibility.
The blueprint microsite runs separately
(`npm run dev:blueprint` → http://localhost:5275); see the
[contributor guide](docs/blueprint-microsite-contributor-guide.md).

For POC2 mocks (hiring demo): `npm run dev:mcp:poc2` in another
terminal.

## Layout

```
api/     — Python: FastAPI + Durable Functions + MAF graphs + skills + personae + MCP tools
web/
  client/    — Control Plane UI (operator surface, domain-neutral)
  portal/    — Candidate portal + recruiter view (POC2)
  blueprint/ — Editorial microsite + live observatory of the substrate
mocks/   — 10 Node MCP servers (3 finance + 7 HR/comms)
tests/   — pytest (api/), vitest (web/), Playwright (e2e/)
docs/    — see docs/README.md for the full index
scripts/ — boot-demo.sh, build-blueprint-image.sh, deploy-blueprint.sh, profile-*.sh, blueprint-ticker.sh
```

Root-level configs (`pyproject.toml`, `package.json`, `host.json`,
`function_app.py`, `vite.config.ts`, `Makefile`, `docker-compose.yml`)
serve the whole repo.

## More

- [docs/README.md](docs/README.md) — index of every doc in this repo + what each is for
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — what the system is + why it's built this way
- [docs/ADD-A-DOMAIN.md](docs/ADD-A-DOMAIN.md) — how to extend it (manual → compose-domain meta-skill)
- [docs/visualisation.md](docs/visualisation.md) — what you'll see (`?view=constellation` / `entities` / `functions` / `org-clone`), the visual vocabulary, plus contributor guide
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local dev, terminals, debugging
- [docs/blueprint-microsite-contributor-guide.md](docs/blueprint-microsite-contributor-guide.md) — making new domains light up on the page + the Azure Container Apps deploy
- [docs/superpowers/skills/compose-domain/SKILL.md](docs/superpowers/skills/compose-domain/SKILL.md) — meta-skill that graduates new domains

## Stop

`Ctrl-C` the `make up` terminal. In-memory Fleet Manager + simulator state
clears; Durable Functions state persists in `azurite-data/`. `make reset`
wipes it between demo takes.
