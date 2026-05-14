# `scripts/demos/` — pre-recorded fast-forward scenarios (pitch-g2)

Four scripted scenarios that produce **named demo snapshots**. Each
script is run **once** during demo prep against a live local stack; the
operator then restores the resulting snapshot at demo time so the cosmic
lens, conversations and HUD all light up immediately — no waiting for
the simulator ramp loop.

Underlying mechanism: each script POSTs to the existing
`/api/simulator/*` inject endpoints, lets the simulator settle for a
few seconds, then calls `make snapshot-save NAME=<scenario>` (which
delegates to `scripts/zava-snapshot.py`). The bundle lands in
`data/snapshots/<scenario>.tgz`.

## Build flow (one-time, demo prep)

```bash
# 1. start the stack (in another terminal, or background it)
make up

# 2. wait until http://localhost:3101/api/kpis/agency responds, then
#    run the scenario builder you want
python scripts/demos/build-morning-peak.py
python scripts/demos/build-vendor-crisis.py
python scripts/demos/build-cfo-month-end-push.py
python scripts/demos/build-creative-awards-week.py

# 3. (optional) tear the stack down — the snapshot is now persisted on disk
make down
```

The scripts will abort with a clear error if the stack is not reachable
on `http://localhost:3101`. They do **not** start or stop the stack.

## Restore at demo time

`scripts/boot-demo.sh` already supports `BOOT_DEMO_SNAPSHOT=<name>` —
when set, it restores `data/snapshots/<name>.tgz` before FastAPI
starts. So at demo time:

| Scenario | Restore command |
| --- | --- |
| `morning-peak` — heavy AP-invoice + onboarding flow at 09:00 | `BOOT_DEMO_SNAPSHOT=morning-peak make up` |
| `vendor-crisis` — 3 vendors flag KYC red simultaneously (triggers I2 auto-block) | `BOOT_DEMO_SNAPSHOT=vendor-crisis make up` |
| `cfo-month-end-push` — 50+ contract-review approvals queued | `BOOT_DEMO_SNAPSHOT=cfo-month-end-push make up` |
| `creative-awards-week` — wave of creative-campaign + media-pitch activity | `BOOT_DEMO_SNAPSHOT=creative-awards-week make up` |

You can also restore manually against an existing stack (Kuzu must not
be locked — stop the API process first):

```bash
make snapshot-restore NAME=morning-peak
```

## Listing & introspection

```bash
make snapshot-list                # lists data/snapshots/*.tgz with metadata
ls -lh data/snapshots/            # raw bundle sizes
```

## Adding a new scenario

1. Copy one of the existing `build-*.py` scripts as a template.
2. Pick a kebab-case `SCENARIO` name; that becomes the snapshot
   filename and the value to set in `BOOT_DEMO_SNAPSHOT`.
3. Inject the workflows via `/api/simulator/*` (see
   `api/server/routes/simulator.py` for the available endpoints).
4. Document the scenario in the table above.

## Caveats

- Snapshots are **not** stack-version-portable. Rebuild them after any
  schema migration in `data/portal/entity_graph.kuzu/`.
- The scripts are intentionally idempotent at the HTTP level (each
  POST spawns a new workflow) — running a builder twice doubles the
  workload the snapshot captures. Delete the previous bundle first
  (`rm data/snapshots/<scenario>.tgz`) if you want a clean rebuild.
