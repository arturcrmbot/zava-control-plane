# Airline Vertical Seller Review

**Status:** PENDING (requires human review)

## Machine proof

All nine `docs/VERTICAL-PROOF.md` machine criteria pass for:

- Integrated Hub Disruption Recovery
- AOG Engineering and Spares Recovery
- Pre-emptive Schedule Resilience

Run:

```bash
LLM_RUNTIME=aoai AZURE_OPENAI_DEPLOYMENT=gpt-4.1 \
  bash tools/airline_zava_e2e_proof.sh
```

The ignored local evidence is written to
`tmp/airline-zava-e2e-proof/`. Curated recordings are under
`verticals/airline/recordings/` and `data/blueprint-recordings/`.

## Hero 1: Integrated Hub Disruption Recovery

1. [ ] Orient the reviewer to the synthetic morning hub bank.
2. [ ] Trigger `synthetic-hub-cascade`.
3. [ ] Follow the delay and stand constraint through the workflow.
4. [ ] Confirm the Duty Operations Manager decision is understandable.
5. [ ] Confirm the typed recovery command and measured outcome are visible.
6. [ ] Confirm `AIRHUB-0001` is consistent across all eight surfaces.

## Hero 2: AOG Engineering and Spares Recovery

1. [ ] Trigger `synthetic-aog-defect`.
2. [ ] Confirm the grounded aircraft, maintenance task, provider, and spares evidence are clear.
3. [ ] Confirm the Engineering Duty Manager decision is understandable.
4. [ ] Confirm the work order and spare coordination are visible.
5. [ ] Confirm the experience never claims that AI released the aircraft to service.
6. [ ] Confirm `AOGA-0001` is consistent across all eight surfaces.

## Hero 3: Pre-emptive Schedule Resilience

1. [ ] Trigger `synthetic-schedule-restriction`.
2. [ ] Confirm the forecast restriction and affected sectors are clear.
3. [ ] Confirm the Network Operations Director decision is understandable.
4. [ ] Confirm `monitor_risk` remains visible as a governed no-action option.
5. [ ] Confirm the selected adjustment and counterfactual are clear.
6. [ ] Confirm `AIRSCHED-0001` is consistent across all eight surfaces.

## Human-only criteria

- [ ] Reset is clean between heroes.
- [ ] Pacing is suitable for a seller-led walkthrough.
- [ ] Visual quality meets the presentation bar.
- [ ] The three stories form a coherent airline narrative.
- [ ] No UI element is confusing or misleading.

## Readiness

| Gate | Status |
|---|---|
| Build ready | PASS |
| Demo ready | PENDING |
| Deployed | NOT STARTED |
