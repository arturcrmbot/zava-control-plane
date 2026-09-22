# Zava Bank — demo runbook

The banking vertical, how to record it, and how to present it without
depending on a model quota on the day.

## The rule

**Record once, live. Present from replay.**

Replay makes zero model requests, so it cannot rate-limit, stall mid-run, or
vary between takes. Live agent work is the thing you prove *on camera once*,
not the thing you gamble a thirty-minute slot on. This mirrors the
composer's guidance in
[compose-demo-runbook.md](compose-demo-runbook.md): *"Every demo: replay
(bulletproof)."*

---

## 1. One-time: record the banking tape

Preconditions:

- **clean tree** — `record_tape.sh` stamps `ZAVA_APP_SHA` and marks a dirty
  tape unpublishable;
- **healthy model quota** — every live banking process does real agent work,
  so a tape recorded against an exhausted quota records failures;
- `.env` has `ZAVA_VERTICAL=banking` and `LLM_RUNTIME=ghcp`.

```bash
# Autonomy must be ON or the tape records an empty organisation.
sed -i '' 's/^SIMULATOR_RAMP_ENABLED=0/SIMULATOR_RAMP_ENABLED=1/' .env

DURATION=30m OUT=tapes/banking.tar.gz \
  MEMORY_DOMAINS=app-fraud-reimbursement \
  scripts/record_tape.sh
```

While it runs, in a second terminal, drive the hero so the governed human
decision is *inside* the tape:

```bash
# the approved path
curl -X POST localhost:3101/api/world/scenarios/synthetic-app-fraud-claim
# the vulnerability protection
curl -X POST localhost:3101/api/world/scenarios/synthetic-app-fraud-vulnerable
# the refusal — governance denies and names the escalation target
curl -X POST localhost:3101/api/world/scenarios/synthetic-app-fraud-over-delegation
```

Approve the hero gate through the operator surface (or
`POST /api/exceptions/<id>/resolve` with `{"resolution":"approve"}`), so the
tape contains a human decision rather than an auto-close.

Commit the tape.

## 2. Every demo: replay

```bash
ZAVA_MODE=replay ZAVA_TAPE_PATH=tapes/banking.tar.gz make up
curl -s localhost:3101/api/replay/meta    # mode=replay, pack_matches_tape=true
```

`pack_matches_tape` must be `true`. If it is `null` or `false` the tape was
recorded against a different pack and the surfaces will disagree with the
organisation on screen.

---

## 3. Configuration that matters

| Setting | Demo value | Why |
|---|---|---|
| `ZAVA_VERTICAL` | `banking` | selects the pack |
| `LLM_RUNTIME` | `ghcp` | uses the `gh` CLI token; `aoai` needs a correct Azure tenant |
| `SIMULATOR_RAMP_ENABLED` | `1` | the autonomy switch — `0` means nothing spawns |
| `PERSONA_AUTO_CLOSE` | `financial_crime_lead,payments_operations_lead` | the bank runs itself; the hero decision waits for a human |

Model requests are metered. Supporting cadence is deliberately bounded to
one case every 90 and 120 demo-seconds; opening background cases faster
starves the hero's own agent session. For a busier steady state, move to a
runtime with its own quota rather than speeding up the ramp.

---

## 4. The walk

| Time | Show | Say |
|---|---|---|
| 0:00 | Constellation, seven planets | Seven functions of one bank, each its own colour. Nothing here is a slide. |
| 0:03 | Rockets moving, cases opening | Nobody pressed anything. The ramp loop opens real cases continuously. |
| 0:06 | A rocket parked at a persona city | That is a human gate, rendered as a place. Work waits for a person. |
| 0:10 | Hero: the £18,400 claim | Follow one claim. Two deterministic phases, then a real agent phase. |
| 0:14 | The agent's tool calls | `claim-evidence-assessor` called both declared tools. That is recorded evidence, not a caption. |
| 0:17 | Approve the gate | The agent ranked. The human decides. Watch the typed command fire. |
| 0:20 | World mutation + evaluation | £18,400 reimbursed, £6,100 recovered, £9,200 as the receiving provider's half-share. |
| 0:23 | The vulnerable claim | Refusal was never admitted — the deterministic layer refused it, and no ranking can resurrect it. |
| 0:26 | The £92,000 claim | Capped at £85,000, still above the manager's delegation. Governance refuses *and names who can*. |
| 0:29 | `SYN-CORP-014` | The mule account belongs to the same client carrying the wholesale exposure. Two ends of one bank. |

## 5. What not to claim

- This is **not build ready**. The `VERTICAL-PROOF.md` §3 replay probes and
  the live/replay parity pass are outstanding, and no seller review has
  happened.
- Every record is synthetic. No threshold, limit or policy here describes a
  real institution.
- The supporting processes hold no actor-world records, so they mutate no
  world state. Say so rather than implying they do.

## 6. Reset between takes

```bash
make reset          # wipes Durable state
bash scripts/down-demo.sh && make up
```

In replay there is nothing to reset — restart the stack and the tape plays
from the top.
