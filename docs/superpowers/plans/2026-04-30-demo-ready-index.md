# Index — Demo-ready by 2026-05-08

Five parallelisable streams to land both POCs end-to-end live to WPP next Friday. Each plan below is independently dispatchable (subagent-driven-development pattern) and produces working software on its own.

**Master spec:** [../specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md)

| # | Stream | Plan | Heaviest? | Depends on |
|---|---|---|---|---|
| 1 | Candidate portal | [candidate-portal-plan.md](2026-04-30-candidate-portal-plan.md) | yes | none |
| 2 | Voice real (s2s accelerator) | [voice-real-plan.md](2026-04-30-voice-real-plan.md) | yes | accelerator path; #1 Vite scaffold (loose) |
| 3 | Avatar real (Azure AI Speech) | [avatar-real-plan.md](2026-04-30-avatar-real-plan.md) | medium | AZURE_SPEECH_REGION env var; #1 blob_store.py (already landed) |
| 4 | AG-UI render (POC2 §4.21) | [ag-ui-render-plan.md](2026-04-30-ag-ui-render-plan.md) | small | none |
| 5 | POC1 Foundry corpus run (AC #4) | [poc1-foundry-corpus-run-plan.md](2026-04-30-poc1-foundry-corpus-run-plan.md) | small (ops-heavy) | Azure Foundry provisioning |

## Suggested fan-out

```
Today / Friday        Stream 5 starts (provisioning + pre-classify is wall-clock-bound)
                      Stream 1 starts (no blockers)
                      Stream 4 starts (no blockers)

Mon                   Stream 2 starts (after user shares accelerator path; Phase 0 first)
                      Stream 3 starts (Azure Speech resource provisioned + AZURE_SPEECH_REGION set)

Mon-Wed               5 streams running in parallel; subagents dispatched per task
Thu                   Integration — full hire walk-through end-to-end
Fri                   Dry run + screenshots + tag v1.0-poc2-frontier
```

## Coordination points (avoid subagent collisions)

| File | Owner | Notes |
|---|---|---|
| `api/server/main.py` | Stream 1 (router registration) | Streams 2/3 add their routes via PRs against the version Stream 1 lands |
| `api/server/services/blob_store.py` | Stream 1 (Task 3) | Stream 3 consumes; if Stream 3 starts before Stream 1's Task 3, Stream 3 lands `blob_store.py` itself |
| `web/portal/src/routes/Screen.tsx` | Stream 1 places stub (Task 12); Stream 2 fills content (Task 3) | Coordinate via stub→fill, not concurrent edits |
| `data/synthetic/hiring/cvs/*.json` | Stream 4 hand-authors `component_spec` for 3 fixtures | No conflict with other streams |
| `.env.example` | All streams append; merge serially | Diff-friendly file |
| `docs/poc1-status.md`, `docs/SCOPE-DELTA.md` | Stream 5 final-state edit | Last edit wins; minor coordination |

## Cut order if behind (from master spec §10)

1. AG-UI render (Stream 4) — narrate against the existing primitive
2. POC1 corpus iterations beyond first pass (Stream 5) — accept first-pass accuracy if ≥90%
3. Avatar real (Stream 3) — fall back to canned mp4 (existing `mocks/heygen-mcp` stays in repo as the fallback path; renamed only conceptually)
4. Portal `/screen` route (Stream 2 frontend) — voice falls back to canned `acs-mcp` mock
5. Voice real (Stream 2 backend) — keep canned transcript mock; narrate s2s accelerator against architecture

## Definition of done (demo readiness)

- [ ] Stream 1: candidate portal boots; apply → triage → magic link → status pages all work
- [ ] Stream 2: candidate completes a real voice screen via portal; Phase 6 advances
- [ ] Stream 3: Phase 10 produces a real Azure Speech avatar mp4; portal plays it
- [ ] Stream 4: WorkflowDetail shows agent-emitted scorecards for hiring workflows
- [ ] Stream 5: AC #4 ≥95% (or first-pass accuracy if cut) captured in baseline JSON
- [ ] `docs/poc2-DEMO.md` updated with portal/voice/avatar beats inserted into the 22-capability walkthrough
- [ ] Demo dry run rehearsed against the actual demo machine + accounts
