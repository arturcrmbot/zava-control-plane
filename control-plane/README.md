# WPP Control Plane v1

Working Control Plane demo for the WPP RFP response, built on GHCP SDK.

## Quickstart

```bash
gh auth login          # if not already authenticated; needs Copilot license
cp .env.example .env   # only PORT vars matter; auth comes from `gh auth token`
npm install
npm run dev
```

- UI: http://localhost:5173
- API: http://localhost:3001
- Mock MCP servers: :4101 (workday), :4102 (d365), :4103 (maconomy), :4104 (payment)

## Auth

Fleet Manager uses your **personal GitHub Copilot license** via `gh auth token` at server boot. No Azure Foundry credentials needed. If `gh auth token` fails, the server still boots — only the Fleet Manager agent is skipped.

## Architecture

See [docs/superpowers/specs/2026-04-13-wpp-control-plane-v1-design.md](../docs/superpowers/specs/2026-04-13-wpp-control-plane-v1-design.md).

Three tiers:
1. **Fleet Manager** — always-on `@github/copilot-sdk` session. Subscribes to in-process EventBus; debounces + coalesces triggering events; calls 5 MCP tools (`query-fleet`, `query-traces`, `compose-exception`, `propose-skill-amplification`, `dry-run-policy`); streams reasoning + tool calls to UI right rail via SSE.
2. **Workflow orchestration** — deterministic 6-phase lifecycle (Intake → Validation → Routing → Approval → Payment → Reconciliation), running 30–50 concurrent invoices, calling 4 mock MCP servers, emitting OTEL-shaped events.
3. **Mock MCP servers** — 4 small Express services backed by JSON fixtures (workday vendors/cost centres, d365 POs/GL, maconomy projects, payment gateway with first-call timeout simulation).

## Inject demo scenarios

```bash
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"duplicate-invoice"}'
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"sanctions-flag"}'
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"po-mismatch"}'
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"threshold-exceeded"}'
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"payment-timeout"}'
curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"compliance"}'
```

## Layout

```
control-plane/
├── src/
│   ├── shared/        # types, events, policies.yaml
│   ├── client/        # React UI (App, routes, components, hooks)
│   └── server/        # Express + GHCP SDK + simulator
│       ├── services/  # eventBus, stateStore, triage, simulator, fleetManagerService, sseHub, etc.
│       ├── mcp-tools/ # Fleet Manager's 5 MCP tools
│       ├── routes/    # /api/workflows, /api/exceptions, /api/policy, /api/stream/*, etc.
│       ├── skills/    # fleet-manager.skill.md
│       └── fixtures/  # vendors, POs, agencies, policy refs
├── mocks/             # 4 mock MCP servers (workday, d365, maconomy, payment)
├── tests/unit/        # vitest, 20 tests
├── spike/             # Phase 0.2 SDK de-risk artefacts
└── docs/              # demo-script.md
```

## Stop

Ctrl-C. All state is in-memory; next `npm run dev` starts fresh.

## Scope notes

- POC1 (Finance P2P) only. POC2 (HR hiring) views are out of scope for v1 — architecture supports it via role switcher.
- No persistence across restarts.
- No production auth — local single-operator implicit identity.
- Cuttable screens (Analytics, Evaluations) are present but lightweight.
