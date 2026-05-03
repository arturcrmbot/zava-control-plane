# Design-time skills

> ⚠️ **Read this before adding anything here.**
>
> The SKILL.md files in this directory are **design-time tooling**. They run
> in the engineer's IDE / Copilot session against the repo. They MUST NOT be
> loaded into a runtime GHCP session — they are not domain skills, they are
> skills that *write* domain skills.
>
> The runtime SDK reads only `api/server/skills/`
> ([`api/functions/graphs/executors/agents/_wrapper.py`](../../../api/functions/graphs/executors/agents/_wrapper.py)
> sets `_SKILLS_DIR = …/server/skills`). Anything under
> `docs/superpowers/skills/` is invisible to runtime sessions by construction.
>
> **Forbidden:**
> - Copying any SKILL.md from this tree into `api/server/skills/`.
> - Symlinking from `api/server/skills/` into this tree.
> - Adding this tree to any `skill_directories` argument.
>
> If you want a runtime version of any of these (e.g. a customer-environment
> `skill-author` that runs inside the harness), that is a separate engagement
> with its own sandboxing, validators, identity scope, and CI gate. See the
> microsite section 6 for the design.

## What's here

| Skill | Role |
|---|---|
| `compose-domain/` | Orchestrator. Reads a brief, plans the artefact set, calls sub-skills, writes a sandbox snapshot. Entry point. |
| `author-runtime-skill/` | Sub-skill. Writes one runtime SKILL.md (phase agent or persona). Shape-isomorphic to existing skills under `api/server/skills/`. |
| `author-mcp-tool/` | Sub-skill. Writes one in-process Python MCP tool stub. Shape-isomorphic to existing tools under `api/server/mcp_tools/`. |
| `author-durable-domain/` | Sub-skill. Writes the Durable orchestrator file, activity functions, per-phase MAF graphs, and validators. Shape-isomorphic to `expense_claim.py` and friends. |

## How to invoke

In a Copilot session, ask the agent:

> Run `compose-domain` against
> `docs/superpowers/specs/fleet-holiday-brief.yaml`.

The agent reads `compose-domain/SKILL.md` and follows it literally.

## How to iterate the skill itself

When a generated sandbox looks wrong, **fix the SKILL.md, not the
sandbox**. The whole point is to make the procedure reliable. Then delete
the sandbox run and re-invoke. Two runs against the same brief should diff
to nothing meaningful.

## Sandbox

Generated artefacts go to `tools/scratch/compose-domain/<run-id>/` (gitignored).
Nothing in this skill set ever writes to `api/server/`, `api/functions/`,
`function_app.py`, or any other live tree on its own. Graduation into the
real trees is a separate manual step against
`compose-domain/CHECKLIST.md` §"Graduation".
