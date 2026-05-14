# Plans

Living implementation plans for the Zava control-plane PoC.

## Active

Plans currently being executed or queued for work. Each carries a `status:` header (`Planned`, `In progress`, `Shipped`).

| File | Status | Summary |
|---|---|---|
| [feature-enterprise-pitch-readiness-1.md](feature-enterprise-pitch-readiness-1.md) | Planned | Living simulator: tiny-but-real Zava agency you can spin up and leave for hours. Centre of gravity is **Tracks H + I + J** (cross-domain entanglement, learning loops, longitudinal observability). Foundation tracks A + B gate everything. Pass criteria measured in emergent behaviour, not entity counts. ~67 todos in session SQL with `pitch-` prefix. |
| [refactor-repo-coherence-remediation-1.md](refactor-repo-coherence-remediation-1.md) | In progress | 6-track repo coherence sweep — sharded-rel reader bug, doc honesty, security guardrails, cosmic-lens humanization (Track F), frontend stabilisation, cleanup. Tracked in session SQL. Per-task detail for Track F lives in the archived `archive/feature-humanize-cosmic-lens-1.md`. |
| [feature-foundry-credibility-friday-1.md](feature-foundry-credibility-friday-1.md) | In progress | Foundry tracing + real cost telemetry + immutable audit blob. |
| [feature-agent365-identity-bridge-1.md](feature-agent365-identity-bridge-1.md) | Planned | Microsoft 365 identity bridge for personae. |
| [feature-poc3-ai-agency-1.md](feature-poc3-ai-agency-1.md) | Planned | POC3 — agency-of-agents engagement model. |

## Archive

Shipped / completed plans kept for historical context. **Do not read these as current state** — implementation has landed and the codebase has moved on. See [archive/README.md](archive/README.md) for the index.

## Conventions

- **Filenames:** `feature-<slug>-<n>.md` for new features, `refactor-<slug>-<n>.md` for refactors. The trailing `-<n>` allows a successor plan if the topic recurs.
- **Status header:** every plan carries a YAML-ish `status:` line and a Shields.io badge near the top so the row in this README is grep-derivable.
- **Move to archive when:** all phases ship and the plan's "Update YYYY-MM-DD" line confirms `Shipped` / `Completed`. Use `git mv plan/foo.md plan/archive/foo.md` so history is preserved, then update cross-references (the plans frequently cite each other and active docs cite plans).
- **Cross-refs from archive:** sibling plans that have ALSO been archived stay as `[name](name.md)`; sibling plans still in `plan/` need `[name](../name.md)`. Repo-relative paths inside an archived plan need an extra `../` level (`../api/...` → `../../api/...`).
