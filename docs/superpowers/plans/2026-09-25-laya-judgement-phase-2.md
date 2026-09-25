# Laya judgement, phase 2: the world notices and reacts. Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mule investigations open because the bank noticed suspicious payments,
not on a timer. Dispositions change the world. Customers react to reimbursement
decisions, and merchant risk is read from the merchant's own description.

**Architecture:**
- **The world owns everything; Laya only reads text.**
  - Payments carry references.
  - A hidden set of mule accounts receives scam-pattern payments from a seeded scam loop.
  - A pack-owned screener asks Laya which described pattern a reference matches, cached per reference.
  - If Laya is down, keyword rules decide and the event says so.
- **Opening a case.** Code opens a mule case when an account has flagged payments from two or more
  customers. It opens through a real world sensor, so the existing world bridge starts
  the mule orchestration with the world's observation.
- **Consequences.** The mule command is applied to the world: restrained accounts stop receiving
  scam payments; monitored ones keep collecting and can be reopened.
- **Flag.** Everything is behind `BANKING_WORLD_SCREENING=1`. With it off, the mule timer runs as
  today.

**Tech stack:** SimPy world (`verticals/banking/worlds`), world bridge, Durable
supporting engine, judgement `LayaClient`, pytest.

---

## Decisions made while planning

- **The screener never blocks the world.** A cache hit applies at once. A miss is screened on
  an asyncio task, and the world publishes the result on its next step. With no running loop
  (tests, the Functions worker), the keyword rules apply synchronously.
- **The scam loop draws from its own random stream,** so the existing seeded book (balances,
  bands, payments) is unchanged.
- **Mule cases are world-owned when the flag is on:**
  - the mule domain drops its spawner, so the ramp and bursts stop timing them
  - the world registers a route and a responder
  - the floor's "Mule activity detected" button asks the world for a burst of scam payments
- **Commands.** The mule command carries the world trace and `financial-crime` as issuer
  (gateway rules). Merchant commands are unchanged.

## Tasks

### Task 1: References and mule accounts (reference data, model)
- [ ] Tests:
  - every payment has a non-empty reference
  - payments into mule accounts carry scam-pattern references
  - the three hero beneficiaries are mule accounts
  - seeded balances and bands are unchanged: `build_beneficiaries()` and `build_payments()` amounts equal the previous values
- [ ] `Payment.reference`, `BeneficiaryAccount.mule` (hidden truth, never shown to the bank's decisions); reference lists; a separate random stream.

### Task 2: Screener
- [ ] Tests for the rules screener's patterns and the unclear case. Laya screener with a fake client:
  - a clear pattern is flagged
  - a low lead is unclear
  - the cache avoids a second call
  - a Laya failure falls back to rules
- [ ] `verticals/banking/worlds/screening.py`: `Screening(pattern, lead, by)`, `RulesScreener`, `LayaScreener` (async classify, sync cache).

### Task 3: The world notices
- [ ] Tests (rules screener, stepped world):
  - scam payments settle and are flagged
  - a second customer's flagged payment into the same account trips `sensor:mule_pattern` once
  - the observation for that sensor carries the account's real band, balance and flagged payments
  - with the flag off, no scam loop runs and no mule sensor trips
- [ ] `ZavaBankWorld`: scam loop, `_screen`, `_apply_screening`, mule case tracking, `build_observation` branch, `run_scenario("mule-activity")`, snapshot counts.

### Task 4: Registration, domain and orchestration input
- [ ] Tests:
  - with the flag on, the banking world routes `sensor:mule_pattern` to the mule responder, and the mule domain has no spawner (so the ramp skips it)
  - with the flag off, both are as today
  - `case_evidence_activity` builds the case from a world observation
  - `case_command_activity` returns a full `SimulationCommand` (trace, issuer) for a world case, and the old shape for a spawned case
- [ ] `registration.py`, `domains.py`, `support_constants.py` (sensor, objective), `supporting_durable.py`.

### Task 5: Consequences
- [ ] Tests:
  - applying the mule command restrains, monitors or closes the account and emits `banking.mule_disposition.applied`
  - a restrained account receives no further scam payments
  - a monitored one does, and trips a new investigation after new flags
- [ ] `ZavaBankWorld.apply_command` handles the mule command; the scam loop respects status.

### Task 6: Customer reactions
- [ ] Tests:
  - after a reimbursement is applied, the world asks the reaction model how upset the customer is (upset scale)
  - it draws the reaction with its own random stream: accepts, chases or complains
  - it emits `banking.customer.reacted`
  - with no model, the reaction uses rules (refusal means complain, partial means chase, full means accept), recorded as rules
- [ ] `verticals/banking/worlds/reactions.py` plus a hook in the reimbursement command path.

### Task 7: Merchant descriptions
- [ ] Tests:
  - the merchant spawner gives each application a one-line business description
  - Laya picks the business category from described categories
  - a code table maps category to risk band
  - with Laya off, the band is drawn as today (recorded as such)
- [ ] `spawners.py`, `verticals/banking/merchant_categories.py`.

### Task 8: Floor, docs and verification
- [ ] Floor:
  - flagged payments and mule cases in the journal and story
  - the "Mule activity detected" button asks the world
  - customer reactions counted
- [ ] Runbook and spec: flag, behaviour, fallbacks.
- [ ] Verify:
  - unit suites
  - live screener golden set against Laya
  - an in-process run: the world steps with the Laya screener, a mule case opens from the sensor, the mule orchestration runs with the world observation and the persona responder, and the command is applied back to the world
