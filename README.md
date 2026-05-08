# Zava Control Plane — Apex Substrate

[![OWASP Agentic AI Top 10 — 10/10 covered](https://img.shields.io/badge/OWASP%20Agentic%20Top%2010-10%2F10%20covered-brightgreen)](plan/feature-agent-governance-toolkit-1.md)

A composable agentic substrate (skills + MCP tools + harness + governance)
running on a single laptop, with multiple business domains composed on
top of it. Production-shaped — [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework)
durable workflows for orchestration, GHCP SDK Python for agent identities,
a long-lived Fleet Manager session supervising exceptions in real time.

**Eight domains live in `main`.** Two were hand-built (POC1 finance,
POC2 hiring); six were graduated end-to-end by the
[`compose-domain`](docs/superpowers/skills/compose-domain/SKILL.md)
meta-skill (v3) over a single weekend. Every per-domain integration
fact (workflow_type, prefix, orchestrator, HITL gates, persona,
operator surface, wake hints) lives in a single registry —
[`api/shared/domains.py`](api/shared/domains.py) — so the substrate's
generic layers (Fleet Manager skill text, simulator spawners, exception
resolve route, blueprint inventory) read every domain at runtime
instead of switching on hard-coded literals.

| Domain | Where it lives | Status |
|---|---|---|
| **POC1** — Finance expense compliance | [`api/functions/workflows/expense_claim.py`](api/functions/workflows/expense_claim.py) — 7 phases | Live · 13 ACs, brief in [docs/poc1-brief.md](docs/poc1-brief.md), status in [docs/poc1-status.md](docs/poc1-status.md) |
| **POC2** — HR talent lifecycle | [`api/functions/workflows/hiring.py`](api/functions/workflows/hiring.py) — 10 phases | Live · 22 capabilities, status in [docs/poc2-status.md](docs/poc2-status.md), demo in [docs/poc2-DEMO.md](docs/poc2-DEMO.md) |
| **Fleet travel pre-approval** | [`api/functions/workflows/fleet_travel_preapproval.py`](api/functions/workflows/fleet_travel_preapproval.py) — 3 phases | Composed · `compose-domain` v1; first existence proof |
| **Fleet vendor onboarding & KYC** | [`api/functions/workflows/fleet_vendor_kyc.py`](api/functions/workflows/fleet_vendor_kyc.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet employee onboarding** | [`api/functions/workflows/fleet_employee_onboarding.py`](api/functions/workflows/fleet_employee_onboarding.py) — 4 phases | Composed · `compose-domain` v3 |
| **Fleet IT access request** | [`api/functions/workflows/fleet_it_access_request.py`](api/functions/workflows/fleet_it_access_request.py) — 5 phases | Composed · `compose-domain` v3 |
| **Fleet contract renewal** | [`api/functions/workflows/fleet_contract_renewal.py`](api/functions/workflows/fleet_contract_renewal.py) — 5 phases | Composed · `compose-domain` v3 |
| **Fleet performance review** | [`api/functions/workflows/fleet_perf_review.py`](api/functions/workflows/fleet_perf_review.py) — 5 phases | Composed · `compose-domain` v3 |

The pitch behind this is captured in [docs/blueprint.md](docs/blueprint.md);
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
  See [plan/feature-agent-governance-toolkit-1.md](plan/feature-agent-governance-toolkit-1.md)
  for the full architecture; CI runs `agt verify` on every PR and
  publishes an `agt-evidence.json` artefact.

## Ports

| Service                       | Port        | What |
|-------------------------------|-------------|------|
| Vite — Control Plane UI       | 5173        | Domain-neutral operator surface |
| Vite — Candidate Portal       | 5174        | POC2 candidate-facing app + recruiter view |
| Vite — Blueprint microsite    | 5175        | Editorial page + live observatory (local dev) |
| FastAPI                       | 3001        | Fleet Manager, simulator, REST, SSE, blueprint stream |
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

UI at http://localhost:5173, candidate portal at http://localhost:5174.
The simulator's domain-aware ramp loop trickles real workflows from
all eight domains into the dashboard automatically when the substrate
is up; the [persona responder](api/server/services/persona_responder.py)
closes HITL gates per the configured `PERSONA_AUTO_CLOSE` allow-list
(personae now support a third `escalate` verdict for high-risk inputs,
which leaves the gate open and produces an enriched FM exception).
The blueprint microsite runs separately
(`npm run dev:blueprint` → http://localhost:5175); see the
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
- [docs/CODEBASE-TOUR.md](docs/CODEBASE-TOUR.md) — narrative walkthrough for first-time visitors
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — three tiers + how events flow + the multi-domain pattern
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local dev, terminals, debugging
- [docs/DEMO.md](docs/DEMO.md) — POC1 demo (also points at POC2 + blueprint runbooks)
- [docs/blueprint.md](docs/blueprint.md) — the pitch this whole substrate carries
- [docs/blueprint-microsite-contributor-guide.md](docs/blueprint-microsite-contributor-guide.md) — making new domains light up on the page + the Azure Container Apps deploy
- [docs/superpowers/skills/compose-domain/SKILL.md](docs/superpowers/skills/compose-domain/SKILL.md) — meta-skill that graduates new domains

## Stop

`Ctrl-C` the `make up` terminal. In-memory Fleet Manager + simulator state
clears; Durable Functions state persists in `azurite-data/`. `make reset`
wipes it between demo takes.
