# Visual Domain Composer — demo runbook

The composer lives at `?view=compose` in the blueprint microsite. Two modes:
a **live** mode (a real `copilot` agent composes a new domain) and a **replay**
mode (a recorded compose plays back through the same cockpit — deterministic,
fast, demo-safe). Localhost-only, `.poc-safety`-gated.

## One-time: record the tape (real compose)

1. Fresh checkout / clean tree: `git status` shows nothing.
2. `bash scripts/boot-demo.sh` (COMPOSE_RECORD=1 is the default; API :3101,
   Functions host :7071, blueprint :5275). PIDs are written to `.compose/`.
3. Open `http://localhost:5275/?view=compose`, drop the prepared capex process
   doc (it contains one deliberate ambiguity so a question fires).
4. Answer the question, approve the brief, let it graduate + verify, then Ignite.
5. Confirm the domain is live:
   `curl -s localhost:3101/api/blueprint/composition | grep <workflow_type>`.
6. A tape now exists under `data/compose-recordings/`. Commit it *and* the
   graduated domain so the replay's Ignite→lens handoff is real.

## Every demo: replay (bulletproof)

- Deep link (hands-free): `http://localhost:5275/?view=compose&replay=<tape>.jsonl`
- Or the intake screen → **"Replay a recorded compose"** → pick the tape →
  optionally uncheck **hands-free** to click through the question yourself.
- Ignite pans to the cosmic lens; because the domain was really graduated when
  the tape was recorded, the planet is genuinely present. Real footage, zero
  risk of a mid-run agent stall.

## Live mode (real authoring, for actual work)

- Same intake screen — drop a doc and let it run (5–12 min). Localhost +
  **throwaway machine** only (`COMPOSE_PERMISSION_POLICY=autopilot` runs the
  agent with `--allow-all`). Not recommended on-camera unless you have time and
  a clean tree to reset between takes.

## Knobs

| Env | Default | Meaning |
|---|---|---|
| `COMPOSE_RECORD` | `1` | Auto-save a tape when a real run finishes. |
| `COMPOSE_PERMISSION_POLICY` | `autopilot` | `autopilot` (`--allow-all`) or `in_repo_only` (stricter). |
| `COMPOSE_MODEL` | `claude-sonnet-4.6` | Model the compose agent runs on. |
| `COMPOSE_MCP_URL` | `http://127.0.0.1:3101/api/compose/mcp` | Where the agent reaches the compose-bridge MCP. |

## Reset between takes

`git checkout . && git clean -fd api/ function_app.py` (drops a live-composed
domain), then re-`boot-demo.sh`. `make reset` wipes Durable state.
