# WPP Control Plane — POC1 (Finance Expense Compliance)

Production-shaped demo of a 7-phase expense compliance pipeline driven by
[Microsoft Agent Framework](https://learn.microsoft.com/agent-framework)
durable workflows, with a GHCP-SDK-powered Fleet Manager supervising
every exception in real time.

Brief: [docs/poc1-brief.md](docs/poc1-brief.md). Status + canonical
architecture: [docs/poc1-status.md](docs/poc1-status.md).

**Stack**
- Python 3.11 · FastAPI · Azure Durable Functions · MAF · GHCP SDK Python
- React 19 · Vite 6 · TailwindCSS 4
- Node mock MCP servers (Workday, SAP Concur, Maconomy)

## Ports

| Service         | Port        |
|-----------------|-------------|
| Vite (UI)       | 5173        |
| FastAPI         | 3001        |
| Functions host  | 7071        |
| Azurite         | 10000-10002 |
| Mock MCPs       | 4101-4103   |

## Quickstart

Prerequisites: Python 3.11 + 3.13, Node 20+, [`uv`](https://astral.sh/uv),
Azure Functions Core Tools v4.9+, Docker (for Azurite — or `npm i -g azurite`),
GitHub Copilot license (`gh auth login`).

```bash
make install                                   # uv sync + npm install
make funcvenv                                  # Windows: one-time Py 3.11 venv for func
cp local.settings.json.example local.settings.json
cp .env.example .env
gh auth login
make up                                        # boots the full stack in one terminal
```

UI at http://localhost:5173. The simulator ramps expense-claim workflows
into the dashboard automatically when `SIMULATOR_TARGET_WORKFLOWS` is set.

## Layout

```
api/     — Python: FastAPI + Durable Functions + MAF graphs + skills
web/     — React 19 + Vite 6 UI
mocks/   — Node MCP servers (Workday, Concur, Maconomy)
tests/   — pytest (api/), vitest (web/), Playwright (e2e/)
docs/    — poc1-brief, poc1-status, ARCHITECTURE, DEVELOPMENT, DEMO
scripts/ — boot-demo.sh
```

Root-level configs (`pyproject.toml`, `package.json`, `host.json`,
`function_app.py`, `vite.config.ts`, `Makefile`, `docker-compose.yml`)
serve the whole repo.

## More

- [docs/poc1-status.md](docs/poc1-status.md) — canonical state, acceptance criteria, what's left
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — three tiers + how events flow
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local dev, terminals, debugging
- [docs/DEMO.md](docs/DEMO.md) — demo scenarios + expected UI flow

## Stop

`Ctrl-C` the `make up` terminal. In-memory Fleet Manager + simulator state
clears; Durable Functions state persists in `azurite-data/`. `make reset`
wipes it between demo takes.
