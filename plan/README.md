# Plans (legacy location)

**This folder is no longer the active home for implementation plans.**

New work uses the superpowers convention:

- **Specs** (the "what & why") live in [`docs/superpowers/specs/`](../docs/superpowers/specs/) as `YYYY-MM-DD-<name>-design.md`.
- **Plans** (the executable "how", with TDD checkbox tasks) live in [`docs/superpowers/plans/`](../docs/superpowers/plans/) as `YYYY-MM-DD-<name>.md`.

Plans in the new location are designed for subagent execution via `superpowers:subagent-driven-development` and follow the `writing-plans` skill format (TDD steps, real code in every step, exact commands, no placeholders).

## What lives here now

Only [`archive/`](archive/) — historical plans kept for reference. Do not read them as current state; the codebase has moved on.

If you want the index of archived plans, see [`archive/README.md`](archive/README.md).

## Why we moved

Two competing plan formats had grown side by side (REQ/TASK spec-style here vs TDD-checkbox superpowers in `docs/superpowers/plans/`). One standard, one location is easier to find, easier to execute, easier for subagents to pick up.
