# Implementation plans

This is the canonical location for executable implementation plans in this repo.

> **Working on the dream-pass?** Start at [2026-05-19-dream-pass-overview.md](2026-05-19-dream-pass-overview.md) for the ordered pickup list and dependency graph across the 7 related plans.

## Convention

- **Filename**: `YYYY-MM-DD-<feature-name>.md` (date first, lowercase kebab-case name).
- **Format**: superpowers `writing-plans` — required header, checkbox-tracked tasks (`- [ ]`), real code in every step, exact commands, no placeholders. See [`~/.copilot/installed-plugins/superpowers-marketplace/superpowers/skills/writing-plans/SKILL.md`](../../../../.copilot/installed-plugins/superpowers-marketplace/superpowers/skills/writing-plans/SKILL.md) for the full skill spec.
- **Related specs**: longer-form design documents live in [`../specs/`](../specs/) as `YYYY-MM-DD-<name>-design.md`. A plan should link back to its spec in its header.
- **Multi-phase work**: one plan file per phase, named `YYYY-MM-DD-<feature>-phase-N-<topic>.md`. Each phase plan should produce working, testable software on its own.

## Execution

- **Subagent-driven** (recommended): use `superpowers:subagent-driven-development`. One subagent per task, two-stage review between tasks.
- **Inline**: use `superpowers:executing-plans` to step through tasks in the current session.

## Where the old plans went

The previous `/plan/` folder used a different (REQ/TASK spec-style) format. It is now archive-only — see [`/plan/README.md`](../../../plan/README.md) for the explanation and [`/plan/archive/`](../../../plan/archive/) for the historical content.

## Current plans

```
ls docs/superpowers/plans/*.md
```
