# Zava Bank — demo runbook

The banking vertical: how to boot it, walk it on both screens, and keep it
safe on a metered model quota.

## The rule

**Present live. Keep the tape as the constellation fallback.**

Both screens need the live world. The world is deterministic and costs no
model quota; only agent work is metered. Replay cannot carry the demo alone:
it runs without the world and is read-only, so the control-plane floor would
be empty and the stories could not start.

---

## 1. Quota hygiene — the only real risk

Every agent step runs on the Copilot account behind `gh auth token`, and any
other Copilot use of that account counts against the same limit.

- **Rest the account** for a couple of hours before the slot.
- **Keep the ramp slow**: `DEMO_TIME_WARP_FACTOR=15` opens a mule case about
  every 6 minutes and a merchant case about every 8, so the organisation stays
  visibly busy without spending the budget the stories need.
- **"Spawn 8 cases" opens eight real mule and merchant cases at once** — eight
  agent sessions. Press it only if the budget can take it.
- **Symptom of exhaustion**: a claim card reads `Workflow failed · …` and the
  Durable history says *"rate limit … try again in N minutes"*. The agent
  activity is retried once after 10 s, and each attempt already retries a hung
  session internally; that absorbs a blip, not a limit.
  Switch the constellation to the tape (section 5).

## 2. Boot (T-30 minutes)

`.env`:

| Setting | Demo value | Why |
|---|---|---|
| `ZAVA_VERTICAL` | `banking` | selects the pack |
| `LLM_RUNTIME` | `ghcp` | uses the `gh` CLI token; `aoai` needs a correct Azure tenant |
| `SIMULATOR_RAMP_ENABLED` | `1` | the autonomy switch — `0` means no supporting cases open |
| `DEMO_TIME_WARP_FACTOR` | `15` | supporting-case cadence (section 1) |
| `PERSONA_AUTO_CLOSE` | `*` | synthetic demo: every gate is decided by its persona within delegated authority; nobody approves by hand |
| `MEMORY_BACKEND` | `fallback` | in-process memory; the configured Azure OpenAI endpoint rejects embeddings, so `auto` loses every write |

```bash
bash scripts/down-demo.sh && make up
curl -s 'localhost:3101/api/world/state?compact=true' | jq '.enabled, .bank.payments_settled_total'
curl -s localhost:3101/api/personas/narrative-arcs | jq -r '.[].name'   # the bank's six decision-makers
# memory is in-process, so seed it on every boot (no model calls)
for f in verticals/banking/demo/memory-seed-round1.json verticals/banking/demo/memory-seed-round2.json; do
  curl -s -X POST localhost:3101/api/memory/v2/seed-demo -H 'content-type: application/json' --data @"$f"; done
```

Open both screens:

- constellation — <http://localhost:5275/?view=constellation>
- control plane — <http://localhost:5273/world>, or **Open control plane →**
  at the constellation's bottom-left

Expect Payments, Credit and Markets alive with events per minute, the other
four functions dimmed until work arrives, and the floor reading *No fraud
claims raised*. Let the ramp open a case or two before the first story: the
first model sessions after a cold start can fail authentication once, and
the retry absorbs it off stage rather than on it.

## 3. The walk

| Time | Screen | Show | Say |
|---|---|---|---|
| 0:00 | Constellation | Three planets with events/min | Seven functions of one bank. Three are running it right now — payments settling, exposures revalued, positions marked — with no workflow involved. |
| 0:03 | Constellation | The cast panel | The bank's own decision-makers, each owning a function. |
| 0:05 | Floor | Rails, settlements, credit, markets | The same world as an operations floor. Nothing here is a slide. |
| 0:07 | Floor | **APP fraud claim · £18,400** | A customer reports a scam. Watch Retail banking flare on the constellation — the world raised a signal. |
| 0:09 | Floor | Chain: claim raised → case opened → agents investigating | A real agent is reading the claim evidence and ranking the admitted options. |
| 0:12 | Floor | Chain: decision approved | The agent ranked; the fraud decision manager persona approved within its £50,000 delegation, and the decision names the rule. |
| 0:15 | Floor | Chain completes | £18,400 reimbursed; the mule account traced to `SYN-CORP-014`, a corporate client. |
| 0:18 | Floor | **Vulnerable customer · £6,750** | Refusal was never admitted — the deterministic layer refused it, and no ranking can resurrect it. |
| 0:22 | Floor | **Over-delegation · £92,000** | Capped at £85,000, still above the manager's £50,000 delegation. *Refused by authority · needs Financial crime lead* — governance refuses and names who can. |
| 0:26 | Constellation / Knowledge | Decisions and the entity graph | Every decision is recorded; the mule account and the wholesale exposure are two ends of one bank. |

## 4. Reset between takes

The workflow store and memory are in-process: restarting the API empties the
feed and memory (re-seed memory afterwards). Between takes reset only the
world, which keeps the feed's history. Show history with the feed's **All
activity**; *All my decisions today* lists only decisions made by hand in this
browser, and with personas deciding every gate it stays empty.

A story runs once per world. Start a fresh world (claims dormant again):

```bash
curl -X POST localhost:3101/api/world/reset
```

Full reset, including Durable state: `make reset`, then
`bash scripts/down-demo.sh && make up`.

## 5. Fallback: the tape (constellation only)

```bash
bash scripts/down-demo.sh
ZAVA_MODE=replay ZAVA_TAPE_PATH=tapes/banking.tar.gz make up
curl -s localhost:3101/api/replay/meta    # pack_matches_tape must be true
```

The constellation replays the recorded organisation with zero model
requests. The control plane is read-only in replay and its world floor is
empty; present the floor from the live take instead.

## 6. Recording the tape

Only with a healthy quota and a clean tree (`record_tape.sh` stamps
`ZAVA_APP_SHA` and marks a dirty tape unpublishable). It boots its own stack,
so stop the running one first.

```bash
bash scripts/down-demo.sh
sed -i '' 's/^SIMULATOR_RAMP_ENABLED=0/SIMULATOR_RAMP_ENABLED=1/' .env
DEMO_TIME_WARP_FACTOR=15 DURATION=30m OUT=tapes/banking.tar.gz \
  MEMORY_DOMAINS=app-fraud-reimbursement \
  MEMORY_SEED_ROUND1=verticals/banking/demo/memory-seed-round1.json \
  MEMORY_SEED_ROUND2=verticals/banking/demo/memory-seed-round2.json \
  scripts/record_tape.sh
```

Without the seed files the recorder seeds hiring memories, which do not
belong in a bank. While it runs, start the three stories a few minutes
apart and approve each hero gate through **Review & decide** (or
`POST /api/exceptions/<id>/resolve` with `{"resolution":"approve"}`), so the
tape holds human decisions rather than auto-closes. Check the over-delegation
story ends in *Refused by authority*, not *Workflow failed*.

Tapes are gitignored (`/tapes/`), so they live on disk and are not carried by
a clone.

### Recorded tape

`tapes/banking.tar.gz` — `tape_e1752da7`, 30 minutes, 12,478 events, app SHA
`f6028d4c`, `pack_fingerprint banking:1:3885135132db92aa`. It holds all three
stories: the approved £18,400 claim (its first attempt, at the cold start,
failed and was re-run after a world reset), the vulnerable claim, and the
over-delegation refusal naming `financial_crime_lead`; 11 agent sessions, 14
persona decisions and 10 human-gate resumes. `tapes/banking-tape2-backup.tar.gz`
is the previous take, whose over-delegation story failed on the model quota
before reaching governance.

## 7. What not to claim

- This is **not build ready**. The `VERTICAL-PROOF.md` §3 replay probes and
  the live/replay parity pass are outstanding, and no seller review has
  happened.
- Every record is synthetic. No threshold, limit or policy here describes a
  real institution.
- The supporting processes hold no actor-world records, so they mutate no
  world state. Say so rather than implying they do.
- Memory holds the seeded decision notes, but the dream pass distils no
  lessons here: memory runs on the in-process fallback without an Azure
  OpenAI endpoint. Do not claim learned lessons.
