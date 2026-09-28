# Zava Bank Vertical Seller Review

**Status:** PENDING (requires human review)

Machine proof cannot set this to PASS. A human must walk the demo and sign
off on reset, pacing, visual quality and story coherence.

## Machine proof position

Passing (re-checked 2026-09-28 on `main` after #47):

- pack validates; 8 packs discovered; no cross-pack leakage
- banking and judgement suites: 205 passed, 26 skipped, with the Laya flags
  off and on; control-plane and blueprint vitest: 568 passed; `tsc` clean
- hero completes the full chain — actor world, sensor, objective, Durable,
  real agent phase, persona gate (judged through Laya when
  `JUDGEMENT_ENABLED=1`), typed command, world mutation, evaluation,
  `objective.resolved`
- live with Laya on: a claim within delegation approved by the fraud decision
  manager on a quick check; a claim above it handed to and decided by the
  financial crime lead
- all three live workflow types run a real agent phase with instrumented
  tool evidence
- real `check_authority` allows, refuses, and names the escalation target
- entity projections schema-valid; zero reflector errors
- blocking execution-visibility gate:

```bash
ZAVA_VERTICAL=banking .venv/bin/python tools/workflow_visibility_proof.py \
  --vertical banking --base-url http://localhost:3101 \
  --save-dir proof/workflow-details/live
# {"result": "PASS", "workflowInstances": 4, "workflowTypes": 3}
```

Outstanding:

- `docs/VERTICAL-PROOF.md` §3 replay probes (Functions disabled; actor world
  disabled)
- §5a live/replay parity pass against a banking tape
- a banking tape recorded with Laya on: `tapes/banking.tar.gz` exists on disk
  (tapes are gitignored) but predates judgement, screening and the living
  world

Curated recordings are under `verticals/banking/recordings/`.

## Hero: APP Fraud Reimbursement

1. [ ] Orient the reviewer to the synthetic bank: seven functions, the
       retail book, the rails, the receiving-provider estate.
2. [ ] Press **Fraud claim reported** (or trigger the seeded
       `synthetic-app-fraud-claim`).
3. [ ] Confirm the two deterministic phases are distinguishable from the
       agent phase.
4. [ ] Confirm the agent's tool calls are visible as recorded evidence, not
       asserted in a caption.
5. [ ] Confirm the Fraud Decision Manager's decision is understandable: the
       floor says *quick check*, *closer review* or *standard rules*, and the
       case shows each Laya reading with its probability.
6. [ ] Confirm the typed command, its four actions, and the measured
       outcome are visible.
7. [ ] Confirm the reimbursed, recovered and receiving-provider figures
       reconcile.

## Variant: vulnerability protection

1. [ ] Press **Vulnerable customer claim** (or trigger the seeded
       `synthetic-app-fraud-vulnerable`).
2. [ ] Confirm refusal appears in the rejected options with the reason
       naming the vulnerability marker.
3. [ ] Confirm the experience never suggests a ranking or a human could
       have admitted that refusal.

## Variant: above delegation

1. [ ] Press **High-value claim** (or trigger the seeded
       `synthetic-app-fraud-over-delegation`).
2. [ ] Confirm a claim over the synthetic ceiling caps at £85,000.
3. [ ] With judgement on: confirm governance names the Financial Crime Lead,
       who decides within their £250,000 delegation, and the chain says so.
4. [ ] With judgement off: confirm governance refuses the Fraud Decision
       Manager **and** names the escalation target, and nothing in the world
       mutated on the refused claim.

## Supporting processes

1. [ ] Confirm mule cases open because screening flagged payments, not on a
       timer.
2. [ ] Confirm each carries its own skill, persona and authority band.
3. [ ] Confirm a mule disposition changes the account (restrained or
       monitored), and the experience never claims a merchant review changes
       the world.

## Living world (Laya)

1. [ ] Confirm the five steps fill as customers spend, are targeted, are
       caught out, ring the bank, and have their claims decided.
2. [ ] Confirm each customer choice shows Laya's probabilities, and the same
       moment can plausibly go either way.
3. [ ] Confirm the world opens cases on its own no faster than
       `BANKING_WORLD_CASES_PER_HOUR`.
4. [ ] Confirm **A customer calls** and **Ask the persona** behave as the
       runbook describes (section 2c).

## Cross-bank linkage

1. [ ] Confirm the mule beneficiary resolves to `SYN-CORP-014`.
2. [ ] Confirm that client also carries the wholesale exposure.
3. [ ] Confirm the link is shown from the entity graph rather than asserted.

## Presentation

1. [ ] Seven function planets are individually distinguishable.
2. [ ] Rockets parked at persona cities read as work waiting on a persona.
3. [ ] Zero browser console errors across the walk. Known: a new case can
       log a 404 in the browser console while it is being created; the
       floor retries and shows it.
4. [ ] Reset between takes restores a clean organisation.
5. [ ] Every surface states the data is synthetic.

## Claims the reviewer must reject if heard

- that the vertical is build ready or demo ready
- that any threshold, limit or policy reflects a real institution
- that merchant reviews mutate world state
- that Laya decides money or approvals on its own
- that machine proof constitutes this sign-off
