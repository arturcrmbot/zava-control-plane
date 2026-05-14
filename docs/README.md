# Docs

Six docs. That's it. Anything else is either generated from code, lives
in `superpowers/`, or has been retired to `archive/`.

| If you want… | Read |
|---|---|
| What the system is + why it's built this way | [ARCHITECTURE.md](ARCHITECTURE.md) |
| How to add a new business domain | [ADD-A-DOMAIN.md](ADD-A-DOMAIN.md) |
| How to run / hack on this locally | [DEVELOPMENT.md](DEVELOPMENT.md) |
| How the cosmic-lens visualisation works (and how to extend it) | [visualisation.md](visualisation.md) |
| How to ship the public blueprint microsite | [blueprint-microsite-contributor-guide.md](blueprint-microsite-contributor-guide.md) |
| The compose-domain meta-skill (the one a coding agent runs to add a domain) | [superpowers/skills/compose-domain/SKILL.md](superpowers/skills/compose-domain/SKILL.md) |

## What's NOT a doc

The substrate is mostly self-documenting. Don't write a doc for any of
these — they live next to the code that owns them:

| Topic | Source of truth |
|---|---|
| Domain registry (37 domains, integration facts per domain) | [`api/shared/domains.py`](../api/shared/domains.py) |
| Function ownership (10 functions × their domains) | [`api/shared/functions.py`](../api/shared/functions.py) |
| Persona registry (79 personae + display colours) | [`api/shared/personas.py`](../api/shared/personas.py) + [`api/server/personae/<role>/SKILL.md`](../api/server/personae/) |
| Live skill list | Walked from `api/server/skills/*/SKILL.md` at boot, surfaced by `GET /api/blueprint/composition` |
| Live MCP tool list | Walked from `api/server/mcp_tools/*.py` at boot, surfaced by the same route |
| Ports + quickstart | Root [`README.md`](../README.md) |

## `superpowers/`

| Path | Contents |
|---|---|
| [`superpowers/skills/`](superpowers/skills/) | The author / compose meta-skills agents use to extend the substrate (`compose-domain`, `compose-persona`, `author-runtime-skill`, etc.) |
| [`superpowers/specs/`](superpowers/specs/) | Live design specs (most recent first). Older specs are in `superpowers/specs/archive/`. |
| [`superpowers/plans/`](superpowers/plans/) | Active implementation plans. Executed plans are in `superpowers/plans/archive/`. |

## `archive/`

Historical docs kept for audit only — the bid-era POC briefs, status
snapshots, pitch manuscripts, demo runbooks, the Plane 1 design doc.
**Do not read as current state.** See [archive/README.md](archive/README.md).
