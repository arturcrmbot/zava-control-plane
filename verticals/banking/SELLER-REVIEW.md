# Zava Bank Vertical Seller Review

**Status:** PENDING (requires human review)

Machine proof cannot set this to PASS. A human must walk the demo and sign
off on reset, pacing, visual quality and story coherence.

## Machine proof position

Passing:

- pack validates; 8 packs discovered; no cross-pack leakage
  (`tests/api/shared`: 278 passed, 2 skipped)
- hero completes the full chain — actor world, sensor, objective, Durable,
  real agent phase, human gate, typed command, world mutation, evaluation,
  `objective.resolved`
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
- a committed banking tape (`tapes/banking.tar.gz`)

Curated recordings are under `verticals/banking/recordings/`.

## Hero: APP Fraud Reimbursement

1. [ ] Orient the reviewer to the synthetic bank: seven functions, the
       retail book, the rails, the receiving-provider estate.
2. [ ] Trigger `synthetic-app-fraud-claim`.
3. [ ] Confirm the two deterministic phases are distinguishable from the
       agent phase.
4. [ ] Confirm the agent's tool calls are visible as recorded evidence, not
       asserted in a caption.
5. [ ] Confirm the Fraud Decision Manager gate is understandable, and that
       it waits for a human rather than auto-closing.
6. [ ] Confirm the typed command, its four actions, and the measured
       outcome are visible.
7. [ ] Confirm the reimbursed, recovered and receiving-provider figures
       reconcile.

## Variant: vulnerability protection

1. [ ] Trigger `synthetic-app-fraud-vulnerable`.
2. [ ] Confirm refusal appears in the rejected options with the reason
       naming the vulnerability marker.
3. [ ] Confirm the experience never suggests a ranking or a human could
       have admitted that refusal.

## Variant: governed refusal

1. [ ] Trigger `synthetic-app-fraud-over-delegation`.
2. [ ] Confirm the claim caps at the synthetic ceiling.
3. [ ] Confirm governance refuses the Fraud Decision Manager **and** names
       the escalation target rather than simply failing.
4. [ ] Confirm nothing in the world mutated on the refused claim.

## Supporting processes

1. [ ] Confirm cases open continuously with nobody driving.
2. [ ] Confirm each carries its own skill, persona and authority band.
3. [ ] Confirm the experience never claims these mutate world state — they
       hold no actor-world records.

## Cross-bank linkage

1. [ ] Confirm the mule beneficiary resolves to `SYN-CORP-014`.
2. [ ] Confirm that client also carries the wholesale exposure.
3. [ ] Confirm the link is shown from the entity graph rather than asserted.

## Presentation

1. [ ] Seven function planets are individually distinguishable.
2. [ ] Rockets parked at persona cities read as work waiting for a person.
3. [ ] Zero browser console errors across the walk.
4. [ ] Reset between takes restores a clean organisation.
5. [ ] Every surface states the data is synthetic.

## Claims the reviewer must reject if heard

- that the vertical is build ready or demo ready
- that any threshold, limit or policy reflects a real institution
- that the supporting processes mutate world state
- that machine proof constitutes this sign-off
