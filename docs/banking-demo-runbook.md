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
- **The world spends quota on its own.** With the living world on (section
  2b+), customers ring the bank and the world opens up to
  `BANKING_WORLD_CASES_PER_HOUR` (default 10) cases an hour, two of them
  straight after boot. Unclear judgements add up to
  `JUDGEMENT_LLM_BUDGET_PER_HOUR` (default 6) deep reviews an hour. Run
  `make down` whenever you are not presenting.
- **"Spawn 8 cases" opens eight real cases at once** — eight agent sessions.
  Press it only if the budget can take it.
- **Symptom of exhaustion**: a claim card reads `Workflow failed · …` and the
  Durable history says *"rate limit … try again in N minutes"*. The agent
  activity is retried once after 10 s, and each attempt already retries a hung
  session internally; that absorbs a blip, not a limit.
  Switch the constellation to the tape (section 5).
- **Symptom of a busy account**: sessions slow down instead of failing. A case
  sits in *Assess Claim Evidence* for about five minutes, then the retry
  decides it. Seen on 2026-09-28 with five agent sessions running at once;
  every case completed.

## 2. Boot (T-30 minutes)

`.env` (gitignored; these are the demo values, and `.env.example` ships with
Laya off):

| Setting | Demo value | Why |
|---|---|---|
| `ZAVA_VERTICAL` | `banking` | selects the pack |
| `LLM_RUNTIME` | `ghcp` | uses the `gh` CLI token; `aoai` needs a correct Azure tenant |
| `PERSONA_AUTO_CLOSE` | `*` | synthetic demo: every gate is decided by its persona within delegated authority; nobody approves by hand |
| `MEMORY_BACKEND` | `fallback` | in-process memory; the configured Azure OpenAI endpoint rejects embeddings, so `auto` loses every write |
| `JUDGEMENT_ENABLED` | `1` | personas read each case with Laya before deciding (section 2a) |
| `LAYA_URL` | `http://127.0.0.1:8765` | where Laya listens; `make up` starts it here |
| `BANKING_WORLD_SCREENING` | `1` | the bank screens payments and opens mule cases itself (section 2b) |
| `BANKING_WORLD_LIFE` | `1` | about 200 customers live in the world and open cases (section 2b+) |
| `SIMULATOR_RAMP_ENABLED` | `0` | the living world opens cases itself; `1` adds timer-driven supporting cases on top |
| `DEMO_TIME_WARP_FACTOR` | `15` | cadence of those timer-driven cases, if the ramp is on |

```bash
bash scripts/down-demo.sh && make up
curl -s 'localhost:3101/api/world/state?compact=true' | jq '.enabled, .bank.payments_settled_total'
curl -s localhost:3101/api/judgement/status   # "enabled": true, "laya": {"available": true}
curl -s localhost:3101/api/personas/narrative-arcs | jq -r '.[].name'   # the bank's six decision-makers
# memory is in-process, so seed it on every boot (no model calls)
for f in verticals/banking/demo/memory-seed-round1.json verticals/banking/demo/memory-seed-round2.json; do
  curl -s -X POST localhost:3101/api/memory/v2/seed-demo -H 'content-type: application/json' --data @"$f"; done
```

`make up` also:

- **starts Laya** when `LAYA_URL` points at this machine and it is not
  already running (`~/.copilot/skills/laya/scripts/start.sh`; set
  `LAYA_START_SCRIPT` to use another), and waits up to 45 s for it. If it
  cannot, it says so and the rules decide instead. `make down` stops the Laya
  it started and leaves one you started yourself running.
- **rebuilds the control-plane bundle** when any of its sources is newer than
  `dist/`, so a pull or merge never serves yesterday's UI.

Open both screens:

- constellation — <http://localhost:5275/?view=constellation>
- control plane — <http://localhost:5273/world>, or **Open control plane →**
  at the constellation's bottom-left

Expect Payments, Credit and Markets alive with events per minute and the other
functions dimmed until work arrives. The World page opens on *Zava Bank* and
five steps (customers, fraudsters target them, some are caught out, the bank
finds out, investigated and decided), filling up as the world runs. Let a case
or two open before the first story: the first model sessions after a cold
start can fail authentication once, and the retry absorbs it off stage rather
than on it.

## 2a. Persona judgement (on in the demo config)

With judgement on, each persona reads the case before deciding instead of only
checking the amount. Laya is a small local model: it answers narrow questions
about the agent's reasoning in about 50-300 ms, at no token cost. Code then
checks those answers against the record, and Laya weighs the concerns in the
persona's character: approve, or hold and hand the case up. The rules
(`decision_policy`), admission and the governance kernel still set the
ceiling. Laya can hold a case, but it can never approve one the rules would
not.

`make up` starts Laya (section 2). To run it by hand, for example between
takes with the stack down:

```bash
LAYA_PORT=8765 ~/.copilot/skills/laya/scripts/start.sh   # run in the background; ready in ~5-15 s
curl -s localhost:8765/health                             # {"status": "ok", "device": "mps", ...}
```

`.env` (both the API and the Functions host read it):

| Setting | Value | Why |
|---|---|---|
| `JUDGEMENT_ENABLED` | `1` | personas with a `judgement:` profile read each case; over-authority claims go to who can decide |
| `LAYA_URL` | `http://127.0.0.1:8765` | where Laya listens; empty means the rules decide (and say so) |
| `JUDGEMENT_LLM_BUDGET_PER_HOUR` | `6` | unclear judgements go to an LLM deep review, at most this many an hour, on the same Copilot quota |
| `JUDGEMENT_GATE_DEADLINE_S` | `180` (default) | a gate is judged within this, hand-ups included; if deep reviews are queued, the late ones are decided by the rules and say so |

What judgement changes:

| Moment | With judgement on |
|---|---|
| A claim within delegation | The fraud decision manager reads the agent's reasoning. The chain shows *Fraud decision manager approved*, marked *quick check*, with the concerns it found, if any. |
| A contradiction | If the agent's reasoning contradicts the record (e.g. says "no vulnerability marker" for a flagged customer), the manager holds it and hands it to the financial crime lead, who decides. Both steps show on the chain. |
| A refusal | A refusal is never waved through on its £0 value: refusals always get a second pair of eyes. |
| At the top of the chain | The last persona can send the case back to the agent with its reasons. The agent re-assesses once and the gate is raised again; the chain shows *sent it back to the agent*, then *approved after re-assessment*. |
| A claim above delegation | It no longer dead-ends. Governance names the financial crime lead, who decides within a £250,000 delegation (a claim over £85,000 is capped first). The chain shows *Decision approved · … · by Financial crime lead*. |

Fallbacks are automatic and recorded on the decision:
- Laya down or slow (2 s timeout; after three failures it is skipped for 30 s): the rules decide.
- Deep-review budget spent or the LLM failing: the rules decide.

Every decision records who decided (Laya, an LLM deep review or the rules; the floor
says *quick check*, *closer review* or *standard rules*), each
question with its probabilities, the lead over the runner-up, and the
threshold. It shows in the drawer and in `persona.judgement` events. Laya needs
about 3 GB of memory; stop it after the slot.

## 2b. The world notices (on in the demo config; best with Laya)

With `BANKING_WORLD_SCREENING=1` the bank screens the payments it sees:
- New payments arrive with references, and Laya matches each against described
  scam patterns. The floor's *Payments the bank flagged* panel lists them.
- Flagged payments from two or more customers into one account open a mule
  investigation through a world sensor, so mule cases stop arriving on a timer.
  **Mule activity detected** now makes such payments land.
- The disposition changes the account: *restrained* stops it receiving, and
  *monitored* can reopen it. Merchant reviews still change nothing in the world.
- Customers react to reimbursement decisions (accepted, chased, complained).
- Merchant applications describe the business, and the risk band is read from it.

With Laya down, keyword rules screen and rules pick reactions, and each event says
so. The cadence is set by `BANKING_NEW_PAYMENT_MINUTES` (default 30 synthetic
minutes) and `BANKING_SCAM_SHARE` (default 0.35). At the demo speed that opens a
mule case every few minutes.

## 2b+. People live in the world (on in the demo config; needs Laya)

With `BANKING_WORLD_LIFE=1` about 200 named customers live in the bank. They spend on
what fits who they are (Laya picks, from their profile and the time of day), get paid,
pay rent, and sometimes something happens to them. Scam crews pick tactics from what
worked, and each target's caution is read by Laya from who they are; the bank's
warning and the scam's fit do the rest. Victims realise, ring the bank, and the claim
runs through the hero path. New customers join; some leave after a refusal.

The floor becomes a page a banker can follow. It opens on *Zava Bank* and five steps:
customers, fraudsters target them, some are caught out, the bank finds out,
investigated and decided. Then *Why customers did what they did* (each choice with
Laya's probabilities), *What's happening*, *Losses nobody has reported yet*, *What the
bank hasn't been told*, *Criminal groups*, *How the bank responded* (the cases, each
openable) and *Steer the world*. Laya is named once, in the folded *How this simulation
works*, with its numbers: its share of customer choices, and the managers' decisions
split into quick checks, closer reviews and standard rules.

The world opens at most `BANKING_WORLD_CASES_PER_HOUR` (default 10) cases on its own,
two of them straight after boot, so the agents' Copilot quota stays predictable.

## 2c. Steer it live (under *Steer the world*)

- **Make something happen.** **Fraud claim reported**, **High-value claim** and
  **Vulnerable customer claim** each raise a new claim with drawn facts, and the kind
  only shapes those facts; the outcome still comes from admission, the agent,
  governance and the persona. **Mule activity detected** makes suspicious payments
  land; with screening on, a mule case opens once the bank flags them.
  **Merchant risk flagged** opens a merchant review. Every click is a new case.
- **A customer calls about a payment.** Pick any recent payment on the floor and type
  what the customer says. The bank raises a claim on that payment and the whole hero
  path runs on it. A first impression of the words (Laya's reading) shows next to it and is advisory: the
  record decides vulnerability, and the rules decide what is permitted. The list of
  payments holds still while you choose; press ↻ for newer ones. The bank refuses a
  call while the same customer or receiving account already has a case being
  decided, and says so: wait for that decision, then call again. For the same
  reason, a story waits while a called claim on its account is being decided.
- **Ask the persona.** Under the claim story, edit the agent's reasoning or tick
  *customer carries a vulnerability marker* and press **Ask**. The persona says how it
  would judge the case now. This uses no tokens and changes nothing.

## 3. The walk

Allow 1.5-2.5 minutes for a claim to be decided and under a minute for a mule or
merchant case. Start one before you need it.

| Time | Screen | Show | Say |
|---|---|---|---|
| 0:00 | Constellation | Payments, Credit and Markets with events per minute; the cast panel | Seven functions of one bank. Three are running it right now, with no workflow involved. These are its decision-makers. |
| 0:03 | World | The five steps across the top | About 200 fictional customers live in this bank: wages in, bills out, shopping. Fraudsters target them, some are caught out, the bank finds out, and each case is investigated and decided. Nothing is scripted. |
| 0:06 | World | *Why customers did what they did* | Every choice is a reading by Laya, a small model on this laptop. The bars are its probabilities, so the same moment can go either way. |
| 0:09 | World | *What the bank hasn't been told*, *Losses nobody has reported yet* | The world knows things the bank does not. The bank only learns when a customer rings or screening flags a payment. |
| 0:11 | World | **Fraud claim reported**, or **A customer calls** in your own words | A new case each time. Agents gather the evidence and rank only the options the rules admit. |
| 0:14 | World | The case under *How the bank responded*: *Fraud decision manager approved · quick check* | The persona read the agent's reasoning with Laya, checked it against the record, and approved within its £50,000 delegation. Open the case for the evidence and each reading's probability. |
| 0:17 | World | **High-value claim** | Above the manager's delegation, so governance names the financial crime lead, who decides within £250,000. |
| 0:20 | World | **Ask the persona** under the claim | Tick *customer carries a vulnerability marker* or edit the reasoning, and the persona says how it would judge now. No tokens, and nothing changes. |
| 0:23 | Dashboard, Memory, Knowledge | Decisions counted; the personas' memories; the entity graph | Every decision is recorded, the personas remember past decisions, and the graph links the cases to the people and accounts behind them. |
| 0:27 | Constellation | **Spawn 8 cases** | Eight real cases land on the planets, a mix of claims, mule investigations and merchant reviews, and settle within a few minutes. That is eight agent sessions. |

## 4. Reset between takes

The workflow store and memory are in-process: restarting the API empties the
feed and memory (re-seed memory afterwards), and the living world starts a new
cast. Durable state is not in-process: a case interrupted by `make down` resumes
on the next `make up`. Between takes reset only the world, which keeps the
feed's history. Show history with the feed's **All
activity**; *All my decisions today* lists only decisions made by hand in this
browser, and with personas deciding every gate it stays empty.

The buttons under *Steer the world* raise a new case every time. The three
seeded stories (`POST /api/world/scenarios/synthetic-app-fraud-*`) each run once
per world; a fresh world makes them dormant again:

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
DEMO_TIME_WARP_FACTOR=15 DURATION=30m OUT=tapes/banking.tar.gz \
  MEMORY_DOMAINS=app-fraud-reimbursement \
  MEMORY_SEED_ROUND1=verticals/banking/demo/memory-seed-round1.json \
  MEMORY_SEED_ROUND2=verticals/banking/demo/memory-seed-round2.json \
  scripts/record_tape.sh
```

Without the seed files the recorder seeds hiring memories, which do not
belong in a bank. `record_tape.sh` boots through `make up`'s script, so Laya
and the living world run as they do live, and the world opens its own cases.
While it runs, press **Fraud claim reported** and **High-value claim** a few
minutes apart. With `PERSONA_AUTO_CLOSE=*` nothing waits for a person: check
the high-value claim ends *by Financial crime lead*, not in *Workflow failed*.

Tapes are gitignored (`/tapes/`), so they live on disk and are not carried by
a clone.

### Recorded tape

`tapes/banking.tar.gz` — `tape_e1752da7`, 30 minutes, 12,478 events, app SHA
`f6028d4c`, `pack_fingerprint banking:1:3885135132db92aa`. It holds all three
stories: the approved £18,400 claim (its first attempt, at the cold start,
failed and was re-run after a world reset), the vulnerable claim, and the
over-delegation refusal naming `financial_crime_lead`; 11 agent sessions, 14
persona decisions and 10 human-gate resumes. It was recorded before Laya, so
it replays the three seeded stories without judgement, screening or the living
world; re-record it (above) to replay those. `tapes/banking-tape2-backup.tar.gz`
is the previous take, whose over-delegation story failed on the model quota
before reaching governance.

## 7. What not to claim

- This is **not build ready**. The `VERTICAL-PROOF.md` §3 replay probes and
  the live/replay parity pass are outstanding, and no seller review has
  happened.
- Every record is synthetic. No threshold, limit or policy here describes a
  real institution.
- A mule investigation's disposition changes the account only with screening
  on (restrained stops it receiving; monitored can reopen it). Merchant reviews
  change nothing in the world. Say so rather than implying they do.
- Memory holds the seeded decision notes, but the dream pass distils no
  lessons here: memory runs on the in-process fallback without an Azure
  OpenAI endpoint. Do not claim learned lessons.
- With judgement on, do not say Laya decides money. It reads and weighs.
  Admission, the authority matrix and the rules still set every ceiling, and
  the value and option never come from Laya. Its readings are probabilities:
  quote the lead the drawer shows, not certainty.
